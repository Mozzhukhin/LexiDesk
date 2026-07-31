from __future__ import annotations

import argparse
import sqlite3
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from .autostart import set_autostart
from .backup import ensure_daily_backup
from .batch import BatchAddDialog
from .config import APP_ID, APP_NAME, database_path, settings_path
from .database import WordRepository
from .diagnostics import configure_logging
from .dialogs import AddWordDialog, DeckSelectionDialog, SettingsDialog
from .insights import AnalyticsDialog
from .language_dialog import LanguagePackagesDialog
from .library import LibraryDialog
from .service_client import request_service, schedule_example_enrichment
from .settings import SettingsStore
from .support import SupportDialog
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
        "--delete", type=int, metavar="ID", help="Delete a vocabulary card"
    )
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
    mode.add_argument(
        "--settings",
        action="store_true",
        help="Open only the application settings",
    )
    mode.add_argument(
        "--support",
        action="store_true",
        help="Open the developer support page",
    )
    mode.add_argument(
        "--languages",
        action="store_true",
        help="Manage downloadable offline language packages",
    )
    mode.add_argument(
        "--decks",
        action="store_true",
        help="Choose the active language deck",
    )
    mode.add_argument(
        "--self-test",
        action="store_true",
        help="Verify the bundled offline translation runtime and exit",
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    arguments = _arguments()
    if arguments.self_test:
        translator = OfflineTranslator()
        for text in ("This is a practical suggestion.", "Это полезное предложение."):
            if not translator.translate(text).translation:
                return 1
        return 0
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
                settings.active_source_language = str(
                    add_dialog.word_data["source_lang"]
                )
                settings.active_target_language = str(
                    add_dialog.word_data["target_lang"]
                )
                settings_store.save(settings)
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
            active_pair=(
                settings.active_source_language,
                settings.active_target_language,
            ),
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

    if arguments.delete is not None:
        try:
            word = repository.get_word(arguments.delete)
        except KeyError:
            QMessageBox.warning(None, "Card not found", "That card no longer exists.")
            repository.close()
            return 1
        answer = QMessageBox.question(
            None,
            "Delete card",
            f"Delete “{word.source_text}” and its review history?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            repository.delete_word(word.id)
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

    if arguments.settings:
        settings_dialog = SettingsDialog(settings)
        settings_dialog.setStyleSheet(stylesheet(settings.theme, settings.font_scale))
        if settings_dialog.exec() == settings_dialog.DialogCode.Accepted:
            settings_dialog.apply_to(settings)
            settings_store.save(settings)
            set_autostart(settings.autostart)
            request_service(
                {
                    "command": "configure",
                    "desired_retention": settings.desired_retention,
                }
            )
        repository.close()
        return 0

    if arguments.support:
        support_dialog = SupportDialog()
        support_dialog.setStyleSheet(stylesheet(settings.theme, settings.font_scale))
        support_dialog.exec()
        repository.close()
        return 0

    if arguments.languages:
        language_dialog = LanguagePackagesDialog()
        language_dialog.setStyleSheet(stylesheet(settings.theme, settings.font_scale))
        language_dialog.exec()
        repository.close()
        return 0

    if arguments.decks:
        deck_dialog = DeckSelectionDialog(
            repository.language_pairs(),
            (
                settings.active_source_language,
                settings.active_target_language,
            ),
        )
        deck_dialog.setStyleSheet(stylesheet(settings.theme, settings.font_scale))
        if (
            deck_dialog.exec() == deck_dialog.DialogCode.Accepted
            and deck_dialog.selected_pair is not None
        ):
            (
                settings.active_source_language,
                settings.active_target_language,
            ) = deck_dialog.selected_pair
            settings_store.save(settings)
        repository.close()
        return 0

    window = LexiDeskWindow(repository, settings_store, translator)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
