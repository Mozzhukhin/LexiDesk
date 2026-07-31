import sqlite3

import pytest

from lexidesk.dictionary import (
    DictionaryEntry,
    OfflineDictionary,
    SpellingSuggestion,
    clean_dictionary_text,
)
from lexidesk.examples import SemanticExampleIndex
from lexidesk.translation import (
    OfflineTranslator,
    TranslationError,
    TranslationResult,
    _align_quoted_term,
    _best_correction,
    _clean_model_candidate,
    _english_stems,
    _match_source_case,
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


def test_dictionary_text_removes_stress_and_inline_markup() -> None:
    assert clean_dictionary_text(" altog<u>e</u>ther ") == "altogether"
    assert clean_dictionary_text("предложе́ние") == "предложение"


def test_single_word_model_results_drop_sentence_periods() -> None:
    assert _clean_model_candidate(" Restricted. ", single_word=True) == "Restricted"
    assert _clean_model_candidate("Limited.", single_word=True) == "Limited"
    assert (
        _clean_model_candidate("A complete sentence.", single_word=False)
        == "A complete sentence."
    )


def test_autocorrection_preserves_the_entered_case() -> None:
    assert _match_source_case("ограниченный", "Ограниченый") == "Ограниченный"
    assert _match_source_case("restricted", "RESTRCTED") == "RESTRICTED"
    assert _match_source_case("restricted", "restrcted") == "restricted"


def test_translated_definition_uses_the_selected_meaning() -> None:
    translated = "Слово «однозначный» означает открытый для разных толкований."

    aligned = _align_quoted_term(translated, "двусмысленный")

    assert aligned == ("Слово «двусмысленный» означает открытый для разных толкований.")


def test_unrelated_quoted_words_are_not_replaced_in_example() -> None:
    class QuotedExampleTranslator(OfflineTranslator):
        def translate(self, _text: str) -> TranslationResult:
            return TranslationResult(
                "en",
                "ru",
                "«Кошки» — это множественная форма слова «кошка».",
            )

    result = QuotedExampleTranslator().complete_example(
        "The noun “cats” is plural because it refers to more than one cat.",
        "plural",
        "en",
        "множественный",
        "adjective",
    )

    assert result.translation.startswith("«Кошки»")
    assert "множественная" in result.translation


def test_reciprocal_dictionary_evidence_repairs_weak_primary_translation(
    tmp_path,
) -> None:
    path = tmp_path / "dictionary.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE entries (
            source_lang TEXT,
            normalized TEXT,
            headword TEXT,
            translations_json TEXT,
            part_of_speech TEXT
        );
        CREATE TABLE reverse_entries (
            source_lang TEXT,
            normalized TEXT,
            target_text TEXT,
            source_rank INTEGER
        );
        """
    )
    connection.executemany(
        "INSERT INTO entries VALUES (?, ?, ?, ?, ?)",
        [
            ("ru", "писька", "писька", '["weenie", "weiner"]', "noun"),
            ("en", "wiener", "wiener", '["писька"]', "noun"),
        ],
    )
    connection.execute(
        "INSERT INTO reverse_entries VALUES (?, ?, ?, ?)",
        ("ru", "писька", "wiener", 0),
    )
    connection.commit()
    connection.close()

    result = OfflineTranslator(dictionary=OfflineDictionary(path)).translate("писька")

    assert result.translation == "wiener"
    assert result.alternatives == ("weenie",)


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


def test_mismatched_model_example_uses_contextual_fallback() -> None:
    class MismatchingTranslator(OfflineTranslator):
        def translate(self, _text: str) -> TranslationResult:
            return TranslationResult("en", "ru", "Перевод без нужного значения.")

    result = MismatchingTranslator().complete_example(
        "The result seemed reliable in this situation.",
        "reliable",
        "en",
        "надёжный",
        "adjective",
    )

    assert result.source == "The result seemed reliable in this situation."
    assert "надёжный" in result.translation
    assert "используется слово" not in result.translation.casefold()
    assert "used in this example" not in result.source.casefold()
