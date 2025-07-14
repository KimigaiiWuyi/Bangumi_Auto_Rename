#!/usr/bin/env python3
"""
测试OpenAI客户端的多种输出格式支持

验证新增的输出格式功能是否正常工作
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ..src.config.config_manager import cm
from ..src.ai.openai_client import OpenAIClient


def test_output_format_configuration():
    """测试输出格式配置功能"""
    print("🧪 测试OpenAI客户端输出格式配置...")

    # 测试默认配置
    default_format = cm.get_config("openai_output_format")
    print(f"默认输出格式: {default_format}")

    # 测试各种输出格式
    formats = ["function_calling", "json_object", "structured_output", "text"]

    for fmt in formats:
        print(f"\n📋 测试格式: {fmt}")

        # 设置配置
        cm.set_config("openai_output_format", fmt)
        cm.set_config("ai_enabled", True)
        cm.set_config("ai_api_key", "test-key")  # 测试用密钥

        # 创建客户端
        client = OpenAIClient()

        # 验证配置
        assert (
            client.output_format == fmt
        ), f"输出格式配置失败: 期望 {fmt}, 实际 {client.output_format}"
        print(f"✅ 输出格式配置正确: {client.output_format}")

        # 测试配置输出格式方法
        request_params = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "test"}],
            "temperature": 0.1,
        }

        client._configure_output_format(request_params)

        # 验证请求参数配置
        if fmt == "function_calling":
            assert "tools" in request_params, "Function calling模式应该包含tools参数"
            assert (
                "tool_choice" in request_params
            ), "Function calling模式应该包含tool_choice参数"
            print("✅ Function calling参数配置正确")
        elif fmt == "json_object":
            assert (
                "response_format" in request_params
            ), "JSON object模式应该包含response_format参数"
            assert (
                request_params["response_format"]["type"] == "json_object"
            ), "JSON object格式配置错误"
            print("✅ JSON object参数配置正确")
        elif fmt == "structured_output":
            assert (
                "response_format" in request_params
            ), "Structured output模式应该包含response_format参数"
            assert (
                request_params["response_format"]["type"] == "json_schema"
            ), "Structured output格式配置错误"
            print("✅ Structured output参数配置正确")
        elif fmt == "text":
            # Text模式不应该有特殊参数
            assert "tools" not in request_params, "Text模式不应该包含tools参数"
            assert (
                "response_format" not in request_params
            ), "Text模式不应该包含response_format参数"
            print("✅ Text模式参数配置正确")


def test_prompt_instructions():
    """测试提示词指令生成"""
    print("\n📝 测试提示词指令生成...")

    base_prompt = "这是基础提示词"

    formats_to_test = ["function_calling", "json_object", "structured_output", "text"]

    for fmt in formats_to_test:
        cm.set_config("openai_output_format", fmt)

        client = OpenAIClient()
        result_prompt = client._add_openai_json_instructions(base_prompt)

        if fmt in ["function_calling", "structured_output"]:
            # 这些格式不需要额外的JSON指令
            assert result_prompt == base_prompt, f"{fmt}格式不应该添加额外指令"
            print(f"✅ {fmt}格式提示词正确（无额外指令）")
        else:
            # json_object和text格式需要额外的JSON指令
            assert len(result_prompt) > len(base_prompt), f"{fmt}格式应该添加JSON指令"
            assert "JSON" in result_prompt, f"{fmt}格式应该包含JSON相关指令"
            print(f"✅ {fmt}格式提示词正确（包含JSON指令）")


def test_api_capabilities_method():
    """测试API功能测试方法"""
    print("\n🔍 测试API功能测试方法...")

    # 创建未配置的客户端
    cm.set_config("ai_enabled", False)
    cm.set_config("ai_api_key", "")

    client = OpenAIClient()

    # 测试未配置时的行为
    results = client.test_api_capabilities()

    assert not results["json_mode_supported"], "未配置时应该返回不支持"
    assert not results["structured_output_supported"], "未配置时应该返回不支持"
    assert not results["function_calling_supported"], "未配置时应该返回不支持"
    assert "error" in results, "未配置时应该包含错误信息"

    print("✅ API功能测试方法正常工作")


def main():
    """主测试函数"""
    print("🚀 开始测试OpenAI客户端多种输出格式支持...")
    print("=" * 60)

    try:
        test_output_format_configuration()
        test_prompt_instructions()
        test_api_capabilities_method()

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！OpenAI客户端多种输出格式支持功能正常")

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
