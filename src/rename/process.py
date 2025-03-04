import re
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from jikanpy import Jikan

from .utils import MediaInfo

from .trans import Trans
from ..logger import logger
from .get_info import Search
from ..utils.path import TASK_PATH
from ..config.config_manager import cm
from .utils import (
    PATTERN,
    IGNORE_DIR,
    VIDEO_SUFFIX,
    IGNORE_SUFFIX,
    JELLYFIN_IGNORE_TAG,
    JELLYFIN_UNSUPPORT_EXTRA_TAG,
    JELLYFIN_SUPPORT_EXTRA_NAME_DICT,
)
from .cleaner import (
    remove_code,
    remove_season,
    extract_number,
    extract_base_num,
    match_and_extract,
    remove_similar_part,
    find_common_parts_in_videos,
)

from . import matcher

jikan = Jikan()


RECURSION_LEVEL = 0  # 记录递归层数，方便日志输出


# 递归的将一个文件夹中的子文件夹链接到一个地方(预处理，塞到result里)
def link_subitems(src_path: Path, dst_path: Path, result: Dict):
    for i in src_path.iterdir():
        if i.is_dir():
            link_subitems(i, dst_path / i.name, result)
        else:
            result[i] = dst_path / i.name


# 处理未归类的特典文件夹
def process_subitems(
    src_path: Path,  # 要处理的文件夹
    specials_path: Path,  # Season00 的位置
    extras_path: Path,  # 其他特典位置
    result: Dict,  # 直接可以链接过去的
    group: Optional[Dict] = None,  # 需要排序改名的sp
):
    '''
    当特典文件夹并没有明确指明特点类型时
    该函数可以递归扫描其下所有文件
    把含有 special 相关关键字的文件放入 Season00 文件夹
    '''

    logger.info(f'[特典识别] 进入 {src_path.__str__()}')
    for item in src_path.iterdir():
        if item.is_dir():
            process_subitems(
                item, specials_path, extras_path / item.name, result
            )  # 维持未分类特典的原始结构
        else:
            # 此处需要先识别menu, ncop/ed, pv, cm等有明显其他意义的tag
            # 防止遇到给所有extras都打一个sp tag的
            # 但是实际使用效果欠佳，毕竟太杂了识别不全，加太多反而容易误识别
            if matcher.match_extra(item.name):
                result[item] = extras_path / item.name  # 未识别为特典，直接归类到杂项
            elif matcher.match_special(item.name):
                result[item] = specials_path / item.name
                # cerr 可能产生的问题：多个季度的特典顺序混乱
                logger.info(f'[特典识别] 识别到 {item.name}, 移动到 Season00 文件夹')
            else:
                result[item] = extras_path / item.name  # 未识别为特典，直接归类到杂项

            # -------------------我们暂且认为正片只会在季度根目录下出现-------------------

    logger.info(f'[特典识别] 退出 {src_path.__str__()}')

