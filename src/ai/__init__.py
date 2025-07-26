"""
AI模块 - 支持多种AI提供商的智能分析功能

包含以下组件：
- AIClient: AI客户端工厂类，根据配置选择合适的提供商
- OpenAIClient: OpenAI API客户端
- GeminiClient: Google Gemini API客户端
- AIAnalysisResult: AI分析结果数据模型
"""

from .client import AIClient
from .gemini_client import GeminiClient
from .openai_client import OpenAIClient
from .models import SeasonMapping, EpisodeMapping, AIAnalysisResult

__all__ = [
    "AIClient",
    "OpenAIClient",
    "GeminiClient",
    "AIAnalysisResult",
    "SeasonMapping",
    "EpisodeMapping",
]
