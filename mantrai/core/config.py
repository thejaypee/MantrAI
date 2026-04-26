from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG = {
    "db_path": "~/.mantrai/sessions.db",
    "mantra_path": None,
    "default_level": "normal",
    "strict_threshold": 1,
    "normal_threshold": 5,
    "compliance_window_minutes": 5,
    "mempalace_enabled": False,
    "contextual_mode": True,
}


def get_config_path() -> Path:
    return Path("~/.mantrai/config.json").expanduser()


def load_config() -> dict:
    path = get_config_path()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        merged.update(loaded)
        return merged
    return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_db_path(config: Optional[dict] = None) -> Path:
    cfg = config or load_config()
    return Path(cfg.get("db_path", DEFAULT_CONFIG["db_path"])).expanduser()
