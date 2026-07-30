from __future__ import annotations

import os
import sys
from pathlib import Path

from platformdirs import user_config_path, user_data_path

APP_NAME = "LexiDesk"
APP_ID = "io.github.lexidesk"


def data_dir() -> Path:
    override = os.environ.get("LEXIDESK_DATA_DIR")
    if override:
        path = Path(override)
        path.mkdir(parents=True, exist_ok=True)
        return path
    path = user_data_path(APP_NAME, ensure_exists=True)
    return Path(path)


def config_dir() -> Path:
    path = user_config_path(APP_NAME, ensure_exists=True)
    return Path(path)


def database_path() -> Path:
    return data_dir() / "lexidesk.db"


def dictionary_path() -> Path:
    return _data_file("freedict-en-ru.db")


def examples_path() -> Path:
    return _data_file("wordnet-examples.db")


def settings_path() -> Path:
    return config_dir() / "settings.json"


def autostart_path() -> Path:
    if sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA", config_dir()))
        return (
            appdata
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
            / "LexiDesk.cmd"
        )
    return Path.home() / ".config" / "autostart" / "lexidesk.desktop"


def bundled_language_data_dir() -> Path | None:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root is None:
        return None
    path = Path(frozen_root) / "language-data"
    return path if path.is_dir() else None


def _data_file(name: str) -> Path:
    user_file = data_dir() / name
    bundled = bundled_language_data_dir()
    bundled_file = bundled / APP_NAME / name if bundled is not None else None
    if not user_file.exists() and bundled_file is not None and bundled_file.exists():
        return bundled_file
    return user_file
