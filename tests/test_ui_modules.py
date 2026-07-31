from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from lexidesk.database import WordRepository
from lexidesk.dialogs import AddWordDialog, DeckSelectionDialog, SettingsDialog
from lexidesk.insights import AnalyticsDialog
from lexidesk.library import LibraryDialog
from lexidesk.settings import Settings
from lexidesk.translation import TranslationResult


class StubTranslator:
    def translate(self, _text: str) -> TranslationResult:
        return TranslationResult(
            "en",
            "ru",
            "надёжный",
            ("верный",),
            "adjective",
            True,
            corrected_source="reliable",
            spelling_suggestions=("reliable",),
        )

    def example_sentence(
        self,
        source: str,
        _language: str,
        _part_of_speech: str,
    ) -> str:
        return f"The result seemed {source} today."


def _reviewed_repository(path: Path) -> WordRepository:
    repository = WordRepository(path)
    word_id = repository.add_word(
        source_text="reliable",
        source_lang="en",
        target_text="надёжный",
        part_of_speech="adjective",
        tags=["work"],
    )
    repository.review(
        word_id,
        "again",
        quiz_type="translation",
        selected_answer="случайный",
        correct_answer="надёжный",
    )
    return repository


def test_settings_dialog_applies_every_value(qapp: QApplication) -> None:
    settings = Settings()
    dialog = SettingsDialog(settings)
    dialog.theme_combo.setCurrentText("Forest")
    dialog.reveal_combo.setCurrentIndex(dialog.reveal_combo.findData("quiz"))
    dialog.practice_combo.setCurrentIndex(dialog.practice_combo.findData("translation"))
    dialog.rotation_spin.setValue(120)
    dialog.daily_goal_spin.setValue(30)
    dialog.autostart_check.setChecked(True)

    dialog.apply_to(settings)

    assert settings.theme == "Forest"
    assert settings.reveal_mode == "quiz"
    assert settings.practice_mode == "translation"
    assert settings.rotation_seconds == 120
    assert settings.daily_goal == 30
    assert settings.autostart is True


def test_deck_selector_highlights_and_returns_active_pair(
    qapp: QApplication,
) -> None:
    dialog = DeckSelectionDialog(
        [("en", "ru"), ("ru", "uk")],
        ("ru", "uk"),
    )

    assert dialog.pair_combo.currentData() == ("ru", "uk")
    dialog._accept_pair()
    assert dialog.selected_pair == ("ru", "uk")


def test_add_dialog_applies_translation_and_builds_card(qapp: QApplication) -> None:
    translator = StubTranslator()
    dialog = AddWordDialog(translator, initial_text="relyable")  # type: ignore[arg-type]
    assert [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())] == [
        "Add word",
        "Languages",
    ]
    result = translator.translate("relyable")

    dialog._apply_translation(result, "relyable")
    assert dialog.source_edit.text() == "reliable"
    assert dialog.target_edit.text() == "надёжный"
    assert dialog.undo_correction_button.isVisibleTo(dialog)
    dialog.meaning_combo.setCurrentIndex(1)
    assert dialog.target_edit.text() == "верный"
    dialog.tags_edit.setText("work, important")
    dialog.forms_edit.setText("reliably, reliability")
    dialog._validate_and_accept()

    assert dialog.word_data is not None
    assert dialog.word_data["source_text"] == "reliable"
    assert dialog.word_data["target_text"] == "верный"
    assert dialog.word_data["tags"] == ["work", "important"]


def test_analytics_dialog_populates_all_tables(
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    repository = _reviewed_repository(tmp_path / "analytics.db")
    dialog = AnalyticsDialog(repository, daily_goal=5)

    assert "1 meanings" in dialog.summary.text()
    assert dialog.activity.rowCount() == 1
    assert dialog.difficult.rowCount() == 1
    assert dialog.quiz_types.rowCount() == 1
    assert dialog.confusions.rowCount() == 1
    repository.close()


def test_library_search_export_backup_and_delete(
    tmp_path: Path,
    qapp: QApplication,
    monkeypatch,
) -> None:
    repository = _reviewed_repository(tmp_path / "library.db")
    repository.add_word(
        source_text="спасибо",
        source_lang="ru",
        target_text="дякую",
        target_lang="uk",
    )
    dialog = LibraryDialog(
        repository,
        StubTranslator(),  # type: ignore[arg-type]
        active_pair=("ru", "uk"),
    )
    assert dialog.table.rowCount() == 1
    assert dialog.deck_filter.currentData() == ("ru", "uk")
    assert "1 cards" in dialog.stats_label.text()
    dialog.deck_filter.setCurrentIndex(0)
    assert dialog.table.rowCount() == 2
    dialog.search.setText("missing")
    assert dialog.table.rowCount() == 0
    dialog.search.clear()

    exported = tmp_path / "vocabulary.json"
    backup = tmp_path / "complete.db"
    save_paths = iter((str(exported), str(backup)))
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args: (next(save_paths), "LexiDesk JSON (*.json)"),
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )
    dialog.export_file()
    dialog.backup_database()
    assert exported.exists()
    assert backup.exists()

    dialog.table.selectRow(0)
    dialog.delete_selected()
    assert repository.count() == 1

    open_paths = iter((str(exported), str(backup)))
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args: (next(open_paths), "LexiDesk database (*.db)"),
    )
    dialog.import_file()
    assert repository.count() == 2

    dialog.table.selectRow(0)
    dialog.delete_selected()
    assert repository.count() == 1
    dialog.restore_database()
    assert repository.count() == 2
    repository.close()
