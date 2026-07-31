import sqlite3
from pathlib import Path

from lexidesk.examples import (
    MAX_EXAMPLE_LENGTH,
    SemanticExampleIndex,
    cleanup_wordnet_sources,
    example_is_informative,
)


def test_semantic_examples_prefer_the_most_frequent_sense(tmp_path: Path) -> None:
    path = tmp_path / "examples.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE examples (
            lemma TEXT,
            pos TEXT,
            example TEXT,
            definition TEXT,
            frequency INTEGER,
            sense_rank INTEGER
        )
        """
    )
    connection.executemany(
        "INSERT INTO examples VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                "suggestion",
                "n",
                "",
                "persuasion formulated as a suggestion",
                0,
                0,
            ),
            (
                "suggestion",
                "n",
                "the picnic was her suggestion",
                "an idea that is suggested",
                7,
                1,
            ),
        ],
    )
    connection.commit()
    connection.close()

    result = SemanticExampleIndex(path).lookup("suggestion", "noun")

    assert result == "The picnic was her suggestion."


def test_semantic_index_returns_several_distinct_examples(tmp_path: Path) -> None:
    path = tmp_path / "several-examples.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE examples (
            lemma TEXT, pos TEXT, example TEXT, definition TEXT,
            frequency INTEGER, sense_rank INTEGER
        )
        """
    )
    connection.executemany(
        "INSERT INTO examples VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("reliable", "a", "a reliable source checks facts", "dependable", 9, 0),
            ("reliable", "a", "the reliable train arrived on time", "dependable", 8, 1),
            ("reliable", "a", "her reliable method worked again", "dependable", 7, 2),
        ],
    )
    connection.commit()
    connection.close()

    examples = SemanticExampleIndex(path).lookup_many("reliable", "adjective")

    assert len(examples) >= 3
    assert len(set(examples)) == len(examples)
    assert examples[:3] == [
        "A reliable source checks facts.",
        "The reliable train arrived on time.",
        "Her reliable method worked again.",
    ]


def test_wordnet_sources_are_removed_after_indexing(tmp_path: Path) -> None:
    nltk_source = tmp_path / "nltk_data" / "corpora" / "wordnet"
    legacy_source = tmp_path / "wordnet" / "wordnet"
    nltk_source.mkdir(parents=True)
    legacy_source.mkdir(parents=True)
    (nltk_source / "index.noun").touch()
    (legacy_source / "index.noun").touch()

    assert cleanup_wordnet_sources(tmp_path) == 2
    assert not (tmp_path / "nltk_data").exists()
    assert not (tmp_path / "wordnet").exists()


def test_semantic_examples_explain_a_sense_without_an_example(
    tmp_path: Path,
) -> None:
    path = tmp_path / "examples.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE examples (
            lemma TEXT,
            pos TEXT,
            example TEXT,
            definition TEXT,
            frequency INTEGER,
            sense_rank INTEGER
        )
        """
    )
    connection.execute(
        "INSERT INTO examples VALUES (?, ?, ?, ?, ?, ?)",
        (
            "destruction",
            "n",
            "",
            "damage so severe that something no longer exists",
            4,
            0,
        ),
    )
    connection.commit()
    connection.close()

    result = SemanticExampleIndex(path).lookup("destruction", "noun")

    assert result == "The storm caused widespread destruction along the coast."
    assert len(result) <= 82


def test_semantic_example_rejects_a_synonym_only_sentence(tmp_path: Path) -> None:
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
            "ambiguous",
            "a",
            "an equivocal statement",
            "open to two or more interpretations",
            8,
            0,
        ),
    )
    connection.commit()
    connection.close()

    result = SemanticExampleIndex(path).lookup("ambiguous", "adjective")

    assert result == ("The instructions were ambiguous, so we asked for clarification.")
    assert "ambiguous" in result.casefold()
    assert len(result) <= MAX_EXAMPLE_LENGTH


def test_rare_example_does_not_override_a_common_definition(tmp_path: Path) -> None:
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
    connection.executemany(
        "INSERT INTO examples VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                "ambiguous",
                "a",
                "",
                "open to two or more interpretations",
                9,
                0,
            ),
            (
                "ambiguous",
                "s",
                "an ambiguous pattern with no frame of reference",
                "having no intrinsic meaning",
                1,
                1,
            ),
        ],
    )
    connection.commit()
    connection.close()

    result = SemanticExampleIndex(path).lookup("ambiguous", "adjective")

    assert result == ("The instructions were ambiguous, so we asked for clarification.")


def test_meta_sentences_are_not_informative_examples() -> None:
    assert not example_is_informative(
        "The text contains the adjective “Restricted”.",
        "restricted",
    )
    assert not example_is_informative(
        "В тексте встретилось прилагательное «Ограниченный».",
        "ограниченный",
    )
    assert not example_is_informative(
        "The word “destruction” means severe damage.",
        "destruction",
    )
    assert not example_is_informative(
        "Выражение «разъяснения» точно передало смысл разговора.",
        "разъяснения",
    )
    assert not example_is_informative(
        "Они использовали разъяснения при объяснении ситуации.",
        "разъяснения",
    )
    assert not example_is_informative(
        "Результат оказался «Ограниченный» в этой ситуации.",
        "ограниченный",
    )
    assert example_is_informative(
        "Доступ в эту зону ограничен после наступления темноты.",
        "ограниченный",
        allow_inflection=True,
    )


def test_definition_builds_a_meaningful_restricted_example(tmp_path: Path) -> None:
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
            "restricted",
            "a",
            "",
            "subject to restriction or subjected to restriction",
            8,
            0,
        ),
    )
    connection.commit()
    connection.close()

    result = SemanticExampleIndex(path).lookup("restricted", "adjective")

    assert result == "Access to this area is restricted after dark."


def test_plural_definition_uses_a_short_contrastive_example(tmp_path: Path) -> None:
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
        ("plural", "a", "", "grammatical number for two or more", 8, 0),
    )
    connection.commit()
    connection.close()

    assert SemanticExampleIndex(path).lookup("plural", "adjective") == (
        "Cats is the plural of cat."
    )
