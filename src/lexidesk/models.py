from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Word:
    id: int
    source_text: str
    source_lang: str
    target_text: str
    alternatives: list[str]
    part_of_speech: str
    example: str
    example_translation: str
    tags: list[str]
    transcription: str
    forms: list[str]
    frequency: str
    source_info: str
    created_at: datetime
    due_at: datetime
    level: int
    learning_step: int
    know_count: int
    dont_know_count: int
    last_reviewed_at: datetime | None
    last_shown_at: datetime | None
    fsrs_state: int
    fsrs_step: int | None
    stability: float | None
    difficulty: float | None

    @property
    def direction(self) -> str:
        target = "ru" if self.source_lang == "en" else "en"
        return f"{self.source_lang.upper()} → {target.upper()}"

    @property
    def status(self) -> str:
        if self.know_count == 0 and self.dont_know_count == 0:
            return "New"
        if self.fsrs_state == 2 and (self.stability or 0) >= 30:
            return "Known"
        return "Learning"
