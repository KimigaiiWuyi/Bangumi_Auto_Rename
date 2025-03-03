import re
import difflib

from time import sleep

import tmdbsimple as tmdb

from ..logger import logger
from ..config.config_manager import cm
from .cleaner import is_chinese_percentage_sufficient


class Search:
    def __init__(self) -> None:
        self.TMDB_KEY = cm.get_config('api_key')
        tmdb.API_KEY = self.TMDB_KEY

    def get_movie_info(
        self,
        query: str,
        year: int,
    ):
        for i in range(3):
            try:
                search = tmdb.Search()
                search.movie(
                    query=query,
                    language='zh-CN',
                    year=year if year != 0 else None,
                )
                #if search.results:
                #    name_list = [i['title'] for i in search.results]
                #    best_match = difflib.get_close_matches(query,name_list,1)
                #    if len(best_match) == 0:
                #        continue
                #    for i in search.results:
                #        if i['title'] == best_match[0]:
                #            target = i
                target_list = search.__dict__['results']
                if target_list:
                    target = target_list[0]
                    name = target['title']
                    movie = tmdb.Movies(target['id'])
                    movie.info()
                    logger.debug(str(movie.__dict__))
                    return name, movie.__dict__
                return '', None
            except:  # noqa:E722, B001
                sleep(5)
                logger.warning(f'[电影搜索] 网络错误, 重试第{i + 1}次中...')
        return '', None

    def get_tv_info(
        self,
        query: str,
        year: int,
    ):
        for i in range(3):
            try:
                for _ in range(3):
                    search = tmdb.Search()
                    search.tv(
                        query=query,
                        language='zh-CN',
                        first_air_date_year=year if year != 0 else None,
                    )
                    #if search.results:
                    #    # tmdb好像并非精确匹配，如搜索命运石之门，首个匹配结果会是命运石之门0.
                    #    # 尝试加入当未指定年份时，在搜索结果中取匹配率最高的结果
                    #    name_list = [i['name'] for i in search.results]
                    #    best_match = difflib.get_close_matches(query,name_list,1)
                    #    if len(best_match) == 0:
                    #        continue
                    #    for i in search.results:
                    #        if i['name'] == best_match[0]:
                    #            target = i
                    target_list = search.__dict__['results']
                    if target_list:
                        for i in target_list:
                            if i['name'] == query:
                                target = i
                                break
                        else:
                            target = target_list[0]
                        name = target['name']
                        tv = tmdb.TV(target['id'])
                        tv.info()
                        logger.debug(str(tv.__dict__))
                        return name, tv.__dict__
                    else:
                        if is_chinese_percentage_sufficient(query):
                            query = re.sub(r'[a-zA-Z]', '', query)
                return '', None
            except:  # noqa:E722, B001
                sleep(5)
                logger.warning(f'[电视剧搜索] 网络错误, 重试第{i + 1}次中...')
        return '', None
