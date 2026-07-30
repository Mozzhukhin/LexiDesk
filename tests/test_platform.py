from __future__ import annotations

import sys
from pathlib import Path

from lexidesk.autostart import set_autostart
from lexidesk.config import autostart_path
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
