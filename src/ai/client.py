import re
import json
from typing import Dict, List, Tuple, Optional

from openai import OpenAI
from pydantic import ValidationError

from ..logger import logger
from ..config.config_manager import cm
from .models import SeasonMapping, EpisodeMapping, AIAnalysisResult


class AIClient:
    def __init__(self):
        self.api_key = cm.get_config("ai_api_key")
        self.base_url = cm.get_config("ai_base_url")
        self.model = cm.get_config("ai_model")
        self.enabled = bool(cm.get_config("ai_enabled"))
        self.confidence_threshold = cm.get_config("ai_confidence_threshold")
        self.json_mode = bool(cm.get_config("OPENAI_JSON_MODE"))

        if self.enabled and self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            self.client = None

    def is_available(self) -> bool:
        """检查AI客户端是否可用"""
        return bool(self.enabled and self.client and self.api_key)

    def _extract_and_validate_json(
        self, response_message
    ) -> Optional[AIAnalysisResult]:
        """
        从LLM响应中提取JSON内容并使用Pydantic验证
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
                    logger.error(f"[AI识别] 解析Tool-calling JSON失败: {e}")
                    logger.error(f"[AI识别] 原始数据: {tool_call.function.arguments}")
                    return None
        else:
            # 否则，从内容中提取
            content = response_message.content
            if content:
                json_data = self._extract_json_from_response(content)

        if not json_data:
            logger.error("[AI识别] 未能从AI响应中提取到任何JSON数据")
            return None

        try:
            # 使用Pydantic验证和解析
            result = AIAnalysisResult(**json_data)
            logger.info(f"[AI识别] JSON结构验证成功，置信度: {result.confidence}")
            return result
        except ValidationError as e:
            logger.error(f"[AI识别] JSON结构验证失败: {e}")
            logger.error(
                f"[AI识别] 原始数据: {json.dumps(json_data, ensure_ascii=False, indent=2)}"
            )
            return None
        except Exception as e:
            logger.error(f"[AI识别] 解析AI结果时发生未知错误: {str(e)}")
            return None

    def _extract_json_from_response(self, content: str) -> Optional[Dict]:
        """
        从LLM响应中提取JSON内容，兼容思维链输出

        Args:
            content: LLM响应内容

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
        logger.error(f"[AI识别] 无法从响应中提取有效JSON: {content[:200]}...")
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

    def analyze_episode_mapping(
        self,
        anime_info: Dict,
        local_files: List[Dict],
    ) -> Optional[AIAnalysisResult]:
        """
        分析本地文件与TMDB剧集的映射关系

        Args:
            anime_info: TMDB动漫信息
            local_files: 本地文件信息列表，包含文件名、路径、时长等
            season_info: 特定季度信息（可选）

        Returns:
            验证后的AIAnalysisResult对象
        """
        if not self.is_available():
            logger.warning("[AI识别] AI功能未启用或配置不完整")
            return None

        if not self.client:
            logger.error("[AI识别] AI 客户端未初始化。")
            return None

        try:
            prompt = self._build_analysis_prompt(anime_info, local_files)

            system_prompt = (
                "你是一个专业的动漫文件重命名助手。你需要分析本地动漫文件与TMDB数据库中剧集信息的对应关系，特别关注动漫BD发布与官方分季的差异。"
                + "请你只输出匹配到的季度和剧集信息，不要输出其他未匹配到tmdb信息的内容。"
            )
            if not self.json_mode:
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

            if self.json_mode:
                request_params["tools"] = [self._get_json_schema()]
                request_params["tool_choice"] = {
                    "type": "function",
                    "function": {"name": "analyze_file_structure"},
                }

            response = self.client.chat.completions.create(**request_params)

            response_message = response.choices[0].message
            if not response_message:
                logger.error("[AI识别] AI 响应内容为空。")
                return None

            # 提取并验证JSON内容
            result = self._extract_and_validate_json(response_message)

            if not result:
                logger.error("[AI识别] 无法解析或验证AI响应")
                return None

            # 记录低置信度结果
            if result.confidence == "Low":
                logger.warning(f"[AI识别] 低置信度结果: {result.reason}")

            logger.info(f"[AI识别] 分析完成，置信度: {result.confidence}")
            return result

        except Exception as e:
            logger.error(f"[AI识别] 分析失败: {str(e)}")
            return None

    def _build_analysis_prompt(
        self,
        anime_info: Dict,
        local_files: List[Dict],
    ) -> str:
        """构建分析提示词"""

        # 构建TMDB信息
        tmdb_info = f"""
动漫名称: {anime_info.get('name', '未知')}
首播日期: {anime_info.get('first_air_date', '未知')}
总季数: {anime_info.get('number_of_seasons', 0)}
总集数: {anime_info.get('number_of_episodes', 0)}
"""

        # 构建季度信息
        seasons_info = "TMDB 季度信息：\n"
        seasons_info += json.dumps(anime_info.get("seasons", ""), ensure_ascii=False)

        # 构建本地文件信息
        files_info = "本地文件信息 (路径均为相对路径):\n"
        for i, file_info in enumerate(local_files, 1):
            duration_str = ""
            if file_info.get("duration"):
                duration_str = f" (时长: {file_info['duration']:.1f}分钟)"
            files_info += f"  {file_info['path']}{duration_str}\n"

        prompt = f"""
请分析以下动漫的本地文件与TMDB数据的对应关系：

{tmdb_info}

{seasons_info}

{files_info}

请特别注意以下常见情况：
0. TMDB的第0季通常是特典或OVA集
1. 本地目录可能将多季合并为一个目录，或者相反
2. 本地目录剧集的标号可能会是总集号，而不是TMDB的季集号
3. 本地目录可能会给总集篇标注4.5这样的半集号，而TMDB会将其放在第0季
4. OVA/特典可能被放在正片季度末尾，而tmdb会将其放在第0季
5. 本地目录的不同季度可能仅用名称区分，没有明确季号
6. 剧场版有时被混在TV版中，一般会被tmdb视为特典处理；有时剧场版本身被视为单独的电影，但其特典被tmdb放到tv版第0季
"""

        if not self.json_mode:
            prompt += """
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
- 所有confidence值必须是枚举值之一
"""
        return prompt
