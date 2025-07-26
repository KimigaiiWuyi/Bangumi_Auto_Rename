import re
import json
from typing import Dict, List, Optional

from openai import OpenAI
from pydantic import ValidationError

from ..logger import logger
from .models import AIAnalysisResult
from ..config.config_manager import cm


class OpenAIClient:
    """OpenAI API客户端，支持多种格式化输出方式"""

    def __init__(self):
        self.api_key = cm.get_config("ai_api_key")
        self.base_url = cm.get_config("ai_base_url")
        self.model = cm.get_config("ai_model")
        self.enabled = bool(cm.get_config("ai_enabled"))
        self.confidence_threshold = cm.get_config("ai_confidence_threshold")

        # 支持多种输出格式
        self.output_format = cm.get_config("openai_output_format") or "text"

        if self.enabled and self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            self.client = None

    def is_available(self) -> bool:
        """检查OpenAI客户端是否可用"""
        return bool(self.enabled and self.client and self.api_key)

    def analyze_episode_mapping(
        self,
        anime_info: Dict,
        local_files: List[Dict],
    ) -> Optional[AIAnalysisResult]:
        """
        使用OpenAI API分析本地文件与TMDB剧集的映射关系

        Args:
            anime_info: TMDB动漫信息
            local_files: 本地文件信息列表，包含文件名、路径、时长等

        Returns:
            验证后的AIAnalysisResult对象
        """
        if not self.is_available():
            logger.warning("[OpenAI识别] OpenAI功能未启用或配置不完整")
            return None

        if not self.client:
            logger.error("[OpenAI识别] OpenAI 客户端未初始化")
            return None

        try:
            # 导入AIClient以使用通用prompt方法
            from .client import AIClient

            # 使用通用prompt构建基础内容
            base_prompt = AIClient.build_common_prompt(anime_info, local_files)

            # 添加OpenAI特定的JSON格式要求
            prompt = self._add_openai_json_instructions(base_prompt)

            # 使用通用系统提示词
            system_prompt = AIClient.get_system_prompt()
            if self.output_format not in ["function_calling", "structured_output"]:
                system_prompt += " 请严格按照指定的JSON格式返回分析结果。"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

            request_params = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.1,
            }

            # 根据输出格式配置请求参数
            self._configure_output_format(request_params)

            response = self.client.chat.completions.create(**request_params)

            response_message = response.choices[0].message
            if not response_message:
                logger.error("[OpenAI识别] OpenAI 响应内容为空")
                return None

            # 提取并验证JSON内容
            result = self._extract_and_validate_json(response_message)

            if not result:
                logger.error("[OpenAI识别] 无法解析或验证OpenAI响应")
                return None

            # 记录低置信度结果
            if result.confidence == "Low":
                logger.warning(f"[OpenAI识别] 低置信度结果: {result.reason}")

            logger.info(f"[OpenAI识别] 分析完成，置信度: {result.confidence}")
            return result

        except Exception as e:
            logger.error(f"[OpenAI识别] 分析失败: {str(e)}")
            return None

    def _extract_and_validate_json(
        self, response_message
    ) -> Optional[AIAnalysisResult]:
        """
        从OpenAI响应中提取JSON内容并使用Pydantic验证
        兼容常规内容响应和Tool-calling响应

        Args:
            response_message: OpenAI响应的message对象

        Returns:
            验证后的AIAnalysisResult对象，失败返回None
        """
        json_data = None
        # 检查是否是Tool-calling响应
        if response_message.tool_calls:
            tool_call = response_message.tool_calls[0]
            if tool_call.function.name == "analyze_file_structure":
                try:
                    json_data = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as e:
                    logger.error(f"[OpenAI识别] 解析Tool-calling JSON失败: {e}")
                    logger.error(
                        f"[OpenAI识别] 原始数据: {tool_call.function.arguments}"
                    )
                    return None
        else:
            # 否则，从内容中提取
            content = response_message.content
            if content:
                json_data = self._extract_json_from_response(content)

        if not json_data:
            logger.error("[OpenAI识别] 未能从OpenAI响应中提取到任何JSON数据")
            return None

        try:
            # 使用Pydantic验证和解析
            result = AIAnalysisResult(**json_data)
            logger.info(f"[OpenAI识别] JSON结构验证成功，置信度: {result.confidence}")
            return result
        except ValidationError as e:
            logger.error(f"[OpenAI识别] JSON结构验证失败: {e}")
            logger.error(
                f"[OpenAI识别] 原始数据: {json.dumps(json_data, ensure_ascii=False, indent=2)}"
            )
            return None
        except Exception as e:
            logger.error(f"[OpenAI识别] 解析AI结果时发生未知错误: {str(e)}")
            return None

    def _extract_json_from_response(self, content: str) -> Optional[Dict]:
        """
        从OpenAI响应中提取JSON内容，兼容思维链输出

        Args:
            content: OpenAI响应内容

        Returns:
            提取的JSON字典，失败返回None
        """
        try:
            # 首先尝试直接解析整个内容
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 如果直接解析失败，尝试提取JSON部分
        # 查找可能的JSON块
        json_patterns = [
            r"```json\s*(\{.*?\})\s*```",  # ```json {} ```
            r"```\s*(\{.*?\})\s*```",  # ``` {} ```
            r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})",  # 最外层的{}块
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for match in matches:
                try:
                    # 清理可能的思维链内容
                    cleaned_match = self._clean_json_content(match)
                    return json.loads(cleaned_match)
                except json.JSONDecodeError:
                    continue

        # 如果所有方法都失败，记录错误并返回None
        logger.error(f"[OpenAI识别] 无法从响应中提取有效JSON: {content[:200]}...")
        return None

    def _clean_json_content(self, json_str: str) -> str:
        """
        清理JSON字符串中可能的思维链内容

        Args:
            json_str: 原始JSON字符串

        Returns:
            清理后的JSON字符串
        """
        # 移除可能的思维链标记
        thinking_patterns = [
            r"<thinking>.*?</thinking>",
            r"思考：.*?(?=\{)",
            r"分析：.*?(?=\{)",
            r"推理：.*?(?=\{)",
        ]

        cleaned = json_str
        for pattern in thinking_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL)

        return cleaned.strip()

    def _get_json_schema(self) -> Dict:
        """生成符合OpenAI Tool格式的JSON Schema"""
        schema = AIAnalysisResult.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": "analyze_file_structure",
                "description": "分析本地文件结构并返回与TMDB的映射关系",
                "parameters": schema,
            },
        }

    def _add_openai_json_instructions(self, base_prompt: str) -> str:
        """
        为OpenAI添加JSON格式指令

        Args:
            base_prompt: 通用的基础提示词

        Returns:
            添加了OpenAI特定JSON格式要求的完整提示词
        """
        if self.output_format in ["function_calling", "structured_output"]:
            # Tool-calling和structured output模式下不需要额外的JSON格式说明
            return base_prompt

        # JSON object和text模式下需要详细的JSON格式说明
        json_instructions = """
请严格按照以下JSON格式返回分析结果：
{
    "confidence": "High",
    "reason": "分析理由说明",
    "season_mapping": [
        {
            "local_group_name": "JUJUTSU_KAISEN_VOL1",
            "maps_to_tmdb_seasons": [1]
        },
        {
            "local_group_name": "JUJUTSU_KAISEN_VOL2",
            "maps_to_tmdb_seasons": [2, 3]
        }
    ],
    "file_mapping": [
        {
            "file_path": "相对路径/文件名.mkv",
            "tmdb_season": 1,
            "tmdb_episode": 1,
            "episode_type": "regular",
            "confidence": "High"
        }
    ],
    "extra_notes": "额外的特殊情况说明"
}

注意事项：
- confidence只能是: "High", "Medium", "Low"
- local_group_name应该是从文件扫描中获得的实际目录名或组名
- maps_to_tmdb_seasons是整数数组，表示本地组对应的TMDB季度
- episode_type只能是: "regular", "special", "movie"
- 如果整个子路径中均无匹配命中项，则无需包含在season_mapping中
- season_mapping的maps_to_tmdb_seasons中无需包含第零季
"""
        return base_prompt + json_instructions

    def _configure_output_format(self, request_params: Dict) -> None:
        """
        根据配置的输出格式类型配置请求参数

        Args:
            request_params: 请求参数字典，会被直接修改
        """
        if self.output_format == "function_calling":
            request_params["tools"] = [self._get_json_schema()]
            # request_params["tool_choice"] = {
            #     "type": "function",
            #     "function": {"name": "analyze_file_structure"},
            # }
            request_params["tool_choice"] = "auto"
        elif self.output_format == "json_object":
            request_params["response_format"] = {"type": "json_object"}
        elif self.output_format == "structured_output":
            # 使用新的structured output API
            request_params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "ai_analysis_result",
                    "schema": AIAnalysisResult.model_json_schema(),
                },
            }
        # 如果是"text"格式，不添加任何特殊参数
