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

        _s = "width: 60%; flex-wrap: nowrap; max-height: 80vh; overflow-y: auto;"
        with self, ui.card().style(_s).classes("flex"):
            ui.label("配置").style("font-size: 20px; font-weight: bold")
            ui.separator()

            # 基础配置
            ui.label("基础配置").style(
                "font-size: 16px; font-weight: bold; margin-top: 10px;"
            )
            basic_configs = [
                "api_key",
                "bangumi_path",
                "movie_path",
                "anime_path",
                "anime_movie_path",
                "mode",
                "docker_mnt",
            ]
            for cn in basic_configs:
                self._create_config_row(cn)

            ui.separator().style("margin: 20px 0;")

            # AI配置
            ui.label("AI识别配置").style(
                "font-size: 16px; font-weight: bold; margin-top: 10px;"
            )
            ai_configs = [
                "ai_enabled",
                "OPENAI_JSON_MODE",
                "ai_api_key",
                "ai_base_url",
                "ai_model",
                "ai_confidence_threshold",
            ]
            for cn in ai_configs:
                self._create_config_row(cn)

            ui.separator()

            with ui.row(wrap=False).classes("w-full justify-end"):
                RedButton("取消", on_click=self.close).props("outline")
                RedButton("确认修改", on_click=self._handle_ok)

    def _create_config_row(self, cn: str):
        with ui.column(wrap=False).classes("flex no-wrap w-full"):
            with ui.row(wrap=False).classes("flex justify-space-between w-full"):
                with ui.row(wrap=False, align_items="baseline") as row:
                    row.classes("flex w-full")
                    # 配置标签
                    label = CN_MAP.get(cn, cn)
                    ui.label(label).style("min-width: 150px")

                    if cn == "mode":
                        tg = RedToogle(
                            ["链接", "复制", "剪切"],
                            value=cm.get_config(cn),
                            on_change=lambda e, c=cn: self._change(c, e.value),
                        )
                        tg.style("font-size: 10px")
                        tg.classes("flex no-wrap w-full")
                    elif cn == "ai_enabled" or cn == "OPENAI_JSON_MODE":
                        tg = RedToogle(
                            ["启用", "禁用"],
                            value="启用" if cm.get_config(cn) else "禁用",
                            on_change=lambda e, c=cn: self._change(
                                c, e.value == "启用"
                            ),
                        )
                        tg.style("font-size: 10px")
                        tg.classes("flex no-wrap w-full")
                    elif cn == "ai_confidence_threshold":
                        tg = RedToogle(
                            ["High", "Medium", "Low"],
                            value=cm.get_config(cn),
                            on_change=lambda e, c=cn: self._change(c, e.value),
                        )
                        tg.style("font-size: 10px")
                        tg.classes("flex no-wrap w-full")
                    else:
                        ui.input(
                            value=cm.get_config(cn),
                            on_change=lambda e, c=cn: self._change(c, e.value),
                        ).props("filled").props("dense").style(
                            "flex-grow: 2"
                        ).bind_value(
                            self.config, cn
                        )

                    if cn.endswith("path"):
                        RedButton(
                            "选择",
                            on_click=lambda e, c=cn: self.pick(key=c),
                        ).style("min-width: 60px")
                    else:
                        ui.label("").style("min-width: 60px")

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
