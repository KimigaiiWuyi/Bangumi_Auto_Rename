from pathlib import Path
from typing import Optional
from types import SimpleNamespace

from nicegui import ui

from ..logger import logger
from ..rename.process import Rename
from ..utils.utils import get_task, write_task
from ..element.red import RedButton, RedToogle, notify

TASK_MAP = {
    'is_anime': '是否为动画',
    'name': '剧集名称',
    'season_id': '季度',
    'is_movie': '是否为电影',
}


#def value_to_text(value: Optional[bool]) -> str:
#    if value is None:
#        return '自动'
#    elif value:
#        return '是'
#    else:
#        return '否'


#def text_to_value(text: str) -> Optional[bool]:
#    if text == '是':
#        return True
#    elif text == '否':
#        return False
#    elif text == '自动':
#        return None
#    else:
#        return None

#懒得具体修他那里炸了...直接大力出奇迹吧 
def x2text(x):
    if x is None:
        return '自动'
    elif x == '是':
        return '是'
    elif x == '否':
        return '否'
    elif x == True:
        return '是'
    elif x == False:
        return '否'
    logger.warn(f'edit_page.py x2text错误:{x}')
def x2bool(x):
    if x is None:
        return None
    elif x == '是':
        return True
    elif x == '否':
        return False
    elif x == True:
        return True
    elif x == False:
        return False
    logger.warn(f'edit_page.py x2bool错误:{x}')


class EditPage(ui.dialog):

    def __init__(self, uuid: str) -> None:
        super().__init__()
        self.uuid = uuid

        _s = 'width: 40%; flex-wrap: nowrap;'
        task_data = get_task(uuid)
        if task_data is None:
            notify('任务数据不存在！')
            return

        self.data = SimpleNamespace(**task_data)
        with self, ui.card().style(_s).classes('flex'):
            ui.label('编辑').style('font-size: 20px; font-weight: bold')
            ui.separator()
            for key in task_data:
                if key not in ['is_anime', 'name', 'season_id', 'is_movie']:
                    continue
                with ui.column(wrap=False).classes('flex no-wrap w-full'):
                    with ui.row(wrap=False).classes(
                        'flex justify-space-between w-full'
                    ):
                        with ui.row(wrap=False, align_items='baseline') as row:
                            row.classes('flex w-full')
                            # 配置标签
                            label = TASK_MAP.get(key, key)
                            ui.label(label).style('min-width: 120px')
                            if key != 'is_anime' and key != 'is_movie':
                                ui.input(
                                    value=getattr(self.data, key),
                                    on_change=lambda e, c=key: self._change(
                                        c,
                                        e.value,
                                    ),
                                ).props('filled').props('dense').style(
                                    'flex-grow: 2'
                                ).bind_value(
                                    self.data,
                                    key,
                                )
                            else:
                                value = getattr(self.data, key)

                                tg = RedToogle(
                                    ['是', '否', '自动'],
                                    value=x2text(value),
                                    on_change=lambda e, c=key: self._change(
                                        c,
                                        e.value,
                                    ),
                                )
                                tg.style('font-size: 10px')
                                tg.classes('flex no-wrap w-full')

            ui.separator()

            with ui.row(wrap=False).classes('w-full justify-end'):
                RedButton('取消', on_click=self.close).props('outline')
                RedButton('确认修改并重新任务', on_click=self._handle_ok)

    def _change(self, key: str, value: str) -> None:
        setattr(self.data, key, value)

    def _handle_ok(self):
        write_task(self.uuid, self.data.__dict__)
        logger.info(f'[任务] 任务{self.uuid}已修改为： {self.data.__dict__}')
        notify('修改成功！重新开始识别！')
        self.close()
        Rename().process(
            Path(getattr(self.data, 'path')),
            #text_to_value(getattr(self.data, 'is_anime')),
            #text_to_value(getattr(self.data, 'is_movie')),
            x2bool(getattr(self.data, 'is_anime')),
            x2bool(getattr(self.data, 'is_movie')),
            getattr(self.data, 'uuid'),
            getattr(self.data, 'name'),
            getattr(self.data, 'season_id'),
        )


async def edit_page(uuid: str) -> None:
    await EditPage(uuid)
