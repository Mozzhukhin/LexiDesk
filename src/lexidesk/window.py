from __future__ import annotations

import sqlite3

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QMouseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .answers import AnswerGrade, evaluate_answer
from .autostart import set_autostart
from .batch import BatchAddDialog
from .database import WordRepository
from .dialogs import AddWordDialog, SettingsDialog
from .insights import AnalyticsDialog
from .library import LibraryDialog
from .models import Word
from .service_client import request_service, schedule_example_enrichment
from .settings import SettingsStore
from .themes import stylesheet
from .translation import OfflineTranslator


class LexiDeskWindow(QMainWindow):
    def __init__(
        self,
        repository: WordRepository,
        settings_store: SettingsStore,
        translator: OfflineTranslator,
    ) -> None:
        super().__init__()
        self.repository = repository
        self.settings_store = settings_store
        self.translator = translator
        self.settings = settings_store.load()
        self.current_word: Word | None = None
        self.seconds_left = self.settings.rotation_seconds
        self.review_clock = QElapsedTimer()
        self._drag_origin = QPoint()

        self.setWindowTitle("LexiDesk")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(330, 290)
        self.resize(self.settings.width, self.settings.height)
        if self.settings.x is not None and self.settings.y is not None:
            self.move(self.settings.x, self.settings.y)

        self._build_ui()
        self._apply_appearance()

        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(1000)
        self.tick_timer.timeout.connect(self._tick)
        self.tick_timer.start()

        QTimer.singleShot(0, self.next_card)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        root.installEventFilter(self)
        self.setCentralWidget(root)

        self.title_label = QLabel("LEXIDESK")
        self.title_label.setObjectName("brand")

        self.direction_label = QLabel("OFFLINE")
        self.direction_label.setObjectName("badge")
        self.goal_label = QLabel()
        self.goal_label.setObjectName("muted")
        self.goal_label.setToolTip("Reviews completed today")

        add_button = QPushButton("+")
        add_button.setObjectName("icon")
        add_button.setToolTip("Add a word or phrase")
        add_button.clicked.connect(self.add_word)

        more_button = QPushButton("⋮")
        more_button.setObjectName("icon")
        more_button.setToolTip("Card actions")
        card_menu = QMenu(more_button)
        edit_action = card_menu.addAction("Edit current card")
        edit_action.triggered.connect(self.edit_current_word)
        delete_action = card_menu.addAction("Delete current card")
        delete_action.triggered.connect(self.delete_current_word)
        card_menu.addSeparator()
        library_action = card_menu.addAction("Open vocabulary library")
        library_action.triggered.connect(self.open_library)
        batch_action = card_menu.addAction("Batch add from text")
        batch_action.triggered.connect(self.batch_add)
        analytics_action = card_menu.addAction("Learning analytics")
        analytics_action.triggered.connect(self.open_analytics)
        card_menu.addSeparator()
        settings_action = card_menu.addAction("Settings")
        settings_action.triggered.connect(self.open_settings)
        more_button.setMenu(card_menu)

        close_button = QPushButton("×")
        close_button.setObjectName("icon")
        close_button.setToolTip("Close LexiDesk")
        close_button.clicked.connect(self.close)

        header = QHBoxLayout()
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.goal_label)
        header.addWidget(self.direction_label)
        header.addWidget(add_button)
        header.addWidget(more_button)
        header.addWidget(close_button)

        card = QFrame()
        card.setObjectName("card")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.word_label = QLabel("Your vocabulary is empty")
        self.word_label.setObjectName("word")
        self.word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.word_label.setWordWrap(True)

        self.translation_label = QLabel("Add your first word with the + button")
        self.translation_label.setObjectName("translation")
        self.translation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.translation_label.setWordWrap(True)

        self.reveal_button = QPushButton("Reveal translation")
        self.reveal_button.setShortcut("Space")
        self.reveal_button.clicked.connect(self.reveal_translation)
        self.reveal_button.hide()

        self.answer_edit = QLineEdit()
        self.answer_edit.setPlaceholderText("Type the translation…")
        self.answer_edit.setClearButtonEnabled(True)
        self.answer_edit.returnPressed.connect(self.check_typed_answer)
        self.answer_edit.hide()

        self.check_answer_button = QPushButton("Check answer")
        self.check_answer_button.clicked.connect(self.check_typed_answer)
        self.check_answer_button.hide()

        answer_row = QHBoxLayout()
        answer_row.addWidget(self.answer_edit, 1)
        answer_row.addWidget(self.check_answer_button)

        self.answer_feedback = QLabel()
        self.answer_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.answer_feedback.setWordWrap(True)
        self.answer_feedback.hide()

        self.alternatives_label = QLabel()
        self.alternatives_label.setObjectName("metadata")
        self.alternatives_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alternatives_label.setWordWrap(True)

        self.example_label = QLabel()
        self.example_label.setObjectName("example")
        self.example_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.example_label.setWordWrap(True)
        self.example_label.setMaximumHeight(82)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 12, 18, 12)
        card_layout.setSpacing(4)
        card_layout.addStretch()
        card_layout.addWidget(self.word_label)
        card_layout.addWidget(self.translation_label)
        card_layout.addWidget(self.reveal_button, 0, Qt.AlignmentFlag.AlignCenter)
        card_layout.addLayout(answer_row)
        card_layout.addWidget(self.answer_feedback)
        card_layout.addWidget(self.alternatives_label)
        card_layout.addWidget(self.example_label)
        card_layout.addStretch()

        undo_button = QPushButton("Undo")
        undo_button.setObjectName("secondary")
        undo_button.setToolTip("Undo the most recent review")
        undo_button.setShortcut("Ctrl+Z")
        undo_button.clicked.connect(self.undo_review)

        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("know")
        self.next_button.setShortcut("N")
        self.next_button.setToolTip("Show another card without recording a review")
        self.next_button.clicked.connect(self.next_card)

        self.countdown_label = QLabel("1:30")
        self.countdown_label.setObjectName("countdown")

        footer = QGridLayout()
        footer.setHorizontalSpacing(6)
        footer.setVerticalSpacing(3)
        footer.addWidget(self.next_button, 0, 0, 1, 2)
        footer.addWidget(undo_button, 1, 0)
        for column in range(2):
            footer.setColumnStretch(column, 1)
        footer.addWidget(
            self.countdown_label,
            1,
            2,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 8, 10, 9)
        layout.setSpacing(7)
        layout.addLayout(header)
        layout.addWidget(card, 1)
        layout.addLayout(footer)

    def _apply_appearance(self) -> None:
        self.setStyleSheet(stylesheet(self.settings.theme, self.settings.font_scale))
        self.setWindowOpacity(self.settings.opacity)

    def next_card(self) -> None:
        previous_id = self.current_word.id if self.current_word else None
        self.current_word = self.repository.next_word(previous_id)
        self.seconds_left = self.settings.rotation_seconds
        self.review_clock.restart()
        self._render_card()

    def _render_card(self) -> None:
        word = self.current_word
        enabled = word is not None
        self.next_button.setEnabled(enabled)
        stats = self.repository.statistics()
        reviews_today = int(stats["reviews_today"])
        self.goal_label.setText(
            f"{min(reviews_today, self.settings.daily_goal)} / "
            f"{self.settings.daily_goal}"
        )
        self.answer_edit.clear()
        self.answer_edit.setEnabled(True)
        self.answer_edit.hide()
        self.check_answer_button.setEnabled(True)
        self.check_answer_button.hide()
        self.answer_feedback.clear()
        self.answer_feedback.hide()
        if word is None:
            self.direction_label.setText("EMPTY")
            self.word_label.setText("Your vocabulary is empty")
            self.translation_label.setText("Add your first word with the + button")
            self.translation_label.show()
            self.reveal_button.hide()
            self.alternatives_label.clear()
            self.example_label.clear()
            return

        target_language = "RU" if word.source_lang == "en" else "EN"
        self.direction_label.setText(f"{word.source_lang.upper()} → {target_language}")
        self.word_label.setText(word.source_text)
        self.translation_label.setText(word.target_text)
        metadata = []
        if word.transcription:
            metadata.append(word.transcription)
        if word.part_of_speech:
            metadata.append(word.part_of_speech)
        if word.frequency:
            metadata.append(word.frequency)
        metadata.extend(word.alternatives)
        metadata.extend(word.forms)
        self.alternatives_label.setText(" · ".join(metadata))
        example_parts = [
            part for part in (word.example, word.example_translation) if part
        ]
        self.example_label.setText("\n".join(example_parts))
        if self.settings.reveal_mode == "quiz":
            self.translation_label.hide()
            self.alternatives_label.hide()
            self.example_label.hide()
            self.reveal_button.show()
        elif self.settings.reveal_mode == "typing":
            self.translation_label.hide()
            self.alternatives_label.hide()
            self.example_label.hide()
            self.reveal_button.hide()
            self.answer_edit.show()
            self.check_answer_button.show()
            self.answer_edit.setFocus()
        else:
            self.reveal_translation()

    def reveal_translation(self) -> None:
        self.translation_label.show()
        self.alternatives_label.show()
        self.example_label.show()
        self.reveal_button.hide()

    def check_typed_answer(self) -> None:
        if self.current_word is None or not self.answer_edit.text().strip():
            return
        result = evaluate_answer(self.answer_edit.text(), self.current_word)
        self.reveal_translation()
        self.answer_feedback.show()
        if result.grade == AnswerGrade.CORRECT:
            self.answer_feedback.setText("Correct")
            self.answer_feedback.setObjectName("know")
        elif result.grade == AnswerGrade.CLOSE:
            self.answer_feedback.setText(f"Almost correct: {result.matched}")
            self.answer_feedback.setObjectName("metadata")
        else:
            self.answer_feedback.setText(f"Not matched. Expected: {result.expected}")
            self.answer_feedback.setObjectName("unknown")
        self.style().unpolish(self.answer_feedback)
        self.style().polish(self.answer_feedback)
        self.answer_edit.setEnabled(False)
        self.check_answer_button.setEnabled(False)

    def review(self, rating: str) -> None:
        if self.current_word is None:
            return
        duration = self.review_clock.elapsed() if self.review_clock.isValid() else None
        self.repository.review(self.current_word.id, rating, duration)
        self.next_card()

    def undo_review(self) -> None:
        restored = self.repository.undo_last_review()
        if restored is None:
            QMessageBox.information(
                self,
                "Nothing to undo",
                "There is no recent FSRS review available to undo.",
            )
            return
        self.current_word = restored
        self.seconds_left = self.settings.rotation_seconds
        self.review_clock.restart()
        self._render_card()

    def add_word(self) -> None:
        dialog = AddWordDialog(self.translator, self)
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.word_data is None:
            return
        try:
            word_id = self.repository.add_word(**dialog.word_data)
            schedule_example_enrichment(word_id)
        except sqlite3.IntegrityError:
            QMessageBox.information(
                self,
                "Already saved",
                "This word or phrase is already in your vocabulary.",
            )
            return
        self.current_word = self.repository.get_word(word_id)
        self.seconds_left = self.settings.rotation_seconds
        self._render_card()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        dialog.apply_to(self.settings)
        self.settings_store.save(self.settings)
        set_autostart(self.settings.autostart)
        self.repository.desired_retention = self.settings.desired_retention
        self.translator.autocorrect = self.settings.autocorrect
        request_service(
            {
                "command": "configure",
                "desired_retention": self.settings.desired_retention,
            }
        )
        self.seconds_left = min(self.seconds_left, self.settings.rotation_seconds)
        self._apply_appearance()
        self._render_card()

    def open_library(self) -> None:
        dialog = LibraryDialog(
            self.repository,
            self.translator,
            self,
            daily_goal=self.settings.daily_goal,
        )
        dialog.setStyleSheet(self.styleSheet())
        dialog.exec()
        self.current_word = None
        self.next_card()

    def batch_add(self) -> None:
        dialog = BatchAddDialog(self.repository, self.translator, self)
        dialog.setStyleSheet(self.styleSheet())
        dialog.exec()
        self.current_word = None
        self.next_card()

    def open_analytics(self) -> None:
        dialog = AnalyticsDialog(
            self.repository,
            self.settings.daily_goal,
            self,
        )
        dialog.setStyleSheet(self.styleSheet())
        dialog.exec()

    def edit_current_word(self) -> None:
        if self.current_word is None:
            return
        dialog = AddWordDialog(self.translator, self, self.current_word)
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.word_data is None:
            return
        try:
            self.repository.update_word(self.current_word.id, **dialog.word_data)
            schedule_example_enrichment(self.current_word.id)
        except sqlite3.IntegrityError:
            QMessageBox.information(
                self,
                "Already saved",
                "Another card already uses this word or phrase.",
            )
            return
        self.current_word = self.repository.get_word(self.current_word.id)
        self._render_card()

    def delete_current_word(self) -> None:
        if self.current_word is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete card",
            f"Delete “{self.current_word.source_text}” and its review history?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        word_id = self.current_word.id
        self.current_word = None
        self.repository.delete_word(word_id)
        self.next_card()

    def _tick(self) -> None:
        self.seconds_left -= 1
        if self.seconds_left <= 0:
            self.next_card()
        minutes, seconds = divmod(max(0, self.seconds_left), 60)
        self.countdown_label.setText(f"{minutes}:{seconds:02d}")

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.centralWidget():
            if event.type() == QEvent.Type.MouseButtonPress:
                mouse_event = event
                if isinstance(mouse_event, QMouseEvent) and (
                    mouse_event.button() == Qt.MouseButton.LeftButton
                ):
                    handle = self.windowHandle()
                    if handle is not None and handle.startSystemMove():
                        return True
                    self._drag_origin = (
                        mouse_event.globalPosition().toPoint() - self.pos()
                    )
            elif event.type() == QEvent.Type.MouseMove:
                mouse_event = event
                if isinstance(mouse_event, QMouseEvent) and (
                    mouse_event.buttons() & Qt.MouseButton.LeftButton
                ):
                    self.move(
                        mouse_event.globalPosition().toPoint() - self._drag_origin
                    )
                    return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.settings.width = self.width()
        self.settings.height = self.height()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.settings.x = self.x()
        self.settings.y = self.y()
        self.settings.width = self.width()
        self.settings.height = self.height()
        self.settings_store.save(self.settings)
        self.repository.close()
        super().closeEvent(event)
