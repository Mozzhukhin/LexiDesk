from __future__ import annotations

import sys
from pathlib import Path

from lexidesk.autostart import set_autostart
from lexidesk.config import autostart_path, data_dir, dictionary_path
from lexidesk.service_client import request_service


def test_windows_does_not_try_to_load_dbus(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    assert request_service({"command": "stats"}) is None


def test_windows_autostart_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert autostart_path() == (
        tmp_path
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / "LexiDesk.cmd"
    )


def test_windows_autostart_script(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "LexiDesk.cmd"
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr("lexidesk.autostart.autostart_path", lambda: path)

    set_autostart(True)
    content = path.read_text(encoding="utf-8")
    assert content.startswith('@start "" ')
    assert "lexidesk.main" in content

    set_autostart(False)
    assert not path.exists()


def test_data_directory_override(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "language-data"
    monkeypatch.setenv("LEXIDESK_DATA_DIR", str(target))

    assert data_dir() == target
    assert target.is_dir()


def test_bundled_dictionary_is_fallback(monkeypatch, tmp_path: Path) -> None:
    user_data = tmp_path / "user"
    bundled_data = tmp_path / "bundle"
    bundled_dictionary = bundled_data / "LexiDesk" / "freedict-en-ru.db"
    bundled_dictionary.parent.mkdir(parents=True)
    bundled_dictionary.touch()
    monkeypatch.setenv("LEXIDESK_DATA_DIR", str(user_data))
    monkeypatch.setattr(
        "lexidesk.config.bundled_language_data_dir",
        lambda: bundled_data,
    )

    assert dictionary_path() == bundled_dictionary
