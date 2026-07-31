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
        examples = self.lookup_many(word, part_of_speech, limit=1)
        return examples[0] if examples else ""

    def lookup_many(
        self,
        word: str,
        part_of_speech: str = "",
        *,
        limit: int = 5,
    ) -> list[str]:
        if not self.available:
            return []
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
            return []
        finally:
            if connection is not None:
                connection.close()
        if not rows:
            return []
        best_frequency = max(int(row["frequency"]) for row in rows)
        selected: list[str] = []
        seen: set[str] = set()
        for row in rows:
            example = _sentence_case(str(row["example"]))
            frequency = int(row["frequency"])
            if example_is_informative(example, word) and frequency >= max(
                2, best_frequency // 3
            ):
                key = example.casefold()
                if key not in seen:
                    selected.append(example)
                    seen.add(key)
                if len(selected) >= limit:
                    return selected
        definition = str(rows[0]["definition"]).strip()
        if definition:
            for example in _definition_examples(word, definition, category):
                key = example.casefold()
                if key not in seen and example_is_informative(example, word):
                    selected.append(example)
                    seen.add(key)
                if len(selected) >= limit:
                    break
        return selected


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
        r"\bрезультат оказался\b.*\bв этой ситуации\b",
        r"\bвыражение\b.*\b(?:помогло уточнить|точно передало)\b",
        r"\bпонятие\b.*\bстало (?:главным|центральным)\b",
        r"\bмы обсудили\b.*\b(?:перед|прежде чем)\b",
        r"\bстало центральн\w* в (?:их|этом) разговоре\b",
        r"\bwe (?:discussed the|encountered)\b.*"
        r"\b(?:before making|during the discussion)\b",
        r"\bbecame central to (?:their|the) conversation\b",
        r"\bexplained the\b.*\b(?:practical|clear) example\b",
        r"\bthe final result was clearly\b",
        r"\bthe situation became increasingly\b.*\bover time\b",
        r"\bони использовали\b.*\b(?:объясняя|при объяснении)\b",
        r"\bthey used\b.*\bwhile explaining\b",
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
    examples = _definition_examples(word, definition, part_of_speech)
    return examples[0] if examples else ""


def _definition_examples(
    word: str,
    definition: str,
    part_of_speech: str = "",
) -> list[str]:
    term = " ".join(word.strip().split()).casefold()
    meaning = " ".join(definition.strip().rstrip(".").split())
    semantics = meaning.casefold()
    category = part_of_speech.casefold()
    if any(token in semantics for token in ("restriction", "limited", "limit the")):
        sentences = [
            f"Access to this area is {term} after dark.",
            f"The {term} section is open only to authorized staff.",
            f"Travel remained {term} until the road was safe again.",
        ]
    elif any(
        token in semantics
        for token in ("interpretation", "uncertain", "more than one possible meaning")
    ):
        sentences = [
            f"The instructions were {term}, so we asked for clarification.",
            f"Her {term} reply could be understood in two different ways.",
            f"The ending was deliberately {term} and invited discussion.",
        ]
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
        sentences = [
            f"The storm caused widespread {term} along the coast.",
            f"The fire left a trail of {term} through the old building.",
            f"Years of neglect led to the {term} of the historic bridge.",
        ]
    elif any(
        token in semantics
        for token in ("grammatical number", "form of a word", "two or more")
    ):
        sentences = [
            f"Cats is the {term} of cat.",
            f"We use the {term} when talking about more than one item.",
            f"Children is an irregular {term} form in English.",
        ]
    elif any(token in semantics for token in ("idea that is suggested", "proposal")):
        sentences = [
            f"Her {term} helped the team reach a decision.",
            f"Everyone considered his {term} before the meeting ended.",
            f"The manager accepted our {term} for improving the service.",
        ]
    elif any(token in semantics for token in ("occurrences", "given time period")):
        sentences = [
            f"The {term} of the signal increased during the test.",
            f"Doctors measured the {term} of these events over a week.",
            f"The report tracks how the {term} changes over time.",
        ]
    elif category.startswith("noun"):
        sentences = [
            f"We discussed the {term} before making a final decision.",
            f"The {term} became central to their conversation.",
            f"She explained the {term} with a practical example.",
        ]
    elif category.startswith("verb"):
        sentences = [
            f"They agreed to {term} when the time was right.",
            f"We may need to {term} before the deadline.",
            f"She showed us how to {term} safely.",
        ]
    elif category.startswith("adj"):
        sentences = [
            f"The final result was clearly {term}.",
            f"His explanation seemed {term} to everyone in the room.",
            f"The situation became increasingly {term} over time.",
        ]
    elif category.startswith("adv"):
        sentences = [
            f"She responded {term} during the meeting.",
            f"The team worked {term} to solve the problem.",
            f"He explained the decision {term} and calmly.",
        ]
    else:
        sentences = [
            f"We encountered {term} during the discussion.",
            f"The conversation provided a clear example of {term}.",
            f"They used {term} while explaining the situation.",
        ]
    return [sentence for sentence in sentences if len(sentence) <= MAX_EXAMPLE_LENGTH]


def _sentence_case(text: str) -> str:
    sentence = text.strip()
    if not sentence:
        return ""
    sentence = sentence[0].upper() + sentence[1:]
    if sentence[-1] not in ".!?":
        sentence += "."
    return sentence
