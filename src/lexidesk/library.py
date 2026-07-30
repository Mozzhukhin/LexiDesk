from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .batch import BatchAddDialog
from .database import WordRepository
from .dialogs import AddWordDialog
from .insights import AnalyticsDialog
from .service_client import schedule_example_enrichment
from .transfer import export_words, import_words
from .translation import OfflineTranslator


class LibraryDialog(QDialog):
    def __init__(
        self,
        repository: WordRepository,
        translator: OfflineTranslator,
        parent: QWidget | None = None,
        initial_add_text: str = "",
        daily_goal: int = 20,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.translator = translator
        self.daily_goal = daily_goal
        self.setWindowTitle("LexiDesk Library")
        self.resize(920, 620)

        title = QLabel("Vocabulary Library")
        title.setObjectName("word")
        self.stats_label = QLabel()
        self.stats_label.setObjectName("metadata")

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search words, translations, or tags…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "New", "Learning", "Known"])
        self.status_filter.currentTextChanged.connect(self.refresh)

        filters = QHBoxLayout()
        filters.addWidget(self.search, 1)
        filters.addWidget(self.status_filter)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Source",
                "Translation",
                "Direction",
                "Part of speech",
                "Tags",
                "Status",
                "Due",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.doubleClicked.connect(self.edit_selected)

        add_button = QPushButton("Add")
        add_button.clicked.connect(self.add_word)
        edit_button = QPushButton("Edit")
        edit_button.clicked.connect(self.edit_selected)
        delete_button = QPushButton("Delete")
        delete_button.setObjectName("unknown")
        delete_button.clicked.connect(self.delete_selected)
        import_button = QPushButton("Import")
        import_button.clicked.connect(self.import_file)
        batch_button = QPushButton("Batch add")
        batch_button.clicked.connect(self.batch_add)
        export_button = QPushButton("Export")
        export_button.clicked.connect(self.export_file)
        analytics_button = QPushButton("Analytics")
        analytics_button.clicked.connect(self.open_analytics)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        actions = QHBoxLayout()
        actions.addWidget(add_button)
        actions.addWidget(edit_button)
        actions.addWidget(delete_button)
        actions.addStretch()
        actions.addWidget(batch_button)
        actions.addWidget(import_button)
        actions.addWidget(export_button)
        actions.addWidget(analytics_button)
        actions.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.stats_label)
        layout.addLayout(filters)
        layout.addWidget(self.table, 1)
        layout.addLayout(actions)

        self.refresh()
        if initial_add_text:
            self.add_word(initial_add_text)

    def refresh(self, *_args: object) -> None:
        words = self.repository.list_words(
            self.search.text().strip(), self.status_filter.currentText()
        )
        self.table.setRowCount(len(words))
        for row_index, word in enumerate(words):
            due = word.due_at.astimezone().strftime("%Y-%m-%d %H:%M")
            values = (
                word.source_text,
                word.target_text,
                word.direction,
                word.part_of_speech,
                ", ".join(word.tags),
                word.status,
                due,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, word.id)
                self.table.setItem(row_index, column, item)

        stats = self.repository.statistics()
        self.stats_label.setText(
            f"{stats['total']} cards  •  {stats['due']} due  •  "
            f"{stats['known']} known  •  {stats['reviews_today']} reviews today  •  "
            f"{stats['accuracy']}% accuracy  •  {stats['streak']}-day streak"
        )

    def selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def add_word(self, initial_text: str | bool = "") -> None:
        if isinstance(initial_text, bool):
            initial_text = ""
        dialog = AddWordDialog(self.translator, self, initial_text=initial_text)
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.word_data is None:
            return
        try:
            word_id = self.repository.add_word(**dialog.word_data)
            schedule_example_enrichment(word_id)
        except sqlite3.IntegrityError:
            QMessageBox.information(self, "Already saved", "This card already exists.")
        self.refresh()

    def edit_selected(self, *_args: object) -> None:
        word_id = self.selected_id()
        if word_id is None:
            return
        word = self.repository.get_word(word_id)
        dialog = AddWordDialog(self.translator, self, word)
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.word_data is None:
            return
        try:
            self.repository.update_word(word_id, **dialog.word_data)
            schedule_example_enrichment(word_id)
        except sqlite3.IntegrityError:
            QMessageBox.information(
                self, "Already saved", "Another card already uses this source."
            )
        self.refresh()

    def delete_selected(self) -> None:
        word_id = self.selected_id()
        if word_id is None:
            return
        word = self.repository.get_word(word_id)
        answer = QMessageBox.question(
            self,
            "Delete card",
            f"Delete “{word.source_text}” and its complete review history?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.repository.delete_word(word_id)
            self.refresh()

    def export_file(self) -> None:
        filename, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export vocabulary",
            str(Path.home() / "lexidesk-vocabulary.json"),
            "LexiDesk JSON (*.json);;CSV (*.csv)",
        )
        if not filename:
            return
        path = Path(filename)
        if not path.suffix:
            path = path.with_suffix(".csv" if "CSV" in selected_filter else ".json")
        try:
            count = export_words(self.repository, path)
        except (OSError, sqlite3.Error, ValueError) as error:
            QMessageBox.warning(self, "Export failed", str(error))
            return
        QMessageBox.information(self, "Export complete", f"Exported {count} cards.")

    def import_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import vocabulary",
            str(Path.home()),
            "Vocabulary files (*.json *.csv)",
        )
        if not filename:
            return
        try:
            imported, skipped = import_words(self.repository, Path(filename))
        except (OSError, sqlite3.Error, ValueError, KeyError) as error:
            QMessageBox.warning(self, "Import failed", str(error))
            return
        self.refresh()
        QMessageBox.information(
            self,
            "Import complete",
            f"Imported {imported} cards; skipped {skipped}.",
        )

    def batch_add(self) -> None:
        dialog = BatchAddDialog(self.repository, self.translator, self)
        dialog.setStyleSheet(self.styleSheet())
        dialog.exec()
        self.refresh()

    def open_analytics(self) -> None:
        dialog = AnalyticsDialog(self.repository, self.daily_goal, self)
        dialog.setStyleSheet(self.styleSheet())
        dialog.exec()
