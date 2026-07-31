from __future__ import annotations

import logging
from contextlib import suppress
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .languages import language_label
from .models import Word
from .settings import Settings
from .themes import THEMES
from .translation import (
    OfflineTranslator,
    TranslationError,
    TranslationResult,
    detect_language,
)

logger = logging.getLogger(__name__)


class DeckSelectionDialog(QDialog):
    def __init__(
        self,
        pairs: list[tuple[str, str]],
        current_pair: tuple[str, str] = ("", ""),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose language deck")
        self.setMinimumWidth(390)
        self.selected_pair: tuple[str, str] | None = None

        title = QLabel("Language deck")
        title.setObjectName("heading")
        explanation = QLabel(
            "Only cards from the selected direction will appear in the widget. "
            "Other language pairs remain stored separately in your library."
        )
        explanation.setWordWrap(True)
        explanation.setObjectName("muted")
        self.pair_combo = QComboBox()
        for source, target in pairs:
            self.pair_combo.addItem(
                f"{language_label(source)}  ⇄  {language_label(target)}",
                (source, target),
            )
        current_source, current_target = sorted(current_pair)
        current_pair = current_source, current_target
        current_index = next(
            (
                index
                for index in range(self.pair_combo.count())
                if self.pair_combo.itemData(index) == current_pair
            ),
            0,
        )
        self.pair_combo.setCurrentIndex(current_index)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_pair)
        buttons.rejected.connect(self.reject)
        buttons.setEnabled(bool(pairs))

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(self.pair_combo)
        if not pairs:
            empty = QLabel("Add at least one card before choosing a deck.")
            empty.setObjectName("muted")
            layout.addWidget(empty)
        layout.addWidget(buttons)

    def _accept_pair(self) -> None:
        value = self.pair_combo.currentData()
        if not isinstance(value, tuple) or len(value) != 2:
            return
        self.selected_pair = (str(value[0]), str(value[1]))
        self.accept()


class TranslationWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        translator: OfflineTranslator,
        text: str,
        source_language: str = "",
        target_language: str = "",
    ) -> None:
        super().__init__()
        self.translator = translator
        self.text = text
        self.source_language = source_language
        self.target_language = target_language

    def run(self) -> None:
        try:
            self.completed.emit(
                self.translator.translate(
                    self.text,
                    self.source_language,
                    self.target_language,
                )
            )
        except TranslationError as error:
            self.failed.emit(str(error))
        except Exception:
            logger.exception("Unexpected offline translation failure")
            self.failed.emit(
                "The offline translator failed unexpectedly. Open Diagnostics "
                "from the menu to find the log file."
            )


