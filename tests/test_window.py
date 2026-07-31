from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from lexidesk.database import WordRepository
from lexidesk.settings import SettingsStore
from lexidesk.window import LexiDeskWindow


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _window(tmp_path: Path) -> tuple[LexiDeskWindow, WordRepository]:
    _application()
    repository = WordRepository(tmp_path / "widget.db")
    for source, target in (
        ("reliable", "надёжный"),
        ("careful", "осторожный"),
        ("useful", "полезный"),
        ("simple", "простой"),
    ):
        repository.add_word(
            source_text=source,
            source_lang="en",
            target_text=target,
        )
    settings_store = SettingsStore(tmp_path / "settings.json")
    window = LexiDeskWindow(repository, settings_store, object())  # type: ignore[arg-type]
    return window, repository


def test_standalone_translation_quiz_records_fsrs_review(tmp_path: Path) -> None:
    window, repository = _window(tmp_path)
    window.current_word = repository.get_word(1)
    window.set_practice_mode("translation")
    assert window._current_quiz is not None

    window.choose_answer(str(window._current_quiz["answer"]))
    window.advance_timer.stop()

    assert repository.get_word(1).know_count == 1
    assert window.answer_feedback.text() == "Correct"
    window.tick_timer.stop()
    repository.close()


def test_standalone_keeps_english_above_russian(tmp_path: Path) -> None:
    _application()
    repository = WordRepository(tmp_path / "russian.db")
    word_id = repository.add_word(
        source_text="ограниченный",
        source_lang="ru",
        target_text="restricted",
    )
    window = LexiDeskWindow(
        repository,
        SettingsStore(tmp_path / "settings.json"),
        object(),  # type: ignore[arg-type]
    )
    window.current_word = repository.get_word(word_id)
    window._render_card()

    assert window.word_label.text() == "restricted"
    assert window.translation_label.text() == "ограниченный"
    window.tick_timer.stop()
    repository.close()


def test_standalone_uses_mouse_only_next_and_compact_progress(tmp_path: Path) -> None:
    window, repository = _window(tmp_path)
    window.tick_timer.stop()

    assert window.next_button.shortcut().isEmpty()
    assert not hasattr(window, "undo_review")
    assert window.countdown_progress.isTextVisible() is False
    assert "until the next card" in window.countdown_progress.toolTip()
    assert window.direction_label.toolTip() == "Choose language deck"
    assert window.direction_label.text().endswith("▾")

    repository.close()


def test_standalone_mixed_mode_guarantees_a_quiz(tmp_path: Path) -> None:
    window, repository = _window(tmp_path)
    window.settings.practice_mode = "mixed"
    word_id = repository.add_word(
        source_text="steady",
        source_lang="en",
        target_text="стабильный",
    )
    window.current_word = repository.review(word_id, "good")
    variants = {"translation": {"type": "translation", "answer": "стабильный"}}

    for _ in range(4):
        assert window._practice_for_card(variants) == "off"
    assert window._practice_for_card(variants) == "translation"
    assert window._mixed_dry_streak == 0

    window.tick_timer.stop()
    repository.close()


def test_rotation_skips_an_unanswered_quiz(tmp_path: Path) -> None:
    window, repository = _window(tmp_path)
    window.tick_timer.stop()
    window.current_word = repository.get_word(1)
    window.set_practice_mode("translation")
    previous_id = window.current_word.id
    assert window._current_quiz is not None

    window.seconds_left = 1
    window._tick()

    assert window.current_word is not None
    assert window.current_word.id != previous_id
    skipped = repository.get_word(previous_id)
    assert skipped.know_count == 0
    assert skipped.dont_know_count == 0
    repository.close()


def test_fixed_quiz_mode_never_falls_back_to_a_normal_card(tmp_path: Path) -> None:
    window, repository = _window(tmp_path)
    window.tick_timer.stop()
    window.current_word = repository.get_word(1)

    window.set_practice_mode("cloze")

    assert window._current_quiz is None
    assert window.word_label.text() == "No suitable card for this quiz yet"
    assert window.translation_label.isHidden()
    assert "mode selected" in window.quiz_instruction.text()
    assert window.settings.practice_mode == "cloze"
    repository.close()
