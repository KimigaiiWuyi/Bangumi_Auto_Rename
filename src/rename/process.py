import re
import json
import uuid
from pathlib import Path
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Union, Optional

from jikanpy import Jikan

from .trans import Trans
from ..logger import logger
from .get_info import Search, filter_tv_info_by_season
from ..utils.path import TASK_PATH
from .ai_processor import AIProcessor
from ..config.config_manager import cm
from ..ai.models import AIAnalysisResult
from .utils import S0_TAG, EXTRA_TAG, IGNORE_DIR, VIDEO_SUFFIX, IGNORE_SUFFIX
from .cleaner import (
    remove_tag,
    to_sim_max,
    remove_code,
    remove_season,
    divide_by_year,
    extract_number,
    extract_season,
    remove_episode,
    extract_base_num,
    match_and_extract,
    remove_similar_part,
    find_unique_parts_in_videos,
)

jikan = Jikan()


class Rename:
    def __init__(self):
        self.BANGUMI_PATH = Path(cm.get_config('bangumi_path'))
        self.MOVIE_PATH = Path(cm.get_config('movie_path'))
        self.ANIME_PATH = Path(cm.get_config('anime_path'))
        self.ANIME_MOVIE_PATH = Path(cm.get_config('anime_movie_path'))

        self.ANIME_MOVIE_PATH.mkdir(parents=True, exist_ok=True)
        self.MOVIE_PATH.mkdir(parents=True, exist_ok=True)
        self.ANIME_PATH.mkdir(parents=True, exist_ok=True)
        self.BANGUMI_PATH.mkdir(parents=True, exist_ok=True)
        self.search = Search()
        self.ai_processor = AIProcessor()

        self.R = {}

    def get_season_id(
        self,
        tv_info: Dict,
        work_path: Path,
        path: Path,
        titles: Optional[List[Dict]],
    ):
        season_id = 1
        path_name = path.name
        all_similaritys: List[Dict] = []

        for season in tv_info['seasons']:
            info_season_id = season['season_number']
            sname: str = season['name']
            logger.info(f'[处理任务] Season{info_season_id} 季度名: {sname}')

            '''
            int_season = extract_season(sname)
            logger.info(f'[处理任务] 提取信息季号:{int_season}')
            '''

            int_rtpath_name = extract_season(path_name)
            logger.info(f'[处理任务] 提取标题季号:{int_rtpath_name}')
            if info_season_id == int_rtpath_name:
                season_id = int_rtpath_name
                break

            # 如果不是Season1的情况下，sname处于路径之中，则直接跳过
            if not (sname.strip().startswith('Season') and '1' in sname):
                if sname in path.name:
                    sname_list = sname.split(' ')
                    path_name_list = path.stem.split(' ')
                    if len(sname_list) == len(path_name_list):
                        logger.info(f'[处理任务] 季度名称处于标题中：{sname}')
                        season_id = info_season_id
                        break
                    else:
                        logger.info(f'[处理任务] 季度名称与路径名称长度不同：{sname}')

                if titles:
                    # 或者计算相似度
                    for title in titles:
                        similaritys = {}
                        if title['type'] in [
                            'Default',
                            'Synonym',
                            'English',
                            'French',
                        ]:
                            ename = title['title']
                            path_name = path_name.replace(ename, '')
                            similarity = SequenceMatcher(
                                None,
                                sname,
                                remove_tag(path_name),
                            ).ratio()

                            # logger.debug(f'相似度{tindex}：{similarity}')
                            similaritys[similarity] = season_id
                        all_similaritys.append(similaritys)
        else:
            if all_similaritys:
                logger.info(f'[处理任务] 相似度：{all_similaritys}')
                season_id = to_sim_max(all_similaritys)

        logger.info(f'[处理任务] 识别季号：{season_id}')
        return season_id

    def process_sub(
        self,
        itme_path_main_name: str,
        item_repeat: Optional[List[str]],
        item_path: Path,
        work_path: Path,
        season_id: int,
    ):
        item_name = item_path.name
        if item_repeat:
            item_name_remove = remove_similar_part(item_repeat, item_path.stem)
        else:
            item_name_remove = item_path.stem

        item_name_l = item_name_remove.lower()
        item_suffix = item_path.suffix.lower()

        n_item_name_l = item_name.replace(itme_path_main_name, '').lower()
        logger.info(f'[处理任务] 移去主要内容后的文件名Lower：{n_item_name_l}')

        for ignore_dir in IGNORE_DIR:
            if ignore_dir in item_path.name:
                logger.info(f'[处理任务] 忽略文件夹：{item_path.name}')
                break
        else:
            for ignore_tag in IGNORE_SUFFIX:
                if ignore_tag in item_suffix:
                    logger.info(f'[处理任务] 忽略文件：{item_path.name}')
                    break
            else:
                p = r'[a-zA-Z\u4e00-\u9fa5]'
                for ex in EXTRA_TAG:
                    if re.search(
                        rf'(?<!{p}){ex.lower()}(?!{p})',
                        n_item_name_l,
                    ):
                        t = work_path / 'extra'
                        self.R[item_path] = t / item_name
                        logger.info(
                            f'[处理任务] 识别{n_item_name_l},'
                            f'移动到extra文件夹：{item_path.name}'
                        )
                        break
                else:
                    for s0 in S0_TAG:
                        if re.search(rf'{s0.lower()}[\d]{{0,3}}', item_name_l):
                            t = work_path / 'Season0'
                            self.R[item_path] = t / item_name
                            logger.info(
                                f'[处理任务] 识别{n_item_name_l},'
                                f'移动到Season0文件夹：{item_path.name}'
                            )
                            break
                    else:
                        _item_name = remove_code(remove_season(item_name_l))
                        logger.info(
                            f'[处理任务] 开始对{_item_name}处理, 寻找集数中...")'
                        )
                        epp = extract_base_num(_item_name)
                        if epp is None:
                            ep = extract_number(_item_name)
                        else:
                            ep = int(epp)

                        if ep is None:
                            if _item_name.isdigit():
                                ep = int(_item_name)
                            else:
                                season_id = 0
                                ep = 0
                        else:
                            ep = int(ep)

                        _idata = match_and_extract(item_name)
                        if _idata:
                            season_id, ep = _idata[0], _idata[1]

                        t = work_path / f'Season{season_id}'

                        ep = f'0{ep}' if ep < 10 else ep
                        s = f'0{int(season_id)}'
                        ss = s if season_id < 10 else int(season_id)
                        t.mkdir(parents=True, exist_ok=True)
                        ft = f'S{ss}E{ep}'
                        self.R[item_path] = t / f'{ft} - {item_name}'
        logger.info(f'[处理任务] 处理完成{item_name}')

    def process(
        self,
        path: Path,
        _is_anime: Optional[bool] = None,
        _is_movie: Optional[bool] = None,
        _tuuid: Optional[str] = None,
        cus_name: Optional[str] = None,
        cus_season_id: Optional[int] = None,
        _depth: int = 0,
        _max_depth: int = 5,
    ):
        """
        递归处理路径，直到找到包含视频文件的目录或达到最大深度

        Args:
            path: 要处理的路径
            _is_anime: 是否为动漫
            _is_movie: 是否为电影
            _tuuid: 任务UUID
            cus_name: 自定义名称
            cus_season_id: 自定义季号
            _depth: 当前递归深度
            _max_depth: 最大递归深度（默认5层）
        """
        # 检查递归深度
        if _depth > _max_depth:
            logger.warning(f'[处理任务] 已达到最大递归深度 {_max_depth}，停止展开: {path}')
            return

        if path.is_dir():
            # 检查当前目录是否包含视频文件
            has_video = False
            for sub_path in path.iterdir():
                if not sub_path.is_dir() and sub_path.suffix.lower() in VIDEO_SUFFIX:
                    has_video = True
                    break

            if has_video:
                # 当前目录包含视频文件，作为一个任务处理
                logger.info(f'[处理任务] 在深度 {_depth} 发现视频文件，开始处理: {path}')
                self._process(
                    path,
                    _is_anime,
                    _is_movie,
                    _tuuid,
                    cus_name,
                    cus_season_id,
                )
            else:
                # 当前目录不包含视频文件，递归处理子目录
                logger.info(f'[处理任务] 目录深度 {_depth} 未发现视频文件，继续递归: {path}')
                for sub_path in path.iterdir():
                    if sub_path.is_dir():
                        # 递归处理子目录，每个子目录作为独立的任务
                        self.process(
                            sub_path,
                            _is_anime,
                            _is_movie,
                            None,  # 子目录使用新的UUID
                            cus_name,
                            cus_season_id,
                            _depth + 1,
                            _max_depth,
                        )
                    elif sub_path.suffix.lower() in VIDEO_SUFFIX:
                        # 如果是单独的视频文件，直接处理
                        logger.info(f'[处理任务] 在深度 {_depth} 发现单个视频文件: {sub_path}')
                        self._process(
                            sub_path,
                            _is_anime,
                            _is_movie,
                            None,  # 单个文件使用新的UUID
                            cus_name,
                            cus_season_id,
                        )
        else:
            # 如果是文件，直接处理
            self._process(
                path,
                _is_anime,
                _is_movie,
                _tuuid,
                cus_name,
                cus_season_id,
            )

    def select_media_candidate(
        self,
        tv_candidates: List[tuple],
        movie_candidates: List[tuple],
        path: Path,
        is_anime: Optional[bool] = None,
        cus_season_id: Optional[int] = None,
    ) -> Union[Tuple[str, Dict, bool, Optional[int]], None]:
        """
        从多个TMDB候选项中选择最佳匹配（使用AI或传统逻辑）

        Returns:
            Tuple[name, info, is_movie, ai_season_id] or None if selection fails
            - name: 选中的媒体名称
            - info: 选中的TMDB信息
            - is_movie: 是否为电影
            - ai_season_id: AI识别的季号（如果AI选择了TV且识别了季号，否则为None）
        """
        total_candidates = len(tv_candidates) + len(movie_candidates)

        # 检查是否需要使用AI
        # 1. 多个候选项时使用AI
        # 2. 单个TV候选项但包含多季（不只是S0和S1）且用户未指定季号时使用AI
        should_use_ai = False
        if total_candidates > 1:
            should_use_ai = True
        elif total_candidates == 1 and len(tv_candidates) == 1 and cus_season_id is None:
            # 检查是否为多季剧集
            _, tv_info = tv_candidates[0]
            if tv_info and 'seasons' in tv_info:
                # 统计除S0和S1外的季数
                other_seasons = [s for s in tv_info['seasons']
                                if s['season_number'] not in [0, 1]]
                if other_seasons:
                    logger.info(f'[处理任务] 检测到多季剧集（共{len(tv_info["seasons"])}季），'
                               f'且用户未指定季号，将使用AI选择季号')
                    should_use_ai = True

        should_use_ai = (
            should_use_ai and
            self.ai_processor.ai_client.is_available() and
            cm.get_config("ai_enabled")
        )

        if should_use_ai:
            if total_candidates > 1:
                logger.info('[处理任务] 检测到多个候选项，启用AI进行智能选择')
            else:
                logger.info('[处理任务] 单个多季剧集且未指定季号，启用AI进行季号识别')
            ai_result = self.ai_processor.identify_and_select_media(
                tv_candidates=tv_candidates,
                movie_candidates=movie_candidates,
                path=path,
                is_anime=is_anime,
            )

            # 检查AI置信度阈值
            confidence_threshold = cm.get_config("ai_confidence_threshold")
            should_use_ai_result = False

            if ai_result:
                if (
                    confidence_threshold == "High"
                    and ai_result.confidence == "High"
                ):
                    should_use_ai_result = True
                elif confidence_threshold == "Medium" and ai_result.confidence in [
                    "High",
                    "Medium",
                ]:
                    should_use_ai_result = True
                elif confidence_threshold == "Low":
                    should_use_ai_result = True

            if should_use_ai_result and ai_result:
                logger.info(f'[处理任务] 使用AI选择结果：{ai_result.media_type} - {ai_result.selected_name}')
                if ai_result.selected_season is not None:
                    logger.info(f'[处理任务] AI建议季号：{ai_result.selected_season}')

                # 根据AI结果找到对应的候选项
                ai_selected_season = ai_result.selected_season
                if ai_result.media_type == "tv":
                    for name, info in tv_candidates:
                        if info.get("id") == ai_result.selected_tmdb_id:
                            return name, info, False, ai_selected_season
                    logger.warning('[处理任务] AI选择的电视剧ID未在候选项中找到，回退到传统逻辑')
                else:  # movie
                    for name, info in movie_candidates:
                        if info.get("id") == ai_result.selected_tmdb_id:
                            return name, info, True, None
                    logger.warning('[处理任务] AI选择的电影ID未在候选项中找到，回退到传统逻辑')
            else:
                logger.info('[处理任务] AI置信度不足或AI结果无效，使用传统方法处理')

        # 回退到传统逻辑：返回None表示没有AI选择结果
        return None

    def check_task_type(
        self,
        tv_candidates: List[tuple],
        movie_candidates: List[tuple],
        rtpath_name: str,
        path: Path,
    ) -> Tuple[str, Dict, bool]:
        """
        使用传统打分逻辑判断媒体类型（TV vs Movie）

        Returns:
            Tuple[name, info, is_movie]
        """
        logger.info('[处理任务] 使用传统打分逻辑进行媒体类型判断')

        # 获取第一个候选项
        s1_name, s1_info = tv_candidates[0] if tv_candidates else ('', None)
        s2_name, s2_info = movie_candidates[0] if movie_candidates else ('', None)

        logger.debug(f'[处理任务] 传统逻辑选择的电视剧名称: {s1_name}')
        logger.debug(f'[处理任务] 传统逻辑选择的电影名称: {s2_name}')

        season_id_in_name = extract_season(rtpath_name)
        pos = 0

        if s1_name:
            pos += 1
        elif s2_name:
            pos -= 1

        if season_id_in_name == -1:
            pos -= 0.6
            if path.is_file():
                pos -= 0.5
        else:
            pos += 0.6
            if path.is_file():
                pos -= 0.5

        if path.is_dir():
            # 只统计视频文件数量
            path_file_num = len([
                i for i in path.iterdir()
                if i.is_file() and i.suffix.lower() in VIDEO_SUFFIX
            ])
            if path_file_num > 6:
                pos += 0.4
            else:
                pos -= 0.4

        if pos > 0:
            logger.info('[处理任务] 传统逻辑判断: 该文件可能为电视剧！')
            return s1_name, s1_info, False
        else:
            logger.info('[处理任务] 传统逻辑判断: 该文件可能为电影！')
            return s2_name, s2_info, True
    
    def determine_season_id(
        self,
        tv_info: Dict,
        work_path: Path,
        path: Path,
        titles: Optional[List[Dict]],
        cus_season_id: Optional[int] = None,
        ai_season_id: Optional[int] = None,
    ) -> int:
        """
        确定季号，优先级：用户指定 > AI识别 > 传统方法

        Args:
            tv_info: TMDB电视剧信息
            work_path: 工作路径
            path: 原始路径
            titles: 标题列表（用于MyAnimeList）
            cus_season_id: 用户指定的季号
            ai_season_id: AI识别的季号

        Returns:
            确定的季号
        """
        # 优先级1: 用户指定的季号
        if cus_season_id is not None:
            logger.info(f'[处理任务] 使用用户指定季号：{cus_season_id}')
            return int(cus_season_id)

        # 优先级2: AI识别的季号
        if ai_season_id is not None:
            logger.info(f'[处理任务] 使用AI识别季号：{ai_season_id}')
            return ai_season_id

        # 优先级3: 传统方法识别季号
        logger.info('[处理任务] 使用传统方法识别季号')
        season_id = self.get_season_id(tv_info, work_path, path, titles)
        logger.info(f'[处理任务] 传统方法识别季号：{season_id}')
        return season_id

    def _process(
        self,
        path: Path,
        _is_anime: Optional[bool] = None,
        _is_movie: Optional[bool] = None,
        _tuuid: Optional[str] = None,
        cus_name: Optional[str] = None,
        cus_season_id: Optional[int] = None,
    ):
        if _tuuid:
            _uuid = _tuuid
        else:
            _uuid = str(uuid.uuid4())

        if not self.search.TMDB_KEY:
            return self.error_reply(
                _uuid,
                '你还没有配置TMDB的Key！任务失败！请先前往配置界面！',
                path,
                _is_anime,
                _is_movie,
            )

        # 【Step.0】 开始处理
        logger.info(f'[处理任务] 开始处理{path.name}')

        # 【Step.1】
        # 先移除无用的标签, 方便之后搜索
        year = 0
        rtpath_name = remove_tag(path.name)
        # 如果标签移除后啥都没有, 说明文件名也是标签的一部分
        if not rtpath_name:
            rtpath_name = remove_tag(path.name, True)
        # 按照空白、换行符或者连字符（-）分割成列表
        path_atri = re.split(r'[\s-]+', rtpath_name)
        # 如果该列表大于3, 不额外处理
        if len(path_atri) > 3:
            # path_atri.pop(0)
            rtpath_name = ' '.join(path_atri)
        # 如果该列表中有多个点, 则认为是一种规范命名的文件
        # 先用.分割之后, 按照年份分割后按照季度分割
        if rtpath_name.count('.') >= 3:
            rtpath_name = ' '.join(rtpath_name.split('.'))
            rtpath_name, year = divide_by_year(rtpath_name)

        rtpath_name = remove_season(rtpath_name)
        rtpath_name = remove_episode(rtpath_name)
        rtpath_name = rtpath_name.strip('!')
        logger.info(f'[处理任务] 去除标签后: {rtpath_name}')

        # 如果该路径不是一个视频文件或者不是一个文件夹, 则跳过
        if path.is_file() and path.suffix.lower() not in VIDEO_SUFFIX:
            logger.info(f'[处理任务] {path.name} 不是一个视频文件, 跳过')
            return

        # 【特殊改】
        if cus_name:
            rtpath_name = cus_name

        # 【Step.1.5】
        # 获取TMDB候选项（多个）
        logger.info('[处理任务] 未传入任务类型，开始搜索TMDB信息')
        tv_candidates = self.search.get_tv_info_candidates(rtpath_name, year)
        logger.info(f'[处理任务] 搜索到{len(tv_candidates)}个电视剧候选项')
        if not tv_candidates and year != 0:
            tv_candidates = self.search.get_tv_info_candidates(rtpath_name, 0)
            logger.info(f'[处理任务] 删除year后重试，搜索到{len(tv_candidates)}个电视剧候选项')

        movie_candidates = self.search.get_movie_info_candidates(rtpath_name, year)
        logger.info(f'[处理任务] 搜索到{len(movie_candidates)}个电影候选项')
        if not movie_candidates and year != 0:
            movie_candidates = self.search.get_movie_info_candidates(rtpath_name, 0)
            logger.info(f'[处理任务] 删除year后重试，搜索到{len(movie_candidates)}个电影候选项')

        # 如果没有找到任何候选项，返回错误
        if not tv_candidates and not movie_candidates:
            return self.error_reply(
                _uuid,
                f'[TMDB] 未搜索到任何信息, 跳过{rtpath_name}',
                path,
                _is_anime,
                _is_movie,
            )

        # 【Step.2】尝试使用AI选择候选项（如果有多个候选项或单个多季剧集）
        ai_season_id = None
        ai_selection = self.select_media_candidate(
            tv_candidates,
            movie_candidates,
            path,
            _is_anime,
            cus_season_id,
        )

        if ai_selection:
            # AI成功选择了候选项
            name, info, is_movie, ai_season_id = ai_selection
            logger.info(f'[处理任务] 使用AI选择结果：{"电影" if is_movie else "电视剧"} - {name}')
        else:
            # 使用传统打分逻辑判断类型
            name, info, is_movie = self.check_task_type(
                tv_candidates,
                movie_candidates,
                rtpath_name,
                path,
            )

        # 检查是否成功获取信息
        if not info:
            media_type_str = '电影' if is_movie else '电视剧'
            return self.error_reply(
                _uuid,
                f'[TMDB] 未搜索到{media_type_str}信息, 跳过{rtpath_name}',
                path,
                _is_anime,
                _is_movie,
            )

        # 【Step.3】判断是否为动漫
        is_anime = _is_anime
        if is_anime is None:
            for g in info['genres']:
                if g['name'].lower() == 'animation' or g['name'].lower() == 'anime':
                    is_anime = True
                    break
            else:
                is_anime = False

        # 【Step.4】
        # 如果是电影
        if is_movie:
            if is_anime:
                _WORK_PATH = self.ANIME_MOVIE_PATH
            else:
                _WORK_PATH = self.MOVIE_PATH

            first_data = info['release_date']
            first_year = first_data.split('-')[0]
            work_path = _WORK_PATH / f'{name} ({first_year})'
            work_path.mkdir(parents=True, exist_ok=True)
            if path.is_file():
                self.R[path] = work_path / f'{name} - {path.name}'
            else:
                for item_path in path.iterdir():
                    item_name = item_path.name
                    self.R[item_path] = work_path / f'{name} - {item_name}'
            season_id = 0
        # 如果是剧集类型
        else:
            if is_anime:
                if not name:
                    logger.info('[处理任务] TMDB未搜索到!转为MyAnimeList搜索！')
                    search_result = jikan.search(
                        'anime',
                        rtpath_name,
                        page=1,
                    )
                    for i in search_result['data']:
                        if i['type'] == 'Anime':
                            data = i
                            break
                    else:
                        for i in search_result['data']:
                            if i['type'] == 'TV':
                                data = i
                                break
                        else:
                            data = search_result['data'][0]
                    titles = data['titles']
                    logger.info((f'[处理任务] MyAnimeList识别结果: {titles}'))
                else:
                    titles = None
                _WORK_PATH = self.ANIME_PATH
            else:
                titles = [{'type': 'Default', 'title': name}]
                _WORK_PATH = self.BANGUMI_PATH

            first_data: str = info['first_air_date']
            first_year = first_data.split('-')[0]
            work_path = _WORK_PATH / f'{name} ({first_year})'

            # 【Step.5】确定季号（优先级：用户指定 > AI识别 > 传统方法）
            season_id = self.determine_season_id(
                tv_info=info,
                work_path=work_path,
                path=path,
                titles=titles,
                cus_season_id=cus_season_id,
                ai_season_id=ai_season_id,
            )

            # 【AI增强处理】
            # 如果是动漫且启用了AI，使用AI分析文件映射
            if is_anime and self.ai_processor.ai_client.is_available():
                logger.info("[处理任务] 启用AI分析动漫文件映射")
                logger.info("[处理任务] 填充详细季信息")
                tv_info = self.search.fill_season_info(info)

                # 过滤TMDB信息，只保留识别的季和第0季
                logger.info(f"[处理任务] 过滤TMDB信息，只保留Season {season_id}和Season 0")
                filtered_tv_info = filter_tv_info_by_season(tv_info, season_id)

                ai_result: AIAnalysisResult | None = (
                    self.ai_processor.analyze_anime_files(path, filtered_tv_info, season_id)
                )

                # 检查AI置信度阈值
                confidence_threshold = cm.get_config("ai_confidence_threshold")
                should_use_ai = False

                if ai_result:
                    if (
                        confidence_threshold == "High"
                        and ai_result.confidence == "High"
                    ):
                        should_use_ai = True
                    elif confidence_threshold == "Medium" and ai_result.confidence in [
                        "High",
                        "Medium",
                    ]:
                        should_use_ai = True
                    elif confidence_threshold == "Low":
                        should_use_ai = True

                if should_use_ai and ai_result:
                    logger.info("[处理任务] 使用AI分析结果进行文件映射")
                    # AI流程独立生成映射，不再需要传统方法预处理
                    self.R = self.ai_processor.apply_ai_mapping(
                        ai_result=ai_result, base_path=path, work_path=work_path
                    )
                    # 如果AI没有返回任何有效映射，则回退到传统方法
                    if not self.R:
                        logger.warning(
                            "[处理任务] AI未返回有效映射，回退到传统方法处理"
                        )
                        self._process_traditional(
                            path, rtpath_name, work_path, season_id
                        )
                else:
                    logger.info("[处理任务] AI置信度不足或AI结果无效，使用传统方法处理")
                    self._process_traditional(path, rtpath_name, work_path, season_id)
            else:
                # 传统处理方式
                self._process_traditional(path, rtpath_name, work_path, season_id)

        task_path = TASK_PATH / f"{_uuid}.json"
        task_data = {
            "path": str(path),
            "is_anime": is_anime,
            "is_movie": is_movie,
            "name": name,
            "season_id": season_id,
            "uuid": str(_uuid),
            "error": None,
            "use_ai": is_anime and self.ai_processor.ai_client.is_available(),
        }
        trans_result = Trans(self.R, _uuid).trans_file()
        self.R = {}
        if isinstance(trans_result, str):
            return self.error_reply(
                _uuid,
                trans_result,
                path,
                is_anime,
                is_movie,
                name,
                season_id,
            )
        with open(task_path, "w", encoding="UTF-8") as file:
            json.dump(task_data, file, indent=4, ensure_ascii=False)
        return True

    def _process_traditional(
        self, path: Path, rtpath_name: str, work_path: Path, season_id: int
    ):
        """传统处理方式"""
        if path.is_file():
            logger.info(f"[处理任务] 开始对 [单文件] {path.name}处理")
            self.process_sub(
                rtpath_name,
                None,
                path,
                work_path,
                season_id,
            )
        else:
            logger.info(f"[处理任务] 开始对 [文件夹] {path.name}处理")
            repeat = find_unique_parts_in_videos(path)
            for item_path in path.iterdir():
                logger.info(f"[处理任务] 处理嵌套文件夹 {item_path.name}")
                if item_path.is_dir():
                    repeat_2 = find_unique_parts_in_videos(item_path)
                    for sub_item in item_path.iterdir():
                        self.process_sub(
                            rtpath_name,
                            repeat_2,
                            sub_item,
                            work_path,
                            season_id,
                        )
                else:
                    self.process_sub(
                        rtpath_name,
                        repeat,
                        item_path,
                        work_path,
                        season_id,
                    )

    def error_reply(
        self,
        _uuid: str,
        error: str,
        path: Path,
        is_anime: Optional[bool] = None,
        is_movie: Optional[bool] = None,
        name: Optional[str] = None,
        season_id: Optional[int] = None,
    ):
        task_path = TASK_PATH / f'{_uuid}.json'
        task_data = {
            'path': str(path),
            'is_anime': is_anime,
            'is_movie': is_movie,
            'name': name,
            'season_id': season_id,
            'uuid': str(_uuid),
            'error': error,
        }
        with open(task_path, 'w', encoding='UTF-8') as file:
            json.dump(task_data, file, indent=4, ensure_ascii=False)
        return error
