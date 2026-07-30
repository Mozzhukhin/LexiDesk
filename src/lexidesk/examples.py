from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import examples_path
from .dictionary import normalize_headword

POS_CODES = {
    "noun": "n",
    "verb": "v",
    "adjective": "a",
    "adverb": "r",
}


class SemanticExampleIndex:
    """Fast read-only access to examples extracted from Princeton WordNet."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or examples_path()

    @property
    def available(self) -> bool:
        return self.path.exists()

    def lookup(self, word: str, part_of_speech: str = "") -> str:
        if not self.available:
            return ""
        normalized = normalize_headword(word).replace(" ", "_")
        category = part_of_speech.strip().casefold()
        pos = next(
            (code for name, code in POS_CODES.items() if category.startswith(name)),
            "",
        )
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT example, definition
                FROM examples
                WHERE lemma = ?
                  AND (? = '' OR pos = ? OR (? = 'a' AND pos = 's'))
                ORDER BY frequency DESC, sense_rank
                LIMIT 1
                """,
                (normalized, pos, pos, pos),
            ).fetchone()
        except (sqlite3.Error, OSError):
            return ""
        finally:
            if connection is not None:
                connection.close()
        if row is None:
            return ""
        example = str(row["example"]).strip()
        if example:
            return _sentence_case(example)
        definition = str(row["definition"]).strip().rstrip(".")
        if definition:
            term = word.strip().casefold()
            return f"In this context, {term} means {definition}."
        return ""


def _sentence_case(text: str) -> str:
    sentence = text.strip()
    if not sentence:
        return ""
    sentence = sentence[0].upper() + sentence[1:]
    if sentence[-1] not in ".!?":
        sentence += "."
    return sentence