class AddWordDialog(QDialog):
    def __init__(
        self,
        translator: OfflineTranslator,
        parent: QWidget | None = None,
        word: Word | None = None,
        initial_text: str = "",
    ) -> None:
        super().__init__(parent)
        self.translator = translator
        self.word_data: dict[str, Any] | None = None
        self._correction_original = ""
        self._translation_worker: TranslationWorker | None = None
        self.setWindowTitle("Add a word or phrase")
        self.setMinimumWidth(500)

        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Word or phrase")
        self.source_edit.returnPressed.connect(self.translate)

        self.translate_button = QPushButton("Translate offline")
        self.translate_button.clicked.connect(self.translate)

        source_row = QHBoxLayout()
        source_row.addWidget(self.source_edit, 1)
        source_row.addWidget(self.translate_button)
        source_widget = QWidget()
        source_widget.setLayout(source_row)

        self.source_language = QComboBox()
        self.target_language = QComboBox()
        self._refresh_language_selectors()
        language_row = QHBoxLayout()
        language_row.addWidget(self.source_language, 1)
        language_row.addWidget(QLabel("→"))
        language_row.addWidget(self.target_language, 1)
        language_widget = QWidget()
        language_widget.setLayout(language_row)

        self.direction_label = QLabel("Language is detected automatically")
        self.direction_label.setObjectName("muted")
        self.undo_correction_button = QPushButton("Undo correction")
        self.undo_correction_button.clicked.connect(self.undo_correction)
        self.undo_correction_button.hide()
        direction_row = QHBoxLayout()
        direction_row.addWidget(self.direction_label, 1)
        direction_row.addWidget(self.undo_correction_button)
        direction_widget = QWidget()
        direction_widget.setLayout(direction_row)
        self.spelling_suggestions = QComboBox()
        self.use_suggestion_button = QPushButton("Use suggestion")
        self.use_suggestion_button.clicked.connect(self.use_spelling_suggestion)
        spelling_row = QHBoxLayout()
        spelling_row.addWidget(self.spelling_suggestions, 1)
        spelling_row.addWidget(self.use_suggestion_button)
        spelling_widget = QWidget()
        spelling_widget.setLayout(spelling_row)
        spelling_widget.hide()
        self.spelling_widget = spelling_widget
        self.target_edit = QLineEdit()
        self.target_edit.setPlaceholderText("Translation (you can correct it)")
        self.meaning_combo = QComboBox()
        self.meaning_combo.setToolTip("Choose the meaning you want this card to teach")
        self.meaning_combo.currentIndexChanged.connect(self._use_selected_meaning)
        self.alternatives_edit = QLineEdit()
        self.alternatives_edit.setPlaceholderText("Comma-separated, optional")

        self.part_of_speech = QComboBox()
        self.part_of_speech.setEditable(True)
        self.part_of_speech.addItems(
            ["", "noun", "verb", "adjective", "adverb", "phrase", "other"]
        )
        self.example_edit = QLineEdit()
        self.example_edit.setPlaceholderText("Optional example in the source language")
        self.example_translation_edit = QLineEdit()
        self.example_translation_edit.setPlaceholderText("Optional example translation")
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("work, travel, verbs")
        self.transcription_edit = QLineEdit()
        self.transcription_edit.setPlaceholderText(
            "Optional IPA or readable pronunciation"
        )
        self.forms_edit = QLineEdit()
        self.forms_edit.setPlaceholderText("Plural, past tense, related forms")
        self.frequency = QComboBox()
        self.frequency.setEditable(True)
        self.frequency.addItems(["", "very common", "common", "less common", "rare"])
        self.source_info_edit = QLineEdit()
        self.source_info_edit.setPlaceholderText("FreeDict, course, book, personal…")

        form = QFormLayout()
        form.addRow("Word / phrase", source_widget)
        form.addRow("Languages", language_widget)
        form.addRow("", direction_widget)
        form.addRow("Did you mean", spelling_widget)
        form.addRow("Primary translation", self.target_edit)
        form.addRow("Meaning to learn", self.meaning_combo)
        form.addRow("Other meanings", self.alternatives_edit)
        form.addRow("Part of speech", self.part_of_speech)
        form.addRow("Transcription", self.transcription_edit)
        form.addRow("Word forms", self.forms_edit)
        form.addRow("Frequency", self.frequency)
        form.addRow("Example", self.example_edit)
        form.addRow("Example translation", self.example_translation_edit)
        form.addRow("Tags", self.tags_edit)
        form.addRow("Source", self.source_info_edit)

        hint = QLabel(
            "Offline translation gives a suggestion. "
            "Review ambiguous words before saving."
        )
        hint.setWordWrap(True)
        hint.setObjectName("muted")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        self.buttons = buttons

        card_page = QWidget()
        card_layout = QVBoxLayout(card_page)
        card_layout.addLayout(form)
        card_layout.addWidget(hint)
        card_layout.addWidget(buttons)
        layout = QVBoxLayout(self)
        if word is None:
            from .language_dialog import LanguagePackagesPage

            self.tabs = QTabWidget()
            self.tabs.addTab(card_page, "Add word")
            self.language_packages_page = LanguagePackagesPage(self.tabs)
            self.language_packages_page.languages_changed.connect(
                self._languages_changed
            )
            self.tabs.addTab(self.language_packages_page, "Languages")
            layout.addWidget(self.tabs)
            self.resize(610, 680)
        else:
            layout.addWidget(card_page)

        if word is not None:
            self.setWindowTitle("Edit word or phrase")
            self.source_edit.setText(word.source_text)
            self.direction_label.setText(
                f"{word.source_lang.upper()} → {word.target_lang.upper()}"
            )
            if self.source_language.findData(word.source_lang) < 0:
                self.source_language.addItem(
                    language_label(word.source_lang), word.source_lang
                )
            if self.target_language.findData(word.target_lang) < 0:
                self.target_language.addItem(
                    language_label(word.target_lang), word.target_lang
                )
            self.source_language.setCurrentIndex(
                self.source_language.findData(word.source_lang)
            )
            self.target_language.setCurrentIndex(
                self.target_language.findData(word.target_lang)
            )
            self.target_edit.setText(word.target_text)
            self.meaning_combo.addItems([word.target_text, *word.alternatives])
            self.alternatives_edit.setText(", ".join(word.alternatives))
            self.part_of_speech.setCurrentText(word.part_of_speech)
            self.transcription_edit.setText(word.transcription)
            self.forms_edit.setText(", ".join(word.forms))
            self.frequency.setCurrentText(word.frequency)
            self.example_edit.setText(word.example)
            self.example_translation_edit.setText(word.example_translation)
            self.tags_edit.setText(", ".join(word.tags))
            self.source_info_edit.setText(word.source_info)
        elif initial_text:
            self.source_edit.setText(initial_text.strip())
            self.source_edit.selectAll()

    def _refresh_language_selectors(self) -> None:
        source = self.source_language.currentData()
        target = self.target_language.currentData()
        installed_languages = (
            self.translator.installed_languages()
            if hasattr(self.translator, "installed_languages")
            else ("en", "ru")
        ) or ("en", "ru")
        self.source_language.clear()
        self.target_language.clear()
        self.source_language.addItem("Auto-detect EN / RU", "")
        self.target_language.addItem("Automatic EN ↔ RU", "")
        for code in installed_languages:
            label = language_label(code)
            self.source_language.addItem(label, code)
            self.target_language.addItem(label, code)
        self.source_language.setCurrentIndex(
            max(0, self.source_language.findData(source))
        )
        self.target_language.setCurrentIndex(
            max(0, self.target_language.findData(target))
        )

    def _languages_changed(self) -> None:
        if hasattr(self.translator, "reload_models"):
            self.translator.reload_models()
        self._refresh_language_selectors()

    def translate(self) -> None:
        text = self.source_edit.text().strip()
        if not text or self._translation_worker is not None:
            self.source_edit.setFocus()
            return
        self.translate_button.setEnabled(False)
        self.translate_button.setText("Checking offline data…")
        self.buttons.setEnabled(False)
        self.setCursor(Qt.CursorShape.WaitCursor)
        worker = TranslationWorker(
            self.translator,
            text,
            str(self.source_language.currentData() or ""),
            str(self.target_language.currentData() or ""),
        )
        self._translation_worker = worker
        worker.completed.connect(lambda result: self._apply_translation(result, text))
        worker.failed.connect(self._translation_failed)
        worker.finished.connect(self._translation_finished)
        worker.start()

    def _apply_translation(
        self,
        result: TranslationResult,
        original_text: str,
    ) -> None:
        if result.corrected_source:
            self._correction_original = original_text
            self.source_edit.setText(result.corrected_source)
            self.undo_correction_button.show()
        else:
            self._correction_original = ""
            self.undo_correction_button.hide()
        self.spelling_suggestions.clear()
        self.spelling_suggestions.addItems(result.spelling_suggestions)
        self.spelling_widget.setVisible(bool(result.spelling_suggestions))
        self.target_edit.setText(result.translation)
        source_index = self.source_language.findData(result.source_language)
        target_index = self.target_language.findData(result.target_language)
        if source_index >= 0:
            self.source_language.setCurrentIndex(source_index)
        if target_index >= 0:
            self.target_language.setCurrentIndex(target_index)
        self.alternatives_edit.setText(", ".join(result.alternatives))
        self.meaning_combo.blockSignals(True)
        self.meaning_combo.clear()
        self.meaning_combo.addItems([result.translation, *result.alternatives[:3]])
        self.meaning_combo.blockSignals(False)
        if result.part_of_speech:
            self.part_of_speech.setCurrentText(result.part_of_speech)
        if result.source_language == "en" and not self.example_edit.text().strip():
            try:
                example = self.translator.example_sentence(
                    self.source_edit.text().strip(),
                    result.source_language,
                    result.part_of_speech,
                )
                self.example_edit.setText(example)
                self.example_translation_edit.clear()
            except TranslationError:
                pass
        if not self.source_info_edit.text().strip():
            self.source_info_edit.setText(
                "FreeDict offline dictionary"
                if result.dictionary_match
                else "Argos offline model"
            )
        direction = (
            f"{result.source_language.upper()} → {result.target_language.upper()}"
        )
        if result.corrected_source:
            direction += (
                f"  •  Auto-corrected “{original_text}” → “{result.corrected_source}”"
            )
        elif result.dictionary_match:
            direction += "  •  Local dictionary match"
        elif len(original_text.split()) == 1:
            direction += "  •  Offline model — check spelling"
        else:
            direction += "  •  Offline phrase model"
        self.direction_label.setText(direction)
        self.target_edit.setFocus()
        self.target_edit.selectAll()

    def _use_selected_meaning(self, index: int) -> None:
        selected = self.meaning_combo.itemText(index).strip()
        if not selected:
            return
        meanings = [
            self.meaning_combo.itemText(item).strip()
            for item in range(self.meaning_combo.count())
            if self.meaning_combo.itemText(item).strip()
        ]
        self.target_edit.setText(selected)
        self.alternatives_edit.setText(
            ", ".join(meaning for meaning in meanings if meaning != selected)
        )
        self.example_edit.clear()
        self.example_translation_edit.clear()
        with suppress(TranslationError):
            if detect_language(self.source_edit.text().strip()) == "en":
                self.example_edit.setText(
                    self.translator.example_sentence(
                        self.source_edit.text().strip(),
                        "en",
                        self.part_of_speech.currentText(),
                    )
                )

    def _translation_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Translation unavailable", message)

    def _translation_finished(self) -> None:
        worker = self._translation_worker
        self._translation_worker = None
        if worker is not None:
            worker.deleteLater()
        self.unsetCursor()
        self.translate_button.setText("Translate offline")
        self.translate_button.setEnabled(True)
        self.buttons.setEnabled(True)

    def reject(self) -> None:
        if self._translation_worker is not None:
            return
        super().reject()

    def undo_correction(self) -> None:
        if not self._correction_original:
            return
        self.source_edit.setText(self._correction_original)
        self.source_edit.setFocus()
        self.source_edit.selectAll()
        self.direction_label.setText("Correction undone — translate again if needed")
        self._correction_original = ""
        self.undo_correction_button.hide()

    def use_spelling_suggestion(self) -> None:
        suggestion = self.spelling_suggestions.currentText().strip()
        if not suggestion:
            return
        self.source_edit.setText(suggestion)
        self.spelling_widget.hide()
        self.translate()

    def _validate_and_accept(self) -> None:
        source = " ".join(self.source_edit.text().strip().split())
        target = " ".join(self.target_edit.text().strip().split())
        if not source or not target:
            QMessageBox.warning(
                self,
                "Missing information",
                "Both the source and translation are required.",
            )
            return
        try:
            selected_source = str(self.source_language.currentData() or "")
            source_language = selected_source or detect_language(source)
        except TranslationError as error:
            QMessageBox.warning(self, "Invalid source", str(error))
            return
        alternatives = [
            item.strip()
            for item in self.alternatives_edit.text().split(",")
            if item.strip() and item.strip().casefold() != target.casefold()
        ]
        example = self.example_edit.text().strip()
        example_translation = self.example_translation_edit.text().strip()
        selected_target = str(self.target_language.currentData() or "")
        target_language = selected_target or ("ru" if source_language == "en" else "en")
        if source_language == target_language:
            QMessageBox.warning(
                self,
                "Invalid language pair",
                "Source and target languages must be different.",
            )
            return
        if not example and source_language == "en":
            with suppress(TranslationError):
                example = self.translator.example_sentence(
                    source,
                    source_language,
                    self.part_of_speech.currentText(),
                )
        self.word_data = {
            "source_text": source,
            "source_lang": source_language,
            "target_lang": target_language,
            "target_text": target,
            "alternatives": list(dict.fromkeys(alternatives)),
            "part_of_speech": self.part_of_speech.currentText(),
            "transcription": self.transcription_edit.text().strip(),
            "forms": [
                item.strip()
                for item in self.forms_edit.text().split(",")
                if item.strip()
            ],
            "frequency": self.frequency.currentText().strip(),
            "example": example,
            "example_translation": example_translation,
            "tags": [
                item.strip()
                for item in self.tags_edit.text().split(",")
                if item.strip()
            ],
            "source_info": self.source_info_edit.text().strip(),
        }
        self.accept()


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("LexiDesk settings")
        self.setMinimumWidth(410)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEMES))
        self.theme_combo.setCurrentText(settings.theme)

        self.reveal_combo = QComboBox()
        self.reveal_combo.addItem("Show word and translation", "both")
        self.reveal_combo.addItem("Click to reveal translation", "quiz")
        index = self.reveal_combo.findData(settings.reveal_mode)
        self.reveal_combo.setCurrentIndex(max(0, index))

        self.practice_combo = QComboBox()
        self.practice_combo.addItem("Off — normal cards", "off")
        self.practice_combo.addItem("Mixed — adaptive + regular checks", "mixed")
        self.practice_combo.addItem("Choose translation", "translation")
        self.practice_combo.addItem("Reverse translation", "reverse")
        self.practice_combo.addItem("Complete the sentence", "cloze")
        self.practice_combo.addItem("Choose the context", "context")
        self.practice_combo.addItem("Type the translation", "typing")
        practice_index = self.practice_combo.findData(settings.practice_mode)
        self.practice_combo.setCurrentIndex(max(0, practice_index))

        self.rotation_spin = QSpinBox()
        self.rotation_spin.setRange(30, 3600)
        self.rotation_spin.setSuffix(" seconds")
        self.rotation_spin.setValue(settings.rotation_seconds)

        self.opacity_spin = QDoubleSpinBox()
        self.opacity_spin.setRange(0.50, 1.0)
        self.opacity_spin.setSingleStep(0.05)
        self.opacity_spin.setValue(settings.opacity)

        self.font_spin = QSpinBox()
        self.font_spin.setRange(80, 150)
        self.font_spin.setSuffix("%")
        self.font_spin.setValue(settings.font_scale)

        self.daily_goal_spin = QSpinBox()
        self.daily_goal_spin.setRange(1, 500)
        self.daily_goal_spin.setSuffix(" reviews")
        self.daily_goal_spin.setValue(settings.daily_goal)

        self.retention_spin = QDoubleSpinBox()
        self.retention_spin.setRange(0.70, 0.99)
        self.retention_spin.setSingleStep(0.01)
        self.retention_spin.setDecimals(2)
        self.retention_spin.setValue(settings.desired_retention)

        self.autocorrect_check = QCheckBox("Correct confident spelling mistakes")
        self.autocorrect_check.setChecked(settings.autocorrect)

        self.autostart_check = QCheckBox("Launch automatically after login")
        self.autostart_check.setChecked(settings.autostart)

        form = QFormLayout()
        form.addRow("Theme", self.theme_combo)
        form.addRow("Card mode", self.reveal_combo)
        form.addRow("Practice mode", self.practice_combo)
        form.addRow("Change card every", self.rotation_spin)
        form.addRow("Opacity", self.opacity_spin)
        form.addRow("Text size", self.font_spin)
        form.addRow("Daily goal", self.daily_goal_spin)
        form.addRow("FSRS retention", self.retention_spin)
        form.addRow("Offline autocorrection", self.autocorrect_check)
        form.addRow("", self.autostart_check)

        note = QLabel(
            "The standalone window behaves like a normal application. "
            "Use the Plasma widget for desktop-only placement."
        )
        note.setWordWrap(True)
        note.setObjectName("muted")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def apply_to(self, settings: Settings) -> None:
        settings.theme = self.theme_combo.currentText()
        settings.reveal_mode = str(self.reveal_combo.currentData())
        settings.practice_mode = str(self.practice_combo.currentData())
        settings.rotation_seconds = self.rotation_spin.value()
        settings.opacity = self.opacity_spin.value()
        settings.font_scale = self.font_spin.value()
        settings.daily_goal = self.daily_goal_spin.value()
        settings.desired_retention = self.retention_spin.value()
        settings.autocorrect = self.autocorrect_check.isChecked()
        settings.autostart = self.autostart_check.isChecked()
