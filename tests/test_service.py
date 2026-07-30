import json
import sqlite3
from pathlib import Path

from lexidesk.api import quiz_choices
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
