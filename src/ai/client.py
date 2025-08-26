import json
from typing import Dict, List, Optional

from ..logger import logger
from .models import AIAnalysisResult
from ..config.config_manager import cm
from .gemini_client import GeminiClient
from .openai_client import OpenAIClient
from .base_client import BaseAIClient


class AIClient:
    """AI客户端工厂类，根据配置选择合适的AI提供商"""

    def __init__(self):
        self.provider = cm.get_config("ai_provider") or "openai"
        self.enabled = bool(cm.get_config("ai_enabled"))
        self.confidence_threshold = cm.get_config("ai_confidence_threshold")

        # 根据提供商创建相应的客户端
        if self.provider.lower() == "gemini":
            self._client: BaseAIClient = GeminiClient()
        else:  # 默认使用OpenAI
            self._client: BaseAIClient = OpenAIClient()

    def is_available(self) -> bool:
        """检查AI客户端是否可用"""
        return bool(self.enabled and self._client and self._client.is_available())

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

        Returns:
            验证后的AIAnalysisResult对象
        """
        if not self.is_available():
            logger.warning(f"[AI识别] AI功能未启用或{self.provider}客户端不可用")
            return None

        logger.info(f"[AI识别] 使用 {self.provider.upper()} 进行分析")
        result = self._client.analyze_episode_mapping(anime_info, local_files)

        # 统一在此处保存分析数据
        self._client._save_analysis_data(anime_info, local_files, result)

        return result

    @staticmethod
    def build_common_prompt(anime_info: Dict, local_files: List[Dict]) -> str:
        """
        构建通用的分析提示词，不包含JSON格式要求

        Args:
            anime_info: TMDB动漫信息
            local_files: 本地文件信息列表，包含文件名、路径、时长等

        Returns:
            通用的分析提示词
        """
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
        return prompt

    @staticmethod
    def get_system_prompt() -> str:
        """
        获取通用的系统提示词

        Returns:
            系统提示词
        """
        return (
            "你是一个专业的动漫文件重命名助手。你需要分析本地动漫文件与TMDB数据库中剧集信息的对应关系，特别关注动漫BD发布与官方分季的差异。"
            + "请你只输出匹配到的季度和剧集信息，不要输出其他未匹配到tmdb信息的内容。"
        )
