#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path

from lexidesk.config import data_dir, dictionary_path
from lexidesk.dictionary import normalize_headword

SOURCES = {
    "en": "https://download.freedict.org/generated/eng-rus/eng-rus.tei",
    "ru": "https://download.freedict.org/generated/rus-eng/rus-eng.tei",
}
TEI = "{http://www.tei-c.org/ns/1.0}"
POS_NAMES = {
    "n": "noun",
    "v": "verb",
    "adj": "adjective",
    "adv": "adverb",
    "pn": "proper noun",
}


def download(url: str, target: Path) -> None:
    if target.exists():
        return
    partial = target.with_suffix(".part")
    print(f"Downloading {url}…", flush=True)
    with urllib.request.urlopen(url) as response, partial.open("wb") as output:
        total = int(response.headers.get("Content-Length", 0))
        received = 0
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            received += len(chunk)
            if total:
                print(
                    f"\r  {received * 100 // total:3d}% ({received // 1_048_576} MiB)",
                    end="",
                    flush=True,
                )
    print(flush=True)
    partial.replace(target)


def parse(path: Path, source_language: str) -> dict[str, dict[str, object]]:
    entries: dict[str, dict[str, object]] = OrderedDict()
    count = 0
    for _event, element in ET.iterparse(path, events=("end",)):
        if element.tag != f"{TEI}entry":
            continue
        headwords = [
            (node.text or "").strip()
            for node in element.findall(f"./{TEI}form/{TEI}orth")
            if (node.text or "").strip()
        ]
        translations = [
            (node.text or "").strip()
            for node in element.findall(f".//{TEI}cit[@type='trans']/{TEI}quote")
            if (node.text or "").strip()
        ]
        pos_node = element.find(f"./{TEI}gramGrp/{TEI}pos")
        pos_code = (pos_node.text or "").strip() if pos_node is not None else ""
        part_of_speech = POS_NAMES.get(pos_code, pos_code)

        if translations:
            for headword in headwords:
                normalized = normalize_headword(headword)
                if not normalized:
                    continue
                key = f"{source_language}\0{normalized}"
                record = entries.setdefault(
                    key,
                    {
                        "headword": headword,
                        "source_lang": source_language,
                        "normalized": normalized,
                        "translations": [],
                        "parts": [],
                    },
                )
                known_translations = record["translations"]
                for translation in translations:
                    if translation not in known_translations:
                        known_translations.append(translation)
                if part_of_speech and part_of_speech not in record["parts"]:
                    record["parts"].append(part_of_speech)
        count += 1
        if count % 5000 == 0:
            print(f"\r  parsed {count:,} entries", end="", flush=True)
        element.clear()
    print(f"\r  parsed {count:,} entries", flush=True)
    return entries


def build_database(records: list[dict[str, object]], target: Path) -> None:
    temporary = target.with_suffix(".tmp")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            CREATE TABLE entries (
                source_lang TEXT NOT NULL,
                normalized TEXT NOT NULL,
                headword TEXT NOT NULL,
                translations_json TEXT NOT NULL,
                part_of_speech TEXT NOT NULL,
                PRIMARY KEY(source_lang, normalized)
            ) WITHOUT ROWID;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE reverse_entries (
                source_lang TEXT NOT NULL,
                normalized TEXT NOT NULL,
                target_text TEXT NOT NULL,
                source_rank INTEGER NOT NULL,
                PRIMARY KEY(source_lang, normalized, target_text)
            ) WITHOUT ROWID;
            CREATE INDEX idx_reverse_entries_lookup
                ON reverse_entries(source_lang, normalized, source_rank);
            """
        )
        connection.executemany(
            """
            INSERT INTO entries (
                source_lang, normalized, headword, translations_json, part_of_speech
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    record["source_lang"],
                    record["normalized"],
                    record["headword"],
                    json.dumps(record["translations"], ensure_ascii=False),
                    ", ".join(record["parts"]),
                )
                for record in records
            ],
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO reverse_entries (
                source_lang, normalized, target_text, source_rank
            ) VALUES (?, ?, ?, ?)
            """,
            _reverse_rows(records),
        )
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            [
                ("source", "FreeDict/WikDict"),
                ("license", "CC BY-SA 3.0"),
                ("url", "https://freedict.org/"),
                ("entry_count", str(len(records))),
            ],
        )
        connection.commit()
        connection.execute("VACUUM")
    finally:
        connection.close()
    temporary.replace(target)


def ensure_reverse_index(target: Path) -> None:
    """Upgrade an already downloaded dictionary without another download."""
    connection = sqlite3.connect(target)
    try:
        exists = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'reverse_entries'
            """
        ).fetchone()
        if exists is not None:
            return
        connection.executescript(
            """
            CREATE TABLE reverse_entries (
                source_lang TEXT NOT NULL,
                normalized TEXT NOT NULL,
                target_text TEXT NOT NULL,
                source_rank INTEGER NOT NULL,
                PRIMARY KEY(source_lang, normalized, target_text)
            ) WITHOUT ROWID;
            CREATE INDEX idx_reverse_entries_lookup
                ON reverse_entries(source_lang, normalized, source_rank);
            """
        )
        rows = connection.execute(
            """
            SELECT source_lang, headword, translations_json
            FROM entries
            """
        ).fetchall()
        records = [
            {
                "source_lang": source_lang,
                "headword": headword,
                "translations": json.loads(translations_json),
            }
            for source_lang, headword, translations_json in rows
        ]
        connection.executemany(
            """
            INSERT OR IGNORE INTO reverse_entries (
                source_lang, normalized, target_text, source_rank
            ) VALUES (?, ?, ?, ?)
            """,
            _reverse_rows(records),
        )
        connection.commit()
    finally:
        connection.close()


def _reverse_rows(
    records: list[dict[str, object]],
) -> list[tuple[str, str, str, int]]:
    rows: list[tuple[str, str, str, int]] = []
    for record in records:
        source_language = str(record["source_lang"])
        reverse_language = "ru" if source_language == "en" else "en"
        target_text = str(record["headword"]).strip()
        translations = record.get("translations", [])
        if not isinstance(translations, list):
            continue
        for rank, translation in enumerate(translations):
            normalized = normalize_headword(str(translation))
            if normalized:
                rows.append((reverse_language, normalized, target_text, rank))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the FreeDict EN↔RU index")
    parser.add_argument(
        "--force", action="store_true", help="Rebuild an existing index"
    )
    arguments = parser.parse_args()
    if dictionary_path().exists() and not arguments.force:
        ensure_reverse_index(dictionary_path())
        print(f"Offline dictionary is already installed: {dictionary_path()}")
        return 0

    source_dir = data_dir() / "dictionary-sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    combined: list[dict[str, object]] = []

    for language, url in SOURCES.items():
        path = source_dir / f"{language}.tei"
        download(url, path)
        print(f"Indexing {language.upper()} dictionary…", flush=True)
        combined.extend(parse(path, language).values())

    print(f"Building local index with {len(combined):,} headwords…", flush=True)
    build_database(combined, dictionary_path())
    for path in source_dir.glob("*.tei"):
        path.unlink(missing_ok=True)
    print(f"Offline dictionary is ready: {dictionary_path()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
