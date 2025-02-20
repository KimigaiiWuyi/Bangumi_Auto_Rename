from importlib.resources import path
import re
import json
from tkinter.messagebox import IGNORE
import uuid
from pathlib import Path
from difflib import SequenceMatcher
from typing import Dict, List, Optional
from wsgiref.simple_server import server_version

from jikanpy import Jikan

from .trans import Trans
from ..logger import logger
from .get_info import Search
from ..utils.path import TASK_PATH
from ..config.config_manager import cm
from .utils import JELLYFIN_IGNORE_TAG, JELLYFIN_SUPPORT_EXTRA_NAME_DICT, JELLYFIN_UNSUPPORT_EXTRA_TAG, PATTERN, S0_TAG, EXTRA_TAG, IGNORE_DIR, VIDEO_SUFFIX, IGNORE_SUFFIX
from .cleaner import (
    remove_tag,
    to_sim_max,
    remove_code,
    remove_season,
    divide_by_season,
    divide_by_year,

    extract_number,
    extract_season,
    remove_episode,
    extract_base_num,
    match_and_extract,
    remove_similar_part,
    find_common_parts_in_videos,
)

jikan = Jikan()


RECURSION_LEVEL = 0 # 记录递归层数，方便日志输出

def match_special(name):
    for s0 in S0_TAG: # 寻找 Season00
        if s0 == r'\.5':  # 防止5作为后缀开头
            res = re.search(rf'(?<!{PATTERN})\d{{1,2}}{s0}(?![a-zA-Z0-9])', name, re.IGNORECASE)
        elif s0 == '00':  # 防止00出现在奇怪的地方
            res = re.search(rf'\b00\b', name)
        else:
            res = re.search(rf'(?<!{PATTERN}){s0}([\d]{{0,3}})(?!{PATTERN})', name, re.IGNORECASE)

        if res:
            return True
    return False

def match_extra(name):
    for ex in EXTRA_TAG:
        res = re.search(rf'(?<!{PATTERN}){ex}(?!{PATTERN})', name, re.IGNORECASE)
        if res:
            return True
    return False



# 递归的将一个文件夹中的子文件夹链接到一个地方(预处理，塞到result里)
def link_subitems(
    src_path:Path,
    dst_path:Path,
    result:Dict
):
    for i in src_path.iterdir():
        if i.is_dir():
            link_subitems(i, dst_path / i.name, result)
        else:
            result[i]=dst_path / i.name

# 处理未归类的特典文件夹
def process_subitems(
    src_path: Path, # 要处理的文件夹
    specials_path: Path, # Season00 的位置
    extras_path: Path, # 其他特典位置
    result: Dict, # 直接可以链接过去的
    group: Dict = None, # 需要排序改名的sp
    ):
    '''
    当特典文件夹并没有明确指明特点类型时
    该函数可以递归扫描其下所有文件
    把含有 special 相关关键字的文件放入 Season00 文件夹
    '''

    logger.info(f'[特典识别] 进入 {src_path.__str__()}')
    for item in src_path.iterdir():
        if item.is_dir():
            process_subitems(item, specials_path, extras_path / item.name, result) # 维持未分类特典的原始结构
        else:
            # 此处需要先识别menu, ncop/ed, pv, cm等有明显其他意义的tag, 防止遇到给所有extras都打一个sp tag的
            # 但是实际使用效果欠佳，毕竟太杂了识别不全，加太多反而容易误识别
            if match_extra(item.name):
                result[item] = extras_path / item.name # 未识别为特典，直接归类到杂项
            elif match_special(item.name):
                result[item] = specials_path / item.name; # cerr 可能产生的问题：多个季度的特典顺序混乱
                logger.info(f'[特典识别] 识别到 {item.name}, 移动到 Season00 文件夹')
            else:
                result[item] = extras_path / item.name # 未识别为特典，直接归类到杂项

            #-------------------我们暂且认为正片只会在季度根目录下出现-------------------

    logger.info(f'[特典识别] 退出 {src_path.__str__()}')




