from __future__ import annotations

import random
import re
from datetime import UTC, datetime
from typing import Any

from .answers import evaluate_answer
from .database import WordRepository
from .dictionary import OfflineDictionary, normalize_headword
from .languages import language_name
from .models import Word

COMMON_DISTRACTORS = {
    "ru": (
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
    "en": (
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

CONTEXT_DISTRACTORS = {
    "en": (
        "We had little ___ before the meeting began.",
        "This ___ helped the team solve the problem.",
        "She finished the ___ ahead of schedule.",
        "They finally found the right ___ to the question.",
    ),
    "ru": (
        "До начала встречи оставалось мало ___.",
        "Этот ___ помог команде решить проблему.",
        "Она закончила ___ раньше срока.",
        "Они наконец нашли правильный ___ на вопрос.",
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
            "target_language": "",
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
        "target_language": word.target_lang,
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
    variants = quiz_variants(word, repository, dictionary) if word is not None else {}
    quiz = random.choice(list(variants.values())) if variants else {}
    payload["quiz"] = quiz
    payload["quizzes"] = variants
    payload["choices"] = quiz.get("choices", [])
    payload["quiz_probability"] = (
        quiz_probability(word, repository) if word is not None else 0
    )
    payload["adaptive_quiz"] = adaptive_quiz_due(word) if word is not None else False
    payload["quiz_eligible"] = quiz_eligible(word) if word is not None else False
    return payload


def adaptive_quiz_due(word: Word, now: datetime | None = None) -> bool:
    """Return whether Mixed mode should actively test this presentation."""
    reviews = word.know_count + word.dont_know_count
    if reviews == 0:
        return word.view_count >= 2
    return word.due_at <= (now or datetime.now(UTC))


def quiz_eligible(word: Word) -> bool:
    """Return whether a card has been seen enough for a maintenance quiz."""
    return word.view_count >= 2 or word.know_count + word.dont_know_count > 0


def mixed_quiz_due(
    word: Word,
    ordinary_cards_since_quiz: int,
    now: datetime | None = None,
) -> bool:
    """Combine FSRS timing with a guaranteed fifth-card maintenance check."""
    return adaptive_quiz_due(word, now) or (
        quiz_eligible(word) and ordinary_cards_since_quiz >= 5
    )


def quiz_probability(word: Word, repository: WordRepository) -> float:
    reviews = word.know_count + word.dont_know_count
    if reviews == 0:
        return 0.55
    miss_rate = word.dont_know_count / reviews
    if miss_rate >= 0.4:
        return 0.8
    recall = repository.card_retrievability(word)
    if recall is not None and recall < 0.8:
        return 0.7
    if (word.stability or 0) >= 30:
        return 0.2
    return 0.42


def quiz_payload(
    word: Word,
    repository: WordRepository,
    dictionary: OfflineDictionary | None = None,
) -> dict[str, Any]:
    variants = quiz_variants(word, repository, dictionary)
    return random.choice(list(variants.values())) if variants else {}


def quiz_variants(
    word: Word,
    repository: WordRepository,
    dictionary: OfflineDictionary | None = None,
) -> dict[str, dict[str, Any]]:
    candidates = _ranked_candidates(word, repository)
    translation_choices = quiz_choices(
        word,
        repository,
        dictionary,
        candidates=candidates,
    )
    reverse_candidates = [candidate.source_text for candidate in candidates]
    reverse_candidates.extend(COMMON_DISTRACTORS.get(word.source_lang, ()))
    reverse_choices = _distinct_choices(word.source_text, reverse_candidates)
    variants: dict[str, dict[str, Any]] = {
        "typing": {
            "type": "typing",
            "prompt": word.source_text,
            "answer": word.target_text,
            "choices": [],
            "instruction": "Type the translation",
        }
    }
    if len(translation_choices) == 4:
        variants["translation"] = {
            "type": "translation",
            "prompt": word.source_text,
            "answer": word.target_text,
            "choices": translation_choices,
            "instruction": "Choose the translation",
        }
    if len(reverse_choices) == 4:
        variants["reverse"] = {
            "type": "reverse",
            "prompt": word.target_text,
            "answer": word.source_text,
            "choices": reverse_choices,
            "instruction": f"Choose the {language_name(word.source_lang)} word",
        }
    cloze = _cloze_sentence(word)
    cloze_language, cloze_answer = _cloze_side(word)
    cloze_candidates = [
        candidate.source_text
        if cloze_language == word.source_lang
        else candidate.target_text
        for candidate in candidates
    ]
    cloze_candidates.extend(COMMON_DISTRACTORS.get(cloze_language, ()))
    cloze_choices = _distinct_choices(
        cloze_answer,
        cloze_candidates,
    )
    if cloze and len(cloze_choices) == 4:
        variants["cloze"] = {
            "type": "cloze",
            "prompt": cloze,
            "answer": cloze_answer,
            "choices": cloze_choices,
            "instruction": "Complete the sentence",
        }
    category = word.part_of_speech.split(",", 1)[0].strip().casefold()
    same_category = [
        candidate
        for candidate in candidates
        if candidate.part_of_speech.split(",", 1)[0].strip().casefold() == category
    ]
    correct_context = cloze
    context_candidates = [
        *same_category,
        *(candidate for candidate in candidates if candidate not in same_category),
    ]
    context_choices = _distinct_choices(
        correct_context,
        [
            masked
            for candidate in context_candidates
            if (masked := _masked_context(candidate))
        ]
        + list(CONTEXT_DISTRACTORS.get(cloze_language, ())),
    )
    if correct_context and len(context_choices) == 4:
        variants["context"] = {
            "type": "context",
            "prompt": f"Where does “{cloze_answer}” fit best?",
            "answer": correct_context,
            "choices": context_choices,
            "instruction": "Choose the matching context",
        }
    return variants


def quiz_choices(
    word: Word,
    repository: WordRepository,
    dictionary: OfflineDictionary | None = None,
    *,
    candidates: list[Word] | None = None,
) -> list[str]:
    excluded = {word.target_text, *word.alternatives}
    seen = {normalize_headword(value) for value in excluded}
    distractors: list[str] = []

    candidate_pool = (
        candidates if candidates is not None else _ranked_candidates(word, repository)
    )
    for candidate in candidate_pool:
        value = candidate.target_text.strip()
        key = normalize_headword(value)
        if (
            candidate.id != word.id
            and candidate.source_lang == word.source_lang
            and candidate.target_lang == word.target_lang
            and value
            and key not in seen
        ):
            distractors.append(value)
            seen.add(key)
        if len(distractors) == 3:
            break

    if len(distractors) < 3 and {word.source_lang, word.target_lang} == {"en", "ru"}:
        offline_dictionary = dictionary or OfflineDictionary()
        additions = offline_dictionary.random_translations(
            word.source_lang,
            excluded=excluded | set(distractors),
            part_of_speech=word.part_of_speech,
            limit=3 - len(distractors),
        )
        distractors.extend(additions)

    common_candidates = list(COMMON_DISTRACTORS.get(word.target_lang, ()))
    random.shuffle(common_candidates)
    for value in common_candidates:
        key = normalize_headword(value)
        if key not in seen:
            distractors.append(value)
            seen.add(key)
        if len(distractors) == 3:
            break

    if len(distractors) < 3:
        return []
    choices = [word.target_text, *distractors[:3]]
    random.shuffle(choices)
    return choices


def _ranked_candidates(word: Word, repository: WordRepository) -> list[Word]:
    return repository.quiz_candidates(word)


def _distinct_choices(answer: str, candidates: list[str]) -> list[str]:
    if not answer:
        return []
    values = [answer]
    seen = {normalize_headword(answer)}
    for value in candidates:
        key = normalize_headword(value)
        if value and key not in seen:
            values.append(value)
            seen.add(key)
        if len(values) == 4:
            break
    if len(values) < 4:
        return []
    random.shuffle(values)
    return values


def _cloze_sentence(word: Word) -> str:
    cloze_language, term = _cloze_side(word)
    if cloze_language == word.source_lang:
        example = word.example
    else:
        example = word.example_translation
    if not example or not term:
        return ""
    pattern = re.compile(
        rf"(?<!\w){re.escape(term)}(?!\w)",
        flags=re.IGNORECASE,
    )
    masked, replacements = pattern.subn("___", example, count=1)
    if replacements:
        return masked
    normalized_term = normalize_headword(term)
    if " " in normalized_term or len(normalized_term) < 5:
        return ""
    stem_length = max(4, len(normalized_term) - 3)
    stem = normalized_term[:stem_length]
    for match in re.finditer(r"[^\W\d_]+", example, flags=re.UNICODE):
        if normalize_headword(match.group()).startswith(stem):
            return f"{example[: match.start()]}___{example[match.end() :]}"
    return ""


def _cloze_side(word: Word) -> tuple[str, str]:
    """Prefer English for its semantic example index, otherwise use source."""
    if word.source_lang == "en" or word.target_lang != "en":
        return word.source_lang, word.source_text
    return word.target_lang, word.target_text


def _masked_context(word: Word) -> str:
    return _cloze_sentence(word)


def execute_request(
    repository: WordRepository,
    request: dict[str, Any],
) -> dict[str, Any]:
    command = str(request.get("command", ""))
    if command == "card":
        exclude = request.get("exclude")
        source_lang = str(request.get("source_lang", ""))
        target_lang = str(request.get("target_lang", ""))
        return card_payload(
            repository.next_word(
                int(exclude) if exclude is not None else None,
                adaptive=bool(request.get("adaptive", False)),
                source_lang=source_lang,
                target_lang=target_lang,
            ),
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
            quiz_type=str(request.get("quiz_type", "")),
            selected_answer=str(request.get("selected_answer", "")),
            correct_answer=str(request.get("correct_answer", "")),
        )
        return card_payload(
            repository.next_word(
                word_id,
                adaptive=bool(request.get("adaptive", False)),
                source_lang=str(request.get("source_lang", "")),
                target_lang=str(request.get("target_lang", "")),
            ),
            repository,
        )
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
        source_lang = str(request.get("source_lang", ""))
        target_lang = str(request.get("target_lang", ""))
        return repository.statistics(source_lang, target_lang)
    if command == "analytics":
        return {
            "statistics": repository.statistics(),
            "activity": repository.review_activity(int(request.get("days", 30))),
            "difficult": [
                word_payload(word, repository)
                for word in repository.difficult_words(int(request.get("limit", 10)))
            ],
            "quiz_breakdown": repository.quiz_breakdown(),
            "confusions": repository.common_confusions(),
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
