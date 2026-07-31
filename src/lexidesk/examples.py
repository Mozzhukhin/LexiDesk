from __future__ import annotations

import re
import shutil
import sqlite3
import unicodedata
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
            if example_is_informative(example, word) and frequency >= max(
                2, best_frequency // 3
            ):
                return example
        definition = str(rows[0]["definition"]).strip()
        if definition:
            return _definition_example(word, definition, category)
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
    normalized_term = unicodedata.normalize("NFC", normalize_headword(term))
    if len(normalized_term) < 5:
        return False
    stem_length = max(
        4,
        len(normalized_term) - (5 if re.search(r"[а-яё]", normalized_term) else 3),
    )
    stem = normalized_term[:stem_length]
    return any(
        unicodedata.normalize(
            "NFC",
            normalize_headword(token.strip(".,!?;:«»“”\"'()")),
        ).startswith(stem)
        for token in sentence.split()
    )


def example_is_informative(
    example: str,
    word: str,
    *,
    allow_inflection: bool = False,
) -> bool:
    """Reject examples that mention a word without showing its meaning."""
    if not example_is_suitable(
        example,
        word,
        allow_inflection=allow_inflection,
    ):
        return False
    normalized = " ".join(example.casefold().split())
    weak_patterns = (
        r"\bthe (?:word|term|phrase)\b.*\b(?:means|appears|appeared|is used)\b",
        r"\bthe text contains\b",
        r"\bi heard the phrase\b",
        r"\bthe intended meaning here\b",
        r"\bno frame of reference\b",
        r"\b(?:слово|термин)\b.*\bозначает\b",
        r"\bв тексте (?:встретил(?:ось|ась)?|содержится)\b",
        r"\bпонятие\b.*\b(?:важн|повлиял)",
        r"\b(?:выражение|фраза)\b.*\b(?:помог|передал)",
        r"\bважный смысл здесь\b",
        r"\bрезультат можно описать как\b",
    )
    return not any(re.search(pattern, normalized) for pattern in weak_patterns)


def select_human_example(examples: list[str], word: str) -> str:
    for candidate in examples:
        sentence = _sentence_case(candidate)
        if example_is_informative(sentence, word):
            return sentence
    return ""


def _definition_example(
    word: str,
    definition: str,
    part_of_speech: str = "",
) -> str:
    term = " ".join(word.strip().split()).casefold()
    meaning = " ".join(definition.strip().rstrip(".").split())
    semantics = meaning.casefold()
    category = part_of_speech.casefold()
    if any(token in semantics for token in ("restriction", "limited", "limit the")):
        sentence = f"Access to this area is {term} after dark."
    elif any(
        token in semantics
        for token in ("interpretation", "uncertain", "more than one possible meaning")
    ):
        sentence = f"The instructions were {term}, so we asked for clarification."
    elif any(
        token in semantics
        for token in (
            "destroy",
            "severe damage",
            "damage so severe",
            "no longer exists",
            "termination",
        )
    ):
        sentence = f"The storm caused widespread {term} along the coast."
    elif any(
        token in semantics
        for token in ("grammatical number", "form of a word", "two or more")
    ):
        sentence = f"Cats is the {term} of cat."
    elif any(token in semantics for token in ("idea that is suggested", "proposal")):
        sentence = f"Her {term} helped the team reach a decision."
    elif any(token in semantics for token in ("occurrences", "given time period")):
        sentence = f"The {term} of the signal increased during the test."
    elif category.startswith("noun"):
        sentence = f"We discussed the {term} before making a final decision."
    elif category.startswith("verb"):
        sentence = f"They agreed to {term} when the time was right."
    elif category.startswith("adj"):
        sentence = f"The final result was clearly {term}."
    elif category.startswith("adv"):
        sentence = f"She responded {term} during the meeting."
    else:
        sentence = f"We encountered {term} during the discussion."
    if len(sentence) <= MAX_EXAMPLE_LENGTH:
        return sentence
    return f"The situation involved {term}."


def _sentence_case(text: str) -> str:
    sentence = text.strip()
    if not sentence:
        return ""
    sentence = sentence[0].upper() + sentence[1:]
    if sentence[-1] not in ".!?":
        sentence += "."
    return sentence
