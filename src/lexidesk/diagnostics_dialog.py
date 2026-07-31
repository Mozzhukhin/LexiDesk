from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .database import WordRepository
from .diagnostics import diagnostic_report, log_path


class DiagnosticsDialog(QDialog):
    def __init__(
        self,
        repository: WordRepository,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("LexiDesk Diagnostics")
        self.resize(680, 430)
        row = repository.connection.execute("PRAGMA integrity_check").fetchone()
        integrity = str(row[0]) if row else "unknown"
        self.report = diagnostic_report(integrity)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(self.report)

        copy_button = QPushButton("Copy report")
        copy_button.clicked.connect(self.copy_report)
        folder_button = QPushButton("Open log folder")
        folder_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path().parent)))
        )
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        actions = QHBoxLayout()
        actions.addWidget(copy_button)
        actions.addWidget(folder_button)
        actions.addStretch()
        actions.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
        layout.addLayout(actions)

    def copy_report(self) -> None:
        QApplication.clipboard().setText(self.report)
