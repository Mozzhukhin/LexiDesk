import pytest

from lexidesk.dictionary import DictionaryEntry, SpellingSuggestion
from lexidesk.translation import (
    TranslationError,
    _best_correction,
    _english_stems,
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
