import sqlite3
from pathlib import Path

from lexidesk.examples import MAX_EXAMPLE_LENGTH, SemanticExampleIndex


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
