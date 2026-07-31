from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from lexidesk.model_translation import (
    OfflineModelRegistry,
    TranslationModel,
    split_short_text,
)


class FakeTokenizer:
    def encode(self, sentence: str, *, out_type: type[str]) -> list[str]:
        assert out_type is str
        return sentence.split()

    def decode(self, pieces: list[str]) -> str:
        return " ".join(pieces)


class FakeTranslator:
    def translate_batch(self, tokenized: list[list[str]], **options: object) -> list:
        assert options["beam_size"] == 4
        assert options["num_hypotheses"] == 4
        return [
            SimpleNamespace(
                hypotheses=[
                    [f"{token}-translated" for token in sentence] for _ in range(4)
                ],
                scores=[0.0] * 4,
            )
            for sentence in tokenized
        ]


def test_compact_model_keeps_translation_beam_settings(tmp_path: Path) -> None:
    model = TranslationModel(tmp_path, "en", "ru")
    model._tokenizer = FakeTokenizer()
    model._translator = FakeTranslator()

    hypotheses = model.hypotheses("A short sentence. Another one!")

    assert len(hypotheses) == 4
    assert hypotheses[0] == (
        "A-translated short-translated sentence.-translated "
        "Another-translated one!-translated"
    )


def test_short_text_splitter_handles_cards_and_paragraphs() -> None:
    assert split_short_text("One sentence.") == ["One sentence."]
    assert split_short_text("First. Second!\nТретье?") == [
        "First.",
        "Second!",
        "Третье?",
    ]


def test_registry_finds_argos_compatible_model_directory(tmp_path: Path) -> None:
    package = tmp_path / "translate-en_ru-1_9"
    (package / "model").mkdir(parents=True)
    (package / "model" / "model.bin").touch()
    (package / "sentencepiece.model").touch()
    (package / "metadata.json").write_text(
        json.dumps({"from_code": "en", "to_code": "ru"}),
        encoding="utf-8",
    )

    models = OfflineModelRegistry((tmp_path,)).models()

    assert models[("en", "ru")].path == package
