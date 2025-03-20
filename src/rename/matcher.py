import re

from pathlib import Path
from difflib import SequenceMatcher
from typing import Dict, List, Optional


from . import cleaner
from . import utils
from .utils import MediaInfo
from ..logger import logger

search = 0


def match_special(name):
    for s0 in utils.S0_TAG:  # 寻找 Season00
        if s0 == r'\.5':  # 防止5作为后缀开头
            res = re.search(
                rf'(?<!{utils.PATTERN})\d{{1,2}}{s0}(?![a-zA-Z0-9])',
                name,
                re.IGNORECASE,
            )
        elif s0 == '00':  # 防止00出现在奇怪的地方
            res = re.search(r'\b00\b', name)
        else:
            res = re.search(
                rf'(?<!{utils.PATTERN}){s0}([\d]{{0,3}})(?!{utils.PATTERN})',
                name,
                re.IGNORECASE,
            )

        if res:
            return True
    return False


def match_extra(name):
    for key, value in utils.JELLYFIN_SUPPORT_EXTRA_NAME_DICT.items():
        res = re.search(
            rf'(?<!{utils.PATTERN}){key}(?!{utils.PATTERN})',
            name,
            re.IGNORECASE,
        )
        if res:
            return value
    return None


def get_season_id(media: MediaInfo):
    '''
    调用 media 中的 path, info
    修改 media 中的 season
    '''
    season_id = 1
    path_name = media.path.name
    all_similaritys: List[Dict] = []

    # 对要扫描的季度按季度降序排序，以防止识别不到季号后缀直接return
    sorted_info = sorted(
        media.info['seasons'], key=lambda i: i['season_number'], reverse=True
    )

    for season in sorted_info:
        info_season_id = season['season_number']
        # target_fold = work_path / f'Season{info_season_id}'
        # target_fold.mkdir(parents=True, exist_ok=True)

        sname: str = season['name']
        logger.info(f'[处理任务] Season{info_season_id} 季度名: {sname}')

        '''
        int_season = extract_season(sname)
        logger.info(f'[处理任务] 提取信息季号:{int_season}')
        '''

        int_rtpath_name = cleaner.extract_season(path_name)
        logger.info(f'[处理任务] 提取标题季号:{int_rtpath_name}')
        if info_season_id == int_rtpath_name:
            season_id = int_rtpath_name
            break

        # 如果不是Season1的情况下，sname处于路径之中，则直接跳过
        if not (sname.strip().startswith('Season') and '1' in sname):
            # 如果采用
            if sname in media.path.name:
                logger.info(f'[处理任务] 季度名称处于标题中：{sname}')
                season_id = info_season_id
                break

    else:
        if all_similaritys:
            logger.info(f'[处理任务] 相似度：{all_similaritys}')
            season_id = cleaner.to_sim_max(all_similaritys)

    logger.info(f'[处理任务] 识别季号：{season_id}')
    media.season = season_id
    return season_id

# 封装标签移除和年份，季度识别


def analyse_path_name(media: MediaInfo):
    '''
    调用 media 中的 path
    修改 media 中的 rtpath_name, year, season_id
    仅依赖文件名剥离名称，识别年份和季度
    '''
    if media.path.is_file():
        dir_name = media.path.stem
    else:
        dir_name = media.path.name
    rtpath_name = media.rtpath_name
    logger.info(f'[标签移除] 开始分析 {dir_name}')
    year = 0
    season_id = media.season

    if not rtpath_name:
        rtpath_name = cleaner.remove_tag(dir_name)
    # 如果标签移除后啥都没有, 说明文件名也是标签的一部分
    if not rtpath_name:
        rtpath_name = cleaner.remove_tag(dir_name, True)
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
        rtpath_name, season_id = cleaner.divide_by_season(rtpath_name)
        rtpath_name, year = cleaner.divide_by_year(rtpath_name)

    rtpath_name = cleaner.remove_season(rtpath_name)
    rtpath_name = cleaner.remove_episode(rtpath_name, media.path.is_dir())
    rtpath_name = rtpath_name.strip('!')

    logger.info(f'[标签移除] 去除标签后: {rtpath_name}, 年份识别为： {year}')

    media.rtpath_name = rtpath_name
    media.year = year
    media.season = season_id
    return rtpath_name, year, season_id

