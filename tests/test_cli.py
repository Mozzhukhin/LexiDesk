from pathlib import Path

import lexidesk.cli
from lexidesk.database import WordRepository


def test_cli_card_and_review(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "cli.db"
    repository = WordRepository(path)
    word_id = repository.add_word(
        source_text="reliable",
        source_lang="en",
        target_text="надёжный",
    )
    repository.close()
    monkeypatch.setattr(lexidesk.cli, "database_path", lambda: path)

    card = lexidesk.cli.run(["card"])
    assert card["id"] == word_id
    assert card["direction"] == "EN → RU"

    next_card = lexidesk.cli.run(["review", str(word_id), "know"])
    assert next_card["id"] == word_id
    checked = lexidesk.cli.run(["check", str(word_id), "надёжный"])
    assert checked["grade"] == "correct"
    stats = lexidesk.cli.run(["stats"])
    assert stats["accuracy"] == 100.0
    restored = lexidesk.cli.run(["undo"])
    assert restored["undone"] is True
