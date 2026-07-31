import json
import sqlite3
from datetime import timedelta
from pathlib import Path

from lexidesk.api import (
    adaptive_quiz_due,
    card_payload,
    mixed_quiz_due,
    quiz_choices,
    quiz_variants,
)
from lexidesk.database import WordRepository
from lexidesk.dictionary import OfflineDictionary
from lexidesk.service import LexiDeskService


def test_service_processes_json_requests(tmp_path: Path) -> None:
    repository = WordRepository(tmp_path / "service.db")
    repository.add_word(
        source_text="reliable",
        source_lang="en",
        target_text="надёжный",
    )
    service = LexiDeskService(repository)
    stats = json.loads(service.Request('{"command":"stats"}'))
    assert stats["total"] == 1
    invalid = json.loads(service.Request("[]"))
    assert invalid["type"] == "ValueError"
    repository.close()


def test_quiz_choices_use_deck_and_offline_dictionary(tmp_path: Path) -> None:
    dictionary_path = tmp_path / "dictionary.db"
    connection = sqlite3.connect(dictionary_path)
    connection.execute(
        """
        CREATE TABLE entries (
            source_lang TEXT,
            normalized TEXT,
            headword TEXT,
            translations_json TEXT,
            part_of_speech TEXT
        )
        """
    )
    connection.executemany(
        "INSERT INTO entries VALUES (?, ?, ?, ?, ?)",
        [
            ("en", "window", "window", '["окно"]', "noun"),
            ("en", "door", "door", '["дверь"]', "noun"),
        ],
    )
    connection.commit()
    connection.close()

    repository = WordRepository(tmp_path / "quiz.db")
    word_id = repository.add_word(
        source_text="suggestion",
        source_lang="en",
        target_text="предложение",
        part_of_speech="noun",
    )
    repository.add_word(
        source_text="destruction",
        source_lang="en",
        target_text="разрушение",
    )
    choices = quiz_choices(
        repository.get_word(word_id),
        repository,
        OfflineDictionary(dictionary_path),
    )

    assert len(choices) == 4
    assert len(set(choices)) == 4
    assert "предложение" in choices
    assert "разрушение" in choices
    repository.close()


def test_quiz_payload_supports_reverse_cloze_and_context(tmp_path: Path) -> None:
    repository = WordRepository(tmp_path / "formats.db")
    records = [
        ("ambiguous", "двусмысленный", "An ambiguous answer has two meanings."),
        ("reliable", "надёжный", "A reliable source checks every fact."),
        ("plural", "множественный", "The word plural refers to several items."),
        ("careful", "осторожный", "A careful person checks the details."),
    ]
    ids = [
        repository.add_word(
            source_text=source,
            source_lang="en",
            target_text=target,
            part_of_speech="adjective",
            example=example,
        )
        for source, target, example in records
    ]
    word = repository.get_word(ids[0])

    variants = quiz_variants(word, repository)
    for kind in ("reverse", "cloze", "context"):
        payload = variants[kind]
        assert payload["type"] == kind
        assert payload["answer"]
        assert len(payload["choices"]) == 4
        if kind == "context":
            assert all("___" in choice for choice in payload["choices"])
            assert all("ambiguous" not in choice for choice in payload["choices"])
    repository.close()


def test_cloze_quiz_rotates_between_saved_examples(tmp_path: Path, monkeypatch) -> None:
    repository = WordRepository(tmp_path / "varied-cloze.db")
    records = [
        ("reliable", "надёжный"),
        ("careful", "осторожный"),
        ("useful", "полезный"),
        ("simple", "простой"),
    ]
    ids = [
        repository.add_word(
            source_text=source,
            source_lang="en",
            target_text=target,
            part_of_speech="adjective",
            example=f"The result was {source} for everyone.",
        )
        for source, target in records
    ]
    repository.replace_examples(
        ids[0],
        [
            (
                "A reliable source checks each fact.",
                "Надёжный источник проверяет факты.",
            ),
            ("The reliable train arrived on time.", "Надёжный поезд прибыл вовремя."),
            ("Her reliable method worked again.", "Её надёжный метод снова сработал."),
        ],
    )
    saved_examples = [example for example, _ in repository.examples_for_word(ids[0])]
    choices = iter(saved_examples)
    monkeypatch.setattr(
        "lexidesk.api.random.choice",
        lambda items: next(choices) if items == saved_examples else items[0],
    )
    word = repository.get_word(ids[0])

    prompts = [quiz_variants(word, repository)["cloze"]["prompt"] for _ in range(3)]

    assert len(set(prompts)) == 3
    assert all("___" in prompt for prompt in prompts)
    repository.close()


