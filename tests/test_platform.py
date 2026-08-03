from __future__ import annotations

import shlex
import sys
from pathlib import Path

from PySide6.QtCore import Qt

import lexidesk.service_client as service_client
from lexidesk.autostart import autostart_enabled, set_autostart
from lexidesk.config import autostart_path, data_dir, dictionary_path
from lexidesk.model_translation import translation_model_roots
from lexidesk.service_client import request_service
from lexidesk.window_behavior import clamp_widget_position, widget_window_flags


def test_windows_does_not_try_to_load_dbus(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    assert request_service({"command": "stats"}) is None


def test_example_enrichment_falls_back_without_dbus(monkeypatch) -> None:
    scheduled: list[int] = []
    monkeypatch.setattr(service_client, "request_service", lambda _request: None)
    monkeypatch.setattr(service_client, "_start_local_worker", lambda: None)
    monkeypatch.setattr(
        service_client._enrichment_queue,
        "put",
        scheduled.append,
    )

    assert service_client.schedule_example_enrichment(42) is True
    assert scheduled == [42]


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


def test_windows_installer_autostart_link_is_detected_and_removed(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "LexiDesk.cmd"
    installer_link = path.with_suffix(".lnk")
    installer_link.touch()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr("lexidesk.autostart.autostart_path", lambda: path)

    assert autostart_enabled() is True
    set_autostart(False)
    assert not installer_link.exists()


def test_appimage_autostart_uses_persistent_image(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "lexidesk.desktop"
    appimage = tmp_path / "LexiDesk.AppImage"
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("APPIMAGE", str(appimage))
    monkeypatch.setattr("lexidesk.autostart.autostart_path", lambda: path)

    set_autostart(True)

    assert f"Exec={shlex.join([str(appimage)])}" in path.read_text(encoding="utf-8")


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


def test_bundled_translation_models_are_cross_platform_fallback(
    monkeypatch, tmp_path: Path
) -> None:
    bundled = tmp_path / "language-data"
    expected = bundled / "argos-translate" / "packages"
    monkeypatch.setattr(
        "lexidesk.model_translation.bundled_language_data_dir",
        lambda: bundled,
    )
    monkeypatch.delenv("LEXIDESK_MODELS_DIR", raising=False)
    monkeypatch.delenv("ARGOS_PACKAGES_DIR", raising=False)

    assert expected in translation_model_roots()


def test_bundle_excludes_training_only_translation_dependencies() -> None:
    spec = (
        Path(__file__).parents[1] / "packaging" / "pyinstaller" / "lexidesk.spec"
    ).read_text(encoding="utf-8")

    for dependency in (
        "argostranslate",
        "numpy",
        "onnxruntime",
        "spacy",
        "stanza",
        "torch",
    ):
        assert f'"{dependency}"' in spec


def test_lite_release_does_not_bundle_language_data() -> None:
    root = Path(__file__).parents[1]
    spec = (root / "packaging" / "pyinstaller" / "lexidesk.spec").read_text(
        encoding="utf-8"
    )
    workflow = (root / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    assert "bundle-data" not in spec
    assert "language-data:" not in workflow
    assert "download-artifact" not in workflow or "name: language-data" not in workflow
    assert "LexiDesk-Lite-Linux-x86_64.AppImage" in workflow
    assert "LexiDesk-Lite-Windows-x64-portable.zip" in workflow


def test_desktop_widget_flags_are_interactive_and_stay_below() -> None:
    flags = widget_window_flags("desktop")

    assert flags & Qt.WindowType.Tool
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnBottomHint
    assert not flags & Qt.WindowType.WindowDoesNotAcceptFocus


def test_floating_widget_flags_stay_above() -> None:
    flags = widget_window_flags("floating")

    assert flags & Qt.WindowType.Tool
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert not flags & Qt.WindowType.WindowStaysOnBottomHint


def test_widget_position_is_clamped_to_the_available_desktop() -> None:
    assert clamp_widget_position(
        5000,
        -400,
        390,
        310,
        left=0,
        top=40,
        right=1919,
        bottom=1079,
    ) == (1530, 40)


def test_plasma_rotation_does_not_pause_for_an_unanswered_quiz() -> None:
    qml = (
        Path(__file__).parents[1]
        / "plasma"
        / "io.github.lexidesk"
        / "contents"
        / "ui"
        / "main.qml"
    ).read_text(encoding="utf-8")

    assert "if (choiceMode && !choiceAnswered)" not in qml
    assert 'root.launchGui("--support", "support")' in qml
