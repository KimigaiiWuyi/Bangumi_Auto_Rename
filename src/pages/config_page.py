from typing import Sequence
from types import SimpleNamespace

from nicegui import ui

from ..logger import logger
from ..config.config_manager import CN_MAP, cm
from ..element.red import RedButton, RedToogle
from ..component.local_file_picker import local_file_picker


class ConfigPage(ui.dialog):

    def __init__(self) -> None:
        super().__init__()
        self.config = SimpleNamespace(**cm.config)

        _s = 'width: 40%; flex-wrap: nowrap;'
        with self, ui.card().style(_s).classes('flex'):
            ui.label('配置').style('font-size: 20px; font-weight: bold')
            ui.separator()
            for cn in cm.config:
                with ui.column(wrap=False).classes('flex no-wrap w-full'):
                    with ui.row(wrap=False).classes(
                        'flex justify-space-between w-full'
                    ):
                        with ui.row(wrap=False, align_items='baseline') as row:
                            row.classes('flex w-full')
                            # 配置标签
                            label = CN_MAP.get(cn, cn)
                            ui.label(label).style('min-width: 120px')
                            if cn == 'mode':
                                tg = RedToogle(
                                    ['链接', '复制', '剪切'],
                                    value=cm.get_config(cn),
                                    on_change=lambda e, c=cn: self._change(
                                        c,
                                        e.value,
                                    ),
                                )
                                tg.style('font-size: 10px')
                                tg.classes('flex no-wrap w-full')
                            elif cn == 'server_type':
                                tg = RedToogle(
                                    ['emby', 'jellyfin'],
                                    value=cm.get_config(cn),
                                    on_change=lambda e, c=cn: self._change(
                                        c,
                                        e.value,
                                    ),
                                )
                                tg.style('font-size: 10px')
                                tg.classes('flex no-wrap w-full')
                            else:
                                ui.input(
                                    value=cm.get_config(cn),
                                    on_change=lambda e, c=cn: self._change(
                                        c,
                                        e.value,
                                    ),
                                ).props('filled').props('dense').style(
                                    'flex-grow: 2'
                                ).bind_value(
                                    self.config,
                                    cn,
                                )

                            if cn.endswith('path'):
                                RedButton(
                                    '选择',
                                    on_click=lambda e, c=cn: self.pick(key=c),
                                ).style('min-width: 60px')
                            else:
                                ui.label('').style('min-width: 60px')

            ui.separator()

            with ui.row(wrap=False).classes('w-full justify-end'):
                RedButton('取消', on_click=self.close).props('outline')
                RedButton('确认修改', on_click=self._handle_ok)

    async def pick(self, *, key: str) -> None:
        result = await local_file_picker('~', multiple=True)
        if isinstance(result, Sequence):
            result = result[0]
        logger.info(f'[配置] {key} 选择了 {result}')
        self._change(key, result)

    def _change(self, key: str, value: str) -> None:
        setattr(self.config, key, value)

    def _handle_ok(self):
        for cn in self.config.__dict__:
            cm.set_config(
                cn,
                getattr(self.config, cn),
            )
        logger.info('[配置] 配置已修改为： {}'.format(cm.config))
        self.close()


async def config_page() -> None:
    await ConfigPage()
