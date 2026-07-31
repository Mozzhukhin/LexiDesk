from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication

import lexidesk.diagnostics as diagnostics
import lexidesk.diagnostics_dialog as diagnostics_dialog
from lexidesk.database import WordRepository


def test_diagnostic_report_lists_runtime_state(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "lexidesk.db"
    database.touch()
    monkeypatch.setattr(diagnostics, "database_path", lambda: database)
    monkeypatch.setattr(diagnostics, "dictionary_path", lambda: tmp_path / "dict.db")
    monkeypatch.setattr(diagnostics, "examples_path", lambda: tmp_path / "examples.db")
    monkeypatch.setattr(
        diagnostics,
        "settings_path",
        lambda: tmp_path / "settings.json",
    )
    monkeypatch.setattr(diagnostics.shutil, "which", lambda _name: "/bin/bridge")

    report = diagnostics.diagnostic_report("ok")

    assert "Database integrity: ok" in report
    assert f"Database: {database} (exists)" in report
    assert "Plasma bridge: /bin/bridge" in report
    assert "Dictionary:" in report and "(missing)" in report


def test_configure_logging_uses_rotating_local_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = tmp_path / "config" / "settings.json"
    monkeypatch.setattr(diagnostics, "settings_path", lambda: settings)
    root = logging.getLogger()
    previous = list(root.handlers)
    for handler in previous:
        root.removeHandler(handler)
    try:
        path = diagnostics.configure_logging()
        logging.getLogger("lexidesk.test").info("diagnostic test")
        for handler in root.handlers:
            handler.flush()
        assert path == settings.parent / "lexidesk.log"
        assert "diagnostic test" in path.read_text(encoding="utf-8")
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
            handler.close()
        for handler in previous:
            root.addHandler(handler)


def test_diagnostics_dialog_copies_report(
    tmp_path: Path,
    qapp: QApplication,
    monkeypatch,
) -> None:
    repository = WordRepository(tmp_path / "dialog.db")
    monkeypatch.setattr(
        diagnostics_dialog,
        "diagnostic_report",
        lambda integrity: f"integrity={integrity}",
    )
    monkeypatch.setattr(
        diagnostics_dialog,
        "log_path",
        lambda: tmp_path / "lexidesk.log",
    )
    dialog = diagnostics_dialog.DiagnosticsDialog(repository)

    dialog.copy_report()

    assert qapp.clipboard().text() == "integrity=ok"
    repository.close()
