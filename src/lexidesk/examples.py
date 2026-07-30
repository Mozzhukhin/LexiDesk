from __future__ import annotations

import re
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
MAX_EXAMPLE_LENGTH = 70


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
            rows = connection.execute(
                """
                SELECT example, definition
                FROM examples
                WHERE lemma = ?
                  AND (? = '' OR pos = ? OR (? = 'a' AND pos = 's'))
                ORDER BY frequency DESC, sense_rank
                LIMIT 12
                """,
                (normalized, pos, pos, pos),
            ).fetchall()
        except (sqlite3.Error, OSError):
            return ""
        finally:
            if connection is not None:
                connection.close()
        if not rows:
            return ""
        for row in rows:
            example = _sentence_case(str(row["example"]))
            if example_is_suitable(example, word):
                return example
        definition = str(rows[0]["definition"]).strip()
        if definition:
            return _definition_example(word, definition)
        return ""


def example_is_suitable(example: str, word: str) -> bool:
    sentence = " ".join(example.strip().split())
    term = " ".join(word.strip().split())
    if (
        not sentence
        or not term
        or len(sentence) > MAX_EXAMPLE_LENGTH
        or len(sentence.rstrip(".!?").split()) < 4
    ):
        return False
    pattern = rf"(?<![\w]){re.escape(term)}(?![\w])"
    return re.search(pattern, sentence, flags=re.IGNORECASE) is not None


def select_human_example(examples: list[str], word: str) -> str:
    for candidate in examples:
        sentence = _sentence_case(candidate)
        if example_is_suitable(sentence, word):
            return sentence
    return ""


def _definition_example(word: str, definition: str) -> str:
    term = " ".join(word.strip().split()).casefold()
    meaning = " ".join(definition.strip().rstrip(".").split())
    meaning = re.split(r"\s*(?:;|--)\s*", meaning, maxsplit=1)[0]
    meaning = meaning.replace(" referring to ", " for ")
    meaning = meaning.replace(" two or more ", " multiple ")
    prefix = f"The word “{term}” means "
    budget = MAX_EXAMPLE_LENGTH - len(prefix) - 1
    if len(meaning) > budget:
        for marker in (
            " by ",
            " that ",
            " which ",
            " with ",
            " involving ",
            " for ",
        ):
            shortened = meaning.split(marker, 1)[0]
            if len(shortened.split()) >= 3 and len(shortened) <= budget:
                meaning = shortened
                break
        else:
            shortened = meaning[: max(1, budget - 1)].rsplit(" ", 1)[0]
            meaning = f"{shortened}…"
    sentence = f"{prefix}{meaning}"
    return (
        sentence if sentence[-1] in ".!?" or sentence.endswith("…") else sentence + "."
    )


def _sentence_case(text: str) -> str:
    sentence = text.strip()
    if not sentence:
        return ""
    sentence = sentence[0].upper() + sentence[1:]
    if sentence[-1] not in ".!?":
        sentence += "."
    return sentence
