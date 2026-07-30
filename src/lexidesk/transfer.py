from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from .database import WordRepository
from .translation import detect_language

FIELDS = (
    "source_text",
    "source_lang",
    "target_text",
    "alternatives",
    "part_of_speech",
    "transcription",
    "forms",
    "frequency",
    "example",
    "example_translation",
    "tags",
    "source_info",
)


def export_words(repository: WordRepository, path: Path) -> int:
    words = repository.list_words()
    records = [
        {
            "source_text": word.source_text,
            "source_lang": word.source_lang,
            "target_text": word.target_text,
            "alternatives": word.alternatives,
            "part_of_speech": word.part_of_speech,
            "transcription": word.transcription,
            "forms": word.forms,
            "frequency": word.frequency,
            "example": word.example,
            "example_translation": word.example_translation,
            "tags": word.tags,
            "source_info": word.source_info,
        }
        for word in words
    ]
    if path.suffix.lower() == ".csv":
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            for record in records:
                flat = dict(record)
                flat["alternatives"] = " | ".join(record["alternatives"])
                flat["forms"] = " | ".join(record["forms"])
                flat["tags"] = " | ".join(record["tags"])
                writer.writerow(flat)
    else:
        path.write_text(
            json.dumps(
                {"format": "lexidesk", "version": 1, "words": records},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return len(records)


def import_words(repository: WordRepository, path: Path) -> tuple[int, int]:
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8", newline="") as handle:
            records = list(csv.DictReader(handle))
        for record in records:
            record["alternatives"] = _split_list(record.get("alternatives", ""))
            record["forms"] = _split_list(record.get("forms", ""))
            record["tags"] = _split_list(record.get("tags", ""))
    else:
        raw = json.loads(path.read_text(encoding="utf-8"))
        records = raw["words"] if isinstance(raw, dict) else raw
    if not isinstance(records, list) or not all(
        isinstance(record, dict) for record in records
    ):
        raise ValueError("The import file must contain a list of vocabulary cards.")

    imported = 0
    skipped = 0
    for record in records:
        source = str(record.get("source_text", "")).strip()
        target = str(record.get("target_text", "")).strip()
        if not source or not target:
            skipped += 1
            continue
        language = str(record.get("source_lang", "")).lower()
        if language not in {"en", "ru"}:
            language = detect_language(source)
        try:
            repository.add_word(
                source_text=source,
                source_lang=language,
                target_text=target,
                alternatives=_as_list(record.get("alternatives")),
                part_of_speech=str(record.get("part_of_speech", "")),
                transcription=str(record.get("transcription", "")),
                forms=_as_list(record.get("forms")),
                frequency=str(record.get("frequency", "")),
                example=str(record.get("example", "")),
                example_translation=str(record.get("example_translation", "")),
                tags=_as_list(record.get("tags")),
                source_info=str(record.get("source_info", "")),
            )
            imported += 1
        except sqlite3.IntegrityError:
            skipped += 1
    return imported, skipped


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split("|") if item.strip()]


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return _split_list(value)
    return []
