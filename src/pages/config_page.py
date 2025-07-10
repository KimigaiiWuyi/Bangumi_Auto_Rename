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
                "ai_provider",
                "ai_confidence_threshold",
                "openai_output_format",  # OpenAI输出格式选择
                "ai_api_key",
                "ai_base_url",
                "ai_model",
                "gemini_api_key",
                "gemini_base_url",
                "gemini_model",
            ]
            for cn in ai_configs:
                self._create_config_row(cn)

            # AI API测试功能
            with ui.row(wrap=False).classes("w-full justify-center mt-4"):
                RedButton("🧪 测试OpenAI API功能", on_click=self._test_openai_api).props("outline")

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
                    elif cn == "ai_enabled":
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
                    elif cn == "ai_provider":
                        tg = RedToogle(
                            ["openai", "gemini"],
                            value=cm.get_config(cn) or "openai",
                            on_change=lambda e, c=cn: self._change(c, e.value),
                        )
                        tg.style("font-size: 10px")
                        tg.classes("flex no-wrap w-full")
                    elif cn == "openai_output_format":
                        tg = RedToogle(
                            ["function_calling", "json_object", "structured_output", "text"],
                            value=cm.get_config(cn) or "function_calling",
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
        # 验证URL配置项
        url_configs = ["ai_base_url", "gemini_base_url"]
        for url_config in url_configs:
            if hasattr(self.config, url_config):
                url_value = getattr(self.config, url_config)
                if url_value and not cm.validate_url(url_value):
                    ui.notify(f"❌ {CN_MAP.get(url_config, url_config)} 格式无效", type="negative")
                    return

        # 保存所有配置
        for cn in self.config.__dict__:
            cm.set_config(
                cn,
                getattr(self.config, cn),
            )
        logger.info('[配置] 配置已修改为： {}'.format(cm.config))
        ui.notify("✅ 配置保存成功", type="positive")
        self.close()

    def _test_openai_api(self):
        """测试OpenAI API功能支持情况"""
        try:
            # 获取当前配置
            api_key = getattr(self.config, "ai_api_key", "") or cm.get_config("ai_api_key")
            base_url = getattr(self.config, "ai_base_url", "") or cm.get_config("ai_base_url")
            model = getattr(self.config, "ai_model", "") or cm.get_config("ai_model")

            if not api_key:
                ui.notify("❌ 请先配置OpenAI API密钥", type="negative")
                return

            # 显示测试开始通知
            ui.notify("🧪 开始测试API功能，请稍候...", type="info")

            # 导入OpenAI客户端进行测试
            from ..ai.openai_client import OpenAIClient

            # 创建临时客户端实例进行测试
            temp_client = OpenAIClient()
            temp_client.api_key = api_key
            temp_client.base_url = base_url
            temp_client.model = model
            temp_client.enabled = True

            # 重新初始化客户端
            from openai import OpenAI
            temp_client.client = OpenAI(api_key=api_key, base_url=base_url)

            # 执行测试
            results = temp_client.test_api_capabilities()

            # 显示测试结果
            self._show_test_results(results)

        except Exception as e:
            logger.error(f"[配置] API测试失败: {str(e)}")
            ui.notify(f"❌ API测试失败: {str(e)}", type="negative")

    def _show_test_results(self, results: dict):
        """显示API测试结果"""
        # 创建结果对话框
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("🧪 OpenAI API功能测试结果").classes("text-h6 mb-4")

            # 显示各项功能支持情况
            with ui.column().classes("w-full gap-2"):
                # JSON Mode
                json_icon = "✅" if results.get("json_mode_supported", False) else "❌"
                ui.label(f"{json_icon} JSON Mode: {'支持' if results.get('json_mode_supported', False) else '不支持'}")

                # Structured Output
                struct_icon = "✅" if results.get("structured_output_supported", False) else "❌"
                ui.label(f"{struct_icon} Structured Output: {'支持' if results.get('structured_output_supported', False) else '不支持'}")

                # Function Calling
                func_icon = "✅" if results.get("function_calling_supported", False) else "❌"
                ui.label(f"{func_icon} Function Calling: {'支持' if results.get('function_calling_supported', False) else '不支持'}")

                # 推荐配置
                ui.separator()
                ui.label("💡 推荐配置:").classes("font-bold")
                if results.get("function_calling_supported", False):
                    ui.label("建议使用 Function Calling 模式（最稳定）").classes("text-green")
                elif results.get("structured_output_supported", False):
                    ui.label("建议使用 Structured Output 模式").classes("text-blue")
                elif results.get("json_mode_supported", False):
                    ui.label("建议使用 JSON Object 模式").classes("text-orange")
                else:
                    ui.label("建议使用 Text 模式（需要手动解析JSON）").classes("text-red")

                # 显示错误信息（如果有）
                if results.get("errors"):
                    ui.separator()
                    ui.label("⚠️ 错误详情:").classes("font-bold text-red")
                    for error in results.get("errors", []):
                        ui.label(f"• {error}").classes("text-sm text-red")

            # 关闭按钮
            with ui.row().classes("w-full justify-end mt-4"):
                RedButton("关闭", on_click=dialog.close)

        dialog.open()


async def config_page() -> None:
    await ConfigPage()