# 识别文件夹储存的是电影还是剧集, 建议传入最低级文件夹（即只包含单季度的）
# 重构于 _process 中 step1.5 部分


def analyse_path_type(media: MediaInfo):
    '''
    调用 rtpath_name, year
    修改 name, info, is_movie
    返回 "tv_show", "movie" 或 None
    尝试借助api进行搜索
    返回可能的作品类型和名称
    '''
    logger.info(f'[识别类型] 未传入任务类型，开始判断 {media.path.name} 是否为电影！')
    logger.info(f'[搜索剧集] 开始搜索 {media.rtpath_name} ({media.year})')

    tv_name, tv_info = search.get_tv_info(media.rtpath_name, media.year)
    if not tv_name and media.year != 0:
        tv_name, tv_info = search.get_tv_info(media.rtpath_name, 0)
        logger.info('[搜索剧集] 未搜索到结果, 删除year后重试')
    logger.info(f'[搜索剧集] 搜索到的电视剧名称: {tv_name}')

    logger.info(f'[搜索电影] 开始搜索 {media.rtpath_name} ({media.year})')
    mv_name, mv_info = search.get_movie_info(media.rtpath_name, media.year)
    if not mv_name and media.year != 0:
        mv_name, mv_info = search.get_movie_info(media.rtpath_name, 0)
        logger.info('[搜索电影] 未搜索到结果, 删除year后重试')
    logger.info(f'[搜索电影] 搜索到的电影名称: {mv_name}')

    if not tv_name and not mv_name:
        logger.warning(f'[识别类型] 未搜索到 {media.path.name} 相关的任何结果！')
        return None

    # 根据搜索结果和文件结构进行猜测
    rate = 0
    if tv_name:
        rate += 1
    if mv_name:
        rate -= 1

    if media.path.is_file():
        rate -= 0.4
    else:
        path_video_num = 0
        for i in media.path.iterdir():
            if i.is_file() and i.suffix.lower() in utils.VIDEO_SUFFIX:
                path_video_num += 1
        if path_video_num > 4:
            rate += 0.4
        else:
            rate -= 0.4

    season_id = cleaner.extract_season(media.rtpath_name)
    if season_id == -1:
        rate -= 0.4
    else:
        rate += 0.6

    if media.is_movie is None:
        if rate < 0:
            logger.info(f'[识别类型] {media.path.name} 可能为电影！')
            media.name = mv_name
            media.info = mv_info
            media.is_movie = True
            return 'movie'
        else:
            logger.info(f'[识别类型] {media.path.name} 可能为电视剧！')
            media.name = tv_name
            media.info = tv_info
            media.is_movie = False
            return 'tv_show'
    else:
        if media.is_movie:
            logger.info(f'[识别类型] {media.path.name} 钦定为电影！')
            media.name = mv_name
            media.info = mv_info
            media.is_movie = True
            return 'movie'
        else:
            logger.info(f'[识别类型] {media.path.name} 钦定为电视剧！')
            media.name = tv_name
            media.info = tv_info
            media.is_movie = False
            return 'tv_show'

# 获取完整信息


def get_full_info(media: MediaInfo):
    '''
    此时只有路径
    会尽可能详细的填充信息
    '''
    ######################### [Step.1] 找信息 #########################

    # 先移除无用的标签, 方便之后搜索
    # rtpath_name, year, season_id is returned.
    analyse_path_name(media)
    path_type = analyse_path_type(media)
    if path_type == 'tv_show':
        if media.season is None:
            tid = cleaner.extract_season(media.rtpath_name)
            if tid != -1:
                media.season = tid
        if media.season is None:
            get_season_id(media)
    # 判断类型是否为电影并获取搜索结果
    elif path_type is None:
        logger.warning(f'[获取信息] 未搜索到相关信息, 跳过 {media.rtpath_name}')
        return None
    return path_type
