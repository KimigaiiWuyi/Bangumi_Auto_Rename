import json
from typing import Dict, List, Optional

from google import genai
from pydantic import ValidationError
from google.genai.types import HttpOptions, GenerateContentConfig

from ..logger import logger
from .base_client import BaseAIClient
from .models import AIAnalysisResult, MediaSelectionResult
from ..config.config_manager import cm


class GeminiClient(BaseAIClient):
    """Google Gemini API客户端，支持结构化输出"""

    def __init__(self):
        super().__init__("gemini")
        self.api_key = cm.get_config("gemini_api_key")
        self.base_url = (
            cm.get_config("gemini_base_url")
            or "https://generativelanguage.googleapis.com"
        )
        self.model = cm.get_config("gemini_model") or "gemini-2.5-flash"
        self.temperature = float(cm.get_config("gemini_temperature") or 0.5)
 
        if self.enabled and self.api_key:
            try:
                # 构建http_options以支持自定义base_url
                http_options = HttpOptions()
                if (
                    self.base_url
                    and self.base_url != "https://generativelanguage.googleapis.com"
                ):
                    http_options.base_url = self.base_url

                if http_options:
                    self.client = genai.Client(
                        api_key=self.api_key, http_options=http_options
                    )
                else:
                    self.client = genai.Client(api_key=self.api_key)

                logger.info(f"[Gemini客户端] 初始化成功，使用API地址: {self.base_url}")
            except Exception as e:
                logger.error(f"[Gemini客户端] 初始化失败: {e}")
                self.client = None
        else:
            self.client = None

    def is_available(self) -> bool:
        """检查Gemini客户端是否可用"""
        return bool(self.enabled and self.client and self.api_key)

    def _structured_output_with_validation(
        self,
        prompt: str,
        system_prompt: str,
        response_model,
        **kwargs
    ):
        """
        Gemini的通用结构化输出+验证方法
        """
        if not self.is_available() or not self.client:
            logger.error("[Gemini识别] 客户端不可用")
            return None

        try:
            # 获取JSON Schema
            schema = response_model.model_json_schema()
            
            logger.debug(f"[Gemini识别] 使用Schema: {schema}")

            # 构建请求
            request_config = GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=self.temperature,
            )
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=request_config,
            )

            logger.debug(f"[Gemini识别] Raw response text: {response.text}")
            
            if not response or not response.text:
                logger.error("[Gemini识别] 响应内容为空")
                return None

            # 优先使用Gemini的解析结果
            if hasattr(response, 'parsed') and response.parsed:
                logger.debug(f"[Gemini识别] 使用解析后的结果: {response.parsed}")
                result = response_model.model_validate(response.parsed)
                return result

            # 备用：手动解析JSON
            try:
                json_data = json.loads(response.text)
                logger.debug("[Gemini识别] 手动解析JSON成功")
                result = response_model(**json_data)
                return result
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(f"[Gemini识别] JSON解析失败: {e}")
                logger.error(f"[Gemini识别] 原始响应: {response.text[:200]}...")
                return None

        except Exception as e:
            logger.error(f"[Gemini识别] 结构化输出失败: {str(e)}")
            return None

    def analyze_episode_mapping(
        self,
        anime_info: Dict,
        local_files: List[Dict],
        target_season: Optional[int] = None,
    ) -> Optional[AIAnalysisResult]:
        """
        使用Gemini API分析本地文件与TMDB剧集的映射关系
        """
        try:
            # 导入AIClient以使用通用prompt方法
            from .client import AIClient

            # 构建提示词
            base_prompt = AIClient.build_common_prompt(anime_info, local_files, target_season)
            prompt = self._add_gemini_instructions(base_prompt)
            system_prompt = AIClient.get_system_prompt()

            # 使用通用的结构化输出方法
            return self._structured_output_with_validation(
                prompt=prompt,
                system_prompt=system_prompt,
                response_model=AIAnalysisResult
            )

        except Exception as e:
            logger.error(f"[Gemini识别] 分析失败: {str(e)}")
            return None

    def _add_gemini_instructions(self, base_prompt: str) -> str:
        """
        为Gemini添加特定指令

        Args:
            base_prompt: 通用的基础提示词

        Returns:
            添加了Gemini特定指令的完整提示词
        """
        # Gemini使用原生结构化输出，通过response_schema约束
        # 只需要强调数据结构的重要性
        gemini_instructions = """
注意：请确保返回的数据严格符合AIAnalysisResult的结构定义，所有字段类型和枚举值必须准确。
"""
        return base_prompt + gemini_instructions

    def identify_and_select_media(
        self,
        tv_candidates: List[Dict],
        movie_candidates: List[Dict],
        video_files: List[str],
        directory_name: str,
        is_anime: Optional[bool] = None,
    ) -> Optional[MediaSelectionResult]:
        """
        使用Gemini API识别媒体类型并选择最佳候选项
        """
        try:
            # 从 client.py 导入 AIClient 以使用通用 prompt 方法
            from .client import AIClient

            # 构建提示词
            prompt = AIClient.build_media_selection_prompt(
                tv_candidates, movie_candidates, video_files, directory_name, is_anime
            )
            system_prompt = AIClient.get_media_selection_system_prompt()

            # 使用通用的结构化输出方法
            return self._structured_output_with_validation(
                prompt=prompt,
                system_prompt=system_prompt,
                response_model=MediaSelectionResult
            )

        except Exception as e:
            logger.error(f"[Gemini识别] 媒体选择失败: {str(e)}")
            return None
