#!/usr/bin/env python3
"""
AI识别测试脚本 - 重构版本

支持三种测试模式：
1. manual: 手动模式，生成prompt供用户复制给LLM，然后输入LLM响应进行测试
2. auto: 自动模式，完整的AI识别流程，但不实际移动文件，只输出预期操作
3. save: 保存测试用例模式，将动漫信息和本地文件信息保存为JSON格式

使用方法：
python tests/test_ai_recognition.py --mode manual --path "/path/to/anime"
python tests/test_ai_recognition.py --mode auto --path "/path/to/anime" --provider openai
python tests/test_ai_recognition.py --mode save --path "/path/to/anime" --output test_case.json
python tests/test_ai_recognition.py --mode manual --input test_case.json --provider gemini
python tests/test_ai_recognition.py --mode auto --input test_case.json --provider openai --openai_output_format function_calling
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import logger
from src.ai.client import AIClient
from src.rename.get_info import Search
from src.config.config_manager import cm
from src.rename.utils import VIDEO_SUFFIX
from src.ai.models import AIAnalysisResult
from src.ai.video_analyzer import VideoAnalyzer
from src.rename.cleaner import (
    remove_tag,
    remove_season,
    divide_by_year,
    remove_episode,
)


class DataInput:
    """数据输入模块 - 负责从JSON或路径获取测试数据"""

    def __init__(self):
        self.search = Search()
        self.video_analyzer = VideoAnalyzer()

    def load_from_json(self, input_file: str) -> Optional[Tuple[dict, dict, list]]:
        """从JSON文件加载测试数据，返回(metadata, anime_info, local_files)"""
        input_path = Path(input_file)
        if not input_path.exists():
            print(f"❌ 错误：测试用例文件不存在: {input_path}")
            return None

        try:
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ 错误：无法加载测试用例文件: {e}")
            return None

        # 验证基本格式
        required_keys = ["metadata", "anime_info", "local_files"]
        if not all(key in data for key in required_keys):
            print(f"❌ 错误：文件格式不正确，缺少必要字段: {required_keys}")
            return None

        metadata = data["metadata"]
        anime_info = data["anime_info"]
        local_files = data["local_files"]

        # 检查是否为测试结果文件（包含analysis_result字段）
        if "analysis_result" in data:
            print("ℹ️  检测到测试结果文件，将作为测试用例使用")
            # 确保metadata中有path_name字段
            if "path_name" not in metadata:
                filename = input_path.stem
                if filename.startswith(("manual_", "auto_")):
                    parts = filename.split("_")
                    if len(parts) >= 4:
                        metadata["path_name"] = parts[1]
                    else:
                        metadata["path_name"] = "unknown"
                else:
                    metadata["path_name"] = "unknown"
        else:
            print("ℹ️  检测到测试用例文件")
            if "path_name" not in metadata:
                metadata["path_name"] = "unknown"

        return metadata, anime_info, local_files

    def load_from_path(self, path: Path) -> Optional[Tuple[dict, dict, list]]:
        """从文件系统路径分析获取测试数据，返回(metadata, anime_info, local_files)"""
        # 检查TMDB配置
        if not self.search.TMDB_KEY:
            print("❌ 错误：未配置TMDB API密钥")
            return None

        # 收集视频文件
        video_files = self._collect_video_files(path)
        if not video_files:
            print("❌ 错误：未找到视频文件")
            return None

        print(f"📁 分析路径: {path}")
        print(f"🎬 找到 {len(video_files)} 个视频文件")

        # 获取动漫信息
        name, tv_info = self._get_anime_info(path)
        if not name or not tv_info:
            print("❌ 错误：未找到动漫信息")
            return None

        print(f"🎯 识别动漫: {name}")
        print(f"📅 首播日期: {tv_info.get('first_air_date', '未知')}")

        # 分析视频文件
        print("\n🔍 分析视频文件...")
        file_analysis = self.video_analyzer.analyze_video_files(path, video_files)

        # 构建metadata
        path_name = path.name
        metadata = {
            "created_at": datetime.now().isoformat(),
            "path_name": path_name,
            "anime_name": name,
            "description": f"测试用例：{name}",
            "file_count": len(video_files),
            "total_size_mb": sum(f["size"] for f in file_analysis) / (1024 * 1024),
        }

        return metadata, tv_info, file_analysis

    def _collect_video_files(self, path: Path) -> List[Path]:
        """收集指定路径下的所有视频文件"""
        video_files = []
        if path.is_file():
            if path.suffix.lower() in VIDEO_SUFFIX:
                video_files.append(path)
        else:
            for item in path.rglob("*"):
                if item.is_file() and item.suffix.lower() in VIDEO_SUFFIX:
                    video_files.append(item)
        return sorted(video_files)

    def _get_anime_info(self, path: Path) -> Tuple[str, Optional[Dict]]:
        """获取动漫信息"""
        # 处理文件名
        rtpath_name = remove_tag(path.name)
        if not rtpath_name:
            rtpath_name = remove_tag(path.name, True)

        rtpath_name, year = divide_by_year(rtpath_name)
        rtpath_name = remove_season(rtpath_name)
        rtpath_name = remove_episode(rtpath_name)
        rtpath_name = rtpath_name.strip("!")

        logger.info(f"[测试] 处理后的名称: {rtpath_name}")

        # 搜索动漫信息
        name, tv_info = self.search.get_tv_info_with_seasons(rtpath_name, year)
        if not name and year != 0:
            name, tv_info = self.search.get_tv_info_with_seasons(rtpath_name, 0)

        return name, tv_info


class DataProcessor:
    """数据处理模块 - 负责AI分析和用户交互"""

    def __init__(
        self, provider: Optional[str] = None, openai_output_format: Optional[str] = None
    ):
        # 临时修改配置
        self.original_provider = None
        self.original_output_format = None

        if provider:
            self.original_provider = cm.get_config("ai_provider")
            cm.set_config("ai_provider", provider)
            logger.info(f"[测试] 临时设置AI提供商为: {provider}")

        if openai_output_format is not None:
            self.original_output_format = cm.get_config("openai_output_format")
            cm.set_config("openai_output_format", openai_output_format)
            logger.info(f"[测试] 临时设置OpenAI输出格式为: {openai_output_format}")

        self.ai_client = AIClient()

    def __del__(self):
        """析构函数，恢复原始配置"""
        if self.original_provider is not None:
            cm.set_config("ai_provider", self.original_provider)
        if self.original_output_format is not None:
            cm.set_config("openai_output_format", self.original_output_format)

    def auto_process(
        self, anime_info: dict, local_files: list
    ) -> Optional[AIAnalysisResult]:
        """自动模式处理 - 直接调用AI分析"""
        if not self.ai_client.is_available():
            print("❌ 错误：AI功能未启用或配置不完整")
            self._print_ai_config_status()
            return None

        print(f"\n🤖 使用 {self.ai_client.provider.upper()} 进行AI分析...")
        return self.ai_client.analyze_episode_mapping(anime_info, local_files)

    def manual_process(
        self, anime_info: dict, local_files: list
    ) -> Optional[AIAnalysisResult]:
        """手动模式处理 - 生成prompt并获取用户输入"""
        # 生成prompt
        system_prompt = AIClient.get_system_prompt()
        base_prompt = AIClient.build_common_prompt(anime_info, local_files)

        # 根据AI提供商添加特定指令
        if self.ai_client.provider == "gemini":
            full_prompt = self.ai_client._client._add_gemini_instructions(base_prompt)
        else:
            full_prompt = self.ai_client._client._add_openai_json_instructions(
                base_prompt
            )

        print("\n" + "=" * 60)
        print("📝 系统提示词:")
        print("=" * 60)
        print(system_prompt)
        print("\n" + "=" * 60)
        print("📝 用户提示词（请复制给LLM）:")
        print("=" * 60)
        print(full_prompt)
        print("=" * 60)

        # 获取用户输入
        print(
            f"\n请将上述prompt复制给 {self.ai_client.provider.upper()}，然后将LLM的完整响应粘贴到下面："
        )
        print("（输入完成后按两次回车）")

        response_lines = []
        empty_line_count = 0

        while True:
            try:
                line = input()
                if line.strip() == "":
                    empty_line_count += 1
                    if empty_line_count >= 2:
                        break
                else:
                    empty_line_count = 0
                response_lines.append(line)
            except KeyboardInterrupt:
                print("\n❌ 用户取消")
                return None

        llm_response = "\n".join(response_lines).strip()
        if not llm_response:
            print("❌ 错误：未输入LLM响应")
            return None

        # 解析响应
        print("\n" + "=" * 60)
        print("🔍 分析LLM响应:")
        print("=" * 60)

        ai_result = self._parse_manual_response(llm_response)
        if ai_result:
            print("✅ JSON解析成功")
        else:
            print("❌ JSON解析失败")
            print("原始响应:")
            print(
                llm_response[:500] + "..." if len(llm_response) > 500 else llm_response
            )

        return ai_result

    def _parse_manual_response(self, response: str) -> Optional[AIAnalysisResult]:
        """解析手动输入的LLM响应"""
        try:
            # 尝试直接解析JSON
            if response.strip().startswith('{'):
                json_data = json.loads(response)
                return AIAnalysisResult(**json_data)

            # 尝试提取JSON部分
            import re

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                json_data = json.loads(json_str)
                return AIAnalysisResult(**json_data)

            logger.error("[手动测试] 无法从响应中提取JSON")
            return None

        except json.JSONDecodeError as e:
            logger.error(f"[手动测试] JSON解析错误: {e}")
            return None
        except Exception as e:
            logger.error(f"[手动测试] 响应解析失败: {e}")
            return None

    def _print_ai_config_status(self):
        """打印AI配置状态"""
        print("请检查以下配置：")
        print(f"  - AI启用状态: {cm.get_config('ai_enabled')}")
        print(f"  - AI提供商: {cm.get_config('ai_provider')}")

        if cm.get_config('ai_provider') == 'gemini':
            print(
                f"  - Gemini API密钥: {'已配置' if cm.get_config('gemini_api_key') else '未配置'}"
            )
            print(f"  - Gemini 模型: {cm.get_config('gemini_model')}")
            print(f"  - Gemini API地址: {cm.get_config('gemini_base_url')}")
        else:
            print(
                f"  - OpenAI API密钥: {'已配置' if cm.get_config('ai_api_key') else '未配置'}"
            )
            print(f"  - OpenAI API地址: {cm.get_config('ai_base_url')}")
            print(f"  - OpenAI 模型: {cm.get_config('ai_model')}")
            print(f"  - OpenAI 输出格式: {cm.get_config('openai_output_format')}")


class DataSaver:
    """数据保存模块 - 负责保存测试用例和测试结果"""

    def save_test_case(
        self,
        metadata: dict,
        anime_info: dict,
        local_files: list,
        output_file: str = None,
    ):
        """保存测试用例"""
        path_name = metadata.get('path_name', 'unknown')

        # 如果没有指定输出文件，使用默认命名
        if not output_file:
            output_file = f"case_{path_name}.json"

        # 构建测试用例数据
        test_case = {
            "metadata": metadata,
            "anime_info": anime_info,
            "local_files": local_files,
        }

        # 保存到文件
        output_path = Path(output_file)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(test_case, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 测试用例已保存到: {output_path}")
        print(f"📊 包含 {len(local_files)} 个文件的信息")
        print(f"💿 总大小: {metadata.get('total_size_mb', 0):.1f} MB")

        # 显示文件列表
        print("\n📋 包含的文件:")
        for i, file_info in enumerate(local_files, 1):
            duration_str = (
                f" ({file_info['duration']:.1f}分钟)"
                if file_info.get("duration")
                else " (时长未知)"
            )
            size_mb = file_info["size"] / (1024 * 1024)
            print(f"  {i}. {file_info['filename']}{duration_str} [{size_mb:.1f}MB]")

    def save_test_result(
        self,
        metadata: dict,
        anime_info: dict,
        local_files: list,
        ai_result: AIAnalysisResult,
        mapping_analysis: dict,
        mode: str,
        provider: str,
        result_file: str = None,
    ):
        """保存测试结果，格式与测试用例保持一致，analysis_result直接加在最后"""
        path_name = metadata.get('path_name', 'unknown')

        # 如果没有指定结果文件，使用默认命名
        if not result_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            result_file = f"{mode}_{path_name}_{provider}_{timestamp}.json"

        # 构建结果数据，格式与测试用例一致，analysis_result直接加在最后
        result_data = {
            "metadata": metadata,
            "anime_info": anime_info,
            "local_files": local_files,
            "analysis_result": {
                "mode": mode,
                "provider": provider,
                "timestamp": datetime.now().isoformat(),
                "ai_result": ai_result.model_dump(),
                "mapping_analysis": mapping_analysis,
            },
        }

        # 保存到文件
        output_path = Path(result_file)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)

        print(f"\n💾 测试结果已保存到: {output_path}")
        return output_path

    def display_test_info(
        self, metadata: dict, anime_info: dict, local_files: list, provider: str
    ):
        """显示测试信息"""
        print(f"📁 测试用例: {metadata.get('description', '未知')}")
        print(f"🎯 动漫名称: {metadata.get('anime_name', '未知')}")
        print(f"📅 创建时间: {metadata.get('created_at', '未知')}")
        print(f"🎬 文件数量: {len(local_files)}")
        print(f"💿 总大小: {metadata.get('total_size_mb', 0):.1f} MB")
        print(f"🤖 使用AI提供商: {provider.upper()}")

        # 显示动漫信息
        print(f"\n📺 动漫信息:")
        print(f"  首播日期: {anime_info.get('first_air_date', '未知')}")
        print(f"  总季数: {anime_info.get('number_of_seasons', 0)}")
        print(f"  总集数: {anime_info.get('number_of_episodes', 0)}")

        # 显示季度信息
        if anime_info.get("seasons"):
            print("\n📋 季度信息:")
            for season in anime_info["seasons"]:
                print(
                    f"  第{season['season_number']}季: {season['name']} ({len(season['episodes'])}集)"
                )

        # 显示文件列表
        print(f"\n📁 本地文件 ({len(local_files)}个):")
        for i, file_info in enumerate(local_files, 1):
            duration_str = (
                f" ({file_info['duration']:.1f}分钟)"
                if file_info.get("duration")
                else " (时长未知)"
            )
            size_mb = file_info["size"] / (1024 * 1024)
            print(f"  {i}. {file_info['filename']}{duration_str} [{size_mb:.1f}MB]")

    def analyze_and_display_result(
        self, ai_result: AIAnalysisResult, local_files: list
    ) -> dict:
        """分析并显示AI结果"""
        # 进行文件映射分析
        mapping_analysis = self._analyze_file_mapping(ai_result, local_files)

        print("\n" + "=" * 60)
        print("🤖 AI分析结果")
        print("=" * 60)

        print(f"📊 总体置信度: {ai_result.confidence}")
        print(f"💭 分析理由: {ai_result.reason}")

        # 显示季度映射
        if ai_result.season_mapping:
            print(f"\n🗂️ 季度映射 ({len(ai_result.season_mapping)}个):")
            for sm in ai_result.season_mapping:
                print(
                    f"  - 本地组 '{sm.local_group_name}' -> TMDB季度 {sm.maps_to_tmdb_seasons}"
                )

        # 显示文件映射
        if ai_result.file_mapping:
            print(f"\n📋 文件映射 ({len(ai_result.file_mapping)}个):")
            for i, mapping in enumerate(ai_result.file_mapping, 1):
                confidence_map = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}
                confidence_icon = confidence_map.get(mapping.confidence, "❓")
                type_icon = {
                    "regular": "📺",
                    "special": "⭐",
                    "ova": "🎬",
                    "movie": "🎭",
                }.get(mapping.episode_type, "❓")

                print(f"  {i}. {mapping.file_path}")
                print(
                    f"     -> S{mapping.tmdb_season:02d}E{mapping.tmdb_episode:02d} {type_icon} {mapping.episode_type}"
                )
                print(f"     {confidence_icon} 置信度: {mapping.confidence}")

        if ai_result.extra_notes:
            print(f"\n📝 额外说明: {ai_result.extra_notes}")

        # 文件映射分析报告
        print("\n" + "=" * 60)
        print("📋 文件映射分析报告")
        print("=" * 60)

        print(f"📁 原始文件总数: {mapping_analysis['original_file_count']}")
        print(f"🎯 AI映射文件数: {mapping_analysis['ai_mapped_count']}")
        print(f"✅ 映射准确率: {mapping_analysis['mapping_accuracy']:.1%}")

        if mapping_analysis['successfully_mapped']:
            print(
                f"\n✅ 成功映射的文件 ({len(mapping_analysis['successfully_mapped'])}个):"
            )
            for i, path in enumerate(
                sorted(mapping_analysis['successfully_mapped']), 1
            ):
                print(f"  {i}. {path}")

        if mapping_analysis['missed_by_ai']:
            print(f"\n❌ AI遗漏的文件 ({len(mapping_analysis['missed_by_ai'])}个):")
            for i, path in enumerate(sorted(mapping_analysis['missed_by_ai']), 1):
                print(f"  {i}. {path}")

        if mapping_analysis['ai_generated_extra']:
            print(
                f"\n⚠️  AI生成的额外路径 ({len(mapping_analysis['ai_generated_extra'])}个):"
            )
            for i, path in enumerate(sorted(mapping_analysis['ai_generated_extra']), 1):
                print(f"  {i}. {path}")

        if (
            not mapping_analysis['missed_by_ai']
            and not mapping_analysis['ai_generated_extra']
        ):
            print("\n🎉 完美映射！所有文件都被正确识别，没有遗漏或多余的路径。")

        return mapping_analysis

    def _analyze_file_mapping(
        self, ai_result: AIAnalysisResult, original_files: list
    ) -> dict:
        """分析文件路径映射情况"""
        # 提取原始文件路径
        original_paths = set()
        for file_info in original_files:
            if isinstance(file_info, dict):
                original_paths.add(file_info.get("path", ""))
            else:
                original_paths.add(str(file_info))

        # 提取AI映射的文件路径
        ai_mapped_paths = set()
        if ai_result.file_mapping:
            for mapping in ai_result.file_mapping:
                ai_mapped_paths.add(mapping.file_path)

        # 分析映射情况
        mapped_files = original_paths & ai_mapped_paths  # 被AI成功映射的文件
        missed_files = original_paths - ai_mapped_paths  # 被AI遗漏的文件
        extra_files = ai_mapped_paths - original_paths  # AI生成但原始文件中不存在的路径

        return {
            "original_file_count": len(original_paths),
            "ai_mapped_count": len(ai_mapped_paths),
            "successfully_mapped": list(mapped_files),
            "missed_by_ai": list(missed_files),
            "ai_generated_extra": list(extra_files),
            "mapping_accuracy": (
                len(mapped_files) / len(original_paths) if original_paths else 0
            ),
        }


class AIRecognitionTester:
    """AI识别测试器 - 重构版本，使用模块化设计"""

    def __init__(
        self, provider: Optional[str] = None, openai_output_format: Optional[str] = None
    ):
        self.data_input = DataInput()
        self.data_processor = DataProcessor(provider, openai_output_format)
        self.data_saver = DataSaver()

    def save_test_case(self, path: Path, output_file: str = None):
        """保存测试用例模式：将动漫信息和本地文件信息保存为JSON格式"""
        print("=" * 60)
        print("💾 AI识别测试 - 保存测试用例模式")
        print("=" * 60)

        # 数据输入：从路径分析
        data = self.data_input.load_from_path(path)
        if not data:
            return

        metadata, anime_info, local_files = data

        # 数据处理：save模式跳过

        # 数据保存：保存测试用例
        self.data_saver.save_test_case(metadata, anime_info, local_files, output_file)

    def manual_mode(self, path: Path):
        """手动模式：生成prompt供用户测试"""
        print("=" * 60)
        print("🤖 AI识别测试 - 手动模式")
        print("=" * 60)

        # 数据输入：从路径分析
        data = self.data_input.load_from_path(path)
        if not data:
            return

        metadata, anime_info, local_files = data

        # 显示测试信息
        self.data_saver.display_test_info(
            metadata, anime_info, local_files, self.data_processor.ai_client.provider
        )

        # 数据处理：手动模式，包含用户交互
        ai_result = self.data_processor.manual_process(anime_info, local_files)
        if not ai_result:
            return

        # 分析并显示结果
        mapping_analysis = self.data_saver.analyze_and_display_result(
            ai_result, local_files
        )

        # 数据保存：保存测试结果
        self.data_saver.save_test_result(
            metadata,
            anime_info,
            local_files,
            ai_result,
            mapping_analysis,
            "manual",
            self.data_processor.ai_client.provider,
        )

    def auto_mode(self, path: Path):
        """自动模式：完整AI识别流程但不实际操作文件"""
        print("=" * 60)
        print("🤖 AI识别测试 - 自动模式")
        print("=" * 60)

        # 数据输入：从路径分析
        data = self.data_input.load_from_path(path)
        if not data:
            return

        metadata, anime_info, local_files = data

        # 显示测试信息
        self.data_saver.display_test_info(
            metadata, anime_info, local_files, self.data_processor.ai_client.provider
        )

        # 数据处理：自动模式
        ai_result = self.data_processor.auto_process(anime_info, local_files)
        if not ai_result:
            return

        # 分析并显示结果
        mapping_analysis = self.data_saver.analyze_and_display_result(
            ai_result, local_files
        )

        # 数据保存：保存测试结果
        self.data_saver.save_test_result(
            metadata,
            anime_info,
            local_files,
            ai_result,
            mapping_analysis,
            "auto",
            self.data_processor.ai_client.provider,
        )

    def manual_mode_from_json(self, input_file: str):
        """从JSON测试用例进行手动模式测试"""
        print("=" * 60)
        print("🤖 AI识别测试 - 手动模式 (从测试用例)")
        print("=" * 60)

        # 数据输入：从JSON读取
        data = self.data_input.load_from_json(input_file)
        if not data:
            return

        metadata, anime_info, local_files = data

        # 显示测试信息
        self.data_saver.display_test_info(
            metadata, anime_info, local_files, self.data_processor.ai_client.provider
        )

        # 数据处理：手动模式，包含用户交互
        ai_result = self.data_processor.manual_process(anime_info, local_files)
        if not ai_result:
            return

        # 分析并显示结果
        mapping_analysis = self.data_saver.analyze_and_display_result(
            ai_result, local_files
        )

        # 数据保存：保存测试结果
        self.data_saver.save_test_result(
            metadata,
            anime_info,
            local_files,
            ai_result,
            mapping_analysis,
            "manual",
            self.data_processor.ai_client.provider,
        )

    def auto_mode_from_json(self, input_file: str):
        """从JSON测试用例进行自动模式测试"""
        print("=" * 60)
        print("🤖 AI识别测试 - 自动模式 (从测试用例)")
        print("=" * 60)

        # 数据输入：从JSON读取
        data = self.data_input.load_from_json(input_file)
        if not data:
            return

        metadata, anime_info, local_files = data

        # 显示测试信息
        self.data_saver.display_test_info(
            metadata, anime_info, local_files, self.data_processor.ai_client.provider
        )

        # 数据处理：自动模式
        ai_result = self.data_processor.auto_process(anime_info, local_files)
        if not ai_result:
            return

        # 分析并显示结果
        mapping_analysis = self.data_saver.analyze_and_display_result(
            ai_result, local_files
        )

        # 数据保存：保存测试结果
        self.data_saver.save_test_result(
            metadata,
            anime_info,
            local_files,
            ai_result,
            mapping_analysis,
            "auto",
            self.data_processor.ai_client.provider,
        )


def main():
    parser = argparse.ArgumentParser(
        description="AI识别测试脚本 - 支持多种测试模式和AI提供商",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 手动模式测试
  python tests/test_ai_recognition.py --mode manual --path "/path/to/anime"

  # 自动模式测试，指定AI提供商
  python tests/test_ai_recognition.py --mode auto --path "/path/to/anime" --provider gemini

  # 保存测试用例
  python tests/test_ai_recognition.py --mode save --path "/path/to/anime" --output test_case.json

  # 从测试用例进行手动测试
  python tests/test_ai_recognition.py --mode manual --input test_case.json --provider gemini

  # 从测试用例进行自动测试
  python tests/test_ai_recognition.py --mode auto --input test_case.json --provider openai --openai_output_format function_calling
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["manual", "auto", "save"],
        required=True,
        help="测试模式: manual(手动), auto(自动), save(保存测试用例)",
    )

    parser.add_argument("--path", help="要测试的动漫文件路径")

    parser.add_argument(
        "--provider",
        choices=["openai", "gemini"],
        help="AI提供商选择 (openai 或 gemini)，不指定则使用配置中的默认值",
    )

    parser.add_argument(
        "--openai_output_format",
        choices=["function_calling", "json_object", "structured_output", "text"],
        help="OpenAI输出格式选择，支持: function_calling, json_object, structured_output, text",
    )

    parser.add_argument("--output", help="保存测试用例的文件路径 (save模式必需)")

    parser.add_argument(
        "--input", help="测试用例JSON文件路径 (与--path二选一，同时指定时优先使用)"
    )

    args = parser.parse_args()

    # 验证参数组合
    if not args.path and not args.input:
        parser.error("必须指定 --path 或 --input 参数之一")

    if args.mode == "save" and args.input:
        parser.error("save 模式不支持 --input 参数，请使用 --path 指定源路径")

    # 确定输入数据源，--input 优先
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"❌ 错误：测试用例文件不存在: {input_path}")
            return
        path = None
        input_file = args.input
    else:
        path = Path(args.path)
        if not path.exists():
            print(f"❌ 错误：路径不存在: {path}")
            return
        input_file = None

    # 创建测试器
    tester = AIRecognitionTester(
        provider=args.provider, openai_output_format=args.openai_output_format
    )

    # 执行对应模式
    try:
        if args.mode == "manual":
            if input_file:
                tester.manual_mode_from_json(input_file)
            else:
                tester.manual_mode(path)
        elif args.mode == "auto":
            if input_file:
                tester.auto_mode_from_json(input_file)
            else:
                tester.auto_mode(path)
        elif args.mode == "save":
            tester.save_test_case(path, args.output)
    except KeyboardInterrupt:
        print("\n❌ 用户中断操作")
    except Exception as e:
        print(f"❌ 执行过程中发生错误: {e}")
        logger.error(f"测试脚本执行失败: {e}", exc_info=True)


if __name__ == "__main__":
    main()
