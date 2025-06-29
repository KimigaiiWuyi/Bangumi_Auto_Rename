import json
from typing import Any, Dict

from ..utils.path import CONFIG_PATH

CONFIG_DEFAULT = {
    "api_key": "",
    "bangumi_path": "",
    "movie_path": "",
    "anime_path": "",
    "anime_movie_path": "",
    "mode": "链接",
    "docker_mnt": "/media",
    "ai_api_key": "",
    "ai_base_url": "https://api.openai.com/v1",
    "ai_model": "gpt-4o-mini",
    "ai_enabled": False,
    "ai_confidence_threshold": "Medium",
    "OPENAI_JSON_MODE": False,
}

CN_MAP = {
    "api_key": "🔑 TMDB API密钥",
    "bangumi_path": "🎬 电视剧路径",
    "movie_path": "🎬 电影路径",
    "anime_path": "🎬 动漫路径",
    "anime_movie_path": "🎬 动漫电影路径",
    "mode": "💿 重命名模式",
    "docker_mnt": "📁 Docker挂载路径",
    "ai_api_key": "🤖 AI API密钥",
    "ai_base_url": "🌐 AI API地址",
    "ai_model": "🧠 AI模型",
    "ai_enabled": "🚀 启用AI识别",
    "ai_confidence_threshold": "📊 AI置信度阈值",
    "OPENAI_JSON_MODE": "🤖 OpenAI JSON 模式",
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

    def set_config(self, key: str, value: str) -> bool:
        if key in CONFIG_DEFAULT:
            # 设置值
            self.config[key] = value
            # 重新写回
            self.write_config()
            return True
        else:
            return False


cm = ConfigManager()
