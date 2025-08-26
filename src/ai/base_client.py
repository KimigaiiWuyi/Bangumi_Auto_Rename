import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..config.config_manager import cm
from ..logger import logger
from ..utils.path import AI_ANALYSIS_PATH
from .models import AIAnalysisResult


class BaseAIClient(ABC):
    """AI客户端的抽象基类"""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.enabled = bool(cm.get_config("ai_enabled"))
        self.confidence_threshold = cm.get_config("ai_confidence_threshold")
        self.auto_save = bool(cm.get_config("ai_auto_save"))
        self.save_path = AI_ANALYSIS_PATH
        if self.auto_save and self.save_path:
            Path(self.save_path).mkdir(parents=True, exist_ok=True)

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """检查AI客户端是否可用"""
        raise NotImplementedError

    def _save_analysis_data(
        self,
        anime_info: Dict,
        local_files: List[Dict],
        result: Optional[AIAnalysisResult] = None,
    ):
        """
        保存分析数据和结果到文件

        Args:
            anime_info (Dict): TMDB动漫信息
            local_files (List[Dict]): 本地文件信息
            result (Optional[AIAnalysisResult], optional): AI分析结果. Defaults to None.
        """
        if not self.auto_save or not self.save_path:
            return

        try:
            anime_name = (
                anime_info.get("name", "unknown").replace("/", "_").replace("\\", "_")
            )
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{anime_name}_{self.provider_name}_{timestamp}.json"
            output_path = Path(self.save_path) / filename

            metadata = {
                "created_at": datetime.now().isoformat(),
                "anime_name": anime_info.get("name", "unknown"),
                "provider": self.provider_name,
                "file_count": len(local_files),
            }

            data_to_save = {
                "metadata": metadata,
                "anime_info": anime_info,
                "local_files": local_files,
            }

            if result:
                data_to_save["analysis_result"] = result.model_dump()

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)

            logger.info(
                f"[{self.provider_name.upper()}] 分析数据已保存到: {output_path}"
            )
        except Exception as e:
            logger.error(f"[{self.provider_name.upper()}] 保存分析数据失败: {e}")