class Rename:
    def __init__(self, _root_path = None):
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

        self.search = Search()

        #self.R = {}
        self.prelink = {}

    def get_season_id(
        self,
        tv_info: Dict,
        #work_path: Path,
        path: Path,
        titles: Optional[List[Dict]],
    ):
        season_id = 1
        path_name = path.name
        all_similaritys: List[Dict] = []
        
        # 对要扫描的季度按季度降序排序，以防止识别不到季号后缀直接return
        sorted_info = sorted(tv_info['seasons'], key = lambda i: i['season_number'], reverse = True)

        for season in sorted_info:
            info_season_id = season['season_number']
            #target_fold = work_path / f'Season{info_season_id}'
            #target_fold.mkdir(parents=True, exist_ok=True)

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
                # 如果采用
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

    # 处理特典文件夹
    def _process_extras_dir(
        self,
        source_path: Path, # 要处理的文件夹
        series_workpath: Path, # 系列文件夹
        season_id: int,# cerr don't need
    ):
        '''
        传入季度文件夹下的文件夹
        将其归类为extra，并识别其中混杂的special
        '''

        season_workpath = series_workpath / f"Season {season_id:02}"
        special_path = series_workpath / 'Season 00'
        source_name = source_path.name       
        logger.info(f'[处理特典] 开始处理 {series_workpath.name} 第 {season_id} 季下的 {source_name}')

        # 要忽略的文件夹
        if self.SERVER_TYPE == 'jellyfin':
            selected_ignore = JELLYFIN_IGNORE_TAG
        else:
            selected_ignore = IGNORE_DIR
        for ignore_tag in selected_ignore:
            if re.match(rf'(?<!{PATTERN}){ignore_tag}(?!{PATTERN})',source_name,re.IGNORECASE):# cerr not sure correct
                logger.info(f'[处理特典] 忽略文件夹 {source_name}')
                return

        # 只有当 SERVER_TYPE == 'jellyfin' 时开启
        if self.SERVER_TYPE == 'jellyfin':
            # Jellyfin已定义类型的extras, 按照jellyfin给出的放到对应文件夹中
            for key, value in JELLYFIN_SUPPORT_EXTRA_NAME_DICT.items():
                if re.search(rf'(?!{PATTERN}){key}(?!{PATTERN})', source_name, re.IGNORECASE):
                    logger.info(f'[处理特典] 识别为支持类型 {value}')
                    if self.SERVER_TYPE == 'jellyfin':
                        link_subitems(source_path, season_workpath / value, self.prelink)#直接将整个文件夹链接过去
                    else:
                        link_subitems(source_path, series_workpath / 'extra' / key, self.prelink)
                    return
            # 对 CDs 文件夹特殊处理(直接放到others里，方便后期手动选择theme-music)
            if re.search(rf'(?<!{PATTERN})cd(?!{PATTERN})', source_name, re.IGNORECASE) or re.search(rf'(?<!{PATTERN})cds(?!{PATTERN})', source_name, re.IGNORECASE):
                logger.info(f'[处理特典] 识别为 CDs')
                link_subitems(source_path, season_workpath / 'others' / 'CDs', self.prelink)#直接将整个文件夹链接过去
                return
            # Jellyfin未定义类型的extras, 会尝试从中寻找已定义的类型
            for ex in JELLYFIN_UNSUPPORT_EXTRA_TAG:
                if re.search(rf'{ex}', source_name, re.IGNORECASE):
                    #for sub in source_path.iterdir():
                    #    if(sub.is_dir()):        
                    logger.info(f'[处理特典] 识别为未分类类型 {ex}')
                    # 从中寻找 Season00, 以及处理子文件夹，以防止有些在extras下有嵌套已知文件夹
                    process_subitems(source_path,special_path,season_workpath / 'extras', self.prelink)
                    return
        
        # 都没找到，直接丢到others
        logger.info(f'[处理特典] 识别失败，默认移动到 others')
        # 从中寻找 Season00, 以及处理子文件夹，以防止有些在extras下有嵌套已知文件夹
        if self.SERVER_TYPE == 'jellyfin':
            process_subitems(source_path,special_path,season_workpath / 'others' / source_path.name, self.prelink)
        else:
            process_subitems(source_path,special_path, series_workpath / 'extra' / source_path.name, self.prelink)
        return

    # 处理季度根目录下的视频
    # 重构于 process_sub
    def _process_single_video(
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


        #n_item_name_l = item_name.replace(itme_path_main_name, '').lower()
        #logger.info(f'[处理任务] 移去主要内容后的文件名Lower：{n_item_name_l}')

        season_folder_name = f"Season {season_id:02}"

        if match_extra(item_name_r):
            if self.SERVER_TYPE == 'jellyfin':
                t = work_path / season_folder_name / 'extras'
            else:
                t = work_path / 'extra'
            self.prelink[item_path] = t / item_name
            logger.info(f'[识别视频] 识别 {item_name_r} 为 extra')
            return

        if match_special(item_name_r):
            if self.SERVER_TYPE == 'jellyfin':
                t = work_path / 'Season 00'
            else:
                t = work_path / 'Season0'
            self.prelink[item_path] = t / item_name
            logger.info(f'[识别视频] 识别 {item_name_r} 为 special')
            return

        #_item_name = remove_code(remove_season(item_name_r))
        _item_name = remove_code(item_name_r) # 因为 extract_base_num 需要 season 作为辅助识别，所以先不移除
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
                #season_id = 0
                ep = -1
        else:
            ep = int(ep)

        _idata = match_and_extract(item_name)
        if _idata:
            season_id, ep = _idata[0], _idata[1]

        t = work_path / season_folder_name
        if ep == -1:
            logger.info(f'[识别视频] 未识别到集数，放入others文件夹')
            if self.SERVER_TYPE == 'jellyfin':
                self.prelink[item_path] = t / 'others' / item_name
            else:
                self.prelink[item_path] = work_path / 'extra' / item_name
        else:
            logger.info(f'[识别视频] 识别为第 {ep:02} 集')
            ep = f'{ep:02}'
            ss = f'{season_id:02}'
            #t.mkdir(parents=True, exist_ok=True)
            ft = f'S{ss}E{ep}'
            self.prelink[item_path] = t / f'{ft} - {item_name}'

    #def _process_series(
    #    self,
    #    source_path:Path,
    #    _is_anime: Optional[bool] = None,
    #    _is_movie: Optional[bool] = None,
    #    _tuuid: Optional[str] = None,
    #    cus_name: Optional[str] = None,
    #    cus_season_id: Optional[int] = None,
    #):

    def process(
        self,
        path: Path,
        _is_anime: Optional[bool] = None,
        _is_movie: Optional[bool] = None,
        _tuuid: Optional[str] = None,
        cus_name: Optional[str] = None,
        cus_season_id: Optional[int] = None,
    ):
        # 要处理两种情况
        # 一个是传入根目录（即包含一堆番的单目录）或者是一系列番的目录、
        # 一个是传入单目录（即单季度的番剧文件夹）
        if path.is_file():
            logger.warn(f'[传入目录] 指定的 {path.__str__()} 不是目录')
            return

        # 如果传入目录下有视频，说明传入的是系列目录（所以说请至少给每个动画建个文件夹啊喂）
        for item in path.iterdir():
            if item.is_file() and item.suffix in VIDEO_SUFFIX:
                is_single = True
                break
        else:
            is_single = False

        # 如果是单目录，直接处理
        if is_single:
            logger.info(f'[传入目录] 传入单目录，直接处理')
            self._process_single_folder(
                path,
                _is_anime,
                _is_movie,
                _tuuid,
                cus_name,
                cus_season_id,
            )
        # 处理二级目录
        else: 
            logger.info(f'[传入目录] 传入复合目录，开始递归')
            for sub_item in path.iterdir():
                self.process(
                    sub_item,
                    _is_anime,
                    _is_movie,
                    _tuuid,
                    cus_name,
                    cus_season_id,
                ) 
        return

    #封装标签移除和年份，季度识别
    def analyse_path_name(
        self,
        dir_name: str
    ):
        logger.info(f'[标签移除] 开始分析 {dir_name}')

        year = 0
        season_id = -1

        rtpath_name = remove_tag(dir_name)
        # 如果标签移除后啥都没有, 说明文件名也是标签的一部分
        if not rtpath_name:
            rtpath_name = remove_tag(dir_name, True)
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
            rtpath_name, season_id = divide_by_season(rtpath_name)
            rtpath_name, year = divide_by_year(rtpath_name)

        rtpath_name = remove_season(rtpath_name)
        rtpath_name = remove_episode(rtpath_name)
        rtpath_name = rtpath_name.strip('!')

        logger.info(f'[标签移除] 去除标签后: {rtpath_name}, 年份识别为： {year}')

        return rtpath_name, year, season_id

    # 识别文件夹储存的是电影还是剧集, 建议传入最低级文件夹（即只包含单季度的）
    # 重构于 _process 中 step1.5 部分
    def analyse_path_type(
        self,
        path: Path,
        rtpath_name: str,
        year: int,
        is_movie: bool = None,
        #titles: Dict,
    ):
        '''
        传入文件目录及相关辅助信息
        尝试借助api进行搜索
        返回可能的作品类型和名称
        '''
        logger.info(f'[识别类型] 未传入任务类型，开始判断 {path.name} 是否为电影！')

        logger.info(f'[搜索剧集] 开始搜索 {rtpath_name} ({year})')
        tv_name, tv_info = self.search.get_tv_info(rtpath_name, year)
        if not tv_name and year != 0:
            tv_name, tv_info = self.search.get_tv_info(rtpath_name, 0)
            logger.info(f'[搜索剧集] 未搜索到结果, 删除year后重试')
        logger.info(f'[搜索剧集] 搜索到的电视剧名称: {tv_name}')

        logger.info(f'[搜索电影] 开始搜索 {rtpath_name} ({year})')
        mv_name, mv_info = self.search.get_movie_info(rtpath_name, year)
        if not mv_name and year != 0:
            mv_name, mv_info = self.search.get_movie_info(rtpath_name, 0)
            logger.info(f'[搜索电影] 未搜索到结果, 删除year后重试')
        logger.info(f'[搜索电影] 搜索到的电影名称: {mv_name}')

        #if is_anime:
        #    if not mv_name and not tv_name:#cerr
        #        logger.info('[搜索动画] TMDB未搜索到!转为MyAnimeList搜索！')
        #        search_result = jikan.search(
        #            'anime',
        #            rtpath_name,
        #            page=1,
        #        )
        #        for i in search_result['data']:
        #            if i['type'] == 'Anime':
        #                data = i
        #                break
        #        else:
        #            for i in search_result['data']:
        #                if i['type'] == 'TV':
        #                    data = i
        #                    break
        #                else:
        #                    data = search_result['data'][0]
        #        titles = data['titles']
        #        logger.info((f'[搜索动画] MyAnimeList识别结果: {titles}'))
        #else:
        #    titles =[{'type':'Default','title': name}]


        if not tv_name and not mv_name:
            logger.warning(f'[识别类型] 未搜索到 {path.name} 相关的任何结果！')
            return None, None, None

        # 根据搜索结果和文件结构进行猜测
        rate = 0
        if tv_name:
            rate += 1
        if mv_name:
            rate -= 1

        if path.is_file():
            rate -= 0.5
        else:
            path_video_num = 0
            for i in path.iterdir():
                if i.is_file() and i.suffix.lower() in VIDEO_SUFFIX:
                    path_video_num += 1
            if path_video_num > 4:
                rate += 0.4
            else:
                rate -= 0.4

        season_id = extract_season(rtpath_name)
        if season_id == -1:
            rate -= 0.4
        else:
            rate += 0.6

        if is_movie is None:
            if rate < 0:
                logger.info(f'[识别类型] {path.name} 可能为电影！')
                return mv_name, mv_info, 'movie'
            else:
                logger.info(f'[识别类型] {path.name} 可能为电视剧！')
                return tv_name, tv_info, 'tv_show'
        else:
            if is_movie:
                logger.info(f'[识别类型] {path.name} 钦定为电影！')
                return mv_name, mv_info, 'movie'
            else:
                logger.info(f'[识别类型] {path.name} 钦定为电视剧！')
                return tv_name, tv_info, 'tv_show'
            

    # 处理单季度文件夹
    # 重构于 _process
    def _process_single_folder(
        self,
        path: Path,
        is_anime: Optional[bool] = None,
        is_movie: Optional[bool] = None,
        _tuuid: Optional[str] = None,
        cus_name: Optional[str] = None,
        cus_season_id: Optional[int] = -1,
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
        logger.info(f'[处理任务] 开始处理单文件夹"{path.name}"')

        year = 0
        season_id = -1

        if not path.is_dir():
            logger.info(f'[处理任务] 这不是文件夹"{path.name}"')
            return self.error_reply(
                _uuid,
                f'这不是文件夹 {path.name}',
                path,
                is_anime,
                is_movie,
            )
        # 统计该文件夹下视频文件数量
        path_video_num = 0;
        for i in path.iterdir():
            if i.is_file() and i.suffix.lower() in VIDEO_SUFFIX:
                path_video_num += 1

        # 【Step.1】
        # 先移除无用的标签, 方便之后搜索
        rtpath_name, year, season_id = self.analyse_path_name(path.name)


        # 【特殊改】
        if cus_name:
            rtpath_name = cus_name


        # 【Step.1.5】
        # 判断类型是否为电影并获取搜索结果
        name, info, path_type = self.analyse_path_type(path,rtpath_name,year,is_movie)
        if path_type is None:
            logger.warning(f'[处理任务] 未搜索到相关信息, 跳过 {rtpath_name}')
            return self.error_reply(#cerr
                _uuid,
                f'[TMDB] 未搜索到相关信息, 跳过 {rtpath_name}',
                path,
                is_anime,
                is_movie,
            )
        elif path_type == 'movie':
            is_movie = 1
        #elif path_type == 'tv_show':
        #    is_anime = 1

        tid = extract_season(rtpath_name)
        if tid != -1:
            season_id = tid


        # 【Step.2】
        # 如果是电影
        if path_type == 'movie':
            if is_anime:
                _WORK_PATH = self.ANIME_MOVIE_PATH
            else:
                _WORK_PATH = self.MOVIE_PATH

            # 开始拆分
            if info:
                first_data = info['release_date']
                first_year = first_data.split('-')[0]
                work_path = _WORK_PATH / f'{name} ({first_year})'
                #work_path.mkdir(parents=True, exist_ok=True)
                #链接文件（夹）
                for item_path in path.iterdir():
                    if item_path.is_file():
                        self.prelink[item_path] = work_path / f'{name} - {item_path.name}'
                    else:
                        if self.SERVER_TYPE == 'jellyfin':
                            link_subitems(item_path, work_path / 'others' / item_path.name, self.prelink)
                        else:
                            link_subitems(work_path / 'extra' / item_path.name, self.prelink)
            else:#cerr
                logger.warn('进入了意料之外的分支')
                return self.error_reply(
                _uuid,
                f'进入了意料之外的分支',
                path,
                is_anime,
                is_movie,
                )
        # 如果是剧集类型
        else:
            if is_anime:
                _WORK_PATH = self.ANIME_PATH
            else:
                _WORK_PATH = self.BANGUMI_PATH
            titles = None
            # 开始重命名内部文件
            if info:
                first_data: str = info['first_air_date']
                first_year = first_data.split('-')[0]
                season_id = self.get_season_id(
                    info,
                    path,
                    titles,
                )

                #指定季度，直接覆盖
                if cus_season_id != -1 and cus_season_id != None:#cerr
                    season_id = int(cus_season_id)

                work_path = _WORK_PATH / f'{name} ({first_year})'

                logger.info(f'[处理任务] 开始对 [文件夹] {path.name}处理')
                repeat = find_common_parts_in_videos(path)
                for item_path in path.iterdir():
                    #logger.info(f'[处理任务] 处理嵌套文件夹 {item_path.name}')
                    if item_path.is_dir():
                        #repeat_2 = find_common_parts_in_videos(item_path)
                        #for sub_item in item_path.iterdir():
                        self._process_extras_dir(item_path, work_path, season_id)
                    else:
                        self._process_single_video(item_path,repeat,work_path,season_id)
            else:
                logger.warn('进入了意料之外的分支')
                return self.error_reply(#cerr
                    _uuid,
                    f'进入了意料之外的分支',
                    path,
                    is_anime,
                    is_movie,
                    )
        task_path = TASK_PATH / f'{_uuid}.json'
        task_data = {
            'path': str(path),
            'is_anime': is_anime,
            'name': name,
            'season_id': season_id,
            'uuid': str(_uuid),
            'error': None,
        }
        trans_result = Trans(self.prelink, _uuid).trans_file()
        self.prelink = {}
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
        with open(task_path, 'w', encoding='UTF-8') as file:
            json.dump(task_data, file, indent=4, ensure_ascii=False)
        return True

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
