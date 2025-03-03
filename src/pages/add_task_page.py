from pathlib import Path
from typing import Optional, Sequence

from nicegui import ui, run

from ..logger import logger
from ..rename.process import Rename
from ..pages.data_table_page import create_table
from ..element.red import RedButton, RedToogle, notify
from ..component.local_file_picker import local_file_picker


class choose_is_anime(ui.dialog):
    def __init__(
        self,
    ) -> None:
        super().__init__()
        self.is_anime = True

        _s = 'width: 40%; flex-wrap: nowrap;'
        with self, ui.card().style(_s).classes('flex'):
            ui.label('任务配置').style('font-size: 20px; font-weight: bold')
            ui.separator()
            with ui.column(wrap=False).classes('flex no-wrap w-full'):
                with ui.row(wrap=False) as row1:
                    row1.classes('flex justify-space-between w-full')
                    with ui.row(wrap=False, align_items='baseline') as row:
                        row.classes('flex w-full')
                        # 配置标签
                        label = '是否为动画类型'
                        ui.label(label).style('min-width: 120px')
                        tg = RedToogle(
                            ['是', '否'],
                            value='是',
                            on_change=lambda e: self._change(
                                e.value,
                            ),
                        )
                        tg.style('font-size: 10px')
                        tg.classes('flex no-wrap w-full')

            ui.separator()

            with ui.row(wrap=False).classes('w-full justify-end'):
                RedButton('取消', on_click=self.close).props('outline')
                RedButton('确认提交', on_click=self._handle_ok)

    def _change(self, value: str) -> None:
        self.is_anime = True if value == '是' else False

    def _handle_ok(self) -> None:
        self.close()
        self.submit(self.is_anime)


async def pick_file() -> None:
    result: Optional[Sequence[str]] = await local_file_picker(
        '~',
        multiple=True,
    )
    if result is None:
        return notify('取消添加任务！')
    is_anime: bool = await choose_is_anime()

    for p in result:
        logger.info(f'[开始任务] 选择了 {result}')
        data = await run.io_bound(
            Rename().process,
            Path(p),
            is_anime,
        )
        create_table.refresh()
        if isinstance(data, str):
            notify(data)
        else:
            notify(f'开始任务 {result}！')
