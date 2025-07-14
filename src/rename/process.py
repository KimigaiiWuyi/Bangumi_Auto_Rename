import re
import json
import uuid
from pathlib import Path
from difflib import SequenceMatcher
from typing import Dict, List, Optional

from jikanpy import Jikan

from .trans import Trans
from ..logger import logger
from .get_info import Search
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
            target_fold = work_path / f'Season{info_season_id}'
            target_fold.mkdir(parents=True, exist_ok=True)

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
                    logger.info(f'[处理任务] 季度名称处于标题中：{sname}')
                    season_id = info_season_id
                    break

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

    def process(
        self,
        path: Path,
        _is_anime: Optional[bool] = None,
        _is_movie: Optional[bool] = None,
        _tuuid: Optional[str] = None,
        cus_name: Optional[str] = None,
        cus_season_id: Optional[int] = None,
    ):
        if path.is_dir():
            is_video = False
            for sub_path in path.iterdir():
                if not sub_path.is_dir() and sub_path.suffix in VIDEO_SUFFIX:
                    is_video = True

            if is_video:
                self._process(
                    path,
                    _is_anime,
                    _is_movie,
                    _tuuid,
                    cus_name,
                    cus_season_id,
                )
            else:
                for sub_path in path.iterdir():
                    self._process(
                        sub_path,
                        _is_anime,
                        _is_movie,
                        _tuuid,
                        cus_name,
                        cus_season_id,
                    )
        else:
            self._process(
                path,
                _is_anime,
                _is_movie,
                _tuuid,
                cus_name,
                cus_season_id,
            )

    def _process(
        self,
        path: Path,
        is_anime: Optional[bool] = None,
        is_movie: Optional[bool] = None,
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
                is_anime,
                is_movie,
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
        # 判断类型是否为电影
        season_id = 1
        pos = 0
        logger.info('[处理任务] 未传入任务类型，开始判断该文件是否为电影！')

        s1_name, s1_info = self.search.get_tv_info(rtpath_name, year)
        logger.info(f'[处理任务] 搜索到的电视剧名称: {s1_name}')
        if not s1_name and year != 0:
            s1_name, s1_info = self.search.get_tv_info(rtpath_name, 0)
            logger.info(f'[处理任务] 未搜索到结果, 删除year后重试: {s1_name}')

        s2_name, s2_info = self.search.get_movie_info(rtpath_name, year)
        logger.info(f'[处理任务] 搜索到的电影名称: {s2_name}')

        if not s2_name and year != 0:
            s2_name, s2_info = self.search.get_movie_info(
                rtpath_name,
                year,
            )
            logger.info(f'[处理任务] 未搜索到结果, 删除year后重试: {s2_name}')

        if s1_name:
            pos += 1
        elif s2_name:
            pos -= 1

        season_id = extract_season(rtpath_name)
        if season_id == -1:
            pos -= 0.6
            if path.is_file():
                pos -= 0.5
        else:
            pos += 0.6
            if path.is_file():
                pos += 0.5

        if path.is_dir():
            path_file_num = len([i for i in path.iterdir() if i.is_file()])
            if path_file_num > 6:
                pos += 0.4
            else:
                pos -= 0.4

        if pos > 0 or (is_movie is not None and not is_movie):
            logger.info('[处理任务] 该文件可能为电视剧！')
            is_movie = False
            tv_info = s1_info
            movie_info = None
            name = s1_name
        else:
            logger.info('[处理任务] 该文件可能为电影！')
            is_movie = True
            tv_info = None
            movie_info = s2_info
            name = s2_name

        # 【Step.2】
        # 如果是电影
        if is_movie:
            if not name:
                logger.warning(f'[处理任务] 未搜索到电影信息, 跳过{rtpath_name}')
                return self.error_reply(
                    _uuid,
                    f'[TMDB] 未搜索到电影信息, 跳过{rtpath_name}',
                    path,
                    is_anime,
                    is_movie,
                )

            if is_anime:
                _WORK_PATH = self.ANIME_MOVIE_PATH
            else:
                _WORK_PATH = self.MOVIE_PATH

            # 开始拆分
            if movie_info:
                first_data = movie_info['release_date']
                first_year = first_data.split('-')[0]
                work_path = _WORK_PATH / f'{name} ({first_year})'
                work_path.mkdir(parents=True, exist_ok=True)
                if path.is_file():
                    self.R[path] = work_path / f'{name} - {path.name}'
                else:
                    for item_path in path.iterdir():
                        item_name = item_path.name
                        self.R[item_path] = work_path / f'{name} - {item_name}'
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

            if not name:
                logger.warning(f'[处理任务] 未搜索到剧集信息, 跳过{rtpath_name}')
                return self.error_reply(
                    _uuid,
                    f'[TMDB] 未搜索到剧集信息, 跳过{rtpath_name}',
                    path,
                    is_anime,
                    is_movie,
                )

            # 开始重命名内部文件
            if tv_info:
                first_data: str = tv_info['first_air_date']
                first_year = first_data.split('-')[0]
                work_path = _WORK_PATH / f'{name} ({first_year})'

                season_id = self.get_season_id(
                    tv_info,
                    work_path,
                    path,
                    titles,
                )

                if cus_season_id:
                    season_id = int(cus_season_id)

                # 【AI增强处理】
                # 如果是动漫且启用了AI，使用AI分析文件映射
                if is_anime and self.ai_processor.ai_client.is_available():
                    logger.info("[处理任务] 启用AI分析动漫文件映射")
                    logger.info("[处理任务] 填充详细季信息")
                    tv_info = self.search.fill_season_info(tv_info)
                    ai_result: AIAnalysisResult | None = (
                        self.ai_processor.analyze_anime_files(path, tv_info)
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
                        elif (
                            confidence_threshold == "Medium"
                            and ai_result.confidence in ["High", "Medium"]
                        ):
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
                        logger.info(
                            "[处理任务] AI置信度不足或AI结果无效，使用传统方法处理"
                        )
                        self._process_traditional(
                            path, rtpath_name, work_path, season_id
                        )
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
