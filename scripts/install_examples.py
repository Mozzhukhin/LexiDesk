#!/usr/bin/env python
from __future__ import annotations

import sqlite3
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

from lexidesk.config import data_dir, examples_path
from lexidesk.examples import cleanup_wordnet_sources, select_human_example

WORDNET_URL = (
    "https://raw.githubusercontent.com/nltk/nltk_data/"
    "gh-pages/packages/corpora/wordnet.zip"
)


def download_wordnet(target: Path) -> Path:
    corpus = target / "wordnet"
    if (corpus / "index.noun").exists():
        return corpus
    archive = target / "wordnet.zip"
    partial = archive.with_suffix(".part")
    target.mkdir(parents=True, exist_ok=True)
    print("Downloading Princeton WordNet examples…", flush=True)
    with urllib.request.urlopen(WORDNET_URL) as response, partial.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    partial.replace(archive)
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            path = PurePosixPath(member.filename)
            if (
                not path.parts
                or path.parts[0] != "wordnet"
                or ".." in path.parts
                or path.is_absolute()
            ):
                raise ValueError(f"Unsafe WordNet archive entry: {member.filename}")
        bundle.extractall(target)
    archive.unlink(missing_ok=True)
    return corpus


def build_index(nltk_root: Path, target: Path) -> None:
    import nltk.data
    from nltk.corpus import wordnet

    nltk.data.path.insert(0, str(nltk_root))
    wordnet.ensure_loaded()
    temporary = target.with_suffix(".tmp")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    ranks: defaultdict[tuple[str, str], int] = defaultdict(int)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            CREATE TABLE examples (
                lemma TEXT NOT NULL,
                pos TEXT NOT NULL,
                example TEXT NOT NULL,
                definition TEXT NOT NULL,
                frequency INTEGER NOT NULL,
                sense_rank INTEGER NOT NULL
            );
            CREATE INDEX idx_examples_lookup
                ON examples(lemma, pos, sense_rank);
            """
        )
        batch: list[tuple[str, str, str, str, int, int]] = []
        for synset in wordnet.all_synsets():
            examples = synset.examples()
            definition = synset.definition()
            pos = synset.pos()
            for lemma in synset.lemmas():
                example = select_human_example(
                    examples,
                    lemma.name().replace("_", " "),
                )
                key = (lemma.name().casefold(), pos)
                rank = ranks[key]
                ranks[key] += 1
                batch.append((key[0], pos, example, definition, lemma.count(), rank))
            if len(batch) >= 5000:
                connection.executemany(
                    "INSERT INTO examples VALUES (?, ?, ?, ?, ?, ?)",
                    batch,
                )
                batch.clear()
        if batch:
            connection.executemany(
                "INSERT INTO examples VALUES (?, ?, ?, ?, ?, ?)",
                batch,
            )
        connection.commit()
        connection.execute("PRAGMA user_version=2")
        connection.execute("VACUUM")
    finally:
        connection.close()
    temporary.replace(target)


def main() -> int:
    target = examples_path()
    if target.exists():
        connection = sqlite3.connect(target)
        try:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        finally:
            connection.close()
        if version >= 2:
            removed = cleanup_wordnet_sources()
            print(f"Semantic examples are already installed: {target}")
            if removed:
                print(f"Removed {removed} obsolete WordNet source directories.")
            return 0
        target.unlink()
    nltk_root = data_dir() / "nltk_data"
    download_wordnet(nltk_root / "corpora")
    print("Building the fast semantic-example index…", flush=True)
    build_index(nltk_root, target)
    cleanup_wordnet_sources()
    print(f"Semantic examples are ready: {target}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
