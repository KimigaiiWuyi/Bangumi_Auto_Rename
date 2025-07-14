import json
from urllib.parse import urlparse
from typing import Any, Dict, Union

from ..utils.path import CONFIG_PATH

CONFIG_DEFAULT = {
    "api_key": "",
    "bangumi_path": "",
    "movie_path": "",
    "anime_path": "",
    "anime_movie_path": "",
    "mode": "链接",
    "docker_mnt": "/media",
    "ai_provider": "openai",
    "ai_api_key": "",
    "ai_base_url": "https://api.openai.com/v1",
    "ai_model": "gpt-4o-mini",
    "gemini_api_key": "",
    "gemini_base_url": "https://generativelanguage.googleapis.com",
    "gemini_model": "gemini-2.5-flash",
    "ai_enabled": False,
    "ai_confidence_threshold": "Medium",
    "openai_output_format": "function_calling",  # OpenAI输出格式选择
}

CN_MAP = {
    "api_key": "🔑 TMDB API密钥",
    "bangumi_path": "🎬 电视剧路径",
    "movie_path": "🎬 电影路径",
    "anime_path": "🎬 动漫路径",
    "anime_movie_path": "🎬 动漫电影路径",
    "mode": "💿 重命名模式",
    "docker_mnt": "📁 Docker挂载路径",
    "ai_provider": "🤖 AI提供商",
    "ai_api_key": "🤖 OpenAI API密钥",
    "ai_base_url": "🌐 OpenAI API地址",
    "ai_model": "🧠 OpenAI模型",
    "gemini_api_key": "💎 Gemini API密钥",
    "gemini_base_url": "🌐 Gemini API地址",
    "gemini_model": "💎 Gemini模型",
    "ai_enabled": "🚀 启用AI识别",
    "ai_confidence_threshold": "📊 AI置信度阈值",
    "openai_output_format": "🎯 OpenAI输出格式",
}


class ConfigManager:
    def __init__(self) -> None:
        if not CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'w', encoding='UTF-8') as file:
                json.dump(CONFIG_DEFAULT, file, indent=4, ensure_ascii=False)

        self.update_config()

    def write_config(self):
        # 使用缓存文件避免强行关闭造成文件损坏
        temp_file_path = CONFIG_PATH.parent / f'{CONFIG_PATH.name}.bak'

        if temp_file_path.exists():
            temp_file_path.unlink()

        with open(temp_file_path, 'w', encoding='UTF-8') as file:
            json.dump(self.config, file, indent=4, ensure_ascii=False)

        CONFIG_PATH.unlink()
        temp_file_path.rename(CONFIG_PATH)

    def update_config(self):
        # 打开config.json
        with open(CONFIG_PATH, 'r', encoding='UTF-8') as f:
            self.config: Dict[str, Any] = json.load(f)
        # 对没有的值，添加默认值
        for key in CONFIG_DEFAULT:
            if key not in self.config:
                self.config[key] = CONFIG_DEFAULT[key]

        # 清空不存在的key
        for key in list(self.config.keys()):
            if key not in CONFIG_DEFAULT:
                del self.config[key]

        # 按照默认key排序
        self.config = {key: self.config[key] for key in CONFIG_DEFAULT}

        # 重新写回
        self.write_config()

    def get_config(self, key: str) -> str:
        if key in self.config:
            return self.config[key]
        elif key in CONFIG_DEFAULT:
            self.update_config()
            return self.config[key]
        else:
            return ''

    def set_config(self, key: str, value: Union[str, bool]) -> bool:
        if key in CONFIG_DEFAULT:
            # 对URL类型的配置项进行特殊处理
            if key.endswith('_base_url') and value and isinstance(value, str):
                value = self._normalize_url(value)

            # 设置值
            self.config[key] = value
            # 重新写回
            self.write_config()
            return True
        else:
            return False

    def _normalize_url(self, url: str) -> str:
        """
        标准化URL格式，去除结尾斜杠并验证有效性

        Args:
            url: 原始URL

        Returns:
            标准化后的URL
        """
        if not url:
            return url

        # 去除结尾的斜杠
        url = url.rstrip('/')

        # 如果没有协议，默认添加https
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        # 验证URL格式
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                raise ValueError("Invalid URL format")
        except Exception:
            # 如果URL无效，返回原始值让用户自己处理
            pass

        return url

    def validate_url(self, url: str) -> bool:
        """
        验证URL是否有效

        Args:
            url: 要验证的URL

        Returns:
            是否为有效URL
        """
        if not url:
            return True  # 空URL视为有效（使用默认值）

        try:
            parsed = urlparse(url)
            return bool(parsed.netloc and parsed.scheme in ('http', 'https'))
        except Exception:
            return False


cm = ConfigManager()
