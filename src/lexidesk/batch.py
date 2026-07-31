from __future__ import annotations

import re
import sqlite3
from collections import Counter
from collections.abc import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
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

type PreparedRecord = tuple[str, str, str, str, str, str]

WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё'-]{2,}")
STOPWORDS = {
    "en": {
        "the",
        "and",
        "that",
        "this",
        "with",
        "from",
        "have",
        "were",
        "been",
        "they",
        "their",
        "about",
        "would",
        "there",
        "which",
        "when",
        "what",
        "your",
        "into",
        "than",
        "then",
        "also",
        "just",
        "does",
        "for",
        "are",
    },
    "ru": {
        "это",
        "как",
        "что",
        "для",
        "или",
        "его",
        "она",
        "они",
        "был",
        "была",
        "были",
        "при",
        "также",
        "только",
        "когда",
        "если",
        "чтобы",
        "который",
        "которая",
        "которые",
        "этот",
        "того",
        "есть",
        "уже",
        "еще",
        "ещё",
    },
}


def prepare_batch_records(
    records: list[tuple[str, str]],
    translator: OfflineTranslator,
    *,
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[int], None] = lambda _value: None,
) -> list[PreparedRecord]:
    """Translate batch records outside the GUI thread with cooperative cancel."""
    prepared: list[PreparedRecord] = []
    for index, (source, supplied_target) in enumerate(records):
        if cancelled():
            break
        try:
            if supplied_target:
                source_language = detect_language(source)
                corrected = source
                target = supplied_target
                part_of_speech = ""
            else:
                result = translator.translate(source)
                source_language = result.source_language
                corrected = result.corrected_source or source
                target = result.translation
                part_of_speech = result.part_of_speech
            try:
                example = translator.example_sentence(
                    corrected,
                    source_language,
                    part_of_speech,
                )
            except TranslationError:
                example = ""
            prepared.append(
                (
                    corrected,
                    target,
                    source_language,
                    part_of_speech,
                    example,
                    "",
                )
            )
        except TranslationError:
            pass
        finally:
            progress(index + 1)
    return prepared


class BatchPreviewWorker(QThread):
    progress_changed = Signal(int)
    completed = Signal(object, bool)
    failed = Signal(str)

    def __init__(
        self,
        translator: OfflineTranslator,
        records: list[tuple[str, str]],
    ) -> None:
        super().__init__()
        self.translator = translator
        self.records = records

    def run(self) -> None:
        try:
            prepared = prepare_batch_records(
                self.records,
                self.translator,
                cancelled=self.isInterruptionRequested,
                progress=self.progress_changed.emit,
            )
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.completed.emit(prepared, self.isInterruptionRequested())


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
        self._preview_worker: BatchPreviewWorker | None = None
        self._progress_dialog: QProgressDialog | None = None
        self._close_after_preview = False
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
        self.mode.addItem("Smart words from article", "extract")

        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(
            "opportunity = возможность\nlook forward to\n\nor paste an article…"
        )

        self.preview_button = QPushButton("Build offline preview")
        self.preview_button.clicked.connect(self.build_preview)

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
        layout.addWidget(self.preview_button)
        layout.addWidget(self.table, 1)
        layout.addWidget(buttons)

    def _sources(self) -> list[tuple[str, str]]:
        text = self.input.toPlainText()
        if self.mode.currentData() == "extract":
            counts: Counter[tuple[str, str]] = Counter()
            for match in WORD_RE.finditer(text):
                word = match.group(0)
                try:
                    language = detect_language(word)
                except TranslationError:
                    continue
                normalized = word.casefold()
                if normalized in STOPWORDS[language]:
                    continue
                counts[(normalized, language)] += 1
            existing = {
                (word.source_text.casefold(), word.source_lang)
                for word in self.repository.list_words()
            }
            ranked: list[tuple[int, str, str]] = []
            for (normalized, language), count in counts.items():
                if (normalized, language) in existing:
                    continue
                entry = self.translator.dictionary.lookup(normalized, language)
                if entry is None or not entry.translations:
                    continue
                score = count * 10 + min(len(normalized), 12)
                ranked.append((score, entry.headword, entry.translations[0]))
            ranked.sort(key=lambda item: (-item[0], item[1].casefold()))
            return [(source, target) for _, source, target in ranked[:50]]

        records: list[tuple[str, str]] = []
        for raw_line in text.splitlines():
            line = " ".join(raw_line.strip().split())
            if not line:
                continue
            source, separator, target = line.partition("=")
            records.append((source.strip(), target.strip() if separator else ""))
        return records[:100]

    def build_preview(self) -> None:
        if self._preview_worker is not None:
            return
        records = self._sources()
        if not records:
            QMessageBox.information(
                self, "Nothing to preview", "Paste some text first."
            )
            return
        progress_dialog = QProgressDialog(
            "Translating locally…",
            "Cancel",
            0,
            len(records),
            self,
        )
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(False)
        progress_dialog.setAutoReset(False)
        worker = BatchPreviewWorker(self.translator, records)
        worker.progress_changed.connect(progress_dialog.setValue)
        worker.completed.connect(self._preview_ready)
        worker.failed.connect(self._preview_failed)
        worker.finished.connect(self._preview_finished)
        progress_dialog.canceled.connect(worker.requestInterruption)
        self._preview_worker = worker
        self._progress_dialog = progress_dialog
        self.preview_button.setEnabled(False)
        progress_dialog.show()
        worker.start()

    def _preview_ready(
        self,
        prepared: list[PreparedRecord],
        _cancelled: bool,
    ) -> None:
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

    def _preview_failed(self, message: str) -> None:
        QMessageBox.warning(
            self,
            "Could not build preview",
            message or "The offline preview failed unexpectedly.",
        )

    def _preview_finished(self) -> None:
        worker = self._preview_worker
        progress_dialog = self._progress_dialog
        self._preview_worker = None
        self._progress_dialog = None
        self.preview_button.setEnabled(True)
        if progress_dialog is not None:
            progress_dialog.close()
            progress_dialog.deleteLater()
        if worker is not None:
            worker.deleteLater()
        if self._close_after_preview:
            self._close_after_preview = False
            super().reject()

    def reject(self) -> None:
        if self._preview_worker is not None:
            self._close_after_preview = True
            self._preview_worker.requestInterruption()
            if self._progress_dialog is not None:
                self._progress_dialog.setLabelText("Cancelling after this word…")
            return
        super().reject()

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
