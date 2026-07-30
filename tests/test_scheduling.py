from datetime import UTC, datetime, timedelta

from lexidesk.scheduling import mark_known, mark_unknown

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_new_card_known_is_due_in_one_day() -> None:
    result = mark_known(0, -1, NOW)
    assert result.level == 1
    assert result.learning_step == -1
    assert result.due_at == NOW + timedelta(days=1)


def test_unknown_card_enters_ten_minute_relearning() -> None:
    result = mark_unknown(5, NOW)
    assert result.level == 3
    assert result.learning_step == 0
    assert result.due_at == NOW + timedelta(minutes=10)


def test_relearning_card_progresses_through_short_steps() -> None:
    hour_step = mark_known(2, 0, NOW)
    day_step = mark_known(2, 1, NOW)
    graduated = mark_known(2, 2, NOW)
    assert hour_step.due_at == NOW + timedelta(hours=1)
    assert day_step.due_at == NOW + timedelta(days=1)
    assert graduated.learning_step == -1
    assert graduated.due_at == NOW + timedelta(days=3)
