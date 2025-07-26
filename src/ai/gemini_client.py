import json
from typing import Dict, List, Optional

from google import genai
from pydantic import ValidationError
from google.genai.types import HttpOptions

from ..logger import logger
from .models import AIAnalysisResult
from ..config.config_manager import cm


class GeminiClient:
    """Google Gemini API客户端，支持结构化输出"""

    def __init__(self):
        self.api_key = cm.get_config("gemini_api_key")
        self.base_url = (
            cm.get_config("gemini_base_url")
            or "https://generativelanguage.googleapis.com"
        )
        self.model = cm.get_config("gemini_model") or "gemini-2.5-flash"
        self.enabled = bool(cm.get_config("ai_enabled"))
        self.confidence_threshold = cm.get_config("ai_confidence_threshold")

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

    def analyze_episode_mapping(
        self,
        anime_info: Dict,
        local_files: List[Dict],
    ) -> Optional[AIAnalysisResult]:
        """
        使用Gemini API分析本地文件与TMDB剧集的映射关系

        Args:
            anime_info: TMDB动漫信息
            local_files: 本地文件信息列表，包含文件名、路径、时长等

        Returns:
            验证后的AIAnalysisResult对象
        """
        if not self.is_available():
            logger.warning("[Gemini识别] Gemini功能未启用或配置不完整")
            return None

        if not self.client:
            logger.error("[Gemini识别] Gemini 客户端未初始化")
            return None

        try:
            # 导入AIClient以使用通用prompt方法
            from .client import AIClient

            # 使用通用prompt构建基础内容
            base_prompt = AIClient.build_common_prompt(anime_info, local_files)

            # Gemini使用原生结构化输出，不需要额外的JSON格式说明
            prompt = self._add_gemini_instructions(base_prompt)

            # 使用通用系统提示词
            system_prompt = AIClient.get_system_prompt()

            # 使用Gemini的结构化输出功能
            # 获取Gemini兼容的JSON Schema（移除了additionalProperties）
            schema = AIAnalysisResult.model_json_schema()

            logger.debug(f"[Gemini识别] 使用Schema: {schema}")

            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=f"{system_prompt}\n\n{prompt}",
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": schema,
                    },
                )
            except Exception as e:
                logger.error(f"[Gemini识别] Gemini API调用失败: {e}")
                return None

            if not response or not response.text:
                logger.error("[Gemini识别] Gemini 响应内容为空")
                return None

            # 直接使用Gemini的解析结果
            if hasattr(response, 'parsed') and response.parsed:
                logger.debug(f"[Gemini识别] 解析后的JSON: {response.parsed}")
                result = AIAnalysisResult.model_validate(response.parsed)
                logger.info(
                    f"[Gemini识别] 使用解析后的结果，置信度: {result.confidence}"
                )
                return result

            # 如果没有解析结果，尝试手动解析JSON
            try:
                json_data = json.loads(response.text)
                logger.debug("[Gemini识别] 手动解析的JSON成功!")
                result = AIAnalysisResult(**json_data)
                logger.info(f"[Gemini识别] 手动解析成功，置信度: {result.confidence}")
                return result
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(f"[Gemini识别] JSON解析失败: {e}")
                logger.error(f"[Gemini识别] 原始响应: {response.text[:200]}...")
                return None

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
