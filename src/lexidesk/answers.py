from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from .dictionary import _damerau_levenshtein
from .models import Word

NON_WORD = re.compile(r"[^\w\s-]", re.UNICODE)


class AnswerGrade(StrEnum):
    CORRECT = "correct"
    CLOSE = "close"
    WRONG = "wrong"


@dataclass(frozen=True, slots=True)
class AnswerResult:
    grade: AnswerGrade
    expected: str
    matched: str

    @property
    def suggested_rating(self) -> str:
        return {
            AnswerGrade.CORRECT: "good",
            AnswerGrade.CLOSE: "hard",
            AnswerGrade.WRONG: "again",
        }[self.grade]


def normalize_answer(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    without_stress = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return " ".join(NON_WORD.sub("", without_stress).split())


def evaluate_answer(answer: str, word: Word) -> AnswerResult:
    cleaned = normalize_answer(answer)
    variants = [word.target_text, *word.alternatives]
    normalized_variants = [
        (variant, normalize_answer(variant)) for variant in variants if variant.strip()
    ]
    for original, normalized in normalized_variants:
        if cleaned and cleaned == normalized:
            return AnswerResult(AnswerGrade.CORRECT, word.target_text, original)

    if cleaned:
        closest = min(
            normalized_variants,
            key=lambda item: _damerau_levenshtein(cleaned, item[1]),
        )
        distance = _damerau_levenshtein(cleaned, closest[1])
        allowed = 1 if max(len(cleaned), len(closest[1])) >= 4 else 0
        if distance <= allowed:
            return AnswerResult(AnswerGrade.CLOSE, word.target_text, closest[0])

    return AnswerResult(AnswerGrade.WRONG, word.target_text, "")
