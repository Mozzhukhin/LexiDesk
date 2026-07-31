from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from fsrs import Card, Rating, Scheduler, State

# Successful reviews grow conservatively. The first success waits one day.
SUCCESS_INTERVALS = (
    timedelta(days=1),
    timedelta(days=3),
    timedelta(days=7),
    timedelta(days=14),
    timedelta(days=30),
    timedelta(days=60),
    timedelta(days=120),
    timedelta(days=240),
)

# A missed card is reintroduced quickly, then allowed to graduate again.
RELEARNING_INTERVALS = (
    timedelta(minutes=10),
    timedelta(hours=1),
    timedelta(days=1),
)


@dataclass(frozen=True, slots=True)
class Schedule:
    level: int
    learning_step: int
    due_at: datetime


class ReviewRating(StrEnum):
    AGAIN = "again"
    HARD = "hard"
    GOOD = "good"
    EASY = "easy"


FSRS_RATINGS = {
    ReviewRating.AGAIN: Rating.Again,
    ReviewRating.HARD: Rating.Hard,
    ReviewRating.GOOD: Rating.Good,
    ReviewRating.EASY: Rating.Easy,
}

FSRS_LEARNING_STEPS = (timedelta(minutes=10), timedelta(hours=1))
FSRS_RELEARNING_STEPS = (timedelta(minutes=10),)


def _scheduler(desired_retention: float) -> Scheduler:
    return Scheduler(
        desired_retention=desired_retention,
        learning_steps=FSRS_LEARNING_STEPS,
        relearning_steps=FSRS_RELEARNING_STEPS,
        enable_fuzzing=False,
    )


@dataclass(frozen=True, slots=True)
class FSRSState:
    state: int
    step: int | None
    stability: float | None
    difficulty: float | None
    due_at: datetime
    last_reviewed_at: datetime | None


def schedule_fsrs_review(
    *,
    card_id: int,
    state: int,
    step: int | None,
    stability: float | None,
    difficulty: float | None,
    due_at: datetime,
    last_reviewed_at: datetime | None,
    rating: ReviewRating,
    now: datetime,
    desired_retention: float = 0.9,
) -> FSRSState:
    scheduler = _scheduler(desired_retention)
    card = Card(
        card_id=card_id,
        state=State(state),
        step=step,
        stability=stability,
        difficulty=difficulty,
        due=due_at,
        last_review=last_reviewed_at,
    )
    reviewed, _ = scheduler.review_card(card, FSRS_RATINGS[rating], now)
    return FSRSState(
        state=reviewed.state.value,
        step=reviewed.step,
        stability=reviewed.stability,
        difficulty=reviewed.difficulty,
        due_at=reviewed.due,
        last_reviewed_at=reviewed.last_review,
    )


def retrievability(
    *,
    card_id: int,
    state: int,
    step: int | None,
    stability: float | None,
    difficulty: float | None,
    due_at: datetime,
    last_reviewed_at: datetime | None,
    now: datetime,
    desired_retention: float = 0.9,
) -> float | None:
    if last_reviewed_at is None or stability is None:
        return None
    scheduler = _scheduler(desired_retention)
    card = Card(
        card_id=card_id,
        state=State(state),
        step=step,
        stability=stability,
        difficulty=difficulty,
        due=due_at,
        last_review=last_reviewed_at,
    )
    return scheduler.get_card_retrievability(card, now)


def mark_known(level: int, learning_step: int, now: datetime) -> Schedule:
    """Advance a card, including cards currently in the relearning ladder."""
    if learning_step >= 0:
        next_step = learning_step + 1
        if next_step < len(RELEARNING_INTERVALS):
            return Schedule(
                level=max(level, 0),
                learning_step=next_step,
                due_at=now + RELEARNING_INTERVALS[next_step],
            )
        # Graduating from relearning restores a short, not zero, interval.
        new_level = max(1, level)
        return Schedule(new_level, -1, now + SUCCESS_INTERVALS[new_level - 1])

    new_level = min(level + 1, len(SUCCESS_INTERVALS))
    return Schedule(new_level, -1, now + SUCCESS_INTERVALS[new_level - 1])


def mark_unknown(level: int, now: datetime) -> Schedule:
    """Move a missed card to relearning without erasing its full history."""
    retained_level = max(0, level - 2)
    return Schedule(retained_level, 0, now + RELEARNING_INTERVALS[0])
