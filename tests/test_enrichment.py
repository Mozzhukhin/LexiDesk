from __future__ import annotations

from pathlib import Path

from lexidesk.database import WordRepository
from lexidesk.enrichment import enrich_example
from lexidesk.translation import ExampleResult


class StubTranslator:
    def generate_example(self, *_args) -> ExampleResult:
        return ExampleResult(
            "A reliable source checks each fact.",
            "Надёжный источник проверяет каждый факт.",
        )

    def complete_example(self, *_args) -> ExampleResult:
        return ExampleResult(
            "The result seemed reliable to everyone.",
            "Результат казался надёжным для всех.",
        )

    def generate_examples(self, *_args) -> tuple[ExampleResult, ...]:
        return (
            self.generate_example(),
            ExampleResult(
                "The final result was clearly reliable.",
                "Итоговый результат был явно надёжным.",
            ),
            ExampleResult(
                "Her reliable method worked every time.",
                "Её надёжный метод работал каждый раз.",
            ),
        )


def test_enrichment_generates_missing_example(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "enrich.db"
    repository = WordRepository(path)
    word_id = repository.add_word(
        source_text="reliable",
        source_lang="en",
        target_text="надёжный",
        part_of_speech="adjective",
    )
    repository.close()
    monkeypatch.setattr("lexidesk.enrichment.OfflineTranslator", StubTranslator)

    assert enrich_example(path, word_id) is True

    repository = WordRepository(path)
    assert repository.get_word(word_id).example.startswith("A reliable source")
    assert len(repository.examples_for_word(word_id)) == 3
    repository.close()


def test_enrichment_repairs_mismatched_translation(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "repair.db"
    repository = WordRepository(path)
    word_id = repository.add_word(
        source_text="reliable",
        source_lang="en",
        target_text="надёжный",
        part_of_speech="adjective",
        example="The result seemed reliable to everyone.",
        example_translation="Совсем другое значение находится здесь.",
    )
    repository.close()
    monkeypatch.setattr("lexidesk.enrichment.OfflineTranslator", StubTranslator)

    assert enrich_example(path, word_id) is True

    repository = WordRepository(path)
    assert "надёжным" in repository.get_word(word_id).example_translation
    repository.close()


def test_enrichment_handles_missing_card(tmp_path: Path) -> None:
    path = tmp_path / "missing.db"
    WordRepository(path).close()

    assert enrich_example(path, 999) is False


def test_enrichment_replaces_meta_example(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "meta.db"
    repository = WordRepository(path)
    word_id = repository.add_word(
        source_text="restricted",
        source_lang="en",
        target_text="ограниченный",
        part_of_speech="adjective",
        example="The text contains the adjective “restricted”.",
        example_translation="В тексте встретилось прилагательное «ограниченный».",
    )
    repository.close()
    monkeypatch.setattr("lexidesk.enrichment.OfflineTranslator", StubTranslator)

    assert enrich_example(path, word_id) is True

    repository = WordRepository(path)
    assert repository.get_word(word_id).example.startswith("A reliable source")
    repository.close()
