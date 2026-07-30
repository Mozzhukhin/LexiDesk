from __future__ import annotations

import random
from typing import Any

from .answers import evaluate_answer
from .database import WordRepository
from .dictionary import OfflineDictionary, normalize_headword
from .models import Word

COMMON_DISTRACTORS = {
    "en": (
        "время",
        "человек",
        "работа",
        "место",
        "вопрос",
        "ответ",
        "возможность",
        "решение",
        "причина",
        "результат",
        "развитие",
        "изменение",
        "поддержка",
        "знание",
        "опыт",
        "цель",
        "выбор",
        "помощь",
        "ошибка",
        "пример",
    ),
    "ru": (
        "time",
        "person",
        "work",
        "place",
        "question",
        "answer",
        "opportunity",
        "decision",
        "reason",
        "result",
        "development",
        "change",
        "support",
        "knowledge",
        "experience",
        "goal",
        "choice",
        "help",
        "mistake",
        "example",
    ),
}


def word_payload(
    word: Word | None,
    repository: WordRepository | None = None,
) -> dict[str, Any]:
    if word is None:
        return {
            "empty": True,
            "id": 0,
            "source": "",
            "translation": "",
            "direction": "",
            "part_of_speech": "",
            "alternatives": [],
            "transcription": "",
            "forms": [],
            "frequency": "",
            "example": "",
            "example_translation": "",
            "tags": [],
            "source_info": "",
            "status": "Empty",
            "retrievability": None,
        }
    probability = repository.card_retrievability(word) if repository else None
    return {
        "empty": False,
        "id": word.id,
        "source": word.source_text,
        "translation": word.target_text,
        "source_language": word.source_lang,
        "direction": word.direction,
        "part_of_speech": word.part_of_speech,
        "alternatives": word.alternatives,
        "transcription": word.transcription,
        "forms": word.forms,
        "frequency": word.frequency,
        "example": word.example,
        "example_translation": word.example_translation,
        "tags": word.tags,
        "source_info": word.source_info,
        "status": word.status,
        "stability": word.stability,
        "difficulty": word.difficulty,
        "retrievability": round(probability * 100, 1)
        if probability is not None
        else None,
        "due_at": word.due_at.isoformat(),
    }


def card_payload(
    word: Word | None,
    repository: WordRepository,
    dictionary: OfflineDictionary | None = None,
) -> dict[str, Any]:
    payload = word_payload(word, repository)
    payload["choices"] = (
        quiz_choices(word, repository, dictionary) if word is not None else []
    )
    return payload


def quiz_choices(
    word: Word,
    repository: WordRepository,
    dictionary: OfflineDictionary | None = None,
) -> list[str]:
    excluded = {word.target_text, *word.alternatives}
    seen = {normalize_headword(value) for value in excluded}
    distractors: list[str] = []

    for candidate in repository.list_words():
        value = candidate.target_text.strip()
        key = normalize_headword(value)
        if (
            candidate.id != word.id
            and candidate.source_lang == word.source_lang
            and value
            and key not in seen
        ):
            distractors.append(value)
            seen.add(key)
        if len(distractors) == 3:
            break

    common_candidates = list(COMMON_DISTRACTORS[word.source_lang])
    random.shuffle(common_candidates)
    for value in common_candidates:
        key = normalize_headword(value)
        if key not in seen:
            distractors.append(value)
            seen.add(key)
        if len(distractors) == 3:
            break

    if len(distractors) < 3:
        offline_dictionary = dictionary or OfflineDictionary()
        additions = offline_dictionary.random_translations(
            word.source_lang,
            excluded=excluded | set(distractors),
            part_of_speech=word.part_of_speech,
            limit=3 - len(distractors),
        )
        distractors.extend(additions)

    if len(distractors) < 3:
        return []
    choices = [word.target_text, *distractors[:3]]
    random.shuffle(choices)
    return choices


def execute_request(
    repository: WordRepository,
    request: dict[str, Any],
) -> dict[str, Any]:
    command = str(request.get("command", ""))
    if command == "card":
        exclude = request.get("exclude")
        return card_payload(
            repository.next_word(int(exclude) if exclude is not None else None),
            repository,
        )
    if command == "get":
        return card_payload(
            repository.get_word(int(request["word_id"])),
            repository,
        )
    if command == "review":
        word_id = int(request["word_id"])
        repository.review(
            word_id,
            str(request["rating"]),
            _optional_int(request.get("duration_ms")),
        )
        return card_payload(repository.next_word(word_id), repository)
    if command == "undo":
        restored = repository.undo_last_review()
        payload = card_payload(restored, repository)
        payload["undone"] = restored is not None
        return payload
    if command == "check":
        word = repository.get_word(int(request["word_id"]))
        result = evaluate_answer(str(request.get("answer", "")), word)
        return {
            "grade": result.grade,
            "expected": result.expected,
            "matched": result.matched,
            "suggested_rating": result.suggested_rating,
        }
    if command == "stats":
        return repository.statistics()
    if command == "analytics":
        return {
            "statistics": repository.statistics(),
            "activity": repository.review_activity(int(request.get("days", 30))),
            "difficult": [
                word_payload(word, repository)
                for word in repository.difficult_words(int(request.get("limit", 10)))
            ],
        }
    if command == "configure":
        retention = float(request.get("desired_retention", 0.9))
        if not 0.7 <= retention <= 0.99:
            raise ValueError("Desired retention must be between 0.70 and 0.99.")
        repository.desired_retention = retention
        return {"configured": True, "desired_retention": retention}
    raise ValueError(f"Unsupported command: {command}")


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("Expected an integer value.")
    return int(value)
