import re
import json
from typing import Dict, List, Optional

from openai import OpenAI
from pydantic import ValidationError

from ..logger import logger
from .base_client import BaseAIClient
from .models import AIAnalysisResult, MediaSelectionResult
from ..config.config_manager import cm


class OpenAIClient(BaseAIClient):
    """OpenAI API客户端，支持多种格式化输出方式"""

    def __init__(self):
        super().__init__("openai")
        self.api_key = cm.get_config("ai_api_key")
        self.base_url = cm.get_config("ai_base_url")
        self.model = cm.get_config("ai_model")
        self.temperature = float(cm.get_config("ai_temperature") or 0.1)

        # 支持多种输出格式
        self.output_format = cm.get_config("openai_output_format") or "text"

        if self.enabled and self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            self.client = None

    def is_available(self) -> bool:
        """检查OpenAI客户端是否可用"""
        return bool(self.enabled and self.client and self.api_key)

    def _structured_output_with_validation(
        self,
        prompt: str,
        system_prompt: str,
        response_model,
        **kwargs
    ):
        """
        OpenAI的通用结构化输出+验证方法
        """
        if not self.is_available() or not self.client:
            logger.error("[OpenAI识别] 客户端不可用")
            return None

        try:
            # 对于需要手动指定JSON格式的模式，将格式说明添加到system prompt
            if self.output_format not in ["function_calling", "structured_output"]:
                system_prompt += self._get_json_instructions_for_model(response_model)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

            request_params = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
            }

            # 根据输出格式配置请求参数
            self._configure_output_format_for_model(request_params, response_model)

            logger.debug(
                f"[OpenAI识别] Request: {json.dumps(request_params, indent=2, ensure_ascii=False)}"
            )
            response = self.client.chat.completions.create(**request_params)

            response_message = response.choices[0].message
            logger.debug(f"[OpenAI识别] Response content: {response_message.content}")
            
            if not response_message:
                logger.error("[OpenAI识别] 响应内容为空")
                return None

            # 提取并验证JSON内容
            return self._extract_and_validate_json_for_model(response_message, response_model)

        except Exception as e:
            logger.error(f"[OpenAI识别] 结构化输出失败: {str(e)}")
            return None

    def analyze_episode_mapping(
        self,
        anime_info: Dict,
        local_files: List[Dict],
        target_season: Optional[int] = None,
    ) -> Optional[AIAnalysisResult]:
        """
        使用OpenAI API分析本地文件与TMDB剧集的映射关系
        """
        try:
            # 导入AIClient以使用通用prompt方法
            from .client import AIClient

            # 构建提示词
            prompt = AIClient.build_common_prompt(anime_info, local_files, target_season)
            system_prompt = AIClient.get_system_prompt()

            # 使用通用的结构化输出方法
            return self._structured_output_with_validation(
                prompt=prompt,
                system_prompt=system_prompt,
                response_model=AIAnalysisResult
            )

        except Exception as e:
            logger.error(f"[OpenAI识别] 分析失败: {str(e)}")
            return None

    def identify_and_select_media(
        self,
        tv_candidates: List[Dict],
        movie_candidates: List[Dict],
        video_files: List[str],
        directory_name: str,
        is_anime: Optional[bool] = None,
    ) -> Optional[MediaSelectionResult]:
        """
        使用OpenAI API识别媒体类型并选择最佳候选项
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
            logger.error(f"[OpenAI识别] 媒体选择失败: {str(e)}")
            return None

    def _extract_and_validate_json_for_model(
        self, response_message, response_model
    ):
        """
        从OpenAI响应中提取JSON内容并使用指定模型验证
        """
        json_data = None
        
        # 检查是否是Tool-calling响应
        if response_message.tool_calls:
            tool_call = response_message.tool_calls[0]
            expected_function_name = getattr(response_model, 'FUNCTION_NAME', f"analyze_{response_model.__name__.lower()}")
            
            logger.debug(f"[OpenAI识别] 识别到Tool-calling: {tool_call.function.name}")
            logger.debug(f"[OpenAI识别] 期望的函数名: {expected_function_name}")
            
            # 验证函数名是否匹配
            if tool_call.function.name != expected_function_name:
                logger.warning(f"[OpenAI识别] 函数名不匹配，期望: {expected_function_name}, 实际: {tool_call.function.name}")
            
            try:
                json_data = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as e:
                logger.error(f"[OpenAI识别] 解析Tool-calling JSON失败: {e}")
                return None
        else:
            # 从内容中提取
            content = response_message.content
            logger.debug(f"[OpenAI识别] 普通内容响应: {content}")
            if content:
                json_data = self._extract_json_from_response(content)

        if not json_data:
            logger.error("[OpenAI识别] 未能从OpenAI响应中提取到任何JSON数据")
            return None

        try:
            # 使用指定模型验证和解析
            result = response_model(**json_data)
            logger.info(f"[OpenAI识别] JSON结构验证成功")
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

    def _get_json_instructions_for_model(self, response_model) -> str:
        """
        获取指定模型的JSON格式指令
        """
        schema = response_model.model_json_schema()
        schema.pop("title", None)
        schema.pop("description", None)
        schema_str = json.dumps(schema, indent=2, ensure_ascii=False)

        return f"""
请严格按照以下JSON Schema格式返回分析结果。不要添加任何额外的解释或注释，只返回JSON对象。

JSON Schema:
```json
{schema_str}
```
"""

    def _configure_output_format_for_model(self, request_params: Dict, response_model) -> None:
        """
        根据配置的输出格式类型和响应模型配置请求参数
        """
        if self.output_format == "function_calling":
            # 使用模型类中定义的静态function name
            function_name = getattr(response_model, 'FUNCTION_NAME', f"analyze_{response_model.__name__.lower()}")
            request_params["tools"] = [self._get_json_schema_for_model(response_model, function_name)]
            request_params["tool_choice"] = {
                "type": "function",
                "function": {"name": function_name},
            }
        elif self.output_format == "json_object":
            request_params["response_format"] = {"type": "json_object"}
        elif self.output_format == "structured_output":
            request_params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__.lower(),
                    "schema": response_model.model_json_schema(),
                },
            }

    def _get_json_schema_for_model(self, response_model, function_name: str) -> Dict:
        """生成指定模型的OpenAI Tool格式JSON Schema"""
        schema = response_model.model_json_schema()
        description = getattr(response_model, 'FUNCTION_DESCRIPTION', f"分析并返回{response_model.__name__}格式的结果")
        
        return {
            "type": "function",
            "function": {
                "name": function_name,
                "description": description,
                "parameters": schema,
            },
        }