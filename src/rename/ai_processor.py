from pathlib import Path
from typing import Dict, List, Optional

from ..logger import logger
from .utils import VIDEO_SUFFIX
from ..ai.client import AIClient
from ..ai.models import AIAnalysisResult
from ..ai.video_analyzer import VideoAnalyzer


class AIProcessor:
    """AI辅助处理器，用于智能分析和重命名"""

    def __init__(self):
        self.ai_client = AIClient()
        self.video_analyzer = VideoAnalyzer()

    def analyze_anime_files(
        self, path: Path, anime_info: Dict
    ) -> Optional[AIAnalysisResult]:
        """
        使用AI分析动漫文件的映射关系

        Args:
            path: 本地文件路径
            anime_info: TMDB动漫信息
            season_info: 特定季度信息（可选）

        Returns:
            验证后的AI分析结果
        """
        if not self.ai_client.is_available():
            logger.info("[AI处理] AI功能未启用，跳过AI分析")
            return None

        # 收集视频文件
        video_files = self._collect_video_files(path)
        if not video_files:
            logger.warning("[AI处理] 未找到视频文件")
            return None

        # 分析视频文件
        file_analysis = self.video_analyzer.analyze_video_files(path, video_files)

        # 使用AI分析映射关系
        ai_result = self.ai_client.analyze_episode_mapping(anime_info, file_analysis)

        if ai_result:
            logger.info(f"[AI处理] AI分析完成，置信度: {ai_result.confidence}")

            # 记录低置信度结果到单独日志
            if ai_result.confidence == "Low":
                self._log_low_confidence_result(path, ai_result)

        return ai_result

    def apply_ai_mapping(
        self,
        ai_result: AIAnalysisResult | None,
        base_path: Path,
        work_path: Path,
    ) -> Dict[Path, Path]:
        """
        应用AI分析结果生成全新的文件映射，并处理关联文件。

        Args:
            ai_result: 验证后的AI分析结果
            base_path: 媒体文件扫描的根目录
            work_path: 目标工作目录路径

        Returns:
            一个全新的文件映射字典
        """
        if not ai_result or not ai_result.file_mapping:
            logger.info("[AI处理] 无有效AI分析结果，返回空映射")
            return {}

        new_mapping: Dict[Path, Path] = {}
        all_local_files = (
            list(base_path.rglob("*"))
            if base_path.is_dir()
            else list(base_path.parent.iterdir())
        )

        try:
            # 记录季度映射信息
            if ai_result.season_mapping:
                logger.info("[AI处理] AI季度映射:")
                for season_map in ai_result.season_mapping:
                    logger.info(
                        f"  {season_map.local_group_name} -> TMDB季度: {season_map.maps_to_tmdb_seasons}"
                    )

            for mapping in ai_result.file_mapping:
                relative_path_str = mapping.file_path
                tmdb_season = mapping.tmdb_season
                tmdb_episode = mapping.tmdb_episode
                episode_type = mapping.episode_type
                confidence = mapping.confidence

                # 从相对路径还原绝对路径
                source_path = (base_path / relative_path_str).resolve()

                if not source_path.exists():
                    logger.warning(f"[AI处理] AI返回的文件路径不存在: {source_path}")
                    continue

                # 根据类型确定目标目录
                if episode_type == "special":
                    target_dir = work_path / "Season0"
                elif episode_type == "movie":
                    target_dir = work_path / "Movies"
                else:
                    target_dir = work_path / f"Season{tmdb_season}"

                target_dir.mkdir(parents=True, exist_ok=True)

                # 生成新的文件名
                if episode_type in ["special", "ova"]:
                    new_video_filename = f"S00E{tmdb_episode:02d}{source_path.suffix}"
                elif episode_type == "movie":
                    new_video_filename = source_path.name
                else:
                    new_video_filename = (
                        f"S{tmdb_season:02d}E{tmdb_episode:02d}{source_path.suffix}"
                    )

                # 1. 添加视频文件自身的映射
                target_video_path = target_dir / new_video_filename
                new_mapping[source_path] = target_video_path
                logger.info(
                    f"[AI处理] AI映射: {source_path.name} -> {new_video_filename} "
                    f"(类型: {episode_type}, 置信度: {confidence})"
                )

                # 2. 查找并添加关联文件的映射
                video_filename = source_path.stem
                for other_file in all_local_files:
                    if not other_file.is_file() or other_file == source_path:
                        continue

                    # 检查是否为关联文件：完整文件名包含"视频文件名."的就是关联文件
                    if other_file.name.startswith(f"{video_filename}."):
                        # 提取关联文件的后缀部分（保留所有后缀，如 .lang.ass）
                        suffix_part = other_file.name[
                            len(video_filename) :  # noqa: E203
                        ]

                        # 构建关联文件的新文件名：新视频文件名（不含扩展名）+ 关联文件后缀
                        new_video_stem = new_video_filename.rsplit(".", 1)[0]
                        new_associated_filename = f"{new_video_stem}{suffix_part}"

                        target_associated_path = target_dir / new_associated_filename
                        new_mapping[other_file] = target_associated_path
                        logger.info(
                            f"[AI处理] 发现并映射关联文件: {other_file.name} -> {new_associated_filename}"
                        )

        except Exception as e:
            logger.error(f"[AI处理] 应用AI映射时发生严重错误: {str(e)}", exc_info=True)
            return {}  # 发生错误时返回空映射，避免部分成功导致的数据不一致

        return new_mapping

    def _collect_video_files(self, path: Path) -> List[Path]:
        """收集指定路径下的所有视频文件"""
        video_files = []

        if path.is_file():
            if path.suffix.lower() in VIDEO_SUFFIX:
                video_files.append(path)
        else:
            for item in path.rglob("*"):
                if item.is_file() and item.suffix.lower() in VIDEO_SUFFIX:
                    video_files.append(item)

        return sorted(video_files)

    def _log_low_confidence_result(self, path: Path, ai_result: AIAnalysisResult):
        """记录低置信度结果到单独日志"""
        confidence = ai_result.confidence
        reason = ai_result.reason

        logger.warning(
            f"[AI低置信度] 路径: {path} | 置信度: {confidence} | "
            f"理由: {reason} | 映射数量: {len(ai_result.file_mapping)}"
        )

        # 记录季度映射
        if ai_result.season_mapping:
            for season_map in ai_result.season_mapping:
                logger.warning(
                    f"[AI低置信度] 季度映射: {season_map.local_group_name} -> {season_map.maps_to_tmdb_seasons}"
                )

        # 详细记录每个映射的置信度
        for mapping in ai_result.file_mapping:
            if mapping.confidence == "Low":
                logger.warning(
                    f"[AI低置信度文件] {mapping.file_path} -> "
                    f"S{mapping.tmdb_season:02d}E{mapping.tmdb_episode:02d} "
                    f"(类型: {mapping.episode_type}, 置信度: {mapping.confidence})"
                )

        # 记录额外说明
        if ai_result.extra_notes:
            logger.warning(f"[AI低置信度] 额外说明: {ai_result.extra_notes}")
