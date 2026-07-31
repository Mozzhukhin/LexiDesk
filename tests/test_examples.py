import sqlite3
from pathlib import Path

from lexidesk.examples import (
    MAX_EXAMPLE_LENGTH,
    SemanticExampleIndex,
    cleanup_wordnet_sources,
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

    assert result.startswith("The word “destruction” means")
    assert "damage" in result
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

    assert result == "The word “ambiguous” means open to multiple interpretations."
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

    assert result == "The word “ambiguous” means open to multiple interpretations."
