import json
import sqlite3
from pathlib import Path

from lexidesk.api import quiz_choices, quiz_variants
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
