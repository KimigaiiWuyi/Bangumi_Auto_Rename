#!/usr/bin/env python3
"""
统一AI测试器 - 使用当前界面配置进行测试

支持功能：
1. AI识别功能测试 - 使用项目测试用例进行完整的AI识别测试
2. OpenAI API多格式测试 - 测试function_calling、structured_output、json_object三种输出格式

特点：
- 使用当前界面配置，不保存配置
- 统一的测试架构，代码复用
- 异步处理避免UI阻塞
- 项目相关测试用例
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..logger import logger
from ..ai.client import AIClient
from ..config.config_manager import cm
from ..ai.models import AIAnalysisResult


class UnifiedAITester:
    """统一的AI测试器，使用当前界面配置进行测试"""

    def __init__(self, current_config: Dict[str, Any]):
        """
        Args:
            current_config: 当前界面配置字典
        """
        self.current_config = current_config
        self.original_config = {}
        self.test_case_path = (
            Path(__file__).parent.parent.parent / "tests" / "example_test_case.json"
        )
        self.expected_path = (
            Path(__file__).parent.parent.parent / "tests" / "example_expected.json"
        )

    def _apply_current_config(self):
        """应用当前界面配置"""
        logger.info("[AI识别测试] 应用当前界面配置")
        for key, value in self.current_config.items():
            self.original_config[key] = cm.get_config(key)
            cm.set_config(key, value)
            if "api_key" in key:
                value = len(str(value)) * '*'
            logger.debug(f"[AI识别测试] 设置配置 {key}: {value}")
        if not cm.get_config("ai_enabled"):
            cm.set_config("ai_enabled", True)
            logger.debug("[AI识别测试] 未启用AI功能，暂时启用进行测试")

    def _restore_config(self):
        """恢复原始配置"""
        logger.info("[AI识别测试] 恢复原始配置")
        for key, value in self.original_config.items():
            cm.set_config(key, value)
            if "api_key" in key:
                value = len(str(value)) * '*'
            logger.debug(f"[AI识别测试] 恢复配置 {key}: {value}")
        self.original_config.clear()

    def _load_test_case(self) -> Optional[Dict[str, Any]]:
        """加载测试用例"""
        try:
            if not self.test_case_path.exists():
                logger.error(f"[AI识别测试] 测试用例文件不存在: {self.test_case_path}")
                return None

            with open(self.test_case_path, 'r', encoding='utf-8') as f:
                test_case = json.load(f)
                logger.info(
                    f"[AI识别测试] 成功加载测试用例: {test_case.get('metadata', {}).get('path_name', 'Unknown')}"
                )
                return test_case
        except Exception as e:
            logger.error(f"[AI识别测试] 加载测试用例失败: {str(e)}")
            return None

    def _load_expected_result(self) -> Optional[Dict[str, Any]]:
        """加载期望结果"""
        try:
            if not self.expected_path.exists():
                logger.warning(f"[AI识别测试] 期望结果文件不存在: {self.expected_path}")
                return None

            with open(self.expected_path, 'r', encoding='utf-8') as f:
                expected = json.load(f)
                logger.info("[AI识别测试] 成功加载期望结果")
                return expected
        except Exception as e:
            logger.error(f"[AI识别测试] 加载期望结果失败: {str(e)}")
            return None

    def _validate_ai_result(
        self, ai_result: AIAnalysisResult, expected: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """验证AI分析结果"""
        validation_result = {
            "success": False,
            "confidence": ai_result.confidence if ai_result else "None",
            "file_mapping_count": 0,
            "validation_details": {},
        }

        if not ai_result:
            validation_result["validation_details"]["error"] = "AI分析失败，返回None"
            return validation_result

        # 基本验证
        validation_result["success"] = True
        validation_result["file_mapping_count"] = len(ai_result.file_mapping)

        # 如果有期望结果，进行详细验证
        if expected and "file_mapping" in expected:
            expected_mapping_list = expected["file_mapping"]  # 这是一个字典列表

            # 将期望结果转换为字典，key为file_path
            expected_mapping = {}
            for item in expected_mapping_list:
                file_path = item["file_path"]
                expected_mapping[file_path] = {
                    "tmdb_season": item["tmdb_season"],
                    "tmdb_episode": item["tmdb_episode"],
                    "episode_type": item.get("episode_type", "regular"),
                    "confidence": item.get("confidence", "Medium"),
                }

            # 将AI结果转换为字典，key为file_path
            actual_mapping = {}
            for item in ai_result.file_mapping:
                file_path = item.file_path
                actual_mapping[file_path] = {
                    "tmdb_season": item.tmdb_season,
                    "tmdb_episode": item.tmdb_episode,
                    "episode_type": item.episode_type,
                    "confidence": item.confidence,
                }

            # 计算匹配情况
            matched_count = 0
            total_expected = len(expected_mapping)
            matched_files = []
            missing_files = []
            extra_files = []

            for file_path, expected_info in expected_mapping.items():
                if file_path in actual_mapping:
                    actual_info = actual_mapping[file_path]
                    # 检查关键字段是否匹配（不包括confidence）
                    if (
                        actual_info["tmdb_season"] == expected_info["tmdb_season"]
                        and actual_info["tmdb_episode"] == expected_info["tmdb_episode"]
                        and actual_info["episode_type"] == expected_info["episode_type"]
                    ):
                        matched_count += 1
                        matched_files.append(file_path)
                else:
                    missing_files.append(file_path)

            # 检查AI结果中是否有期望结果中没有的文件
            for file_path in actual_mapping:
                if file_path not in expected_mapping:
                    extra_files.append(file_path)

            validation_result["validation_details"] = {
                "expected_count": total_expected,
                "actual_count": len(actual_mapping),
                "matched_count": matched_count,
                "accuracy": matched_count / total_expected if total_expected > 0 else 0,
                "matched_files": matched_files,
                "missing_files": missing_files,
                "extra_files": extra_files,
            }

        return validation_result

    def _run_single_ai_test(self) -> Dict[str, Any]:
        """运行单次AI识别测试（核心复用逻辑）"""
        start_time = time.time()
        result = {
            "success": False,
            "error": None,
            "duration": 0,
            "ai_result": None,
            "validation": None,
            "config_used": self.current_config.copy(),
        }

        try:
            # 应用当前配置
            self._apply_current_config()

            # 加载测试用例
            test_case = self._load_test_case()
            if not test_case:
                result["error"] = "无法加载测试用例"
                return result

            # 创建AI客户端
            ai_client = AIClient()
            if not ai_client.is_available():
                result["error"] = f"AI客户端不可用 - 提供商: {ai_client.provider}"
                return result

            # 执行AI分析
            logger.info(f"[AI识别测试] 开始AI分析 - 提供商: {ai_client.provider}")
            ai_result = ai_client.analyze_episode_mapping(
                test_case["anime_info"], test_case["local_files"]
            )

            # TODO
            if ai_result is None:
                result["error"] = "AI分析失败，返回None"
                return result

            # 加载期望结果并验证
            expected = self._load_expected_result()
            validation = self._validate_ai_result(ai_result, expected)

            # 分类结果状态
            if ai_result is None:
                result_status = "ai_failed"  # AI请求或解析失败
            elif validation and validation.get("validation_details"):
                details = validation["validation_details"]
                accuracy = details.get("accuracy", 0)
                missing_files = details.get("missing_files", [])
                extra_files = details.get("extra_files", [])

                if (
                    accuracy == 1.0
                    and len(missing_files) == 0
                    and len(extra_files) == 0
                ):
                    result_status = "perfect"  # 完全正确
                else:
                    result_status = "validation_failed"  # 结果验证不正确
            else:
                result_status = "validation_failed"  # 无法验证，视为验证失败

            result.update(
                {
                    "success": ai_result is not None,
                    "ai_result": ai_result,
                    "validation": validation,
                    "provider": ai_client.provider,
                    "result_status": result_status,
                }
            )

            logger.info(f"[AI识别测试] AI分析完成 - 成功: {result['success']}")

        except Exception as e:
            logger.error(f"[AI识别测试] AI测试异常: {str(e)}")
            result["error"] = str(e)
        finally:
            # 恢复原始配置
            self._restore_config()
            result["duration"] = time.time() - start_time

        return result

    def test_ai_recognition(self) -> Dict[str, Any]:
        """测试AI识别功能"""
        logger.info("[AI识别测试] 开始AI识别功能测试")
        return self._run_single_ai_test()

    def test_openai_api_formats(self) -> Dict[str, Any]:
        """测试OpenAI API的多种输出格式支持"""
        logger.info("[AI识别测试] 开始OpenAI API多格式测试")

        # 要测试的输出格式
        formats_to_test = ["function_calling", "structured_output", "json_object"]
        format_results = []
        successful_formats = []

        for output_format in formats_to_test:
            logger.info(f"[AI识别测试] 测试输出格式: {output_format}")

            # 创建临时配置，修改输出格式
            temp_config = self.current_config.copy()
            temp_config["openai_output_format"] = output_format

            # 创建临时测试器并运行测试
            temp_tester = UnifiedAITester(temp_config)
            result = temp_tester._run_single_ai_test()
            result["output_format"] = output_format
            format_results.append(result)

            if result["success"]:
                successful_formats.append(output_format)

        # 汇总结果和推荐格式
        overall_result = {
            "success": len(successful_formats) > 0,
            "format_results": format_results,
            "successful_formats": successful_formats,
            "recommended_format": self._get_recommended_format(format_results),
        }

        logger.info(
            f"[AI识别测试] OpenAI多格式测试完成 - 成功格式: {successful_formats}"
        )
        return overall_result

    def _get_recommended_format(self, format_results: List[Dict[str, Any]]) -> str:
        """根据测试结果推荐最佳格式"""
        priority_order = ["function_calling", "structured_output", "json_object"]

        # 当前使用简单测试用例，不允许出错，只要有错误就标记为失败
        perfect_formats = []  # 完全正确的格式

        for result in format_results:
            if not result.get("success", False):
                continue

            output_format = result.get("output_format", "")
            validation = result.get("validation", {})

            # 检查是否完全正确（100%准确率）
            is_perfect = False
            if validation and "validation_details" in validation:
                validation_details = validation["validation_details"]
                accuracy = validation_details.get("accuracy", 0)
                missing_files = validation_details.get("missing_files", [])
                extra_files = validation_details.get("extra_files", [])

                # 必须100%准确率，且没有遗漏文件和多余文件
                if (
                    accuracy == 1.0
                    and len(missing_files) == 0
                    and len(extra_files) == 0
                ):
                    is_perfect = True

            if is_perfect:
                perfect_formats.append(output_format)

        # 从完全正确的格式中按优先级选择
        if perfect_formats:
            for preferred_format in priority_order:
                if preferred_format in perfect_formats:
                    logger.info(f"[AI识别测试] 推荐格式: {preferred_format} (完全正确)")
                    return preferred_format
            # 如果优先级列表中没有，选择第一个完全正确的
            best_format = perfect_formats[0]
            logger.info(f"[AI识别测试] 推荐格式: {best_format} (完全正确)")
            return best_format

        # 如果没有完全正确的格式，回退到text
        logger.warning("[AI识别测试] 没有完全正确的格式，回退到text")
        return "text"
