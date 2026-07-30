from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .database import WordRepository


class AnalyticsDialog(QDialog):
    def __init__(
        self,
        repository: WordRepository,
        daily_goal: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.daily_goal = max(1, daily_goal)
        self.setWindowTitle("LexiDesk Learning Analytics")
        self.resize(760, 600)

        self.summary = QLabel()
        self.summary.setObjectName("word")
        self.summary.setWordWrap(True)

        self.goal_label = QLabel()
        self.goal_label.setObjectName("metadata")
        self.goal_progress = QProgressBar()
        self.goal_progress.setRange(0, self.daily_goal)

        activity_title = QLabel("Review activity — last 30 days")
        activity_title.setObjectName("metadata")
        self.activity = QTableWidget(0, 4)
        self.activity.setHorizontalHeaderLabels(
            ["Day", "Reviews", "Recalled", "Average rating"]
        )
        self.activity.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.activity.verticalHeader().hide()
        self.activity.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        difficult_title = QLabel("Cards needing attention")
        difficult_title.setObjectName("metadata")
        self.difficult = QTableWidget(0, 4)
        self.difficult.setHorizontalHeaderLabels(
            ["Word", "Translation", "Difficulty", "Stability"]
        )
        self.difficult.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.difficult.verticalHeader().hide()
        self.difficult.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(self.goal_label)
        layout.addWidget(self.goal_progress)
        layout.addWidget(activity_title)
        layout.addWidget(self.activity, 1)
        layout.addWidget(difficult_title)
        layout.addWidget(self.difficult, 1)
        layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight)
        self.refresh()

    def refresh(self) -> None:
        stats = self.repository.statistics()
        reviews_today = int(stats["reviews_today"])
        self.summary.setText(
            f"{stats['total']} cards  •  {stats['due']} due  •  "
            f"{stats['accuracy']}% recall  •  {stats['streak']}-day streak  •  "
            f"{stats['forecast_7_days']} scheduled in 7 days"
        )
        self.goal_label.setText(
            f"Daily goal: {min(reviews_today, self.daily_goal)} / {self.daily_goal}"
        )
        self.goal_progress.setValue(min(reviews_today, self.daily_goal))

        activity = self.repository.review_activity(30)
        self.activity.setRowCount(len(activity))
        for row_index, day in enumerate(reversed(activity)):
            values = (
                day["day"],
                day["reviews"],
                day["recalled"],
                day["average_rating"],
            )
            for column, value in enumerate(values):
                self.activity.setItem(
                    row_index,
                    column,
                    QTableWidgetItem(str(value)),
                )

        difficult = self.repository.difficult_words(12)
        self.difficult.setRowCount(len(difficult))
        for row_index, word in enumerate(difficult):
            values = (
                word.source_text,
                word.target_text,
                f"{word.difficulty:.1f}" if word.difficulty is not None else "—",
                f"{word.stability:.1f} d" if word.stability is not None else "—",
            )
            for column, value in enumerate(values):
                self.difficult.setItem(
                    row_index,
                    column,
                    QTableWidgetItem(value),
                )
