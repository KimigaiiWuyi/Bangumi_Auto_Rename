# AI识别功能测试指南

## 概述

本测试脚本适配了最新的AI识别架构，支持OpenAI和Gemini双AI提供商，提供四种测试模式，并新增了测试用例保存和读取功能，便于快速测试和社区收集测试用例。

## 功能特性

### 🎯 支持的测试模式

1. **manual**: 手动模式 - 生成prompt供用户复制给LLM测试
2. **auto**: 自动模式 - 完整AI识别流程，不实际移动文件
3. **save**: 保存模式 - 将动漫信息和本地文件信息保存为JSON测试用例
4. **load**: 加载模式 - 从JSON文件加载测试用例进行AI分析

### 🤖 支持的AI提供商

- **OpenAI**: 支持GPT-4、GPT-3.5等模型，兼容OpenAI API格式
- **Gemini**: 支持Google Gemini系列模型，原生结构化输出

## 使用方法

### 前置条件

请先在web ui中或json配置文件中完成以下配置：

1. 配置TMDB API密钥
2. 配置AI提供商API密钥（OpenAI或Gemini）
3. 确保AI功能已启用

### 命令行参数

```bash
python tests/test_ai_recognition.py [选项]

必需参数:
  --mode {manual,auto,save,load}  测试模式

可选参数:
  --path PATH                     动漫文件路径 (manual/auto/save模式必需)
  --provider {openai,gemini}      AI提供商选择
  --json_mode {true,false}        强制设置OpenAI JSON模式
  --output OUTPUT                 保存测试用例的文件路径 (save模式必需)
  --input INPUT                   加载测试用例的文件路径 (load模式必需)
```

### 使用示例

#### 1. 手动模式测试

```bash
# 使用默认AI提供商
python tests/test_ai_recognition.py --mode manual --path "/path/to/anime"

# 指定使用Gemini
python tests/test_ai_recognition.py --mode manual --path "/path/to/anime" --provider gemini
```

手动模式会：
- 生成系统提示词和用户提示词
- 等待用户输入LLM响应
- 解析和验证响应结果
- 保存测试结果到文件

#### 2. 自动模式测试

```bash
# 使用OpenAI进行完整测试
python tests/test_ai_recognition.py --mode auto --path "/path/to/anime" --provider openai

# 使用Gemini进行测试
python tests/test_ai_recognition.py --mode auto --path "/path/to/anime" --provider gemini
```

自动模式会：
- 自动调用AI API进行分析
- 显示完整的分析结果
- 模拟文件重命名操作
- 保存详细的测试结果

#### 3. 保存测试用例

```bash
# 保存测试用例到JSON文件
python tests/test_ai_recognition.py --mode save --path "/path/to/anime" --output test_case.json
```

保存模式会：
- 收集动漫信息和本地文件信息
- 分析视频文件元数据
- 保存为标准化的JSON格式
- 便于后续重复测试

#### 4. 加载测试用例

```bash
# 从JSON文件加载测试用例
python tests/test_ai_recognition.py --mode load --input test_case.json --provider gemini

# 对比不同AI提供商的结果
python tests/test_ai_recognition.py --mode load --input test_case.json --provider openai
```

加载模式会：
- 从JSON文件读取测试用例
- 使用指定的AI提供商进行分析
- 显示分析结果并保存
- 支持批量测试和对比

## 测试用例格式

测试用例采用JSON格式，包含以下结构：

```json
{
  "metadata": {
    "created_at": "创建时间",
    "source_path": "原始路径",
    "anime_name": "动漫名称",
    "description": "描述信息",
    "file_count": "文件数量",
    "total_size_mb": "总大小(MB)"
  },
  "anime_info": {
    "TMDB动漫信息": "包含季度、剧集等详细信息"
  },
  "local_files": [
    {
      "filename": "文件名",
      "path": "相对路径",
      "size": "文件大小",
      "duration": "时长(分钟)"
    }
  ]
}
```

AI分析结果会单独保存为另一个JSON文件，包含完整的分析结果和置信度信息。

## 输出文件

### 输出文件说明

#### 测试用例文件 (save模式)
- 文件名：用户指定的输出文件名
- 内容：动漫信息和本地文件信息，不包含AI分析结果

#### AI分析结果文件 (manual/auto/load模式)
- 手动模式: `ai_manual_test_result_{provider}_{timestamp}.json`
- 自动模式: `ai_auto_test_result_{provider}_{timestamp}.json`
- 加载模式: `ai_test_result_{provider}_{timestamp}.json`

#### 结果文件内容

AI分析结果文件包含：
- **测试元数据**：模式、提供商、时间戳等
- **动漫信息和本地文件信息**：TMDB数据和文件列表
- **AI分析结果**：季度映射、文件映射、置信度等
- **文件映射分析报告**：
  - `original_file_count`: 原始文件总数
  - `ai_mapped_count`: AI映射的文件数
  - `successfully_mapped`: 成功映射的文件列表
  - `missed_by_ai`: AI遗漏的文件列表
  - `ai_generated_extra`: AI生成的多余路径列表
  - `mapping_accuracy`: 映射准确率 (0.0-1.0)
- **原始LLM响应**（手动模式）

## 期待社区贡献

### 1. 提供多样的测试用例

- 使用save模式收集各种类型的动漫测试用例
- 包含不同的文件结构和命名规则
- 覆盖多季度、OVA、特典等复杂情况
- 本地分季规则与TMDB不符的情况

### 2. 不同AI模型对比

- 使用相同测试用例对比不同AI模型
- 分析各提供商的优势和局限性
- 记录置信度和准确性差异

## 故障排除

### 常见问题

1. **AI功能未启用**: 检查配置文件中的ai_enabled设置
2. **API密钥未配置**: 确保正确配置对应AI提供商的API密钥
3. **网络连接问题**: 检查API地址和网络连接
4. **文件路径错误**: 确保指定的路径存在且包含视频文件

### 调试技巧

- 使用manual模式检查生成的prompt是否正确
- 使用manual模式在AI提供商的web UI上快速测试prompt
- 查看详细的日志输出了解错误原因
- 使用save模式保存问题用例便于重现
- 对比不同AI模型的分析结果

## 文件映射分析

### 分析功能

脚本会自动分析AI识别结果的准确性，提供详细的映射分析报告：

#### 📊 统计信息
- **原始文件总数**：输入的视频文件数量
- **AI映射文件数**：AI识别并映射的文件数量
- **映射准确率**：成功映射文件数 / 原始文件总数

#### ✅ 成功映射
显示AI正确识别并映射的文件列表，这些文件的路径在原始文件中存在且被AI正确处理。

#### ❌ AI遗漏
显示原始文件中存在但AI未能识别或映射的文件，可能原因：
- 文件名格式特殊，AI无法解析
- 文件为非标准剧集（如PV、CM等）
- AI模型的识别能力和推理能力限制

#### ⚠️ AI生成的额外路径
显示AI生成的文件路径但在原始文件中不存在的情况，可能原因：
- AI对文件路径的理解有误
- AI生成时出现幻觉
- 输入数据中的路径信息不准确

### 使用建议
映射准确性仅供参考，大量遗漏为正常情况，因为可能存在大量CM、IV、PV、OP、ED等非剧集内容。
实际准确性需要人工检查。

## 示例文件

项目提供了示例测试用例文件 `example_test_case.json`，展示了标准的JSON格式和数据结构，可作为创建自定义测试用例的参考。该文件只包含动漫信息和本地文件信息，AI分析结果会在测试时单独生成和保存。