class Rename:
    def __init__(self, _root_path=None):
        self.BANGUMI_PATH = Path(cm.get_config('bangumi_path'))
        self.MOVIE_PATH = Path(cm.get_config('movie_path'))
        self.ANIME_PATH = Path(cm.get_config('anime_path'))
        self.ANIME_MOVIE_PATH = Path(cm.get_config('anime_movie_path'))
        self.SERVER_TYPE = cm.get_config('server_type')
        self.ALL_IN_ONE = cm.get_config('all_in_one')

        self.ANIME_MOVIE_PATH.mkdir(parents=True, exist_ok=True)
        self.MOVIE_PATH.mkdir(parents=True, exist_ok=True)
        self.ANIME_PATH.mkdir(parents=True, exist_ok=True)
        self.BANGUMI_PATH.mkdir(parents=True, exist_ok=True)

        self.ROOT_PATH = _root_path
        self.SERIES_NAME = None

        self.prelink = {}

        matcher.search = Search()



    # 处理特典文件夹
    def _process_extras_dir(
        self,
        source_path: Path,  # 要处理的文件夹
        series_workpath: Path,  # 系列文件夹
        season_id: int,  # cerr don't need
    ):
        '''
        传入季度文件夹下的文件夹
        将其归类为extra，并识别其中混杂的special
        '''

        season_workpath = series_workpath / f"Season {season_id:02}"
        special_path = series_workpath / 'Season 00'
        source_name = source_path.name
        _hint = f'{series_workpath.name} 第 {season_id} 季下的 {source_name}'
        logger.info(f'[处理特典] 开始处理 {_hint}')

        # 要忽略的文件夹
        if self.SERVER_TYPE == 'jellyfin':
            selected_ignore = JELLYFIN_IGNORE_TAG
        else:
            selected_ignore = IGNORE_DIR
        for ignore_tag in selected_ignore:
            if re.match(
                rf'(?<!{PATTERN}){ignore_tag}(?!{PATTERN})',
                source_name,
                re.IGNORECASE,
            ):  # cerr not sure correct
                logger.info(f'[处理特典] 忽略文件夹 {source_name}')
                return

        # 只有当 SERVER_TYPE == 'jellyfin' 时开启
        if self.SERVER_TYPE == 'jellyfin':
            # Jellyfin已定义类型的extras, 按照jellyfin给出的放到对应文件夹中
            for key, value in JELLYFIN_SUPPORT_EXTRA_NAME_DICT.items():
                if re.search(
                    rf'(?!{PATTERN}){key}(?!{PATTERN})',
                    source_name,
                    re.IGNORECASE,
                ):
                    logger.info(f'[处理特典] 识别为支持类型 {value}')
                    if self.SERVER_TYPE == 'jellyfin':
                        link_subitems(
                            source_path, season_workpath / value, self.prelink
                        )  # 直接将整个文件夹链接过去
                    else:
                        link_subitems(
                            source_path,
                            series_workpath / 'extra' / key,
                            self.prelink,
                        )
                    return
            # 对 CDs 文件夹特殊处理(直接放到others里，方便后期手动选择theme-music)
            if re.search(
                rf'(?<!{PATTERN})cd(?!{PATTERN})', source_name, re.IGNORECASE
            ) or re.search(
                rf'(?<!{PATTERN})cds(?!{PATTERN})', source_name, re.IGNORECASE
            ):
                logger.info('[处理特典] 识别为 CDs')
                link_subitems(
                    source_path,
                    season_workpath / 'others' / 'CDs',
                    self.prelink,
                )  # 直接将整个文件夹链接过去
                return
            # Jellyfin未定义类型的extras, 会尝试从中寻找已定义的类型
            for ex in JELLYFIN_UNSUPPORT_EXTRA_TAG:
                if re.search(rf'{ex}', source_name, re.IGNORECASE):
                    # for sub in source_path.iterdir():
                    #    if(sub.is_dir()):
                    logger.info(f'[处理特典] 识别为未分类类型 {ex}')
                    # 从中寻找 Season00, 以及处理子文件夹，以防止有些在extras下有嵌套已知文件夹
                    process_subitems(
                        source_path,
                        special_path,
                        season_workpath / 'extras',
                        self.prelink,
                    )
                    return

        # 都没找到，直接丢到others
        logger.info('[处理特典] 识别失败，默认移动到 others')
        # 从中寻找 Season00, 以及处理子文件夹，以防止有些在extras下有嵌套已知文件夹
        if self.SERVER_TYPE == 'jellyfin':
            process_subitems(
                source_path,
                special_path,
                season_workpath / 'others' / source_path.name,
                self.prelink,
            )
        else:
            process_subitems(
                source_path,
                special_path,
                series_workpath / 'extra' / source_path.name,
                self.prelink,
            )
        return

    # 处理季度根目录下的视频
    # 重构于 process_sub
    def _process_sub_video(
        self,
        item_path: Path,
        item_repeat: Optional[List[str]],
        work_path: Path,
        season_id: int,
    ):
        '''
        传入季度根目录下的视频
        识别其为 extra, special 或 正片 并归类
        '''
        item_suffix = item_path.suffix.lower()
        for ignore_tag in IGNORE_SUFFIX:
            if ignore_tag in item_suffix:
                logger.info(f'[识别视频] 忽略文件 {item_path.name}')
                return

        item_name = item_path.name
        if item_repeat:
            item_name_r = remove_similar_part(item_repeat, item_path.stem)
        else:
            item_name_r = item_path.stem

        logger.info(f'[识别视频] 将 {item_name} 提取为 {item_name_r}')

        # n_item_name_l = item_name.replace(itme_path_main_name, '').lower()
        # logger.info(f'[处理任务] 移去主要内容后的文件名Lower：{n_item_name_l}')

        season_folder_name = f"Season {season_id:02}"

        if matcher.match_extra(item_name_r):
            if self.SERVER_TYPE == 'jellyfin':
                t = work_path / season_folder_name / 'extras'
            else:
                t = work_path / 'extra'
            self.prelink[item_path] = t / item_name
            logger.info(f'[识别视频] 识别 {item_name_r} 为 extra')
            return

        if matcher.match_special(item_name_r):
            if self.SERVER_TYPE == 'jellyfin':
                t = work_path / 'Season 00'
            else:
                t = work_path / 'Season0'
            self.prelink[item_path] = t / item_name
            logger.info(f'[识别视频] 识别 {item_name_r} 为 special')
            return

        # _item_name = remove_code(remove_season(item_name_r))
        _item_name = remove_code(
            item_name_r
        )  # 因为 extract_base_num 需要 season 作为辅助识别，所以先不移除
        logger.info(f'[识别视频] 再次对 {item_name_r} 精简为 {_item_name}, 寻找集数')
        epp = extract_base_num(_item_name)
        if epp is None:
            ep = extract_number(remove_season(_item_name))
        else:
            ep = int(epp)

        if ep is None:
            if _item_name.isdigit():
                ep = int(_item_name)
            else:
                # season_id = 0
                ep = -1
        else:
            ep = int(ep)

        _idata = match_and_extract(item_name)
        if _idata:
            season_id, ep = _idata[0], _idata[1]

        t = work_path / season_folder_name
        if ep == -1:
            logger.info('[识别视频] 未识别到集数，放入others文件夹')
            if self.SERVER_TYPE == 'jellyfin':
                self.prelink[item_path] = t / 'others' / item_name
            else:
                self.prelink[item_path] = work_path / 'extra' / item_name
        else:
            logger.info(f'[识别视频] 识别为第 {ep:02} 集')
            ep = f'{ep:02}'
            ss = f'{season_id:02}'
            # t.mkdir(parents=True, exist_ok=True)
            ft = f'S{ss}E{ep}'
            self.prelink[item_path] = t / f'{ft} - {item_name}'

    # def _process_series(
    #    self,
    #    source_path:Path,
    #    _is_anime: Optional[bool] = None,
    #    _is_movie: Optional[bool] = None,
    #    _tuuid: Optional[str] = None,
    #    cus_name: Optional[str] = None,
    #    cus_season_id: Optional[int] = None,
    # ):


    def _classify_movie(self,media:MediaInfo):
        if media.is_anime:
            _WORK_PATH = self.ANIME_MOVIE_PATH
        else:
            _WORK_PATH = self.MOVIE_PATH

        # 开始拆分
        if media.info:
            first_data = media.info['release_date']
            first_year = first_data.split('-')[0]
            work_path = _WORK_PATH / f'{media.name} ({first_year})'
            # work_path.mkdir(parents=True, exist_ok=True)
            # 链接文件（夹）
            if media.path.is_file():
                logger.info(f'[分类电影] 开始对 [单文件] {media.path.name} 处理')
                self.prelink[media.path] = (
                    work_path / f'{media.name} - {media.path.name}'
                )
            else:
                logger.info(f'[分类电影] 开始对 [文件夹] {media.path.name} 处理')
                for item_path in media.path.iterdir():
                    if item_path.is_file():
                        self.prelink[item_path] = (
                            work_path / f'{media.name} - {item_path.name}'
                        )
                    else:
                        if self.SERVER_TYPE == 'jellyfin':
                            link_subitems(
                                item_path,
                                work_path / 'others' / item_path.name,
                                self.prelink,
                            )
                        else:
                            link_subitems(
                                item_path,
                                work_path / 'extra' / item_path.name,
                                self.prelink,
                            )
        else:  # cerr
            logger.warn('进入了意料之外的分支')
            return 1
        return 0
    
    def _classify_tvshow(self, media:MediaInfo):
        if media.is_anime:
            _WORK_PATH = self.ANIME_PATH
        else:
            _WORK_PATH = self.BANGUMI_PATH
        # 开始重命名内部文件
        if media.info:
            first_data: str = media.info['first_air_date']
            first_year = first_data.split('-')[0]
            #if media.season is None or media.season == -1:
            #    matcher.get_season_id(media)

            work_path = _WORK_PATH / f'{media.name} ({first_year})'

            if media.path.is_file():
                logger.info(f'[分类剧集] 开始对 [单文件] {media.path.name} 处理')
                self._process_sub_video(
                    media.path, "", work_path, media.season
                )
            else:
                logger.info(f'[分类剧集] 开始对 [文件夹] {media.path.name} 处理')
                repeat = find_common_parts_in_videos(media.path)
                for item_path in media.path.iterdir():
                    # logger.info(f'[处理任务] 处理嵌套文件夹 {item_path.name}')
                    if item_path.is_dir():
                        # repeat_2 = find_common_parts_in_videos(item_path)
                        # for sub_item in item_path.iterdir():
                        self._process_extras_dir(
                            item_path,
                            work_path,
                            media.season,
                        )
                    else:
                        self._process_sub_video(
                            item_path, repeat, work_path, media.season
                        )
        else:
            logger.warn('进入了意料之外的分支')
            return 1
        return 0

    # 整理文件到对应目录
    def _classify(
        self,
        media: MediaInfo,
        uid: Optional[str],
    ):
        '''
        此时已经获取媒体基本信息
        开始分类整理文件到对应目录
        '''
        ######################### [Step.2] 链文件 #########################
        # 如果是电影
        if media.is_movie:
            if self._classify_movie(media):
                return self.error_reply(
                uid,
                '进入了意料之外的分支',
                media.path,
                media.is_anime,
                media.is_movie,
                )
        # 如果是剧集类型
        else:
            if self._classify_tvshow(media):
                return self.error_reply(
                uid,
                '进入了意料之外的分支',
                media.path,
                media.is_anime,
                media.is_movie,
                )
        task_path = TASK_PATH / f'{uid}.json'
        task_data = {
            'path': str(media.path),
            'is_anime': media.is_anime,
            'name': media.name,
            'season_id': media.season,
            'uuid': str(uid),
            'error': None,
        }
        trans_result = Trans(self.prelink, uid).trans_file()
        self.prelink = {}
        if isinstance(trans_result, str):
            return self.error_reply(
                uid,
                trans_result,
                media.path,
                media.is_anime,
                media.is_movie,
                media.name,
                media.season,
            )
        with open(task_path, 'w', encoding='UTF-8') as file:
            json.dump(task_data, file, indent=4, ensure_ascii=False)
        return True

    def _preprocess(
        self,
        _path: Path,
        _is_anime: Optional[bool] = None,
        _is_movie: Optional[bool] = None,
        _tuuid: Optional[str] = None,
        _cus_name: Optional[str] = None,
        _cus_season_id: Optional[int] = None,
    ):
        ######################### [Step.0] 初始化 #########################
        if _tuuid:
            uid = _tuuid
        else:
            uid = str(uuid.uuid4())

        if not matcher.search.TMDB_KEY:
            return self.error_reply(
                uid,
                '你还没有配置TMDB的Key！任务失败！请先前往配置界面！',
                _path,
                _is_anime,
                _is_movie,
            )

        logger.info(f'[信息整合] 开始预处理"{_path.name}"')
        media = MediaInfo(_path)
        media.rtpath_name = _cus_name
        media.season = _cus_season_id
        media.is_anime = _is_anime
        media.is_movie = _is_movie
        path_type = matcher.get_full_info(media)
        if path_type is None:
            return self.error_reply(  # cerr
                uid,
                f'[TMDB] 未搜索到相关信息, 跳过 {media.rtpath_name}',
                media.path,
                media.is_anime,
                media.is_movie,
            )
        
        self._classify(media, uid)

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

    def process(
        self,
        path: Path,
        _is_anime: Optional[bool] = None,
        _is_movie: Optional[bool] = None,
        _tuuid: Optional[str] = None,
        cus_name: Optional[str] = None,
        cus_season_id: Optional[int] = None,
    ):
        '''
        可传入单文件或文件夹
        单文件直接处理
        文件夹根据 all in one 状态判断是否要递归
        '''
        # 传入文件
        if path.is_file():
            logger.info(f'[传入目录] 传入的 {path.__str__()} 是文件')
            if path.suffix not in VIDEO_SUFFIX:
                logger.warn(f'[传入目录] 该文件不是视频，自动忽略')
                return
            self._preprocess(
                path,
                _is_anime,
                _is_movie,
                _tuuid,
                cus_name,
                cus_season_id,
            )
            return
        # 传入文件夹
        # 如果传入目录下有视频，说明传入的是系列目录（所以说请至少给每个动画建个文件夹啊喂）
        for item in path.iterdir():
            if item.is_file() and item.suffix in VIDEO_SUFFIX:
                is_single = True
                break
        else:
            is_single = False

        # 如果是单目录，直接处理
        if is_single:
            logger.info('[传入目录] 传入单目录，直接处理')
            self._preprocess(
                path,
                _is_anime,
                _is_movie,
                _tuuid,
                cus_name,
                cus_season_id,
            )
        # 处理二级目录
        else:
            logger.info('[传入目录] 传入复合目录，开始递归')
            if self.ALL_IN_ONE == '开启':
                for sub_item in path.iterdir():
                    self.process(
                        sub_item,
                        _is_anime,
                        _is_movie,
                        _tuuid,
                        cus_name,
                        cus_season_id,
                    )
            else:
                for sub_item in path.iterdir():
                    self._preprocess(
                        sub_item,
                        _is_anime,
                        _is_movie,
                        _tuuid,
                        cus_name,
                        cus_season_id,
                    )
        return