import sqlite3

import pytest

from lexidesk.dictionary import DictionaryEntry, SpellingSuggestion
from lexidesk.examples import SemanticExampleIndex
from lexidesk.translation import (
    OfflineTranslator,
    TranslationError,
    TranslationResult,
    _best_correction,
    _english_stems,
    build_example_sentence,
    detect_language,
)


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("hello", "en"),
        ("look forward to", "en"),
        ("привет", "ru"),
        ("смотреть вперёд", "ru"),
    ],
)
def test_detect_language(text: str, language: str) -> None:
    assert detect_language(text) == language


def test_detect_language_rejects_mixed_scripts() -> None:
    with pytest.raises(TranslationError):
        detect_language("hello мир")


def test_english_inflection_stems_cover_common_forms() -> None:
    assert "car" in _english_stems("cars")
    assert "box" in _english_stems("boxes")
    assert "study" in _english_stems("studied")
    assert "work" in _english_stems("working")
    assert "stop" in _english_stems("stopping")


def test_model_translation_disambiguates_spelling_correction() -> None:
    destruction = SpellingSuggestion(
        DictionaryEntry("destruction", "en", ("разруше́ние",), "noun"),
        1,
    )
    distraction = SpellingSuggestion(
        DictionaryEntry("distraction", "en", ("отвлечение",), "noun"),
        1,
    )
    correction = _best_correction(
        (destruction, distraction),
        ["разрушение"],
        source_length=10,
    )
    assert correction == destruction


def test_ambiguous_short_word_is_not_changed() -> None:
    suggestions = (
        SpellingSuggestion(DictionaryEntry("halo", "en", ("ореол",), "noun"), 1),
        SpellingSuggestion(DictionaryEntry("hello", "en", ("привет",), ""), 1),
    )
    assert _best_correction(suggestions, ["неоднозначно"], source_length=4) is None


@pytest.mark.parametrize(
    ("word", "language", "part_of_speech", "expected_fragment"),
    [
        ("suggestion", "en", "noun", "suggestion"),
        ("improve", "en", "verb", "to improve"),
        ("reliable", "en", "adjective", "seemed reliable"),
        ("предложение", "ru", "noun", "«предложение»"),
        ("как дела", "ru", "phrase", "«как дела»"),
    ],
)
def test_generated_example_contains_the_current_term(
    tmp_path,
    word: str,
    language: str,
    part_of_speech: str,
    expected_fragment: str,
) -> None:
    sentence = build_example_sentence(
        word,
        language,
        part_of_speech,
        SemanticExampleIndex(tmp_path / "missing.db"),
    )

    assert expected_fragment in sentence
    assert sentence[-1] in {".", "!", "?"}


def test_russian_example_uses_english_word_meaning(tmp_path) -> None:
    path = tmp_path / "examples.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE examples (
            lemma TEXT, pos TEXT, example TEXT, definition TEXT,
            frequency INTEGER, sense_rank INTEGER
        )
        """
    )
    connection.execute(
        "INSERT INTO examples VALUES (?, ?, ?, ?, ?, ?)",
        (
            "suggestion",
            "n",
            "the picnic was her suggestion",
            "an idea that is suggested",
            7,
            0,
        ),
    )
    connection.commit()
    connection.close()

    class StubTranslator(OfflineTranslator):
        def translate(self, text: str) -> TranslationResult:
            translations = {
                "предложение": TranslationResult("ru", "en", "suggestion"),
                "The picnic was her suggestion.": TranslationResult(
                    "en",
                    "ru",
                    "Пикник был её предложением.",
                ),
            }
            return translations[text]

    translator = StubTranslator(examples=SemanticExampleIndex(path))
    result = translator.generate_example("предложение", "ru", "noun")

    assert result.source == "Пикник был её предложением."
    assert result.translation == "The picnic was her suggestion."
