from __future__ import annotations

import re
import shutil
import sqlite3
from contextlib import suppress
from pathlib import Path

from .config import data_dir, examples_path
from .dictionary import normalize_headword

POS_CODES = {
    "noun": "n",
    "verb": "v",
    "adjective": "a",
    "adverb": "r",
}
MAX_EXAMPLE_LENGTH = 70


def cleanup_wordnet_sources(root: Path | None = None) -> int:
    """Remove corpora retained after the compact SQLite index is ready."""
    data_root = root or data_dir()
    removed = 0
    for source in (
        data_root / "nltk_data" / "corpora" / "wordnet",
        data_root / "wordnet",
    ):
        if source.is_dir():
            shutil.rmtree(source)
            removed += 1
    for directory in (
        data_root / "nltk_data" / "corpora",
        data_root / "nltk_data",
    ):
        with suppress(OSError):
            directory.rmdir()
    return removed


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
                SELECT example, definition, frequency
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
        best_frequency = max(int(row["frequency"]) for row in rows)
        for row in rows:
            example = _sentence_case(str(row["example"]))
            frequency = int(row["frequency"])
            if example_is_suitable(example, word) and frequency >= max(
                2, best_frequency // 3
            ):
                return example
        definition = str(rows[0]["definition"]).strip()
        if definition:
            return _definition_example(word, definition)
        return ""


def example_is_suitable(
    example: str,
    word: str,
    *,
    allow_inflection: bool = False,
) -> bool:
    sentence = " ".join(example.strip().split())
    term = " ".join(word.strip().split())
    if (
        not sentence
        or not term
        or len(sentence) > MAX_EXAMPLE_LENGTH
        or len(sentence.rstrip(".!?").split()) < 4
        or sentence.endswith(("…", "..."))
    ):
        return False
    pattern = rf"(?<![\w]){re.escape(term)}(?![\w])"
    if re.search(pattern, sentence, flags=re.IGNORECASE) is not None:
        return True
    if not allow_inflection or " " in term:
        return False
    normalized_term = normalize_headword(term)
    if len(normalized_term) < 5:
        return False
    stem_length = max(4, len(normalized_term) - 3)
    stem = normalized_term[:stem_length]
    return any(
        normalize_headword(token.strip(".,!?;:«»“”\"'()")).startswith(stem)
        for token in sentence.split()
    )


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
