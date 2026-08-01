from pathlib import Path

import lexidesk.cli
from lexidesk.database import WordRepository
from lexidesk.settings import SettingsStore


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

    card = lexidesk.cli.run(["card", "--adaptive"])
    assert card["id"] == word_id
    assert card["direction"] == "EN → RU"
    assert card["adaptive_quiz"] is False

    next_card = lexidesk.cli.run(["review", str(word_id), "know"])
    assert next_card["id"] == word_id
    checked = lexidesk.cli.run(["check", str(word_id), "надёжный"])
    assert checked["grade"] == "correct"
    stats = lexidesk.cli.run(["stats"])
    assert stats["accuracy"] == 100.0
    restored = lexidesk.cli.run(["undo"])
    assert restored["undone"] is True


def test_swap_direction_keeps_one_deck_and_persists_order(tmp_path: Path) -> None:
    repository = WordRepository(tmp_path / "cli-direction.db")
    repository.add_word(
        source_text="time",
        source_lang="en",
        target_text="время",
        target_lang="ru",
    )
    store = SettingsStore(tmp_path / "settings.json")
    settings = store.load()
    settings.active_source_language = "en"
    settings.active_target_language = "ru"
    store.save(settings)

    payload = lexidesk.cli.swap_active_direction(store, repository)

    restored = store.load()
    assert payload["direction"] == "RU → EN"
    assert (restored.active_source_language, restored.active_target_language) == (
        "ru",
        "en",
    )
    assert repository.language_pairs() == [("en", "ru")]
    repository.close()
