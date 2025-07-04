#!/usr/bin/env python3
"""
OpenAI API功能测试脚本

测试OpenAI兼容API的各种格式化输出功能支持情况：
- JSON Mode (response_format={"type": "json_object"})
- Structured Output (response_format={"type": "json_schema"})
- Function Calling (tools参数)

使用方法：
python test_openai_api_features.py --api-key YOUR_API_KEY [--base-url YOUR_BASE_URL] [--model YOUR_MODEL]
"""

import json
import re
import argparse
from typing import Optional
from openai import OpenAI
from pydantic import BaseModel


def extract_json(text: str) -> str:
    """从文本中提取第一个 JSON 对象字符串"""
    # 首先尝试直接解析
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass
    
    # 使用正则表达式提取JSON
    match = re.search(r"(\{.*\})", text, re.S)
    if match:
        return match.group(1)
    raise ValueError("未在文本中找到 JSON 对象")


class TestResults:
    """测试结果类"""
    def __init__(self):
        self.json_mode_supported = False
        self.structured_output_supported = False
        self.function_calling_supported = False
        self.errors = []


class StudentInfo(BaseModel):
    """用于测试结构化输出的Pydantic模型"""
    name: str
    age: Optional[int] = None
    major: Optional[str] = None
    university: Optional[str] = None
    gpa: Optional[float] = None


def test_openai_api_features(api_key: str, base_url: str = None, model: str = "gpt-4o-mini") -> TestResults:
    """
    测试OpenAI兼容API的功能支持情况
    
    Args:
        api_key: API密钥
        base_url: API基础URL，如果不是OpenAI官方API则需要提供
        model: 要测试的模型名称
        
    Returns:
        TestResults对象，包含测试结果
    """
    # 初始化客户端
    client_config = {"api_key": api_key}
    if base_url:
        client_config["base_url"] = base_url
    
    client = OpenAI(**client_config)
    results = TestResults()
    
    print("🚀 开始测试OpenAI兼容API功能...")
    print("=" * 50)
    print(f"📋 测试配置:")
    print(f"   模型: {model}")
    print(f"   API地址: {base_url or 'https://api.openai.com/v1'}")
    print("=" * 50)
    
    # 测试1: JSON Mode
    print("\n📝 测试1: JSON Mode支持")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个有用的助手，请以JSON格式回复，遵守以下JSON schema:\n```json\n{\"type\":\"object\",\"properties\":{\"name\":{\"type\":\"string\"},\"age\":{\"type\":\"integer\"},\"major\":{\"type\":\"string\"}},\"required\":[\"name\",\"age\",\"major\"],\"additionalProperties\":false}\n```"},
                {"role": "user", "content": "请提取以下信息并以JSON格式返回：姓名、年龄、专业。文本：张三是一名21岁的计算机科学专业学生。"}
            ],
            response_format={"type": "json_object"},
            temperature=0
        )
        
        # 尝试解析JSON（先提取可能的 JSON 子串）
        raw = response.choices[0].message.content
        json_str = extract_json(raw)
        json_content = json.loads(json_str)
        results.json_mode_supported = True
        print("✅ JSON Mode: 支持")
        print(f"   响应内容: {json_content}")
        
    except Exception as e:
        results.errors.append(f"JSON Mode测试失败: {str(e)}")
        print(f"❌ JSON Mode: 不支持 - {str(e)}")
        if 'response' in locals():
            print(f"   响应内容: {response.choices[0].message.content}")
    
    # 测试2: Structured Output (使用新的API格式)
    print("\n🏗️ 测试2: Structured Output支持")
    try:
        # 尝试使用新的structured output API
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "从给定文本中提取学生信息。"},
                {"role": "user", "content": "李华是北京大学计算机科学专业的大二学生，今年20岁，GPA为3.8。"}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "student_info",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                            "major": {"type": "string"},
                            "university": {"type": "string"},
                            "gpa": {"type": "number"}
                        },
                        "required": ["name"],
                        "additionalProperties": False
                    }
                }
            },
            temperature=0
        )
        
        # 尝试解析结构化 JSON 输出
        raw2 = response.choices[0].message.content
        json_str2 = extract_json(raw2)
        parsed_content = json.loads(json_str2)
        results.structured_output_supported = True
        print("✅ Structured Output: 支持")
        print(f"   结构化数据: {parsed_content}")
        
    except Exception as e:
        results.errors.append(f"Structured Output测试失败: {str(e)}")
        print(f"❌ Structured Output: 不支持 - {str(e)}")
        if 'response' in locals():
            print(f"   响应内容: {response.choices[0].message.content}")
    
    # 测试3: Function Calling
    print("\n🔧 测试3: Function Calling支持")
    try:
        # 定义测试函数
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "获取指定城市的天气信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "城市名称，例如：北京、上海"
                            },
                            "unit": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"],
                                "description": "温度单位"
                            }
                        },
                        "required": ["city"],
                        "additionalProperties": False
                    }
                }
            }
        ]
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "请帮我查询北京今天的天气情况"}
            ],
            tools=tools,
            tool_choice="auto",
            temperature=0
        )
        
        # 检查是否有函数调用
        if response.choices[0].message.tool_calls:
            results.function_calling_supported = True
            print("✅ Function Calling: 支持")
            for tool_call in response.choices[0].message.tool_calls:
                print(f"   函数调用: {tool_call.function.name}")
                print(f"   参数: {tool_call.function.arguments}")
        else:
            print("❌ Function Calling: 模型未触发函数调用")
            print(f"   响应内容: {response.choices[0].message.content}")
            
    except Exception as e:
        results.errors.append(f"Function Calling测试失败: {str(e)}")
        print(f"❌ Function Calling: 不支持 - {str(e)}")
    
    return results


def print_summary(results: TestResults):
    """打印测试结果汇总"""
    print("\n" + "=" * 50)
    print("📊 测试结果汇总:")
    print(f"JSON Mode支持: {'✅' if results.json_mode_supported else '❌'}")
    print(f"Structured Output支持: {'✅' if results.structured_output_supported else '❌'}")
    print(f"Function Calling支持: {'✅' if results.function_calling_supported else '❌'}")
    
    if results.errors:
        print("\n⚠️ 错误详情:")
        for error in results.errors:
            print(f"   - {error}")
    
    # 推荐配置
    print("\n💡 推荐配置:")
    if results.function_calling_supported:
        print("   建议使用 Function Calling 模式（最稳定）")
    elif results.structured_output_supported:
        print("   建议使用 Structured Output 模式")
    elif results.json_mode_supported:
        print("   建议使用 JSON Object 模式")
    else:
        print("   建议使用 Text 模式（需要手动解析JSON）")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="测试OpenAI API功能支持情况")
    parser.add_argument("--api-key", required=True, help="OpenAI API密钥")
    parser.add_argument("--base-url", help="API基础URL（可选）")
    parser.add_argument("--model", default="gpt-4o-mini", help="模型名称（默认：gpt-4o-mini）")
    
    args = parser.parse_args()
    
    # 执行测试
    results = test_openai_api_features(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model
    )
    
    # 打印汇总
    print_summary(results)
    
    return results


if __name__ == "__main__":
    main()
