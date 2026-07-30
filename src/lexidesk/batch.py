from __future__ import annotations

import re
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .database import WordRepository
from .service_client import schedule_example_enrichment
from .translation import OfflineTranslator, TranslationError, detect_language

WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё'-]{2,}")


class BatchAddDialog(QDialog):
    def __init__(
        self,
        repository: WordRepository,
        translator: OfflineTranslator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.translator = translator
        self.setWindowTitle("Batch add vocabulary")
        self.resize(760, 640)

        hint = QLabel(
            "Paste one word or phrase per line. You may provide a translation as "
            "“source = translation”. Extract mode finds unique words in a text. "
            "Review the preview before saving."
        )
        hint.setWordWrap(True)
        hint.setObjectName("muted")

        self.mode = QComboBox()
        self.mode.addItem("One card per line", "lines")
        self.mode.addItem("Extract words from text", "extract")

        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(
            "opportunity = возможность\nlook forward to\n\nor paste an article…"
        )

        preview_button = QPushButton("Build offline preview")
        preview_button.clicked.connect(self.build_preview)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Add", "Source", "Translation"])
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save_selected)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self.mode)
        layout.addWidget(self.input, 1)
        layout.addWidget(preview_button)
        layout.addWidget(self.table, 1)
        layout.addWidget(buttons)

    def _sources(self) -> list[tuple[str, str]]:
        text = self.input.toPlainText()
        if self.mode.currentData() == "extract":
            unique: dict[str, str] = {}
            for match in WORD_RE.finditer(text):
                word = match.group(0)
                unique.setdefault(word.casefold(), word)
            return [(word, "") for word in list(unique.values())[:100]]

        records: list[tuple[str, str]] = []
        for raw_line in text.splitlines():
            line = " ".join(raw_line.strip().split())
            if not line:
                continue
            source, separator, target = line.partition("=")
            records.append((source.strip(), target.strip() if separator else ""))
        return records[:100]

    def build_preview(self) -> None:
        records = self._sources()
        if not records:
            QMessageBox.information(
                self, "Nothing to preview", "Paste some text first."
            )
            return
        progress = QProgressDialog(
            "Translating locally…",
            "Cancel",
            0,
            len(records),
            self,
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        prepared: list[tuple[str, str, str, str, str, str]] = []
        for index, (source, supplied_target) in enumerate(records):
            progress.setValue(index)
            QApplication.processEvents()
            if progress.wasCanceled():
                break
            try:
                if supplied_target:
                    source_language = detect_language(source)
                    corrected = source
                    target = supplied_target
                    part_of_speech = ""
                else:
                    result = self.translator.translate(source)
                    source_language = result.source_language
                    corrected = result.corrected_source or source
                    target = result.translation
                    part_of_speech = result.part_of_speech
                try:
                    example = self.translator.example_sentence(
                        corrected,
                        source_language,
                        part_of_speech,
                    )
                except TranslationError:
                    example = ""
                example_translation = ""
                prepared.append(
                    (
                        corrected,
                        target,
                        source_language,
                        part_of_speech,
                        example,
                        example_translation,
                    )
                )
            except TranslationError:
                continue
        progress.setValue(len(records))

        self.table.setRowCount(len(prepared))
        for row, record in enumerate(prepared):
            source, target, *_metadata = record
            checked = QTableWidgetItem()
            checked.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
            )
            checked.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 0, checked)
            source_item = QTableWidgetItem(source)
            source_item.setData(Qt.ItemDataRole.UserRole, record[2:])
            self.table.setItem(row, 1, source_item)
            self.table.setItem(row, 2, QTableWidgetItem(target))

    def save_selected(self) -> None:
        imported = 0
        skipped = 0
        for row in range(self.table.rowCount()):
            check = self.table.item(row, 0)
            if check is None or check.checkState() != Qt.CheckState.Checked:
                continue
            source_item = self.table.item(row, 1)
            target_item = self.table.item(row, 2)
            if source_item is None or target_item is None:
                skipped += 1
                continue
            source = source_item.text().strip()
            target = target_item.text().strip()
            if not source or not target:
                skipped += 1
                continue
            try:
                metadata = source_item.data(Qt.ItemDataRole.UserRole)
                source_language, part_of_speech, example, example_translation = (
                    metadata
                    if isinstance(metadata, (list, tuple)) and len(metadata) == 4
                    else (detect_language(source), "", "", "")
                )
                word_id = self.repository.add_word(
                    source_text=source,
                    source_lang=source_language,
                    target_text=target,
                    part_of_speech=part_of_speech,
                    example=example,
                    example_translation=example_translation,
                    source_info="Batch import",
                )
                schedule_example_enrichment(word_id)
                imported += 1
            except (sqlite3.IntegrityError, TranslationError):
                skipped += 1
        QMessageBox.information(
            self,
            "Batch import complete",
            f"Added {imported} cards; skipped {skipped}.",
        )
        self.accept()
