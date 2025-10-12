import re
from time import sleep
from typing import Any, Dict, List, Optional, Tuple

import tmdbsimple as tmdb

from ..logger import logger
from ..config.config_manager import cm
from .cleaner import is_chinese_percentage_sufficient


class Search:
    def __init__(self) -> None:
        self.TMDB_KEY = cm.get_config('api_key')
        tmdb.API_KEY = self.TMDB_KEY

    def get_season_info(
        self, tv_id: int, season_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        获取指定季度的详细信息，包括剧集列表

        Args:
            tv_id: 电视剧ID
            season_number: 季度号

        Returns:
            筛选后的季度信息字典，失败返回None
        """
        for i in range(3):
            try:
                season = tmdb.TV_Seasons(tv_id, season_number)
                season_info = season.info(language="zh-CN")

                if not season_info:
                    logger.warning(f"[季度信息] 未获取到Season {season_number}的信息")
                    return None

                # 筛选季度信息，只保留需要的字段
                filtered_season = {
                    "air_date": season_info.get("air_date"),
                    "episode_count": season_info.get("episode_count", 0),
                    "id": season_info.get("id"),
                    "name": season_info.get("name", ""),
                    "overview": season_info.get("overview", ""),
                    "season_number": season_info.get("season_number", season_number),
                    "episodes": [],
                }

                # 处理剧集信息
                episodes: List[Dict] = season_info.get("episodes", [])
                for episode in episodes:
                    filtered_episode = {
                        "air_date": episode.get("air_date"),
                        "episode_number": episode.get("episode_number"),
                        "episode_type": episode.get("episode_type", "regular"),
                        "name": episode.get("name", ""),
                        "overview": episode.get("overview", ""),
                        "runtime": episode.get("runtime"),
                        "season_number": episode.get("season_number", season_number),
                    }
                    filtered_season["episodes"].append(filtered_episode)

                logger.info(
                    f'[季度信息] 获取Season {season_number}信息成功，包含{len(filtered_season["episodes"])}集'
                )
                return filtered_season

            except Exception as e:
                logger.warning(
                    f"[季度信息] 获取Season {season_number}信息失败，重试第{i + 1}次: {str(e)}"
                )
                sleep(5)

        logger.error(f"[季度信息] 获取Season {season_number}信息最终失败")
        return None

    def get_tv_info_with_seasons(
        self, query: str, year: int
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        获取电视剧信息，包含详细的季度和剧集信息

        Args:
            query: 搜索关键词
            year: 年份

        Returns:
            (剧集名称, 包含详细季度信息的tv_info字典)
        """
        # 首先获取基本的电视剧信息
        name, tv_info = self.get_tv_info(query, year)

        if not name or not tv_info:
            return name, tv_info

        # 填充季度信息
        tv_info = self.fill_season_info(tv_info)
        return name, tv_info

    def fill_season_info(self, tv_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        填充电视剧信息中的季度信息

        Args:
            tv_info: 包含电视剧基本信息的字典

        Returns:
            填充后的tv_info字典
        """
        if not tv_info or "id" not in tv_info:
            logger.error("[季度信息] 无效的电视剧信息，无法填充季度信息")
            return tv_info

        tv_id = tv_info["id"]
        seasons = tv_info.get("seasons", [])

        if not seasons:
            logger.warning("[季度信息] 电视剧没有季度信息，尝试获取...")
            # 如果没有季度信息，尝试获取
            name, detailed_tv_info = self.get_tv_info_with_seasons(
                tv_info["name"], tv_info.get("first_air_date", 0)
            )
            if detailed_tv_info:
                return detailed_tv_info
            else:
                logger.error("[季度信息] 获取季度信息失败")
                return tv_info

        # 获取每个季度的详细信息
        for season in seasons:
            season_number = season.get("season_number")
            if season_number is None:
                logger.warning(f"[季度信息] 跳过无效季度: {season}")
                continue

            logger.info(f"[季度信息] 正在获取Season {season_number}的详细信息...")
            detailed_season = self.get_season_info(tv_id, season_number)

            if detailed_season:
                season.update(detailed_season)
            else:
                logger.warning(
                    f"[季度信息] Season {season_number}获取详细信息失败，使用原始数据"
                )

        logger.info(
            f'[季度信息] 电视剧《{tv_info["name"]}》的季度信息填充完成，共{len(seasons)}个季度'
        )
        return tv_info

    def get_movie_info(
        self,
        query: str,
        year: int,
    ):
        """获取单个电影信息（向后兼容）"""
        candidates = self.get_movie_info_candidates(query, year, max_candidates=1)
        if candidates:
            return candidates[0]
        return '', None
    
    def get_movie_info_candidates(
        self,
        query: str,
        year: int,
        max_candidates: int = 5
    ) -> List[Tuple[str, Dict]]:
        """
        获取电影信息，返回多个候选项的name+info数组
        
        Args:
            query: 搜索关键词
            year: 年份
            max_candidates: 最大候选项数量
            
        Returns:
            [(name, info), ...] 候选项列表，按TMDB相关性排序
        """
        candidates = []
        
        for i in range(3):
            try:
                search = tmdb.Search()
                search.movie(
                    query=query,
                    language='zh-CN',
                    year=year if year != 0 else None,
                )
                target_list = search.__dict__['results'][:max_candidates]
                
                for target in target_list:
                    name = target['title']
                    movie = tmdb.Movies(target['id'])
                    movie.info()
                    candidates.append((name, movie.__dict__))
                    
                return candidates
                
            except Exception as e:
                sleep(5)
                logger.warning(f'[电影搜索] 网络错误, 重试第{i + 1}次中...: {e}')
        
        return []

    def get_tv_info(
        self,
        query: str,
        year: int,
    ):
        """获取单个电视剧信息（向后兼容）"""
        candidates = self.get_tv_info_candidates(query, year, max_candidates=1)
        if candidates:
            return candidates[0]
        return '', None
    
    def get_tv_info_candidates(
        self,
        query: str,
        year: int,
        max_candidates: int = 5
    ) -> List[Tuple[str, Dict]]:
        """
        获取电视剧信息，返回多个候选项的name+info数组
        
        Args:
            query: 搜索关键词
            year: 年份
            max_candidates: 最大候选项数量
            
        Returns:
            [(name, info), ...] 候选项列表，按TMDB相关性排序
        """
        candidates = []
        
        for i in range(3):
            try:
                for _ in range(3):
                    search = tmdb.Search()
                    search.tv(
                        query=query,
                        language='zh-CN',
                        first_air_date_year=year if year != 0 else None,
                    )
                    target_list = search.__dict__['results'][:max_candidates]
                    
                    if target_list:
                        for target in target_list:
                            name = target['name']
                            tv = tmdb.TV(target['id'])
                            tv.info()
                            candidates.append((name, tv.__dict__))
                        return candidates
                    else:
                        if is_chinese_percentage_sufficient(query):
                            query = re.sub(r'[a-zA-Z]', '', query)
                            
                return candidates
                
            except Exception as e:
                sleep(5)
                logger.warning(f'[电视剧搜索] 网络错误, 重试第{i + 1}次中...: {e}')
        
        return []


def filter_tv_info_by_season(tv_info: Dict, target_season: int) -> Dict:
    """
    过滤TV信息，只保留指定季和第0季（特典）

    Args:
        tv_info: 完整的TMDB电视剧信息
        target_season: 目标季号

    Returns:
        过滤后的tv_info，只包含目标季和第0季的信息
    """
    if not tv_info:
        return tv_info

    # 复制原始信息，避免修改原始数据
    filtered_info = tv_info.copy()

    # 过滤seasons列表，只保留目标季和第0季
    original_seasons = tv_info.get("seasons", [])
    filtered_seasons = []

    for season in original_seasons:
        season_number = season.get("season_number", -1)
        # 保留目标季和第0季
        if season_number == target_season or season_number == 0:
            filtered_seasons.append(season)
            logger.debug(f"[季度过滤] 保留Season {season_number}的信息")

    filtered_info["seasons"] = filtered_seasons

    # 更新季数统计（不包括第0季）
    non_zero_seasons = [s for s in filtered_seasons if s.get("season_number", 0) != 0]
    filtered_info["number_of_seasons"] = len(non_zero_seasons)

    logger.debug(f"[季度过滤] 过滤完成，保留{len(filtered_seasons)}个季度的信息（包括第0季）")
    return filtered_info


def extract_tv_info(tv_info: Dict) -> Dict:
    """
    从 TMDB 电视剧信息中提取 AI 需要的关键字段
    """
    # 提取季度信息，过滤掉第0季（特别篇）
    seasons = []
    for season in tv_info.get("seasons", []):
        # 跳过第0季（特别篇/OVA等）
        if season.get("season_number", 0) == 0:
            continue

        seasons.append({
            "air_date": season.get("air_date", ""),
            "episode_count": season.get("episode_count", 0),
            "name": season.get("name", ""),
            "overview": season.get("overview", ""),
            "season_number": season.get("season_number", 0)
        })

    return {
        "id": tv_info.get("id"),
        "first_air_date": tv_info.get("first_air_date", ""),
        "name": tv_info.get("name", ""),  # 电视剧使用name字段
        "genres": [g.get("name", "") for g in tv_info.get("genres", [])],
        "number_of_episodes": tv_info.get("number_of_episodes", 0),
        "number_of_seasons": tv_info.get("number_of_seasons", 0),
        "origin_country": tv_info.get("origin_country", []),
        "original_language": tv_info.get("original_language", ""),
        "original_name": tv_info.get("original_name", ""),
        "overview": tv_info.get("overview", ""),
        "seasons": seasons  # 已过滤第0季
    }


def extract_movie_info(movie_info: Dict) -> Dict:
    """
    从 TMDB 电影信息中提取 AI 需要的关键字段
    """
    return {
        "id": movie_info.get("id"),
        "name": movie_info.get("title", ""),  # 电影使用title字段
        "genres": [g.get("name", "") for g in movie_info.get("genres", [])],
        "origin_country": movie_info.get("origin_country", []),
        "original_language": movie_info.get("original_language", ""),
        "original_title": movie_info.get("original_title", ""),
        "overview": movie_info.get("overview", ""),
        "release_date": movie_info.get("release_date", ""),
        "title": movie_info.get("title", "")
    }
