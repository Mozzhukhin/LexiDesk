from __future__ import annotations

import argparse
import sqlite3
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from .backup import ensure_daily_backup
from .batch import BatchAddDialog
from .config import APP_ID, APP_NAME, database_path, settings_path
from .database import WordRepository
from .dialogs import AddWordDialog
from .insights import AnalyticsDialog
from .library import LibraryDialog
from .service_client import schedule_example_enrichment
from .settings import SettingsStore
from .themes import stylesheet
from .translation import OfflineTranslator
from .window import LexiDeskWindow


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LexiDesk vocabulary companion")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--add", action="store_true", help="Open only the add-card dialog"
    )
    mode.add_argument(
        "--add-clipboard",
        action="store_true",
        help="Add the current clipboard text",
    )
    mode.add_argument(
        "--library", action="store_true", help="Open only the vocabulary library"
    )
    mode.add_argument("--edit", type=int, metavar="ID", help="Edit a vocabulary card")
    mode.add_argument(
        "--batch",
        action="store_true",
        help="Open the batch vocabulary importer",
    )
    mode.add_argument(
        "--analytics",
        action="store_true",
        help="Open learning analytics",
    )
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName(APP_ID)
    app.setQuitOnLastWindowClosed(True)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)

    settings_store = SettingsStore(settings_path())
    settings = settings_store.load()
    repository = WordRepository(
        database_path(), desired_retention=settings.desired_retention
    )
    ensure_daily_backup(repository)
    translator = OfflineTranslator(autocorrect=settings.autocorrect)

    if arguments.add or arguments.add_clipboard:
        initial_text = app.clipboard().text() if arguments.add_clipboard else ""
        add_dialog = AddWordDialog(translator, initial_text=initial_text)
        add_dialog.setStyleSheet(stylesheet(settings.theme, settings.font_scale))
        result = add_dialog.exec()
        if (
            result == add_dialog.DialogCode.Accepted
            and add_dialog.word_data is not None
        ):
            try:
                word_id = repository.add_word(**add_dialog.word_data)
                schedule_example_enrichment(word_id)
            except Exception as error:
                QMessageBox.warning(None, "Could not save card", str(error))
        repository.close()
        return 0

    if arguments.library:
        library_dialog = LibraryDialog(
            repository,
            translator,
            daily_goal=settings.daily_goal,
        )
        library_dialog.setStyleSheet(stylesheet(settings.theme, settings.font_scale))
        library_dialog.exec()
        repository.close()
        return 0

    if arguments.edit is not None:
        try:
            word = repository.get_word(arguments.edit)
        except KeyError:
            QMessageBox.warning(None, "Card not found", "That card no longer exists.")
            repository.close()
            return 1
        edit_dialog = AddWordDialog(translator, word=word)
        edit_dialog.setStyleSheet(stylesheet(settings.theme, settings.font_scale))
        if (
            edit_dialog.exec() == edit_dialog.DialogCode.Accepted
            and edit_dialog.word_data is not None
        ):
            try:
                repository.update_word(word.id, **edit_dialog.word_data)
                schedule_example_enrichment(word.id)
            except sqlite3.IntegrityError:
                QMessageBox.warning(None, "Could not save card", "This card exists.")
        repository.close()
        return 0

    if arguments.batch:
        batch_dialog = BatchAddDialog(repository, translator)
        batch_dialog.setStyleSheet(stylesheet(settings.theme, settings.font_scale))
        batch_dialog.exec()
        repository.close()
        return 0

    if arguments.analytics:
        analytics_dialog = AnalyticsDialog(repository, settings.daily_goal)
        analytics_dialog.setStyleSheet(stylesheet(settings.theme, settings.font_scale))
        analytics_dialog.exec()
        repository.close()
        return 0

    window = LexiDeskWindow(repository, settings_store, translator)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
