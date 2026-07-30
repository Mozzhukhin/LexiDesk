import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from lexidesk.backup import ensure_daily_backup
from lexidesk.database import WordRepository


def test_add_select_and_review(tmp_path: Path) -> None:
    repository = WordRepository(tmp_path / "test.db")
    word_id = repository.add_word(
        source_text="opportunity",
        source_lang="en",
        target_text="возможность",
        alternatives=["шанс"],
        part_of_speech="noun",
        tags=["career"],
    )

    assert repository.count() == 1
    word = repository.next_word()
    assert word is not None
    assert word.id == word_id
    assert word.alternatives == ["шанс"]
    assert word.tags == ["career"]
    assert word.status == "New"
    assert repository.get_word(word_id).target_text == "возможность"
    repository.update_example(
        word_id,
        "The opportunity changed everything.",
        "Возможность изменила всё.",
    )
    assert (
        repository.get_word(word_id).example_translation == "Возможность изменила всё."
    )
    assert repository.statistics()["total"] == 1
    backup = ensure_daily_backup(repository)
    assert backup.exists()

    reviewed = repository.review(word_id, "again")
    assert reviewed.dont_know_count == 1
    assert reviewed.fsrs_step == 0
    restored = repository.undo_last_review()
    assert restored is not None
    assert restored.dont_know_count == 0
    assert repository.undo_last_review() is None

    reviewed = repository.review(word_id, "good")
    assert reviewed.know_count == 1
    assert reviewed.difficulty is not None

    repository.update_word(
        word_id,
        source_text="opportunity",
        source_lang="en",
        target_text="шанс",
        tags=["work"],
    )
    assert repository.get_word(word_id).target_text == "шанс"
    assert repository.list_words("work")[0].id == word_id
    repository.connection.execute(
        "UPDATE words SET alternatives_json = 'broken', tags_json = '{}'"
    )
    repository.connection.commit()
    repaired = repository.get_word(word_id)
    assert repaired.alternatives == []
    assert repaired.tags == []
    repository.delete_word(word_id)
    assert repository.count() == 0
    repository.close()


def test_next_word_covers_unseen_cards_before_repeating(tmp_path: Path) -> None:
    repository = WordRepository(tmp_path / "rotation.db")
    ids = [
        repository.add_word(
            source_text=source,
            source_lang="en",
            target_text=target,
        )
        for source, target in (
            ("one", "один"),
            ("two", "два"),
            ("three", "три"),
        )
    ]

    shown = [repository.next_word() for _ in ids]

    assert {word.id for word in shown if word is not None} == set(ids)
    repository.close()


def test_next_word_prefers_oldest_shown_due_card(tmp_path: Path) -> None:
    repository = WordRepository(tmp_path / "priority.db")
    older_id = repository.add_word(
        source_text="older",
        source_lang="en",
        target_text="старый",
    )
    newer_id = repository.add_word(
        source_text="newer",
        source_lang="en",
        target_text="новый",
    )
    now = datetime.now(UTC)
    repository.connection.executemany(
        "UPDATE words SET last_shown_at = ? WHERE id = ?",
        [
            ((now - timedelta(hours=2)).isoformat(), older_id),
            ((now - timedelta(minutes=2)).isoformat(), newer_id),
        ],
    )
    repository.connection.commit()

    selected = repository.next_word()

    assert selected is not None
    assert selected.id == older_id
    repository.close()


def test_passive_rotation_does_not_starve_a_future_card(tmp_path: Path) -> None:
    repository = WordRepository(tmp_path / "no-starvation.db")
    overdue_id = repository.add_word(
        source_text="overdue",
        source_lang="en",
        target_text="просроченный",
    )
    future_id = repository.add_word(
        source_text="future",
        source_lang="en",
        target_text="будущий",
    )
    now = datetime.now(UTC)
    repository.connection.execute(
        "UPDATE words SET last_shown_at = ? WHERE id = ?",
        ((now - timedelta(minutes=2)).isoformat(), overdue_id),
    )
    repository.connection.execute(
        "UPDATE words SET last_shown_at = ?, due_at = ? WHERE id = ?",
        (
            (now - timedelta(hours=2)).isoformat(),
            (now + timedelta(days=2)).isoformat(),
            future_id,
        ),
    )
    repository.connection.commit()

    selected = repository.next_word()

    assert selected is not None
    assert selected.id == future_id
    repository.close()


def test_pre_fsrs_database_is_migrated_without_losing_history(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_text TEXT NOT NULL,
            source_lang TEXT NOT NULL,
            target_text TEXT NOT NULL,
            alternatives_json TEXT NOT NULL DEFAULT '[]',
            part_of_speech TEXT NOT NULL DEFAULT '',
            example TEXT NOT NULL DEFAULT '',
            example_translation TEXT NOT NULL DEFAULT '',
            tags_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            due_at TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 0,
            learning_step INTEGER NOT NULL DEFAULT -1,
            know_count INTEGER NOT NULL DEFAULT 0,
            dont_know_count INTEGER NOT NULL DEFAULT 0,
            last_reviewed_at TEXT,
            last_shown_at TEXT
        );
        CREATE TABLE review_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
            result TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            previous_level INTEGER NOT NULL,
            next_level INTEGER NOT NULL,
            next_due_at TEXT NOT NULL
        );
        INSERT INTO words (
            source_text, source_lang, target_text, created_at, due_at,
            level, know_count, last_reviewed_at
        ) VALUES (
            'reliable', 'en', 'надёжный',
            '2026-01-01T00:00:00+00:00',
            '2026-01-04T00:00:00+00:00',
            2, 1, '2026-01-01T00:00:00+00:00'
        );
        INSERT INTO review_log (
            word_id, result, reviewed_at,
            previous_level, next_level, next_due_at
        ) VALUES (
            1, 'know', '2026-01-01T00:00:00+00:00',
            1, 2, '2026-01-04T00:00:00+00:00'
        );
        """
    )
    connection.close()

    repository = WordRepository(path)
    word = repository.get_word(1)
    assert word.source_text == "reliable"
    assert word.fsrs_state == 2
    assert word.stability == 3.0
    assert repository.connection.execute("PRAGMA user_version").fetchone()[0] == 5
    review = repository.connection.execute("SELECT * FROM review_log").fetchone()
    assert review["rating"] == 3
    assert review["undoable"] == 0
    assert repository.undo_last_review() is None
    repository.close()
