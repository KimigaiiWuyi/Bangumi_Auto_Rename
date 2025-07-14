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
    'use_ai': '使用AI识别',
}


def value_to_text(value: Optional[bool]) -> str:
    if value is None:
        return '自动'
    elif value:
        return '是'
    else:
        return '否'


def text_to_value(text: str) -> Optional[bool]:
    if text == '是':
        return True
    elif text == '否':
        return False
    elif text == '自动':
        return None
    else:
        return None


class EditPage(ui.dialog):

    def __init__(self, uuid: str) -> None:
        super().__init__()
        self.uuid = uuid

        _s = 'width: 50%; flex-wrap: nowrap; max-height: 80vh; overflow-y: auto;'
        task_data = get_task(uuid)
        if task_data is None:
            return notify('任务数据不存在！')

        # 添加use_ai字段的默认值
        if 'use_ai' not in task_data:
            task_data['use_ai'] = True

        self.data = SimpleNamespace(**task_data)
        with self, ui.card().style(_s).classes('flex'):
            ui.label('编辑任务').style('font-size: 20px; font-weight: bold')
            ui.separator()

            # 基本信息
            ui.label('基本信息').style(
                'font-size: 16px; font-weight: bold; margin-top: 10px;'
            )
            basic_fields = ['is_anime', 'name', 'season_id', 'is_movie']
            for key in basic_fields:
                if key in task_data:
                    self._create_field_row(key, task_data[key])

            ui.separator().style('margin: 20px 0;')

            # AI设置
            ui.label('AI设置').style(
                'font-size: 16px; font-weight: bold; margin-top: 10px;'
            )
            self._create_field_row('use_ai', task_data.get('use_ai', True))

            ui.separator()

            with ui.row(wrap=False).classes('w-full justify-end'):
                RedButton('取消', on_click=self.close).props('outline')
                RedButton('确认修改并重新处理', on_click=self._handle_ok)

    def _create_field_row(self, key: str, value):
        with ui.column(wrap=False).classes('flex no-wrap w-full'):
            with ui.row(wrap=False).classes('flex justify-space-between w-full'):
                with ui.row(wrap=False, align_items='baseline') as row:
                    row.classes('flex w-full')
                    # 配置标签
                    label = TASK_MAP.get(key, key)
                    ui.label(label).style('min-width: 120px')

                    if key in ['is_anime', 'is_movie']:
                        tg = RedToogle(
                            ['是', '否', '自动'],
                            value=value_to_text(value),
                            on_change=lambda e, c=key: self._change(c, e.value),
                        )
                        tg.style('font-size: 10px')
                        tg.classes('flex no-wrap w-full')
                    elif key == 'use_ai':
                        tg = RedToogle(
                            ['启用', '禁用'],
                            value='启用' if value else '禁用',
                            on_change=lambda e, c=key: self._change(
                                c, e.value == '启用'
                            ),
                        )
                        tg.style('font-size: 10px')
                        tg.classes('flex no-wrap w-full')
                    else:
                        ui.input(
                            value=getattr(self.data, key),
                            on_change=lambda e, c=key: self._change(c, e.value),
                        ).props('filled').props('dense').style(
                            'flex-grow: 2'
                        ).bind_value(
                            self.data, key
                        )

    def _change(self, key: str, value) -> None:
        setattr(self.data, key, value)

    def _handle_ok(self):
        write_task(self.uuid, self.data.__dict__)
        logger.info(f'[任务] 任务{self.uuid}已修改为： {self.data.__dict__}')
        notify('修改成功！重新开始识别！')
        self.close()

        # 根据use_ai设置决定是否使用AI
        use_ai = getattr(self.data, 'use_ai', True)
        if not use_ai:
            # 临时禁用AI
            from ..config.config_manager import cm

            original_ai_enabled = cm.get_config('ai_enabled')
            cm.set_config('ai_enabled', False)

        try:
            Rename().process(
                Path(getattr(self.data, 'path')),
                text_to_value(getattr(self.data, 'is_anime')),
                text_to_value(getattr(self.data, 'is_movie')),
                getattr(self.data, 'uuid'),
                getattr(self.data, 'name'),
                getattr(self.data, 'season_id'),
            )
        finally:
            if not use_ai:
                # 恢复AI设置
                cm.set_config('ai_enabled', original_ai_enabled)


async def edit_page(uuid: str) -> None:
    await EditPage(uuid)