def test_russian_cloze_uses_safe_fallback_distractors(tmp_path: Path) -> None:
    repository = WordRepository(tmp_path / "russian-cloze.db")
    word_id = repository.add_word(
        source_text="ограниченный",
        source_lang="ru",
        target_text="restricted",
        part_of_speech="adjective",
        example="Доступ в эту зону ограниченный после закрытия.",
        example_translation="Access to this area is restricted after closing.",
    )
    repository.add_word(
        source_text="полезный",
        source_lang="ru",
        target_text="useful",
    )
    variants = quiz_variants(repository.get_word(word_id), repository)

    assert variants["cloze"]["prompt"] == "Доступ в эту зону ___ после закрытия."
    assert len(variants["cloze"]["choices"]) == 4
    assert variants["reverse"]["instruction"] == "Choose the Russian word"
    assert len(variants["context"]["choices"]) == 4
    assert all("___" in choice for choice in variants["context"]["choices"])
    repository.close()


def test_quiz_mistakes_are_available_to_analytics(tmp_path: Path) -> None:
    repository = WordRepository(tmp_path / "analytics.db")
    word_id = repository.add_word(
        source_text="ambiguous",
        source_lang="en",
        target_text="двусмысленный",
    )
    repository.review(
        word_id,
        "again",
        quiz_type="translation",
        selected_answer="очевидный",
        correct_answer="двусмысленный",
    )

    assert repository.quiz_breakdown()[0]["accuracy"] == 0.0
    assert repository.common_confusions()[0]["selected"] == "очевидный"
    repository.close()


def test_adaptive_mode_introduces_then_quizzes_new_cards(tmp_path: Path) -> None:
    repository = WordRepository(tmp_path / "adaptive.db")
    for index in range(6):
        repository.add_word(
            source_text=f"word-{index}",
            source_lang="en",
            target_text=f"слово-{index}",
        )

    introductions = [repository.next_word(adaptive=True) for _ in range(6)]

    assert all(word is not None for word in introductions)
    assert all(word.view_count == 1 for word in introductions if word is not None)
    assert all(
        not adaptive_quiz_due(word) for word in introductions if word is not None
    )

    tested = repository.next_word(adaptive=True)
    assert tested is not None
    assert tested.view_count == 2
    assert adaptive_quiz_due(tested)
    repository.close()


def test_fsrs_due_time_controls_adaptive_quiz(tmp_path: Path) -> None:
    repository = WordRepository(tmp_path / "adaptive-due.db")
    word_id = repository.add_word(
        source_text="reliable",
        source_lang="en",
        target_text="надёжный",
    )
    repository.next_word(adaptive=True)
    reviewed = repository.review(word_id, "again")

    assert reviewed.last_reviewed_at is not None
    assert reviewed.due_at - reviewed.last_reviewed_at == timedelta(minutes=10)
    assert not adaptive_quiz_due(reviewed)
    assert adaptive_quiz_due(reviewed, reviewed.due_at + timedelta(seconds=1))
    repository.close()


def test_mixed_mode_guarantees_maintenance_quiz_on_fifth_card(
    tmp_path: Path,
) -> None:
    repository = WordRepository(tmp_path / "mixed-maintenance.db")
    word_id = repository.add_word(
        source_text="reliable",
        source_lang="en",
        target_text="надёжный",
    )
    repository.next_word(adaptive=True)
    word = repository.review(word_id, "good")

    assert not adaptive_quiz_due(word)
    assert not mixed_quiz_due(word, 4)
    assert mixed_quiz_due(word, 5)
    assert card_payload(word, repository)["quiz_eligible"] is True
    repository.close()
