from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
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
    QVBoxLayout,
    QWidget,
)

from .models import Word
from .settings import Settings
from .themes import THEMES
from .translation import OfflineTranslator, TranslationError, detect_language


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
        self.setWindowTitle("Add a word or phrase")
        self.setMinimumWidth(500)

        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("English or Russian")
        self.source_edit.returnPressed.connect(self.translate)

        self.translate_button = QPushButton("Translate offline")
        self.translate_button.clicked.connect(self.translate)

        source_row = QHBoxLayout()
        source_row.addWidget(self.source_edit, 1)
        source_row.addWidget(self.translate_button)
        source_widget = QWidget()
        source_widget.setLayout(source_row)

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
        form.addRow("", direction_widget)
        form.addRow("Did you mean", spelling_widget)
        form.addRow("Primary translation", self.target_edit)
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

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)

        if word is not None:
            self.setWindowTitle("Edit word or phrase")
            self.source_edit.setText(word.source_text)
            self.direction_label.setText(
                f"{word.source_lang.upper()} → "
                f"{'RU' if word.source_lang == 'en' else 'EN'}"
            )
            self.target_edit.setText(word.target_text)
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

    def translate(self) -> None:
        text = self.source_edit.text().strip()
        if not text:
            self.source_edit.setFocus()
            return
        self.translate_button.setEnabled(False)
        self.translate_button.setText("Translating…")
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            result = self.translator.translate(text)
            if result.corrected_source:
                self._correction_original = text
                self.source_edit.setText(result.corrected_source)
                self.undo_correction_button.show()
            else:
                self._correction_original = ""
                self.undo_correction_button.hide()
            self.spelling_suggestions.clear()
            self.spelling_suggestions.addItems(result.spelling_suggestions)
            show_suggestions = bool(result.spelling_suggestions)
            self.spelling_widget.setVisible(show_suggestions)
            self.target_edit.setText(result.translation)
            self.alternatives_edit.setText(", ".join(result.alternatives))
            if result.part_of_speech:
                self.part_of_speech.setCurrentText(result.part_of_speech)
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
                    f"  •  Auto-corrected “{text}” → “{result.corrected_source}”"
                )
            elif result.dictionary_match:
                direction += "  •  Local dictionary match"
            elif len(text.split()) == 1:
                direction += "  •  Offline model — check spelling"
            else:
                direction += "  •  Offline phrase model"
            self.direction_label.setText(direction)
            self.target_edit.setFocus()
            self.target_edit.selectAll()
        except TranslationError as error:
            QMessageBox.warning(self, "Translation unavailable", str(error))
        finally:
            self.unsetCursor()
            self.translate_button.setText("Translate offline")
            self.translate_button.setEnabled(True)

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
            source_language = detect_language(source)
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
        if example and not example_translation:
            try:
                if detect_language(example) == source_language:
                    example_translation = self.translator.translate(example).translation
            except TranslationError:
                pass
        self.word_data = {
            "source_text": source,
            "source_lang": source_language,
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
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.setCurrentText(settings.theme)

        self.reveal_combo = QComboBox()
        self.reveal_combo.addItem("Show word and translation", "both")
        self.reveal_combo.addItem("Click to reveal translation", "quiz")
        self.reveal_combo.addItem("Type the translation", "typing")
        index = self.reveal_combo.findData(settings.reveal_mode)
        self.reveal_combo.setCurrentIndex(max(0, index))

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
        settings.rotation_seconds = self.rotation_spin.value()
        settings.opacity = self.opacity_spin.value()
        settings.font_scale = self.font_spin.value()
        settings.daily_goal = self.daily_goal_spin.value()
        settings.desired_retention = self.retention_spin.value()
        settings.autocorrect = self.autocorrect_check.isChecked()
        settings.autostart = self.autostart_check.isChecked()
