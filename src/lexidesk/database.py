from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .models import Word
from .scheduling import ReviewRating, retrievability, schedule_fsrs_review


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_storage(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def from_storage(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _clean_meanings(
    target_text: str,
    alternatives: list[str] | None,
) -> tuple[str, list[str]]:
    """Remove sentence periods and duplicates from card-sized meanings."""

    def clean(value: str) -> str:
        cleaned = " ".join(value.strip().split())
        # Translation models often add one sentence-ending dot to a single
        # meaning. Preserve meaningful punctuation in abbreviations such as
        # "U.S." and in multi-sentence phrases.
        if cleaned.endswith(".") and cleaned.count(".") == 1:
            cleaned = cleaned[:-1]
        return cleaned.strip()

    target = clean(target_text)
    if not target:
        raise ValueError("Translation cannot be empty.")
    result: list[str] = []
    seen = {target.casefold()}
    for raw_value in alternatives or []:
        value = clean(raw_value)
        key = value.casefold()
        if value and key not in seen:
            result.append(value)
            seen.add(key)
    return target, result


class WordRepository:
    def __init__(self, path: Path, desired_retention: float = 0.9) -> None:
        self.path = path
        self.desired_retention = desired_retention
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_text TEXT NOT NULL,
                source_lang TEXT NOT NULL CHECK(source_lang IN ('en', 'ru')),
                target_text TEXT NOT NULL,
                alternatives_json TEXT NOT NULL DEFAULT '[]',
                part_of_speech TEXT NOT NULL DEFAULT '',
                example TEXT NOT NULL DEFAULT '',
                example_translation TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]',
                transcription TEXT NOT NULL DEFAULT '',
                forms_json TEXT NOT NULL DEFAULT '[]',
                frequency TEXT NOT NULL DEFAULT '',
                source_info TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                due_at TEXT NOT NULL,
                level INTEGER NOT NULL DEFAULT 0,
                learning_step INTEGER NOT NULL DEFAULT -1,
                know_count INTEGER NOT NULL DEFAULT 0,
                dont_know_count INTEGER NOT NULL DEFAULT 0,
                last_reviewed_at TEXT,
                last_shown_at TEXT,
                view_count INTEGER NOT NULL DEFAULT 0,
                fsrs_state INTEGER NOT NULL DEFAULT 1,
                fsrs_step INTEGER,
                stability REAL,
                difficulty REAL,
                UNIQUE(source_text COLLATE NOCASE, source_lang)
            );

            CREATE TABLE IF NOT EXISTS review_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 4),
                reviewed_at TEXT NOT NULL,
                previous_state INTEGER NOT NULL,
                previous_step INTEGER,
                previous_stability REAL,
                previous_difficulty REAL,
                previous_due_at TEXT NOT NULL,
                previous_last_reviewed_at TEXT,
                next_state INTEGER NOT NULL,
                next_step INTEGER,
                next_stability REAL,
                next_difficulty REAL,
                next_due_at TEXT NOT NULL,
                next_last_reviewed_at TEXT,
                review_duration_ms INTEGER,
                undone INTEGER NOT NULL DEFAULT 0,
                undoable INTEGER NOT NULL DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_words_due ON words(due_at);
            CREATE INDEX IF NOT EXISTS idx_words_quiz_candidates
                ON words(source_lang, part_of_speech COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_review_word ON review_log(word_id);

            CREATE TABLE IF NOT EXISTS quiz_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL REFERENCES review_log(id) ON DELETE CASCADE,
                word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
                quiz_type TEXT NOT NULL,
                selected_answer TEXT NOT NULL,
                correct_answer TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_quiz_word ON quiz_log(word_id);

            CREATE TABLE IF NOT EXISTS word_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
                example TEXT NOT NULL,
                example_translation TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                UNIQUE(word_id, example COLLATE NOCASE)
            );
            CREATE INDEX IF NOT EXISTS idx_word_examples_word
                ON word_examples(word_id, position, id);

            INSERT OR IGNORE INTO word_examples (
                word_id, example, example_translation, position
            )
            SELECT id, example, example_translation, 0
            FROM words
            WHERE example != '';
            """
        )
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(words)").fetchall()
        }
        additions = {
            "tags_json": "TEXT NOT NULL DEFAULT '[]'",
            "transcription": "TEXT NOT NULL DEFAULT ''",
            "forms_json": "TEXT NOT NULL DEFAULT '[]'",
            "frequency": "TEXT NOT NULL DEFAULT ''",
            "source_info": "TEXT NOT NULL DEFAULT ''",
            "fsrs_state": "INTEGER NOT NULL DEFAULT 1",
            "fsrs_step": "INTEGER",
            "stability": "REAL",
            "difficulty": "REAL",
            "view_count": "INTEGER NOT NULL DEFAULT 0",
        }
        migrating_to_fsrs = "fsrs_state" not in columns
        for name, declaration in additions.items():
            if name not in columns:
                self.connection.execute(
                    f"ALTER TABLE words ADD COLUMN {name} {declaration}"
                )
                if name == "view_count":
                    self.connection.execute(
                        "UPDATE words SET view_count = 1 "
                        "WHERE last_shown_at IS NOT NULL"
                    )
        if migrating_to_fsrs:
            self.connection.execute(
                """
                UPDATE words SET
                    fsrs_state = CASE
                        WHEN level > 0 AND learning_step < 0 THEN 2
                        ELSE 1
                    END,
                    fsrs_step = CASE
                        WHEN level > 0 AND learning_step < 0 THEN NULL
                        ELSE max(0, learning_step)
                    END,
                    stability = CASE level
                        WHEN 0 THEN NULL
                        WHEN 1 THEN 1.0
                        WHEN 2 THEN 3.0
                        WHEN 3 THEN 7.0
                        WHEN 4 THEN 14.0
                        WHEN 5 THEN 30.0
                        WHEN 6 THEN 60.0
                        WHEN 7 THEN 120.0
                        ELSE 240.0
                    END,
                    difficulty = CASE WHEN level > 0 THEN 5.0 ELSE NULL END
                """
            )
        review_columns = {
            row["name"]
            for row in self.connection.execute(
                "PRAGMA table_info(review_log)"
            ).fetchall()
        }
        if "rating" not in review_columns:
            self._migrate_review_log()
        self.connection.execute("PRAGMA user_version=7")
        self.connection.commit()

    def _migrate_review_log(self) -> None:
        self.connection.execute("DROP INDEX IF EXISTS idx_review_word")
        self.connection.execute("ALTER TABLE review_log RENAME TO review_log_legacy")
        self.connection.executescript(
            """
            CREATE TABLE review_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 4),
                reviewed_at TEXT NOT NULL,
                previous_state INTEGER NOT NULL,
                previous_step INTEGER,
                previous_stability REAL,
                previous_difficulty REAL,
                previous_due_at TEXT NOT NULL,
                previous_last_reviewed_at TEXT,
                next_state INTEGER NOT NULL,
                next_step INTEGER,
                next_stability REAL,
                next_difficulty REAL,
                next_due_at TEXT NOT NULL,
                next_last_reviewed_at TEXT,
                review_duration_ms INTEGER,
                undone INTEGER NOT NULL DEFAULT 0,
                undoable INTEGER NOT NULL DEFAULT 1
            );

            INSERT INTO review_log (
                id, word_id, rating, reviewed_at,
                previous_state, previous_step, previous_due_at,
                next_state, next_step, next_due_at, next_last_reviewed_at,
                undoable
            )
            SELECT
                id, word_id,
                CASE result WHEN 'dont_know' THEN 1 ELSE 3 END,
                reviewed_at,
                CASE WHEN previous_level > 0 THEN 2 ELSE 1 END,
                NULL,
                reviewed_at,
                CASE WHEN next_level > 0 THEN 2 ELSE 1 END,
                NULL,
                next_due_at,
                reviewed_at,
                0
            FROM review_log_legacy;

            DROP TABLE review_log_legacy;
            CREATE INDEX idx_review_word ON review_log(word_id);
            """
        )

    def add_word(
        self,
        *,
        source_text: str,
        source_lang: str,
        target_text: str,
        alternatives: list[str] | None = None,
        part_of_speech: str = "",
        example: str = "",
        example_translation: str = "",
        tags: list[str] | None = None,
        transcription: str = "",
        forms: list[str] | None = None,
        frequency: str = "",
        source_info: str = "",
    ) -> int:
        now = utc_now()
        cleaned_target, cleaned_alternatives = _clean_meanings(
            target_text,
            alternatives,
        )
        cursor = self.connection.execute(
            """
            INSERT INTO words (
                source_text, source_lang, target_text, alternatives_json,
                part_of_speech, example, example_translation, tags_json,
                transcription, forms_json, frequency, source_info,
                created_at, due_at, fsrs_state, fsrs_step
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
            """,
            (
                source_text.strip(),
                source_lang,
                cleaned_target,
                json.dumps(cleaned_alternatives, ensure_ascii=False),
                part_of_speech.strip(),
                example.strip(),
                example_translation.strip(),
                json.dumps(tags or [], ensure_ascii=False),
                transcription.strip(),
                json.dumps(forms or [], ensure_ascii=False),
                frequency.strip(),
                source_info.strip(),
                to_storage(now),
                to_storage(now),
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not return an ID for the new card.")
        word_id = cursor.lastrowid
        if example.strip():
            self.connection.execute(
                """
                INSERT INTO word_examples (
                    word_id, example, example_translation, position
                ) VALUES (?, ?, ?, 0)
                """,
                (word_id, example.strip(), example_translation.strip()),
            )
        self.connection.commit()
        return word_id

    def count(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) AS total FROM words").fetchone()
        return int(row["total"])

    def update_word(
        self,
        word_id: int,
        *,
        source_text: str,
        source_lang: str,
        target_text: str,
        alternatives: list[str] | None = None,
        part_of_speech: str = "",
        example: str = "",
        example_translation: str = "",
        tags: list[str] | None = None,
        transcription: str = "",
        forms: list[str] | None = None,
        frequency: str = "",
        source_info: str = "",
    ) -> None:
        cleaned_target, cleaned_alternatives = _clean_meanings(
            target_text,
            alternatives,
        )
        cursor = self.connection.execute(
            """
            UPDATE words SET
                source_text = ?, source_lang = ?, target_text = ?,
                alternatives_json = ?, part_of_speech = ?, example = ?,
                example_translation = ?, tags_json = ?, transcription = ?,
                forms_json = ?, frequency = ?, source_info = ?
            WHERE id = ?
            """,
            (
                source_text.strip(),
                source_lang,
                cleaned_target,
                json.dumps(cleaned_alternatives, ensure_ascii=False),
                part_of_speech.strip(),
                example.strip(),
                example_translation.strip(),
                json.dumps(tags or [], ensure_ascii=False),
                transcription.strip(),
                json.dumps(forms or [], ensure_ascii=False),
                frequency.strip(),
                source_info.strip(),
                word_id,
            ),
        )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown word id: {word_id}")
        self.connection.execute(
            "DELETE FROM word_examples WHERE word_id = ?", (word_id,)
        )
        if example.strip():
            self.connection.execute(
                """
                INSERT INTO word_examples (
                    word_id, example, example_translation, position
                ) VALUES (?, ?, ?, 0)
                """,
                (word_id, example.strip(), example_translation.strip()),
            )
        self.connection.commit()

    def delete_word(self, word_id: int) -> None:
        self.connection.execute("DELETE FROM words WHERE id = ?", (word_id,))
        self.connection.commit()

    def update_example(
        self,
        word_id: int,
        example: str,
        example_translation: str,
    ) -> None:
        self.replace_examples(word_id, [(example, example_translation)])

    def replace_examples(
        self,
        word_id: int,
        examples: list[tuple[str, str]],
    ) -> None:
        cleaned: list[tuple[str, str]] = []
        seen: set[str] = set()
        for example, translation in examples:
            source = " ".join(example.strip().split())
            target = " ".join(translation.strip().split())
            key = source.casefold()
            if source and target and key not in seen:
                cleaned.append((source, target))
                seen.add(key)
            if cleaned:
                break
        primary = cleaned[0] if cleaned else ("", "")
        cursor = self.connection.execute(
            """
            UPDATE words
            SET example = ?, example_translation = ?
            WHERE id = ?
            """,
            (*primary, word_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown word id: {word_id}")
        self.connection.execute(
            "DELETE FROM word_examples WHERE word_id = ?", (word_id,)
        )
        self.connection.executemany(
            """
            INSERT INTO word_examples (
                word_id, example, example_translation, position
            ) VALUES (?, ?, ?, ?)
            """,
            [
                (word_id, example, translation, position)
                for position, (example, translation) in enumerate(cleaned)
            ],
        )
        self.connection.commit()

    def examples_for_word(self, word_id: int) -> list[tuple[str, str]]:
        rows = self.connection.execute(
            """
            SELECT example, example_translation
            FROM word_examples
            WHERE word_id = ?
            ORDER BY position, id
            LIMIT 1
            """,
            (word_id,),
        ).fetchall()
        return [(str(row["example"]), str(row["example_translation"])) for row in rows]

    def get_word(self, word_id: int) -> Word:
        row = self.connection.execute(
            "SELECT * FROM words WHERE id = ?", (word_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown word id: {word_id}")
        return self._to_word(row)

    def list_words(self, search: str = "", status: str = "All") -> list[Word]:
        query = """
            SELECT * FROM words
            WHERE (
                ? = '' OR source_text LIKE ? ESCAPE '\\'
                OR target_text LIKE ? ESCAPE '\\'
                OR alternatives_json LIKE ? ESCAPE '\\'
                OR tags_json LIKE ? ESCAPE '\\'
                OR forms_json LIKE ? ESCAPE '\\'
                OR transcription LIKE ? ESCAPE '\\'
            )
        """
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        rows = self.connection.execute(
            query + " ORDER BY source_text COLLATE NOCASE",
            (search, pattern, pattern, pattern, pattern, pattern, pattern),
        ).fetchall()
        words = [self._to_word(row) for row in rows]
        if status != "All":
            words = [word for word in words if word.status == status]
        return words

    def quiz_candidates(self, word: Word, limit: int = 64) -> list[Word]:
        """Return a small, ranked candidate pool without loading the full deck."""
        category = word.part_of_speech.split(",", 1)[0].strip().casefold()
        rows = self.connection.execute(
            """
            SELECT * FROM words
            WHERE id != ? AND source_lang = ?
            ORDER BY
                CASE
                    WHEN lower(trim(
                        CASE
                            WHEN instr(part_of_speech, ',') > 0
                            THEN substr(part_of_speech, 1,
                                instr(part_of_speech, ',') - 1)
                            ELSE part_of_speech
                        END
                    )) = ? THEN 0
                    ELSE 1
                END,
                CASE
                    WHEN know_count + dont_know_count = 0 THEN 0
                    ELSE CAST(dont_know_count AS REAL)
                         / (know_count + dont_know_count)
                END DESC,
                abs(COALESCE(difficulty, 5) - ?),
                last_shown_at,
                id
            LIMIT ?
            """,
            (
                word.id,
                word.source_lang,
                category,
                word.difficulty or 5,
                max(4, min(limit, 256)),
            ),
        ).fetchall()
        return [self._to_word(row) for row in rows]

    def statistics(self) -> dict[str, int | float]:
        now = to_storage(utc_now())
        next_week = to_storage(utc_now() + timedelta(days=7))
        row = self.connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN know_count = 0 AND dont_know_count = 0 THEN 1 ELSE 0 END)
                    AS new_count,
                SUM(CASE WHEN fsrs_state = 2 AND stability >= 30 THEN 1 ELSE 0 END)
                    AS known_count,
                SUM(CASE WHEN due_at <= ? THEN 1 ELSE 0 END) AS due_count,
                SUM(CASE WHEN due_at <= ? THEN 1 ELSE 0 END) AS forecast_count,
                SUM(know_count) AS knows,
                SUM(dont_know_count) AS misses
            FROM words
            """,
            (now, next_week),
        ).fetchone()
        reviews_today = self.connection.execute(
            """
            SELECT COUNT(*) AS total FROM review_log
            WHERE undone = 0
              AND date(reviewed_at, 'localtime') = date('now', 'localtime')
            """
        ).fetchone()["total"]
        quiz_summary = self.connection.execute(
            """
            SELECT
                COUNT(*) AS attempts,
                COUNT(DISTINCT q.word_id) AS checked_cards,
                SUM(CASE WHEN r.reviewed_at >= datetime('now', '-7 days')
                    THEN 1 ELSE 0 END) AS week_attempts
            FROM quiz_log q
            JOIN review_log r ON r.id = q.review_id
            WHERE r.undone = 0
            """
        ).fetchone()
        active_days = [
            date.fromisoformat(row["day"])
            for row in self.connection.execute(
                """
                SELECT DISTINCT date(reviewed_at, 'localtime') AS day
                FROM review_log
                WHERE undone = 0
                ORDER BY day DESC
                """
            ).fetchall()
            if row["day"]
        ]
        streak = 0
        expected = datetime.now().astimezone().date()
        if active_days and active_days[0] == expected - timedelta(days=1):
            expected -= timedelta(days=1)
        for active_day in active_days:
            if active_day != expected:
                break
            streak += 1
            expected -= timedelta(days=1)
        knows = int(row["knows"] or 0)
        misses = int(row["misses"] or 0)
        reviews = knows + misses
        return {
            "total": int(row["total"] or 0),
            "new": int(row["new_count"] or 0),
            "known": int(row["known_count"] or 0),
            "learning": max(
                0,
                int(row["total"] or 0)
                - int(row["new_count"] or 0)
                - int(row["known_count"] or 0),
            ),
            "due": int(row["due_count"] or 0),
            "forecast_7_days": int(row["forecast_count"] or 0),
            "reviews_today": int(reviews_today or 0),
            "quiz_attempts": int(quiz_summary["attempts"] or 0),
            "checked_cards": int(quiz_summary["checked_cards"] or 0),
            "quiz_attempts_7_days": int(quiz_summary["week_attempts"] or 0),
            "accuracy": round((knows / reviews * 100), 1) if reviews else 0.0,
            "streak": streak,
            "average_difficulty": round(
                float(
                    self.connection.execute(
                        "SELECT AVG(difficulty) FROM words WHERE difficulty IS NOT NULL"
                    ).fetchone()[0]
                    or 0
                ),
                1,
            ),
        }

    def next_word(
        self,
        exclude_id: int | None = None,
        *,
        adaptive: bool = False,
    ) -> Word | None:
        """
        Never repeat a card within the next five displays. For decks smaller
        than six cards, the cooldown becomes ``deck size - 1`` so every other
        card is shown before a repeat. Within the eligible pool, unseen and
        least recently shown cards come first. Due state and learning
        difficulty break close ties; RANDOM is only the final tie-breaker.

        Adaptive practice shows every unseen card normally before prioritizing
        cards that are ready for their first quiz or due under FSRS. Passive
        browsing keeps a balanced full-deck rotation.
        """
        now = to_storage(utc_now())
        row = self.connection.execute(
            """
            WITH deck_size(total) AS (
                SELECT COUNT(*) FROM words
            ),
            recent_cards(id) AS (
                SELECT id
                FROM words
                WHERE last_shown_at IS NOT NULL
                ORDER BY last_shown_at DESC, id DESC
                LIMIT MIN(5, MAX(0, (SELECT total FROM deck_size) - 1))
            )
            SELECT * FROM words
            WHERE (
                    (SELECT total FROM deck_size) = 1
                    OR id NOT IN (SELECT id FROM recent_cards)
                )
              AND (
                    ? IS NULL
                    OR id != ?
                    OR (SELECT total FROM deck_size) = 1
                )
            ORDER BY
                CASE WHEN last_shown_at IS NULL THEN 0 ELSE 1 END,
                CASE WHEN ? = 1 THEN
                    CASE
                        WHEN know_count + dont_know_count = 0
                             AND view_count >= 1 THEN 0
                        WHEN know_count + dont_know_count > 0
                             AND due_at <= ? THEN 0
                        ELSE 1
                    END
                    ELSE 0
                END,
                CASE WHEN ? = 1 AND due_at <= ? THEN 0 ELSE 1 END,
                CASE
                    WHEN ? = 1 AND know_count + dont_know_count > 0
                         AND due_at <= ?
                    THEN CAST(dont_know_count AS REAL)
                         / (know_count + dont_know_count)
                    ELSE 0
                END DESC,
                CASE
                    WHEN ? = 1 AND due_at <= ?
                    THEN COALESCE(difficulty, 5)
                    ELSE 0
                END DESC,
                COALESCE(last_shown_at, created_at),
                CASE WHEN due_at <= ? THEN 0 ELSE 1 END,
                CASE
                    WHEN know_count + dont_know_count = 0 THEN 0
                    ELSE CAST(dont_know_count AS REAL)
                         / (know_count + dont_know_count)
                END DESC,
                COALESCE(difficulty, 5) DESC,
                due_at,
                RANDOM()
            LIMIT 1
            """,
            (
                exclude_id,
                exclude_id,
                int(adaptive),
                now,
                int(adaptive),
                now,
                int(adaptive),
                now,
                int(adaptive),
                now,
                now,
            ),
        ).fetchone()
        if row is None:
            return None
        self.connection.execute(
            """
            UPDATE words
            SET last_shown_at = ?, view_count = view_count + 1
            WHERE id = ?
            """,
            (now, row["id"]),
        )
        self.connection.commit()
        return self.get_word(int(row["id"]))

    def review(
        self,
        word_id: int,
        rating: ReviewRating | str | bool,
        review_duration_ms: int | None = None,
        *,
        quiz_type: str = "",
        selected_answer: str = "",
        correct_answer: str = "",
    ) -> Word:
        row = self.connection.execute(
            "SELECT * FROM words WHERE id = ?", (word_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown word id: {word_id}")

        now = utc_now()
        if isinstance(rating, bool):
            review_rating = ReviewRating.GOOD if rating else ReviewRating.AGAIN
        else:
            review_rating = ReviewRating(rating)
        schedule = schedule_fsrs_review(
            card_id=word_id,
            state=row["fsrs_state"],
            step=row["fsrs_step"],
            stability=row["stability"],
            difficulty=row["difficulty"],
            due_at=from_storage(row["due_at"]),  # type: ignore[arg-type]
            last_reviewed_at=from_storage(row["last_reviewed_at"]),
            rating=review_rating,
            now=now,
            desired_retention=self.desired_retention,
        )
        rating_value = {
            ReviewRating.AGAIN: 1,
            ReviewRating.HARD: 2,
            ReviewRating.GOOD: 3,
            ReviewRating.EASY: 4,
        }[review_rating]
        know_increment = int(review_rating != ReviewRating.AGAIN)
        miss_increment = int(review_rating == ReviewRating.AGAIN)
        with self.connection:
            self.connection.execute(
                """
                UPDATE words SET
                    due_at = ?, last_reviewed_at = ?,
                    fsrs_state = ?, fsrs_step = ?,
                    stability = ?, difficulty = ?,
                    know_count = know_count + ?,
                    dont_know_count = dont_know_count + ?
                WHERE id = ?
                """,
                (
                    to_storage(schedule.due_at),
                    to_storage(schedule.last_reviewed_at),
                    schedule.state,
                    schedule.step,
                    schedule.stability,
                    schedule.difficulty,
                    know_increment,
                    miss_increment,
                    word_id,
                ),
            )
            cursor = self.connection.execute(
                """
                INSERT INTO review_log (
                    word_id, rating, reviewed_at,
                    previous_state, previous_step, previous_stability,
                    previous_difficulty, previous_due_at,
                    previous_last_reviewed_at,
                    next_state, next_step, next_stability, next_difficulty,
                    next_due_at, next_last_reviewed_at, review_duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    word_id,
                    rating_value,
                    to_storage(now),
                    row["fsrs_state"],
                    row["fsrs_step"],
                    row["stability"],
                    row["difficulty"],
                    row["due_at"],
                    row["last_reviewed_at"],
                    schedule.state,
                    schedule.step,
                    schedule.stability,
                    schedule.difficulty,
                    to_storage(schedule.due_at),
                    to_storage(schedule.last_reviewed_at),
                    review_duration_ms,
                ),
            )
            if quiz_type and cursor.lastrowid is not None:
                self.connection.execute(
                    """
                    INSERT INTO quiz_log (
                        review_id, word_id, quiz_type,
                        selected_answer, correct_answer
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        cursor.lastrowid,
                        word_id,
                        quiz_type,
                        selected_answer,
                        correct_answer,
                    ),
                )
        return self.get_word(word_id)

    def undo_last_review(self) -> Word | None:
        row = self.connection.execute(
            """
            SELECT * FROM review_log
            WHERE undone = 0 AND undoable = 1
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        know_decrement = int(row["rating"] > 1)
        miss_decrement = int(row["rating"] == 1)
        with self.connection:
            self.connection.execute(
                """
                UPDATE words SET
                    due_at = ?, last_reviewed_at = ?,
                    fsrs_state = ?, fsrs_step = ?,
                    stability = ?, difficulty = ?,
                    know_count = max(0, know_count - ?),
                    dont_know_count = max(0, dont_know_count - ?)
                WHERE id = ?
                """,
                (
                    row["previous_due_at"],
                    row["previous_last_reviewed_at"],
                    row["previous_state"],
                    row["previous_step"],
                    row["previous_stability"],
                    row["previous_difficulty"],
                    know_decrement,
                    miss_decrement,
                    row["word_id"],
                ),
            )
            self.connection.execute(
                "UPDATE review_log SET undone = 1 WHERE id = ?",
                (row["id"],),
            )
        return self.get_word(row["word_id"])

    def card_retrievability(
        self, word: Word, now: datetime | None = None
    ) -> float | None:
        return retrievability(
            card_id=word.id,
            state=word.fsrs_state,
            step=word.fsrs_step,
            stability=word.stability,
            difficulty=word.difficulty,
            due_at=word.due_at,
            last_reviewed_at=word.last_reviewed_at,
            now=now or utc_now(),
            desired_retention=self.desired_retention,
        )

    def review_activity(self, days: int = 30) -> list[dict[str, int | str | float]]:
        rows = self.connection.execute(
            """
            SELECT
                date(reviewed_at, 'localtime') AS day,
                COUNT(*) AS reviews,
                SUM(CASE WHEN rating > 1 THEN 1 ELSE 0 END) AS recalled,
                ROUND(AVG(rating), 2) AS average_rating
            FROM review_log
            WHERE undone = 0
              AND reviewed_at >= datetime('now', ?)
            GROUP BY day
            ORDER BY day
            """,
            (f"-{max(1, days)} days",),
        ).fetchall()
        return [
            {
                "day": row["day"],
                "reviews": int(row["reviews"]),
                "recalled": int(row["recalled"] or 0),
                "average_rating": float(row["average_rating"] or 0),
            }
            for row in rows
        ]

    def difficult_words(self, limit: int = 10) -> list[Word]:
        rows = self.connection.execute(
            """
            SELECT * FROM words
            WHERE know_count + dont_know_count > 0
            ORDER BY
                COALESCE(difficulty, 0) DESC,
                dont_know_count DESC,
                stability ASC
            LIMIT ?
            """,
            (max(1, limit),),
        ).fetchall()
        return [self._to_word(row) for row in rows]

    def quiz_breakdown(self) -> list[dict[str, int | float | str]]:
        rows = self.connection.execute(
            """
            SELECT q.quiz_type,
                   COUNT(*) AS attempts,
                   SUM(CASE WHEN r.rating > 1 THEN 1 ELSE 0 END) AS correct
            FROM quiz_log q
            JOIN review_log r ON r.id = q.review_id
            WHERE r.undone = 0
            GROUP BY q.quiz_type
            ORDER BY attempts DESC
            """
        ).fetchall()
        return [
            {
                "type": row["quiz_type"],
                "attempts": int(row["attempts"]),
                "accuracy": round(
                    int(row["correct"] or 0) / int(row["attempts"]) * 100, 1
                ),
            }
            for row in rows
        ]

    def common_confusions(self, limit: int = 10) -> list[dict[str, int | str]]:
        rows = self.connection.execute(
            """
            SELECT w.source_text AS word, q.selected_answer, q.correct_answer,
                   COUNT(*) AS mistakes
            FROM quiz_log q
            JOIN review_log r ON r.id = q.review_id
            JOIN words w ON w.id = q.word_id
            WHERE r.undone = 0 AND r.rating = 1
              AND q.selected_answer != ''
            GROUP BY w.source_text, q.selected_answer, q.correct_answer
            ORDER BY mistakes DESC, w.source_text
            LIMIT ?
            """,
            (max(1, limit),),
        ).fetchall()
        return [
            {
                "word": row["word"],
                "selected": row["selected_answer"],
                "correct": row["correct_answer"],
                "mistakes": int(row["mistakes"]),
            }
            for row in rows
        ]

    def close(self) -> None:
        self.connection.close()

    def backup_to(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        destination = sqlite3.connect(path)
        try:
            self.connection.backup(destination)
        finally:
            destination.close()

    def restore_from(self, path: Path) -> None:
        """Restore a complete LexiDesk database after validating the backup."""
        if not path.is_file():
            raise ValueError("The selected backup does not exist.")
        if path.resolve() == self.path.resolve():
            raise ValueError("Select a backup file, not the active database.")
        source = sqlite3.connect(path)
        try:
            integrity = source.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise ValueError("The selected backup is damaged.")
            tables = {
                str(row[0])
                for row in source.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            if "words" not in tables:
                raise ValueError("This is not a LexiDesk database backup.")
            self.connection.commit()
            source.backup(self.connection)
            self.connection.commit()
            self._migrate()
        finally:
            source.close()

    @staticmethod
    def _to_word(row: sqlite3.Row) -> Word:
        return Word(
            id=row["id"],
            source_text=row["source_text"],
            source_lang=row["source_lang"],
            target_text=row["target_text"],
            alternatives=_json_string_list(row["alternatives_json"]),
            part_of_speech=row["part_of_speech"],
            example=row["example"],
            example_translation=row["example_translation"],
            tags=_json_string_list(row["tags_json"]),
            transcription=row["transcription"],
            forms=_json_string_list(row["forms_json"]),
            frequency=row["frequency"],
            source_info=row["source_info"],
            created_at=from_storage(row["created_at"]),  # type: ignore[arg-type]
            due_at=from_storage(row["due_at"]),  # type: ignore[arg-type]
            level=row["level"],
            learning_step=row["learning_step"],
            know_count=row["know_count"],
            dont_know_count=row["dont_know_count"],
            last_reviewed_at=from_storage(row["last_reviewed_at"]),
            last_shown_at=from_storage(row["last_shown_at"]),
            view_count=row["view_count"],
            fsrs_state=row["fsrs_state"],
            fsrs_step=row["fsrs_step"],
            stability=row["stability"],
            difficulty=row["difficulty"],
        )


def _json_string_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item)]
