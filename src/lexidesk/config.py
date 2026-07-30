from __future__ import annotations

import os
import sys
from pathlib import Path

from platformdirs import user_config_path, user_data_path

APP_NAME = "LexiDesk"
APP_ID = "io.github.lexidesk"


def data_dir() -> Path:
    path = user_data_path(APP_NAME, ensure_exists=True)
    return Path(path)


def config_dir() -> Path:
    path = user_config_path(APP_NAME, ensure_exists=True)
    return Path(path)


def database_path() -> Path:
    return data_dir() / "lexidesk.db"


def dictionary_path() -> Path:
    return data_dir() / "freedict-en-ru.db"


def examples_path() -> Path:
    return data_dir() / "wordnet-examples.db"


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
