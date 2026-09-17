"""TUI 客户端配置

配置文件存储在 ~/.ask-tui/config.json
设备 ID 首次运行时自动生成。
"""

import json
import uuid
from pathlib import Path


CONFIG_DIR = Path.home() / ".ask-tui"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "api_base_url": "http://localhost:8000",
    "device_id": "",
    "username": "",
}


def load_config() -> dict:
    """加载配置，不存在则创建默认配置（含自动生成的 device_id）"""
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config = DEFAULT_CONFIG.copy()
        config["device_id"] = uuid.uuid4().hex
        save_config(config)
        return config

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        # 确保所有必需字段都存在
        for key, default in DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = default
        if not config.get("device_id"):
            config["device_id"] = uuid.uuid4().hex
            save_config(config)
        return config
    except (json.JSONDecodeError, IOError):
        config = DEFAULT_CONFIG.copy()
        config["device_id"] = uuid.uuid4().hex
        save_config(config)
        return config


def save_config(config: dict):
    """保存配置到文件"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
