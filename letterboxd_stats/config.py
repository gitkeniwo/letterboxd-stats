"""Small local configuration store."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from .paths import config_path


@dataclass
class AppConfig:
    tmdb_api_key: str = ""


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        return AppConfig(
            tmdb_api_key=os.getenv("TMDB_API_KEY", os.getenv("API_KEY", ""))
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppConfig(tmdb_api_key=str(data.get("tmdb_api_key", "")))
    except (OSError, ValueError, TypeError):
        return AppConfig()


def save_config(config: AppConfig) -> None:
    path = config_path()
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        # Windows and some network filesystems do not implement POSIX modes.
        pass
