import os
import json
import shutil
from typing import Dict
from pathlib import Path

from ..logger import logger
from ..utils.path import RECORD_PATH
from ..config.config_manager import cm


class Trans:
    def __init__(self, R: Dict[Path, Path], uuid: str) -> None:
        self.mode = cm.get_config('mode')
        self.R = R
        self.uuid = uuid

    def trans_file(self):
        path = RECORD_PATH / f'{self.uuid}.json'

        _R = {str(k): str(v) for k, v in self.R.items()}

        with open(str(path), 'w', encoding='utf-8') as f:
            json.dump(_R, f, ensure_ascii=False)

        for source_path, target_path in self.R.items():
            try:
                if target_path.is_dir() or source_path.is_dir():
                    continue
                # 提前创建目的目录
                target_path.parent.mkdir(parents=True, exist_ok=True)
                if not target_path.parent.exists():
                    target_path.parent.mkdir(parents=True)
                if self.mode == '剪切':
                    shutil.move(source_path, target_path)
                elif self.mode == '复制':
                    shutil.copy(source_path, target_path)
                elif self.mode == '链接':
                    try:
                        os.link(source_path, target_path)
                    except:  # noqa:E722
                        logger.warning('[处理迁移] 无法创建硬链接, 尝试软链接...')
                        os.symlink(source_path, target_path)
                else:
                    logger.error('[处理迁移] 模式错误！仅支持剪切, 复制, 链接')
            except Exception as e:
                logger.error(str(e))
                return str(e)
