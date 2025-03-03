import re

from pathlib import Path
from difflib import SequenceMatcher
from typing import Dict, List, Optional


from . import cleaner
from .utils import (
    S0_TAG,
    PATTERN,
    EXTRA_TAG,
    MediaInfo,
)
from ..logger import logger


def match_special(name):
    for s0 in S0_TAG:  # 寻找 Season00
        if s0 == r'\.5':  # 防止5作为后缀开头
            res = re.search(
                rf'(?<!{PATTERN})\d{{1,2}}{s0}(?![a-zA-Z0-9])',
                name,
                re.IGNORECASE,
            )
        elif s0 == '00':  # 防止00出现在奇怪的地方
            res = re.search(r'\b00\b', name)
        else:
            res = re.search(
                rf'(?<!{PATTERN}){s0}([\d]{{0,3}})(?!{PATTERN})',
                name,
                re.IGNORECASE,
            )

        if res:
            return True
    return False


def match_extra(name):
    for ex in EXTRA_TAG:
        res = re.search(
            rf'(?<!{PATTERN}){ex}(?!{PATTERN})',
            name,
            re.IGNORECASE,
        )
        if res:
            return True
    return False

def get_season_id(
    media: MediaInfo,
):
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

            #if titles:
            #    # 或者计算相似度
            #    for title in titles:
            #        similaritys = {}
            #        if title['type'] in [
            #            'Default',
            #            'Synonym',
            #            'English',
            #            'French',
            #        ]:
            #            ename = title['title']
            #            path_name = path_name.replace(ename, '')
            #            similarity = SequenceMatcher(
            #                None,
            #                sname,
            #                cleaner.remove_tag(path_name),
            #            ).ratio()

            #            # logger.debug(f'相似度{tindex}：{similarity}')
            #            similaritys[similarity] = season_id
            #        all_similaritys.append(similaritys)
    else:
        if all_similaritys:
            logger.info(f'[处理任务] 相似度：{all_similaritys}')
            season_id = cleaner.to_sim_max(all_similaritys)

    logger.info(f'[处理任务] 识别季号：{season_id}')
    media.season = season_id
    return season_id