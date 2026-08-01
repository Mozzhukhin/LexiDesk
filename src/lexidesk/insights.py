from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
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
        self.resize(820, 680)

        self.summary = QLabel()
        self.summary.setObjectName("heading")
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

        quiz_title = QLabel("Accuracy by quiz type")
        quiz_title.setObjectName("metadata")
        self.quiz_types = QTableWidget(0, 3)
        self.quiz_types.setHorizontalHeaderLabels(["Quiz", "Attempts", "Accuracy"])
        self.quiz_types.verticalHeader().hide()
        self.quiz_types.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        confusion_title = QLabel("Most common confusions")
        confusion_title.setObjectName("metadata")
        self.confusions = QTableWidget(0, 4)
        self.confusions.setHorizontalHeaderLabels(
            ["Word", "Chosen", "Correct", "Mistakes"]
        )
        self.confusions.verticalHeader().hide()
        self.confusions.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.summary)
        content_layout.addWidget(self.goal_label)
        content_layout.addWidget(self.goal_progress)
        content_layout.addWidget(activity_title)
        content_layout.addWidget(self.activity)
        content_layout.addWidget(difficult_title)
        content_layout.addWidget(self.difficult)
        content_layout.addWidget(quiz_title)
        content_layout.addWidget(self.quiz_types)
        content_layout.addWidget(confusion_title)
        content_layout.addWidget(self.confusions)

        scroll = QScrollArea()
        scroll.setObjectName("analyticsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        QTimer.singleShot(0, lambda: scroll.verticalScrollBar().setValue(0))

        layout = QVBoxLayout(self)
        layout.addWidget(scroll, 1)
        layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight)
        self.refresh()

    def refresh(self) -> None:
        stats = self.repository.statistics()
        reviews_today = int(stats["reviews_today"])
        self.summary.setText(
            f"{stats['total']} meanings  •  {stats['known']} mastered  •  "
            f"{stats['checked_cards']} checked by quiz  •  "
            f"{stats['quiz_attempts_7_days']} attempts this week\n"
            f"{stats['due']} due  •  "
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

        breakdown = self.repository.quiz_breakdown()
        self.quiz_types.setRowCount(len(breakdown))
        for row_index, item in enumerate(breakdown):
            quiz_values = (item["type"], item["attempts"], f"{item['accuracy']}%")
            for column, value in enumerate(quiz_values):
                self.quiz_types.setItem(row_index, column, QTableWidgetItem(str(value)))

        confusions = self.repository.common_confusions(12)
        self.confusions.setRowCount(len(confusions))
        for row_index, confusion in enumerate(confusions):
            confusion_values = (
                confusion["word"],
                confusion["selected"],
                confusion["correct"],
                confusion["mistakes"],
            )
            for column, value in enumerate(confusion_values):
                self.confusions.setItem(row_index, column, QTableWidgetItem(str(value)))
