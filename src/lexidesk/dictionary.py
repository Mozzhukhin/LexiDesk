from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .config import dictionary_path


def normalize_headword(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().casefold())
    return "".join(character for character in normalized if character != "\u0301")


def clean_dictionary_text(value: str) -> str:
    """Normalize dictionary markup and stress marks for user-facing text."""
    without_markup = re.sub(r"<[^>]+>", "", value)
    normalized = unicodedata.normalize("NFKD", without_markup.strip())
    without_stress = "".join(
        character for character in normalized if character != "\u0301"
    )
    return " ".join(unicodedata.normalize("NFC", without_stress).split())


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
            headword=clean_dictionary_text(row["headword"]),
            source_language=row["source_lang"],
            translations=_clean_translations(translations),
            part_of_speech=row["part_of_speech"],
        )

    def reciprocal_translations(
        self,
        text: str,
        source_language: str,
        *,
        limit: int = 16,
    ) -> tuple[str, ...]:
        """
        Return translations independently confirmed by the opposite dictionary.

        For example, the RU→EN source may contain a weak entry while the EN→RU
        entry explicitly maps the correct English headword back to the Russian
        word. The generated reverse index makes that evidence fast to query.
        """
        if (
            not self.available
            or source_language not in {"en", "ru"}
            or not text.strip()
            or limit < 1
        ):
            return ()
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            table = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table' AND name = 'reverse_entries'
                """
            ).fetchone()
            if table is None:
                return ()
            rows = connection.execute(
                """
                SELECT target_text
                FROM reverse_entries
                WHERE source_lang = ? AND normalized = ?
                ORDER BY source_rank, target_text COLLATE NOCASE
                LIMIT ?
                """,
                (source_language, normalize_headword(text), limit),
            ).fetchall()
        except (sqlite3.Error, OSError):
            return ()
        finally:
            if connection is not None:
                connection.close()
        return _clean_translations([row["target_text"] for row in rows])

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
                headword=clean_dictionary_text(row["headword"]),
                source_language=row["source_lang"],
                translations=_clean_translations(translations),
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

    def random_translations(
        self,
        source_language: str,
        *,
        excluded: set[str] | None = None,
        part_of_speech: str = "",
        limit: int = 3,
    ) -> tuple[str, ...]:
        """Return distinct offline translations suitable as quiz distractors."""
        if not self.available or source_language not in {"en", "ru"} or limit < 1:
            return ()

        excluded_keys = {
            normalize_headword(value) for value in (excluded or set()) if value.strip()
        }
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT headword, translations_json, part_of_speech
                FROM entries
                WHERE source_lang = ?
                  AND translations_json != '[]'
                ORDER BY
                    CASE
                        WHEN ? != '' AND part_of_speech = ? THEN 0
                        ELSE 1
                    END,
                    RANDOM()
                LIMIT 80
                """,
                (source_language, part_of_speech, part_of_speech),
            ).fetchall()
        except (sqlite3.Error, OSError):
            return ()
        finally:
            if connection is not None:
                connection.close()

        result: list[str] = []
        seen = set(excluded_keys)
        for row in rows:
            headword = str(row["headword"]).strip()
            if not headword or headword != headword.casefold():
                continue
            try:
                translations = json.loads(row["translations_json"])
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(translations, list):
                continue
            for raw_value in translations:
                value = str(raw_value).strip()
                key = normalize_headword(value)
                if (
                    len(key.replace(" ", "").replace("-", "")) < 3
                    or len(value) > 36
                    or value != value.casefold()
                    or not all(
                        character.isalpha() or character in {" ", "-", "'"}
                        for character in value
                    )
                    or key in seen
                ):
                    continue
                result.append(value)
                seen.add(key)
                break
            if len(result) >= limit:
                break
        return tuple(result)


def _clean_translations(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = clean_dictionary_text(str(raw_value))
        key = normalize_headword(value)
        if (
            not value
            or key in seen
            or _looks_like_dictionary_note(value)
            or _has_wrong_script(value)
        ):
            continue
        result.append(value)
        seen.add(key)
    return tuple(result)


def _looks_like_dictionary_note(value: str) -> bool:
    lowered = value.casefold()
    return (
        lowered.startswith(("тж.", "см.", "ср.", "also ", "see "))
        or value.count("(") != value.count(")")
        or value.startswith(("(", ")", ",", ";"))
    )


def _has_wrong_script(value: str) -> bool:
    has_latin = any("a" <= character.casefold() <= "z" for character in value)
    has_cyrillic = any("\u0400" <= character <= "\u04ff" for character in value)
    return has_latin and has_cyrillic


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
