from pathlib import Path

import pytest

from lexidesk.database import WordRepository
from lexidesk.transfer import export_words, import_words


def test_json_round_trip(tmp_path: Path) -> None:
    source = WordRepository(tmp_path / "source.db")
    source.add_word(
        source_text="look forward to",
        source_lang="en",
        target_text="с нетерпением ждать",
        alternatives=["ожидать"],
        part_of_speech="phrase",
        transcription="/lʊk ˈfɔːwəd tuː/",
        forms=["looks forward to", "looked forward to"],
        frequency="common",
        example="I look forward to meeting you.",
        example_translation="Я с нетерпением жду встречи.",
        tags=["work", "phrases"],
        source_info="Course notes",
    )
    export_path = tmp_path / "words.json"
    assert export_words(source, export_path) == 1

    target = WordRepository(tmp_path / "target.db")
    imported, skipped = import_words(target, export_path)
    assert (imported, skipped) == (1, 0)
    word = target.list_words()[0]
    assert word.source_text == "look forward to"
    assert word.tags == ["work", "phrases"]
    assert word.forms == ["looks forward to", "looked forward to"]
    assert word.frequency == "common"
    assert word.transcription == "/lʊk ˈfɔːwəd tuː/"
    assert word.source_info == "Course notes"
    assert word.example_translation == "Я с нетерпением жду встречи."
    assert len(target.examples_for_word(word.id)) == 1

    source.close()
    target.close()


def test_invalid_json_shape_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text('["not a card"]', encoding="utf-8")
    repository = WordRepository(tmp_path / "target.db")
    with pytest.raises(ValueError, match="list of vocabulary cards"):
        import_words(repository, path)
    repository.close()
