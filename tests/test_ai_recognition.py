#!/usr/bin/env python3
"""
AI识别测试脚本

支持两种模式：
1. 手动模式：生成prompt供用户复制给LLM，然后输入LLM响应进行测试
2. 自动模式：完整的AI识别流程，但不实际移动文件，只输出预期操作

使用方法：
python tests/test_ai_recognition.py --mode manual --path "/path/to/anime"
python tests/test_ai_recognition.py --mode auto --path "/path/to/anime"
"""

import sys
import json
import pprint
import argparse
from pathlib import Path
from typing import Dict, List, Optional

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


class AIRecognitionTester:
    """AI识别测试器"""

    def __init__(self, json_mode: Optional[bool] = None):
        self.ai_client = AIClient()
        if json_mode is not None:
            self.ai_client.json_mode = json_mode
            logger.info(f"[测试] 强制设置JSON模式为: {json_mode}")
        self.video_analyzer = VideoAnalyzer()
        self.search = Search()

    def collect_video_files(self, path: Path) -> List[Path]:
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

    def get_anime_info(self, path: Path) -> tuple[str, Optional[Dict]]:
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

    def manual_mode(self, path: Path):
        """手动模式：生成prompt供用户测试"""
        print("=" * 60)
        print("🤖 AI识别测试 - 手动模式")
        print("=" * 60)

        # 检查配置
        if not self.search.TMDB_KEY:
            print("❌ 错误：未配置TMDB API密钥")
            return

        # 收集视频文件
        video_files = self.collect_video_files(path)
        if not video_files:
            print("❌ 错误：未找到视频文件")
            return

        print(f"📁 分析路径: {path}")
        print(f"🎬 找到 {len(video_files)} 个视频文件")

        # 获取动漫信息
        name, tv_info = self.get_anime_info(path)
        if not name or not tv_info:
            print("❌ 错误：未找到动漫信息")
            return

        print(f"🎯 识别动漫: {name}")

        # 分析视频文件
        file_analysis = self.video_analyzer.analyze_video_files(path, video_files)

        # 生成prompt
        prompt = self.ai_client._build_analysis_prompt(tv_info, file_analysis)

        print("\n" + "=" * 60)
        print("📝 生成的Prompt（请复制给LLM）:")
        print("=" * 60)
        pprint.pprint(prompt)
        print("=" * 60)

        # 等待用户输入LLM响应
        print("\n请将上述prompt复制给LLM，然后将LLM的完整响应粘贴到下面：")
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
                return

        llm_response = "\n".join(response_lines).strip()

        if not llm_response:
            print("❌ 错误：未输入LLM响应")
            return

        # 解析和验证响应
        print("\n" + "=" * 60)
        print("🔍 分析LLM响应:")
        print("=" * 60)

        # 模拟一个response_message对象
        from types import SimpleNamespace

        mock_message = SimpleNamespace(content=llm_response, tool_calls=None)
        ai_result = self.ai_client._extract_and_validate_json(mock_message)

        if ai_result:
            print("✅ JSON解析成功")
            print(f"📊 置信度: {ai_result.confidence}")
            print(f"💭 分析理由: {ai_result.reason}")

            if ai_result.season_mapping:
                print("🗂️ 季度映射:")
                for sm in ai_result.season_mapping:
                    print(
                        f"  - 本地组 '{sm.local_group_name}' -> TMDB季度 {sm.maps_to_tmdb_seasons}"
                    )

            print(f"📋 文件映射数量: {len(ai_result.file_mapping)}")

            for i, mapping in enumerate(ai_result.file_mapping, 1):
                print(f"  {i}. {mapping.file_path}")
                print(f"     -> S{mapping.tmdb_season:02d}E{mapping.tmdb_episode:02d}")
                print(
                    f"     类型: {mapping.episode_type}, 置信度: {mapping.confidence}"
                )

            if ai_result.extra_notes:
                print(f"📝 额外说明: {ai_result.extra_notes}")

            # 保存结果到文件
            result_file = Path("ai_test_result.json")
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "path": str(path),
                        "anime_name": name,
                        "ai_result": ai_result.model_dump(),
                        "llm_response": llm_response,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            print(f"💾 结果已保存到: {result_file}")

        else:
            print("❌ JSON解析失败")
            print("原始响应:")
            print(llm_response)

    def auto_mode(self, path: Path):
        """自动模式：完整AI识别流程但不实际操作文件"""
        print("=" * 60)
        print("🤖 AI识别测试 - 自动模式")
        print("=" * 60)

        # 检查AI配置
        if not self.ai_client.is_available():
            print("❌ 错误：AI功能未启用或配置不完整")
            print("请检查以下配置：")
            print(f"  - AI启用状态: {cm.get_config('ai_enabled')}")
            print(
                f"  - API密钥: {'已配置' if cm.get_config('ai_api_key') else '未配置'}"
            )
            print(f"  - API地址: {cm.get_config('ai_base_url')}")
            print(f"  - 模型: {cm.get_config('ai_model')}")
            print(f"  - JSON模式: {'启用' if self.ai_client.json_mode else '禁用'}")
            return

        # 检查TMDB配置
        if not self.search.TMDB_KEY:
            print("❌ 错误：未配置TMDB API密钥")
            return

        # 收集视频文件
        video_files = self.collect_video_files(path)
        if not video_files:
            print("❌ 错误：未找到视频文件")
            return

        print(f"📁 分析路径: {path}")
        print(f"🎬 找到 {len(video_files)} 个视频文件")

        # 获取动漫信息
        name, tv_info = self.get_anime_info(path)
        if not name or not tv_info:
            print("❌ 错误：未找到动漫信息")
            return

        print(f"🎯 识别动漫: {name}")
        print(f"📅 首播日期: {tv_info.get('first_air_date', '未知')}")
        print(f"🎭 总季数: {tv_info.get('number_of_seasons', 0)}")
        print(f"📺 总集数: {tv_info.get('number_of_episodes', 0)}")

        # 显示季度信息
        if tv_info.get("seasons"):
            print("\n📋 季度信息:")
            for season in tv_info["seasons"]:
                print(
                    f"  第{season['season_number']}季: {season['name']} ({season['episode_count']}集)"
                )

        # 分析视频文件
        print("\n🔍 分析视频文件...")
        file_analysis = self.video_analyzer.analyze_video_files(path, video_files)

        for i, file_info in enumerate(file_analysis, 1):
            duration_str = (
                f" ({file_info['duration']:.1f}分钟)"
                if file_info["duration"]
                else " (时长未知)"
            )
            size_mb = file_info["size"] / (1024 * 1024)
            print(f"  {i}. {file_info['filename']}{duration_str} [{size_mb:.1f}MB]")

        # 调用AI分析
        print("\n🤖 调用AI分析...")
        ai_result = self.ai_client.analyze_episode_mapping(tv_info, file_analysis)

        if not ai_result:
            print("❌ AI分析失败")
            return

        print("✅ AI分析完成")
        print(f"📊 总体置信度: {ai_result.confidence}")
        print(f"💭 分析理由: {ai_result.reason}")

        # 显示季度映射
        if ai_result.season_mapping:
            print("\n🗂️ 季度映射:")
            for sm in ai_result.season_mapping:
                print(
                    f"  - 本地组 '{sm.local_group_name}' -> TMDB季度 {sm.maps_to_tmdb_seasons}"
                )

        # 显示文件映射
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

        # 模拟文件操作
        print("\n" + "=" * 60)
        print("📁 预期文件操作 (仅模拟，不实际执行):")
        print("=" * 60)

        work_path = Path(f"./模拟输出/{name} ({tv_info['first_air_date'][:4]})")

        for mapping in ai_result.file_mapping:
            # 找到对应的本地文件
            source_file = None
            for video_file in video_files:
                if mapping.file_path in str(video_file.relative_to(path.parent)):
                    source_file = video_file
                    break

            if not source_file:
                print(f"❌ 未找到文件: {mapping.file_path}")
                continue

            # 确定目标目录和文件名
            if mapping.episode_type in ["special", "ova"]:
                target_dir = work_path / "Season0"
                new_filename = f"S00E{mapping.tmdb_episode:02d} - {source_file.name}"
            elif mapping.episode_type == "movie":
                target_dir = work_path / "Movies"
                new_filename = source_file.name
            else:
                target_dir = work_path / f"Season{mapping.tmdb_season}"
                new_filename = f"S{mapping.tmdb_season:02d}E{mapping.tmdb_episode:02d} - {source_file.name}"

            target_path = target_dir / new_filename

            print(f"📂 {source_file.relative_to(path)}")
            print(f"   -> {target_path}")
            print()

        # 保存详细结果
        result_file = Path("ai_auto_test_result.json")
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "path": str(path),
                    "anime_name": name,
                    "anime_info": tv_info,
                    "file_analysis": file_analysis,
                    "ai_result": ai_result.model_dump(),
                    "confidence_threshold": self.ai_client.confidence_threshold,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        print(f"💾 详细结果已保存到: {result_file}")

        # 置信度分析
        confidence_map = {"High": 3, "Medium": 2, "Low": 1}
        threshold_level = confidence_map.get(self.ai_client.confidence_threshold, 2)
        low_confidence_count = sum(
            1
            for m in ai_result.file_mapping
            if confidence_map.get(m.confidence, 0) < threshold_level
        )
        if low_confidence_count > 0:
            print(
                f"\n⚠️  警告: {low_confidence_count} 个文件的置信度低于阈值 '{self.ai_client.confidence_threshold}'"
            )


def main():
    parser = argparse.ArgumentParser(description="AI识别测试脚本")
    parser.add_argument(
        "--mode",
        choices=["manual", "auto"],
        required=True,
        help="测试模式: manual(手动) 或 auto(自动)",
    )
    parser.add_argument("--path", required=True, help="要测试的动漫文件路径")
    parser.add_argument(
        "--json_mode",
        type=lambda x: (str(x).lower() == "true"),
        default=None,
        help="强制设置OpenAI JSON模式 (true/false)",
    )

    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"❌ 错误：路径不存在: {path}")
        return

    tester = AIRecognitionTester(json_mode=args.json_mode)

    if args.mode == "manual":
        tester.manual_mode(path)
    else:
        tester.auto_mode(path)


if __name__ == "__main__":
    main()
