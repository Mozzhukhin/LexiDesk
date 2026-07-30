import json
import sqlite3
from pathlib import Path

from lexidesk.dictionary import OfflineDictionary, normalize_headword
from lexidesk.translation import OfflineTranslator


def test_normalize_headword_removes_stress_mark() -> None:
    assert normalize_headword("Возможность") == normalize_headword("возможность")
    assert normalize_headword("све́тлый") == normalize_headword("светлый")


def test_dictionary_lookup(tmp_path: Path) -> None:
    path = tmp_path / "dictionary.db"
    connection = sqlite3.connect(path)
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
    connection.execute(
        "INSERT INTO entries VALUES (?, ?, ?, ?, ?)",
        (
            "en",
            "light",
            "light",
            json.dumps(["светлый", "лёгкий"], ensure_ascii=False),
            "adjective",
        ),
    )
    connection.executemany(
        "INSERT INTO entries VALUES (?, ?, ?, ?, ?)",
        [
            (
                "en",
                "destruction",
                "destruction",
                json.dumps(["разрушение"], ensure_ascii=False),
                "noun",
            ),
            (
                "en",
                "distraction",
                "distraction",
                json.dumps(["отвлечение"], ensure_ascii=False),
                "noun",
            ),
        ],
    )
    connection.commit()
    connection.close()

    result = OfflineDictionary(path).lookup("Light", "en")
    assert result is not None
    assert result.translations == ("светлый", "лёгкий")
    assert result.part_of_speech == "adjective"

    translation = OfflineTranslator(OfflineDictionary(path)).translate("Light")
    assert translation.translation == "светлый"
    assert translation.dictionary_match is True

    suggestions = OfflineDictionary(path).suggestions("distruction", "en")
    assert [suggestion.entry.headword for suggestion in suggestions] == [
        "destruction",
        "distraction",
    ]
    assert all(suggestion.distance == 1 for suggestion in suggestions)
    distractors = OfflineDictionary(path).random_translations(
        "en",
        excluded={"разрушение"},
        limit=2,
    )
    assert len(distractors) == 2
    assert "разрушение" not in distractors


def test_corrupt_dictionary_falls_back_to_no_result(tmp_path: Path) -> None:
    path = tmp_path / "broken.db"
    path.write_bytes(b"not a sqlite database")
    assert OfflineDictionary(path).lookup("light", "en") is None
