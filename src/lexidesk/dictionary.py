from __future__ import annotations

import json
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .config import dictionary_path


def normalize_headword(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().casefold())
    return "".join(character for character in normalized if character != "\u0301")


@dataclass(frozen=True, slots=True)
class DictionaryEntry:
    headword: str
    source_language: str
    translations: tuple[str, ...]
    part_of_speech: str


@dataclass(frozen=True, slots=True)
class SpellingSuggestion:
    entry: DictionaryEntry
    distance: int


class OfflineDictionary:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or dictionary_path()

    @property
    def available(self) -> bool:
        return self.path.exists()

    def lookup(self, text: str, source_language: str) -> DictionaryEntry | None:
        if not self.available:
            return None
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT headword, source_lang, translations_json, part_of_speech
                FROM entries
                WHERE normalized = ? AND source_lang = ?
                LIMIT 1
                """,
                (normalize_headword(text), source_language),
            ).fetchone()
            if row is None:
                return None
            translations = json.loads(row["translations_json"])
            if not isinstance(translations, list):
                return None
        except (sqlite3.Error, OSError, ValueError, TypeError):
            return None
        finally:
            if connection is not None:
                connection.close()
        return DictionaryEntry(
            headword=row["headword"],
            source_language=row["source_lang"],
            translations=tuple(str(item) for item in translations if str(item)),
            part_of_speech=row["part_of_speech"],
        )

    def suggestions(
        self,
        text: str,
        source_language: str,
        *,
        limit: int = 12,
    ) -> tuple[SpellingSuggestion, ...]:
        """Return nearby single-word dictionary entries without using the network."""
        normalized = normalize_headword(text)
        if (
            not self.available
            or not normalized.isalpha()
            or len(normalized) < 3
            or source_language not in {"en", "ru"}
        ):
            return ()

        maximum_distance = 1 if len(normalized) < 6 else 2
        first = normalized[0]
        second = normalized[1]
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT headword, source_lang, normalized, translations_json,
                       part_of_speech
                FROM entries
                WHERE source_lang = ?
                  AND normalized NOT LIKE '% %'
                  AND normalized NOT LIKE '%-%'
                  AND length(normalized) BETWEEN ? AND ?
                  AND (
                      substr(normalized, 1, 1) = ?
                      OR substr(normalized, 2, 1) = ?
                  )
                """,
                (
                    source_language,
                    len(normalized) - maximum_distance,
                    len(normalized) + maximum_distance,
                    first,
                    second,
                ),
            ).fetchall()
        except (sqlite3.Error, OSError):
            return ()
        finally:
            if connection is not None:
                connection.close()

        suggestions: list[SpellingSuggestion] = []
        for row in rows:
            if row["headword"].isupper() and not text.isupper():
                continue
            distance = _damerau_levenshtein(normalized, row["normalized"])
            if distance == 0 or distance > maximum_distance:
                continue
            try:
                translations = json.loads(row["translations_json"])
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(translations, list):
                continue
            entry = DictionaryEntry(
                headword=row["headword"],
                source_language=row["source_lang"],
                translations=tuple(
                    str(item) for item in translations if str(item).strip()
                ),
                part_of_speech=row["part_of_speech"],
            )
            suggestions.append(SpellingSuggestion(entry, distance))

        suggestions.sort(
            key=lambda suggestion: (
                suggestion.distance,
                abs(
                    len(normalize_headword(suggestion.entry.headword)) - len(normalized)
                ),
                suggestion.entry.headword.casefold(),
            )
        )
        return tuple(suggestions[: max(1, limit)])


def _damerau_levenshtein(left: str, right: str) -> int:
    """Measure edits while treating an adjacent transposition as one typo."""
    previous_previous: list[int] | None = None
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            value = min(
                current[right_index - 1] + 1,
                previous[right_index] + 1,
                previous[right_index - 1] + (left_character != right_character),
            )
            if (
                previous_previous is not None
                and left_index > 1
                and right_index > 1
                and left_character == right[right_index - 2]
                and left[left_index - 2] == right_character
            ):
                value = min(value, previous_previous[right_index - 2] + 1)
            current.append(value)
        previous_previous, previous = previous, current
    return previous[-1]
