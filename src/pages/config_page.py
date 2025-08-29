from typing import Sequence
from types import SimpleNamespace

from nicegui import ui

from ..logger import logger, update_log_level_from_config
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
                "log_level",
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
                "ai_auto_save",
                "ai_provider",
                "ai_confidence_threshold",
                "openai_output_format",  # OpenAI输出格式选择
                "ai_api_key",
                "ai_base_url",
                "ai_model",
                "ai_temperature",
                "gemini_api_key",
                "gemini_base_url",
                "gemini_model",
                "gemini_temperature",
            ]
            for cn in ai_configs:
                self._create_config_row(cn)

            # AI功能测试按钮
            with ui.row(wrap=False).classes("w-full justify-center mt-4 gap-2"):
                RedButton(
                    "🧪 测试AI识别功能", on_click=self._test_ai_recognition
                ).props("outline")
                RedButton("⚙️ 测试OpenAI API功能", on_click=self._test_openai_api).props(
                    "outline"
                )

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
                    elif cn == "log_level":
                        tg = RedToogle(
                            ["DEBUG", "INFO", "WARNING", "ERROR"],
                            value=cm.get_config(cn),
                            on_change=lambda e, c=cn: self._change(c, e.value),
                        )
                        tg.style("font-size: 10px")
                        tg.classes("flex no-wrap w-full")
                    elif cn == "ai_auto_save":
                        tg = RedToogle(
                            ["启用", "禁用"],
                            value="启用" if cm.get_config(cn) else "禁用",
                            on_change=lambda e, c=cn: self._change(
                                c, e.value == "启用"
                            ),
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
                            [
                                "function_calling",
                                "json_object",
                                "structured_output",
                                "text",
                            ],
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
                    ui.notify(
                        f"❌ {CN_MAP.get(url_config, url_config)} 格式无效",
                        type="negative",
                    )
                    return

        # 保存所有配置
        for cn in self.config.__dict__:
            cm.set_config(
                cn,
                getattr(self.config, cn),
            )
        config_show = cm.config.copy()
        for key in config_show.keys():
            if "api_key" in key:
                config_show[key] = len(str(config_show[key])) * "*"

        logger.info('[配置] 配置已修改为： {}'.format(config_show))
        ui.notify("✅ 配置保存成功", type="positive")
        # 更新运行时日志级别
        try:
            update_log_level_from_config()
            logger.info(f"[配置] 运行时日志级别已更新为 {cm.get_config('log_level')}")
        except Exception as e:
            logger.error(f"[配置] 更新运行时日志级别失败: {e}")
        self.close()

    def _get_current_ui_config(self) -> dict:
        """获取当前界面的配置（未保存的）"""
        current_config = {}
        ai_config_keys = [
            "ai_enabled",
            "ai_auto_save",
            "ai_provider",
            "ai_confidence_threshold",
            "openai_output_format",
            "ai_api_key",
            "ai_base_url",
            "ai_model",
            "gemini_api_key",
            "gemini_base_url",
            "gemini_model",
            "ai_temperature",
            "gemini_temperature",
        ]
        for key in ai_config_keys:
            # 优先使用界面中的值，如果没有则使用配置文件中的值
            if hasattr(self.config, key):
                current_config[key] = getattr(self.config, key)
            else:
                current_config[key] = cm.get_config(key)
        return current_config

    async def _test_ai_recognition(self):
        """测试AI识别功能（使用当前界面配置）"""
        try:
            ui.notify("🧪 开始测试AI识别功能，请稍候...", type="info")
            current_config = self._get_current_ui_config()

            from ..ai.unified_ai_tester import UnifiedAITester

            tester = UnifiedAITester(current_config)

            import asyncio

            result = await asyncio.get_event_loop().run_in_executor(
                None, tester.test_ai_recognition
            )

            self._show_ai_test_results(result)
        except Exception as e:
            logger.error(f"[配置] AI识别测试失败: {str(e)}")
            ui.notify(f"❌ AI识别测试失败: {str(e)}", type="negative")

    async def _test_openai_api(self):
        """测试OpenAI API功能（使用当前界面配置，测试多种输出格式）"""
        try:
            ui.notify("⚙️ 开始测试OpenAI API功能，请稍候...", type="info")
            current_config = self._get_current_ui_config()

            # 检查基本配置
            if not current_config.get("ai_api_key"):
                ui.notify("❌ 请先配置OpenAI API密钥", type="negative")
                return

            if current_config.get("ai_provider", "openai").lower() != "openai":
                ui.notify("❌ 此测试仅支持OpenAI提供商", type="negative")
                return

            from ..ai.unified_ai_tester import UnifiedAITester

            tester = UnifiedAITester(current_config)

            import asyncio

            results = await asyncio.get_event_loop().run_in_executor(
                None, tester.test_openai_api_formats
            )

            self._show_openai_formats_test_results(results)
        except Exception as e:
            logger.error(f"[配置] OpenAI API测试失败: {str(e)}")
            ui.notify(f"❌ OpenAI API测试失败: {str(e)}", type="negative")

    def _show_ai_test_results(self, result: dict):
        """显示AI识别测试结果"""
        with ui.dialog() as dialog, ui.card().classes("w-[600px]"):
            ui.label("🧪 AI识别功能测试结果").classes("text-h6 mb-4")

            # 配置提示
            ui.label("💡 此测试使用界面中的配置，但不会保存配置").classes(
                "text-sm text-blue mb-4"
            )

            with ui.column().classes("w-full gap-3"):
                # 基本信息 - 根据结果状态显示
                result_status = result.get("result_status", "unknown")

                if result_status == "perfect":
                    status_icon = "✅"
                    status_text = "完全正确"
                    status_color = "text-green"
                elif result_status == "validation_failed":
                    status_icon = "⚠️"
                    status_text = "验证失败"
                    status_color = "text-orange"
                elif result_status == "ai_failed":
                    status_icon = "❌"
                    status_text = "AI失败"
                    status_color = "text-red"
                else:
                    status_icon = "❓"
                    status_text = "未知状态"
                    status_color = "text-gray"

                ui.label(f"{status_icon} 测试状态: {status_text}").classes(
                    f"font-bold {status_color}"
                )

                # 配置信息
                config_used = result.get("config_used", {})
                provider = config_used.get("ai_provider", "unknown")
                ui.label(f"🤖 AI提供商: {provider.upper()}")
                ui.label(f"⏱️ 耗时: {result.get('duration', 0):.2f}秒")

                if provider.lower() == "openai":
                    output_format = config_used.get("openai_output_format", "unknown")
                    ui.label(f"📋 输出格式: {output_format}")

                # AI失败情况：显示错误信息
                if result_status == "ai_failed":
                    ui.separator()
                    ui.label("❌ 错误详情").classes("font-bold text-red")
                    if result.get("error"):
                        ui.label(f"错误信息: {result['error']}").classes("text-red")
                    else:
                        ui.label("AI分析返回None，可能是API调用失败或解析错误").classes(
                            "text-red"
                        )

                # 验证失败和完全正确情况：显示详细结果
                elif result_status in ["validation_failed", "perfect"] and result.get(
                    "validation"
                ):
                    validation = result["validation"]
                    ui.separator()
                    ui.label("📊 分析结果").classes("font-bold")

                    confidence = validation.get("confidence", "None")
                    ui.label(f"🎯 置信度: {confidence}")

                    file_count = validation.get("file_mapping_count", 0)
                    ui.label(f"📁 映射文件数: {file_count}")

                    # 验证详情
                    if "validation_details" in validation:
                        details = validation["validation_details"]
                        if "accuracy" in details:
                            accuracy = details["accuracy"] * 100
                            accuracy_color = (
                                "text-green" if accuracy == 100 else "text-orange"
                            )
                            ui.label(f"✅ 准确率: {accuracy:.1f}%").classes(
                                accuracy_color
                            )

                            matched_count = details.get("matched_count", 0)
                            expected_count = details.get("expected_count", 0)
                            ui.label(f"📈 匹配情况: {matched_count}/{expected_count}")

                            # 显示详细的文件匹配情况
                            missing_files = details.get("missing_files", [])
                            extra_files = details.get("extra_files", [])
                            matched_files = details.get("matched_files", [])

                            if matched_files:
                                ui.label(
                                    f"✅ 正确匹配 ({len(matched_files)}):"
                                ).classes("text-green font-bold")
                                for file_path in matched_files:
                                    ui.label(f"  • {file_path}").classes(
                                        "text-sm text-green"
                                    )

                            if missing_files:
                                ui.label(
                                    f"❌ 遗漏文件 ({len(missing_files)}):"
                                ).classes("text-red font-bold")
                                for file_path in missing_files:
                                    ui.label(f"  • {file_path}").classes(
                                        "text-sm text-red"
                                    )

                            if extra_files:
                                ui.label(f"⚠️ 多余文件 ({len(extra_files)}):").classes(
                                    "text-orange font-bold"
                                )
                                for file_path in extra_files:
                                    ui.label(f"  • {file_path}").classes(
                                        "text-sm text-orange"
                                    )

            # 关闭按钮
            with ui.row().classes("w-full justify-end mt-4"):
                RedButton("关闭", on_click=dialog.close)

        dialog.open()

    def _show_openai_formats_test_results(self, results: dict):
        """显示OpenAI多格式测试结果"""
        with ui.dialog() as dialog, ui.card().classes("w-[700px]"):
            ui.label("⚙️ OpenAI API多格式测试结果").classes("text-h6 mb-4")

            # 配置提示
            ui.label("💡 此测试使用界面中的配置，但不会保存配置").classes(
                "text-sm text-blue mb-4"
            )

            with ui.column().classes("w-full gap-3"):
                # 总体结果
                overall_success = results.get("success", False)
                success_icon = "✅" if overall_success else "❌"
                ui.label(
                    f"{success_icon} 总体状态: {'至少一种格式成功' if overall_success else '所有格式均失败'}"
                ).classes("font-bold")

                if results.get("error"):
                    ui.label(f"❌ 错误信息: {results['error']}").classes("text-red")

                # 推荐格式
                if overall_success:
                    recommended = results.get("recommended_format", "text")
                    ui.label(f"🌟 推荐格式: {recommended}").classes(
                        "text-green font-bold"
                    )

                ui.separator()

                # 各格式详细结果
                format_results = results.get("format_results", [])
                for format_result in format_results:
                    output_format = format_result.get("output_format", "unknown")
                    result_status = format_result.get("result_status", "unknown")

                    # 根据结果状态确定图标和标题
                    if result_status == "perfect":
                        icon = "✅"
                        status_text = "完全正确"
                        status_color = "text-green"
                    elif result_status == "validation_failed":
                        icon = "⚠️"
                        status_text = "验证失败"
                        status_color = "text-orange"
                    elif result_status == "ai_failed":
                        icon = "❌"
                        status_text = "AI失败"
                        status_color = "text-red"
                    else:
                        icon = "❓"
                        status_text = "未知状态"
                        status_color = "text-gray"

                    with ui.expansion(
                        f"{icon} {output_format} - {status_text}", icon="settings"
                    ).classes("w-full"):
                        with ui.column().classes("gap-2 p-2"):
                            ui.label(f"状态: {status_text}").classes(
                                status_color + " font-bold"
                            )
                            ui.label(f"耗时: {format_result.get('duration', 0):.2f}秒")

                            # AI失败情况：显示错误信息
                            if result_status == "ai_failed":
                                if format_result.get("error"):
                                    ui.label(
                                        f"错误详情: {format_result['error']}"
                                    ).classes("text-red")
                                else:
                                    ui.label(
                                        "AI分析返回None，可能是API调用失败或解析错误"
                                    ).classes("text-red")

                            # 验证失败和完全正确情况：显示详细结果
                            elif result_status in [
                                "validation_failed",
                                "perfect",
                            ] and format_result.get("validation"):
                                validation = format_result["validation"]
                                confidence = validation.get("confidence", "None")
                                ui.label(f"置信度: {confidence}")

                                file_count = validation.get("file_mapping_count", 0)
                                ui.label(f"映射文件数: {file_count}")

                                if "validation_details" in validation:
                                    details = validation["validation_details"]
                                    if "accuracy" in details:
                                        accuracy = details["accuracy"] * 100
                                        accuracy_color = (
                                            "text-green"
                                            if accuracy == 100
                                            else "text-orange"
                                        )
                                        ui.label(f"准确率: {accuracy:.1f}%").classes(
                                            accuracy_color
                                        )

                                        matched_count = details.get("matched_count", 0)
                                        expected_count = details.get(
                                            "expected_count", 0
                                        )
                                        ui.label(
                                            f"匹配情况: {matched_count}/{expected_count}"
                                        )

                                        # 显示详细的文件匹配情况
                                        missing_files = details.get("missing_files", [])
                                        extra_files = details.get("extra_files", [])
                                        matched_files = details.get("matched_files", [])

                                        if matched_files:
                                            ui.label(
                                                f"✅ 正确匹配 ({len(matched_files)}):"
                                            ).classes("text-green font-bold")
                                            for file_path in matched_files:
                                                ui.label(f"  • {file_path}").classes(
                                                    "text-sm text-green"
                                                )

                                        if missing_files:
                                            ui.label(
                                                f"❌ 遗漏文件 ({len(missing_files)}):"
                                            ).classes("text-red font-bold")
                                            for file_path in missing_files:
                                                ui.label(f"  • {file_path}").classes(
                                                    "text-sm text-red"
                                                )

                                        if extra_files:
                                            ui.label(
                                                f"⚠️ 多余文件 ({len(extra_files)}):"
                                            ).classes("text-orange font-bold")
                                            for file_path in extra_files:
                                                ui.label(f"  • {file_path}").classes(
                                                    "text-sm text-orange"
                                                )

            # 关闭按钮
            with ui.row().classes("w-full justify-end mt-4"):
                RedButton("关闭", on_click=dialog.close)

        dialog.open()


async def config_page() -> None:
    await ConfigPage()
