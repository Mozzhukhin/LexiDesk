from __future__ import annotations

import logging
import platform
import shutil
import sys
from importlib.metadata import PackageNotFoundError, version
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import database_path, dictionary_path, examples_path, settings_path


def log_path() -> Path:
    return settings_path().parent / "lexidesk.log"


def configure_logging() -> Path:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if not any(
        isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) == path
        for handler in root.handlers
    ):
        handler = RotatingFileHandler(
            path,
            maxBytes=1_000_000,
            backupCount=2,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root.addHandler(handler)
    root.setLevel(logging.INFO)
    return path


def diagnostic_report(integrity: str = "not checked") -> str:
    try:
        app_version = version("lexidesk")
    except PackageNotFoundError:
        app_version = "development"
    paths = {
        "Database": database_path(),
        "Dictionary": dictionary_path(),
        "Example index": examples_path(),
        "Settings": settings_path(),
        "Log": log_path(),
    }
    bridge = (
        shutil.which("lexidesk-bridge")
        or shutil.which("lexidesk-cli")
        or "not found in PATH"
    )
    lines = [
        f"LexiDesk: {app_version}",
        f"Python: {platform.python_version()}",
        f"Qt/Python executable: {sys.executable}",
        f"System: {platform.platform()}",
        f"Database integrity: {integrity}",
        f"Plasma bridge: {bridge}",
        "",
        "Data files:",
    ]
    for label, path in paths.items():
        state = "exists" if path.exists() else "missing"
        lines.append(f"- {label}: {path} ({state})")
    return "\n".join(lines)
