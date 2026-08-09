"""Application paths that remain stable across uvx upgrades."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from platformdirs import user_config_path, user_data_path

APP_NAME = "letterboxd-stats"
DATA_DIR_ENV = "LETTERBOXD_STATS_DATA_DIR"


def data_dir() -> Path:
    override = os.getenv(DATA_DIR_ENV)
    path = (
        Path(override).expanduser()
        if override
        else user_data_path(APP_NAME, ensure_exists=True)
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_dir() -> Path:
    override = os.getenv(DATA_DIR_ENV)
    path = (
        Path(override).expanduser()
        if override
        else user_config_path(APP_NAME, ensure_exists=True)
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return data_dir() / "letterboxd.db"


def config_path() -> Path:
    return config_dir() / "config.json"


def migrate_legacy_database(search_dir: Path | None = None) -> bool:
    """Copy a legacy project-local database on first launch, without deleting it."""
    if os.getenv(DATA_DIR_ENV):
        # An explicit directory is normally a test, portable, or advanced-user profile.
        return False
    destination = database_path()
    if destination.exists():
        return False
    source = (search_dir or Path.cwd()) / "letterboxd.db"
    if not source.is_file() or source.resolve() == destination.resolve():
        return False
    shutil.copy2(source, destination)
    return True
