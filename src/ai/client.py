import json
from typing import Dict, List, Optional

from ..logger import logger
from .models import AIAnalysisResult, MediaSelectionResult
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
            self._client = GeminiClient()
        else:  # 默认使用OpenAI
            self._client = OpenAIClient()

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

    @staticmethod
    def build_media_selection_prompt(
        tv_candidates: List[Dict],
        movie_candidates: List[Dict],
        video_files: List[str],
        directory_name: str,
        is_anime: Optional[bool] = None,
    ) -> str:
        """构建媒体选择提示词"""
        
        # 构建本地文件信息
        files_info = f"目录名称: {directory_name}\n本地视频文件列表:\n"
        for i, file_path in enumerate(video_files, 1):
            files_info += f"  {i}. {file_path}\n"
        
        # 构建电视剧候选项
        tv_info = "电视剧候选项:\n"
        if tv_candidates:
            tv_info += json.dumps(tv_candidates, ensure_ascii=False, indent=2)
        else:
            tv_info += "无电视剧候选项"
        
        # 构建电影候选项
        movie_info = "电影候选项:\n"
        if movie_candidates:
            movie_info += json.dumps(movie_candidates, ensure_ascii=False, indent=2)
        else:
            movie_info += "无电影候选项"
        
        # 动漫信息
        anime_info = f"用户指定是否为动漫: {is_anime}\n" if is_anime is not None else "用户未指定媒体类型\n"
        
        prompt = f"""
请分析以下信息，确定媒体类型（电影或电视剧）并选择最匹配的TMDB条目：

{anime_info}
{files_info}
{tv_info}
{movie_info}

请特别注意以下情况：
1. 如果本地文件数量较多（>3），通常是电视剧
2. 如果本地文件数量较少（<=3），可能是电影或电视剧
3. 目录名称中包含季度信息（如Season、S01等）通常表示电视剧
4. 对于动漫，需要区分电视动漫和动漫电影
5. 选择最匹配的条目时，优先考虑名称相似度和发行时间
6. 避免选择新续作而忽略了原作（比如把"吊带袜天使"识别成"新吊带袜天使"）
"""
        return prompt
    
    @staticmethod
    def get_media_selection_system_prompt() -> str:
        """获取媒体选择系统提示词"""
        return (
            "你是一个专业的媒体文件分类助手。你需要根据本地文件信息和TMDB候选项，"
            + "准确判断媒体类型（电影或电视剧）并选择最匹配的TMDB条目。"
            + "请特别注意区分原作和续作，避免选择错误的续作。"
        )
    
    def identify_and_select_media(
        self,
        tv_candidates: List[Dict],
        movie_candidates: List[Dict],
        video_files: List[str],
        directory_name: str,
        is_anime: Optional[bool] = None,
    ) -> Optional[MediaSelectionResult]:
        """
        识别媒体类型并选择最佳TMDB候选项
        
        Args:
            tv_candidates: 电视剧候选项列表
            movie_candidates: 电影候选项列表
            video_files: 本地视频文件列表
            directory_name: 目录名称
            is_anime: 用户指定的是否为动漫
            
        Returns:
            识别和选择结果
        """
        if not self.is_available():
            logger.warning(f"[AI识别] AI功能未启用或{self.provider}客户端不可用")
            return None

        # 调试信息
        tv_count = len(tv_candidates)
        movie_count = len(movie_candidates)
        file_count = len(video_files)
        logger.info(f"[AI识别] 开始媒体选择: {directory_name}")
        logger.info(f"[AI识别] 候选项统计 - TV: {tv_count}, 电影: {movie_count}, 文件: {file_count}")
        logger.info(f"[AI识别] 使用提供商: {self.provider.upper()}")
        if is_anime is not None:
            logger.info(f"[AI识别] 用户指定动漫类型: {is_anime}")
        
        try:
            result = self._client.identify_and_select_media(
                tv_candidates, movie_candidates, video_files, directory_name, is_anime
            )
            
            if result:
                logger.info(f"[AI识别] 媒体选择成功 - 类型: {result.media_type}, ID: {result.selected_tmdb_id}")
                logger.info(f"[AI识别] 选中媒体: {result.selected_name}, 置信度: {result.confidence}")
                if result.confidence == "Low":
                    logger.warning(f"[AI识别] 低置信度警告: {result.reasoning}")
            else:
                logger.warning(f"[AI识别] 媒体选择失败，未返回结果")
            
            return result
            
        except Exception as e:
            logger.error(f"[AI识别] 媒体选择过程中发生异常: {str(e)}")
            return None

    @staticmethod
    def get_media_selection_json_instructions(schema_class) -> str:
        """获取媒体选择JSON指令"""
        schema = schema_class.model_json_schema()
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
