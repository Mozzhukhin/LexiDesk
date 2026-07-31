from __future__ import annotations

import random
import sqlite3
from typing import Any

from PySide6.QtCore import (
    QEasingCurve,
    QElapsedTimer,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QActionGroup, QCloseEvent, QMouseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .answers import AnswerGrade, evaluate_answer
from .api import mixed_quiz_due, quiz_variants
from .autostart import set_autostart
from .batch import BatchAddDialog
from .config import database_path
from .database import WordRepository
from .diagnostics_dialog import DiagnosticsDialog
from .dialogs import AddWordDialog, DeckSelectionDialog, SettingsDialog
from .enrichment import needs_example_enrichment
from .insights import AnalyticsDialog
from .library import LibraryDialog
from .models import Word
from .service_client import request_service, schedule_example_enrichment
from .settings import SettingsStore
from .support import SupportDialog
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
        self._current_quiz: dict[str, Any] | None = None
        self._mixed_dry_streak = 0
        self._choice_buttons: list[QPushButton] = []
        self._quiz_answered = False
        self._example_enrichment_scheduled: set[int] = set()
        self.advance_timer = QTimer(self)
        self.advance_timer.setSingleShot(True)
        self.advance_timer.setInterval(1000)
        self.advance_timer.timeout.connect(self.next_card)

        self.setWindowTitle("LexiDesk")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(330, 290)
        self.resize(self.settings.width, self.settings.height)
        if self.settings.x is not None and self.settings.y is not None:
            self.move(self.settings.x, self.settings.y)

        self._build_ui()
        self._update_practice_button()
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

        self.direction_label = QPushButton("OFFLINE  ▾")
        self.direction_label.setObjectName("badge")
        self.direction_label.setToolTip("Choose language deck")
        self.direction_label.clicked.connect(self.choose_language_deck)
        self.goal_label = QLabel()
        self.goal_label.setObjectName("muted")
        self.goal_label.setToolTip("Reviews completed today")

        self.practice_label = QLabel()
        self.practice_label.setObjectName("modeBadge")

        more_button = QPushButton("⋮")
        more_button.setObjectName("icon")
        more_button.setToolTip("LexiDesk menu")
        card_menu = QMenu(more_button)
        practice_menu = card_menu.addMenu("Practice mode")
        practice_group = QActionGroup(practice_menu)
        practice_group.setExclusive(True)
        practice_modes = (
            ("Off", "off"),
            ("Mixed — adaptive + regular checks", "mixed"),
            ("Choose translation", "translation"),
            ("Reverse translation", "reverse"),
            ("Complete the sentence", "cloze"),
            ("Choose the context", "context"),
            ("Type the translation", "typing"),
        )
        self.practice_actions = {}
        for label, mode in practice_modes:
            action = practice_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(mode == self.settings.practice_mode)
            action.triggered.connect(
                lambda _checked=False, selected=mode: self.set_practice_mode(selected)
            )
            practice_group.addAction(action)
            self.practice_actions[mode] = action

        add_button = QPushButton("+")
        add_button.setObjectName("icon")
        add_button.setToolTip("Add a word or phrase")
        add_button.clicked.connect(self.add_word)

        card_menu.addSeparator()
        deck_action = card_menu.addAction("Choose language deck")
        deck_action.triggered.connect(self.choose_language_deck)
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
        diagnostics_action = card_menu.addAction("Diagnostics")
        diagnostics_action.triggered.connect(self.open_diagnostics)
        card_menu.addSeparator()
        support_action = card_menu.addAction("Support developer")
        support_action.triggered.connect(self.open_support)
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
        header.addWidget(self.practice_label)
        header.addWidget(add_button)
        header.addWidget(more_button)
        header.addWidget(close_button)

        self.card_frame = QFrame()
        self.card_frame.setObjectName("card")
        self.card_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.card_opacity = QGraphicsOpacityEffect(self.card_frame)
        self.card_frame.setGraphicsEffect(self.card_opacity)
        self.card_animation = QPropertyAnimation(self.card_opacity, b"opacity", self)
        self.card_animation.setDuration(180)
        self.card_animation.setStartValue(0.2)
        self.card_animation.setEndValue(1.0)
        self.card_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.word_label = QLabel("Your vocabulary is empty")
        self.word_label.setObjectName("word")
        self.word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.word_label.setWordWrap(True)
        self.word_label.setMinimumHeight(38)
        self.word_label.setMaximumHeight(72)

        self.translation_label = QLabel("Add your first word with the + button")
        self.translation_label.setObjectName("translation")
        self.translation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.translation_label.setWordWrap(True)
        self.translation_label.setMinimumHeight(30)
        self.translation_label.setMaximumHeight(58)

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

        self.quiz_instruction = QLabel()
        self.quiz_instruction.setObjectName("muted")
        self.quiz_instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quiz_instruction.setWordWrap(True)
        self.quiz_instruction.hide()

        self.choice_grid = QGridLayout()
        self.choice_grid.setHorizontalSpacing(6)
        self.choice_grid.setVerticalSpacing(6)

        self.alternatives_label = QLabel()
        self.alternatives_label.setObjectName("metadata")
        self.alternatives_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alternatives_label.setWordWrap(True)
        self.alternatives_label.setMaximumHeight(24)

        self.example_label = QLabel()
        self.example_label.setObjectName("example")
        self.example_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.example_label.setWordWrap(True)
        self.example_label.setMaximumHeight(82)

        self.card_actions = QWidget(self.card_frame)
        self.card_actions.setMaximumHeight(28)
        action_layout = QHBoxLayout(self.card_actions)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(2)
        action_layout.addStretch()
        for label, tooltip, callback in (
            ("✎", "Edit card", self.edit_current_word),
            ("⇥", "Hide for now", self.next_card),
            ("✕", "Delete card…", self.delete_current_word),
            ("☰", "Open vocabulary library", self.open_library),
        ):
            action_button = QPushButton(label)
            action_button.setObjectName("icon")
            action_button.setToolTip(tooltip)
            action_button.clicked.connect(callback)
            action_layout.addWidget(action_button)
        self.card_actions.hide()
        self.card_frame.setMouseTracking(True)
        self.card_frame.installEventFilter(self)

        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(18, 12, 18, 12)
        card_layout.setSpacing(4)
        card_layout.addStretch()
        card_layout.addWidget(self.word_label)
        card_layout.addWidget(self.translation_label)
        card_layout.addWidget(self.quiz_instruction)
        card_layout.addWidget(self.reveal_button, 0, Qt.AlignmentFlag.AlignCenter)
        card_layout.addLayout(answer_row)
        card_layout.addLayout(self.choice_grid)
        card_layout.addWidget(self.answer_feedback)
        card_layout.addWidget(self.alternatives_label)
        card_layout.addWidget(self.example_label)
        card_layout.addStretch()

        self.next_button = QPushButton("Next  →")
        self.next_button.setObjectName("primary")
        self.next_button.setToolTip("Show another card without recording a review")
        self.next_button.clicked.connect(self.next_card)

        self.countdown_progress = QProgressBar()
        self.countdown_progress.setObjectName("countdown")
        self.countdown_progress.setRange(0, max(1, self.settings.rotation_seconds))
        self.countdown_progress.setTextVisible(False)
        self.countdown_progress.setFixedHeight(4)
        self._update_countdown()

        footer = QVBoxLayout()
        footer.setSpacing(4)
        footer.addWidget(self.next_button)
        footer.addWidget(self.countdown_progress)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 8, 10, 9)
        layout.setSpacing(7)
        layout.addLayout(header)
        layout.addWidget(self.card_frame, 1)
        layout.addLayout(footer)
        QTimer.singleShot(0, self._position_card_actions)

    def _apply_appearance(self) -> None:
        self.setStyleSheet(stylesheet(self.settings.theme, self.settings.font_scale))
        self.setWindowOpacity(self.settings.opacity)

    def next_card(self) -> None:
        self.advance_timer.stop()
        previous_id = self.current_word.id if self.current_word else None
        self.current_word = self.repository.next_word(
            previous_id,
            adaptive=self.settings.practice_mode == "mixed",
            source_lang=self.settings.active_source_language,
            target_lang=self.settings.active_target_language,
        )
        self.seconds_left = self.settings.rotation_seconds
        self._update_countdown()
        self.review_clock.restart()
        self._render_card()

    def _render_card(self) -> None:
        word = self.current_word
        enabled = word is not None
        self.next_button.setEnabled(enabled)
        stats = self.repository.statistics(
            self.settings.active_source_language,
            self.settings.active_target_language,
        )
        reviews_today = int(stats["reviews_today"])
        self.goal_label.setText(f"{int(stats['total'])} words")
        self.goal_label.setToolTip(
            f"{min(reviews_today, self.settings.daily_goal)} of "
            f"{self.settings.daily_goal} daily reviews"
        )
        self.answer_edit.clear()
        self.answer_edit.setEnabled(True)
        self.answer_edit.hide()
        self.check_answer_button.setEnabled(True)
        self.check_answer_button.hide()
        self.answer_feedback.clear()
        self.answer_feedback.hide()
        self.answer_feedback.setObjectName("")
        self.quiz_instruction.clear()
        self.quiz_instruction.hide()
        self._current_quiz = None
        self._quiz_answered = False
        self._clear_choices()
        if word is None:
            self.direction_label.setText("EMPTY  ▾")
            self.word_label.setText("Your vocabulary is empty")
            self.translation_label.setText("Add your first word with the + button")
            self.translation_label.show()
            self.reveal_button.hide()
            self.alternatives_label.clear()
            self.example_label.clear()
            self.practice_label.setEnabled(False)
            return

        self.practice_label.setEnabled(True)
        if (
            word.id not in self._example_enrichment_scheduled
            and len(self._example_enrichment_scheduled) < 20
            and self.repository.path == database_path()
            and needs_example_enrichment(self.repository, word)
        ):
            self._example_enrichment_scheduled.add(word.id)
            schedule_example_enrichment(word.id)

        self.direction_label.setText(f"{word.direction}  ▾")
        # The English side always stays on top, regardless of which language was
        # entered when the card was created.
        english_first = word.target_lang == "en"
        self.word_label.setText(word.target_text if english_first else word.source_text)
        self.translation_label.setText(
            word.source_text if english_first else word.target_text
        )
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
        examples = (
            (word.example_translation, word.example)
            if english_first
            else (word.example, word.example_translation)
        )
        example_parts = [part for part in examples if part]
        self.example_label.setText("\n".join(example_parts))
        variants = quiz_variants(word, self.repository)
        practice_mode = self._practice_for_card(variants)
        selected_quiz = variants.get(practice_mode)
        if selected_quiz is not None:
            self._show_quiz(selected_quiz)
        elif practice_mode not in {"off", "mixed"}:
            self.word_label.setText("No suitable card for this quiz yet")
            self.translation_label.hide()
            self.alternatives_label.hide()
            self.example_label.hide()
            self.reveal_button.hide()
            self.quiz_instruction.setText(
                "LexiDesk will keep this mode selected. Press Next or wait "
                "for the next card."
            )
            self.quiz_instruction.show()
        elif self.settings.reveal_mode == "quiz":
            self.translation_label.hide()
            self.alternatives_label.hide()
            self.example_label.hide()
            self.reveal_button.show()
        else:
            self.reveal_translation()
        self.card_animation.stop()
        self.card_animation.start()

    def _practice_for_card(self, variants: dict[str, dict[str, Any]]) -> str:
        mode = self.settings.practice_mode
        if mode != "mixed":
            return mode
        if self.current_word is None:
            return "off"
        self._mixed_dry_streak += 1
        if not mixed_quiz_due(self.current_word, self._mixed_dry_streak):
            return "off"
        available = [
            candidate
            for candidate in ("translation", "reverse", "cloze", "context")
            if candidate in variants
        ]
        if not available:
            return "off"
        self._mixed_dry_streak = 0
        return random.choice(available)

    def set_practice_mode(self, mode: str) -> None:
        if mode not in self.practice_actions:
            return
        self.settings.practice_mode = mode
        self._mixed_dry_streak = 0
        self.settings_store.save(self.settings)
        self.practice_actions[mode].setChecked(True)
        self._update_practice_button()
        self._render_card()

    def _update_practice_button(self) -> None:
        labels = {
            "off": "Off",
            "mixed": "Mixed — adaptive + regular checks",
            "translation": "Choose translation",
            "reverse": "Reverse translation",
            "cloze": "Complete the sentence",
            "context": "Choose the context",
            "typing": "Type the translation",
        }
        selected = labels.get(self.settings.practice_mode, "Off")
        short_labels = {
            "off": "",
            "mixed": "Mixed",
            "translation": "Translation",
            "reverse": "Reverse",
            "cloze": "Sentence",
            "context": "Context",
            "typing": "Typing",
        }
        self.practice_label.setText(short_labels.get(self.settings.practice_mode, ""))
        self.practice_label.setVisible(self.settings.practice_mode != "off")
        self.practice_label.setToolTip(f"Practice mode: {selected}")

    def _show_quiz(self, quiz: dict[str, Any]) -> None:
        self._current_quiz = quiz
        self.word_label.setText(str(quiz.get("prompt", "")))
        self.translation_label.setText(str(quiz.get("answer", "")))
        self.translation_label.hide()
        self.alternatives_label.hide()
        self.example_label.hide()
        self.reveal_button.hide()
        self.quiz_instruction.setText(str(quiz.get("instruction", "")))
        self.quiz_instruction.show()
        if quiz.get("type") == "typing":
            self.answer_edit.show()
            self.check_answer_button.show()
            self.answer_edit.setFocus()
            return
        choices = [str(choice) for choice in quiz.get("choices", [])]
        for index, choice in enumerate(choices):
            button = QPushButton(choice)
            button.setMinimumHeight(38)
            button.clicked.connect(
                lambda _checked=False, selected=choice: self.choose_answer(selected)
            )
            columns = 1 if quiz.get("type") == "context" else 2
            self.choice_grid.addWidget(button, index // columns, index % columns)
            self._choice_buttons.append(button)

    def _clear_choices(self) -> None:
        while self.choice_grid.count():
            item = self.choice_grid.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._choice_buttons.clear()

    def choose_answer(self, selected: str) -> None:
        if self.current_word is None or self._current_quiz is None:
            return
        if self._quiz_answered:
            return
        self._quiz_answered = True
        answer = str(self._current_quiz.get("answer", ""))
        correct = selected == answer
        for button in self._choice_buttons:
            button.setEnabled(False)
            if button.text() == answer:
                button.setObjectName("correctChoice")
            elif button.text() == selected:
                button.setObjectName("wrongChoice")
            self.style().unpolish(button)
            self.style().polish(button)
        self.translation_label.show()
        self.answer_feedback.setObjectName("know" if correct else "unknown")
        self.answer_feedback.setText(
            "Correct" if correct else f"Incorrect — correct answer: {answer}"
        )
        self.answer_feedback.show()
        self.style().unpolish(self.answer_feedback)
        self.style().polish(self.answer_feedback)
        self._record_quiz("good" if correct else "again", selected, answer)

    def _record_quiz(self, rating: str, selected: str, correct: str) -> None:
        if self.current_word is None or self._current_quiz is None:
            return
        duration = self.review_clock.elapsed() if self.review_clock.isValid() else None
        self.repository.review(
            self.current_word.id,
            rating,
            duration,
            quiz_type=str(self._current_quiz.get("type", "")),
            selected_answer=selected,
            correct_answer=correct,
        )
        self.advance_timer.start()

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
        if self._current_quiz is not None and not self._quiz_answered:
            self._quiz_answered = True
            self._record_quiz(
                result.suggested_rating,
                self.answer_edit.text().strip(),
                result.expected,
            )

    def review(self, rating: str) -> None:
        if self.current_word is None:
            return
        duration = self.review_clock.elapsed() if self.review_clock.isValid() else None
        self.repository.review(self.current_word.id, rating, duration)
        self.next_card()

    def add_word(self) -> None:
        dialog = AddWordDialog(self.translator, self)
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.word_data is None:
            return
        try:
            word_id = self.repository.add_word(**dialog.word_data)
            self.settings.active_source_language = str(dialog.word_data["source_lang"])
            self.settings.active_target_language = str(dialog.word_data["target_lang"])
            self.settings_store.save(self.settings)
            schedule_example_enrichment(word_id)
            self._example_enrichment_scheduled.add(word_id)
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

    def choose_language_deck(self) -> None:
        dialog = DeckSelectionDialog(
            self.repository.language_pairs(),
            (
                self.settings.active_source_language,
                self.settings.active_target_language,
            ),
            self,
        )
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.selected_pair is None:
            return
        (
            self.settings.active_source_language,
            self.settings.active_target_language,
        ) = dialog.selected_pair
        self.settings_store.save(self.settings)
        self.current_word = None
        self.next_card()

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
        self.set_practice_mode(self.settings.practice_mode)

    def open_library(self) -> None:
        dialog = LibraryDialog(
            self.repository,
            self.translator,
            self,
            daily_goal=self.settings.daily_goal,
            active_pair=(
                self.settings.active_source_language,
                self.settings.active_target_language,
            ),
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

    def open_diagnostics(self) -> None:
        dialog = DiagnosticsDialog(self.repository, self)
        dialog.setStyleSheet(self.styleSheet())
        dialog.exec()

    def open_support(self) -> None:
        dialog = SupportDialog(self)
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
            self._example_enrichment_scheduled.add(self.current_word.id)
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
            return
        self._update_countdown()

    def _update_countdown(self) -> None:
        minutes, seconds = divmod(max(0, self.seconds_left), 60)
        self.countdown_progress.setRange(0, max(1, self.settings.rotation_seconds))
        self.countdown_progress.setValue(max(0, self.seconds_left))
        self.countdown_progress.setToolTip(
            f"{minutes}:{seconds:02d} until the next card"
        )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if hasattr(self, "card_frame") and watched is self.card_frame:
            if event.type() == QEvent.Type.Enter:
                self.card_actions.setVisible(self.current_word is not None)
            elif event.type() == QEvent.Type.Leave:
                self.card_actions.hide()
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

    def _position_card_actions(self) -> None:
        self.card_actions.adjustSize()
        self.card_actions.move(
            max(8, self.card_frame.width() - self.card_actions.width() - 8),
            8,
        )
        self.card_actions.raise_()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "card_actions"):
            self._position_card_actions()
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
