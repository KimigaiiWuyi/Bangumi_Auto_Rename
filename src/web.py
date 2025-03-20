from typing import cast
from pathlib import Path

from fastapi import Request
from nicegui import ui, app

from .logger import logger
from .models import TaskModel
from .main_page import main_page
from .rename.process import Rename
from .utils.utils import no_scroll_bar
from .pages.data_table_page import create_table

ANI_TAG = ['动漫', 'anime', '动画']
MOVIE_TAG = ['电影', 'movie', '剧场', '剧场版']


@ui.page('/')
def main():
    ui.add_head_html(no_scroll_bar)
    main_page()


@app.post('/sendTask')
async def _send_task(request: Request):
    data: TaskModel = cast(TaskModel, dict(await request.form()))
    logger.info(f'[收到任务] {data}')
    path = data.get('path').encode('latin1').decode('utf-8')
    is_anime = data.get('is_anime', '')
    no_process = data.get('no_process', '')
    tag = data.get('tag', '')

    tag_list = [str(i).strip().lower() for i in tag.split(',')]

    if 'no_process' in tag_list:
        no_process = True
    # 处理anime相关tag
    if 'anime' in tag_list:
        is_anime = True
    elif 'non-anime' in tag_list:
        is_anime = False
    else:
        if not is_anime:
            for i in ANI_TAG:
                if i in tag_list:
                    is_anime = True
                    break
            else:
                is_anime = False
        else:
            is_anime = None
    # 处理movie相关tag
    is_movie = None
    if 'movie' in tag_list:
        is_movie = True
    elif 'tvshow' in tag_list:
        is_movie = False
    else:
        for i in MOVIE_TAG:
            if i in tag_list:
                is_movie = True
                break

    if not path:
        logger.error('[结束任务] 路径为空！')
        return {'code': 400, 'data': '路径为空！'}

    if no_process:
        logger.info(f'[结束任务] {path}忽略, 不处理！')
        return {'code': 202, 'data': f'{path}忽略, 不处理！'}

    _path = Path(path)
    if not _path.exists():
        logger.error(f'[结束任务] 路径{path}不存在！')
        return {'code': 404, 'data': f'路径{path}不存在！'}


    Rename().process(_path, is_anime, is_movie)
    create_table.refresh()

    logger.info(f'[结束任务] {path}处理完成！')
    return {'code': 200, 'data': '提交任务成功, 具体信息可以查看WebUI！'}
