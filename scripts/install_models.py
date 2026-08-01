#!/usr/bin/env python
from __future__ import annotations

import hashlib
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import TypedDict

from lexidesk.config import data_dir
from lexidesk.model_translation import OfflineModelRegistry


class ModelSpec(TypedDict):
    name: str
    url: str
    archive_size: int
    files: dict[str, str]


MODELS: dict[tuple[str, str], ModelSpec] = {
    ("en", "ru"): {
        "name": "translate-en_ru-1_9",
        "url": "https://argos-net.com/v1/translate-en_ru-1_9.argosmodel",
        "archive_size": 195_746_693,
        "files": {
            "model/model.bin": "c262cce6a506447d4b3c7a899787694d"
            "f13783340ba67f0df3ecbf046ae27924",
            "model/config.json": "3f1a3cc20b961c1fe0e6007e8ca66373"
            "0c4a8b82fa54073fde03edf1402c6726",
            "model/shared_vocabulary.json": "5e39116c77f19b90841f9b0d0dbe4e38"
            "ecf6eadd43dff40ea1415104f441c720",
            "sentencepiece.model": "cdd7fd3f6b069cd1baa90d95682ec685"
            "1119ae0d734438ba85d3678b2f1e2a66",
            "metadata.json": "a40657925da1c25d98d8a6bc53c436a5"
            "b1179bd8771e016147d88587edf1b529",
        },
    },
    ("ru", "en"): {
        "name": "translate-ru_en-1_9",
        "url": "https://argos-net.com/v1/translate-ru_en-1_9.argosmodel",
        "archive_size": 156_239_112,
        "files": {
            "model/model.bin": "026d5f34266b4235c13fc29c665f151b"
            "88d0c1b02b0be7f87734fe9c511e20bc",
            "model/config.json": "3f1a3cc20b961c1fe0e6007e8ca66373"
            "0c4a8b82fa54073fde03edf1402c6726",
            "model/shared_vocabulary.json": "32d134b048b6a27a48ba7fad915497674"
            "3b9bed9cbef7080b952108374d1cea1",
            "sentencepiece.model": "d324f59d3b5ba04d9b088e162b5e779e"
            "27a5eb72d56ec8e5e69a9efc1bf8f495",
            "metadata.json": "2034d666010673068722bc15af5bb8561"
            "173665872867c89a1b99695f0fb25d0",
        },
    },
}


def model_directory() -> Path:
    configured = os.environ.get("LEXIDESK_MODELS_DIR") or os.environ.get(
        "ARGOS_PACKAGES_DIR"
    )
    return Path(configured) if configured else data_dir() / "translation-models"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate_model(path: Path, expected: dict[str, str]) -> None:
    for relative, digest in expected.items():
        candidate = path / relative
        if not candidate.is_file() or file_hash(candidate) != digest:
            raise ValueError(f"Model verification failed: {relative}")


def install_model(
    name: str,
    url: str,
    archive_size: int,
    expected: dict[str, str],
    root: Path,
) -> None:
    target = root / name
    if target.is_dir():
        validate_model(target, expected)
        print(f"Offline model is already installed: {name}")
        return

    root.mkdir(parents=True, exist_ok=True)
    archive = root / f".{name}.download"
    staging = root / f".{name}.staging"
    archive.unlink(missing_ok=True)
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    try:
        print(f"Downloading {name}…", flush=True)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "LexiDesk offline model installer"},
        )
        with (
            urllib.request.urlopen(request, timeout=120) as response,
            archive.open("wb") as output,
        ):
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if archive.stat().st_size != archive_size:
            raise ValueError(f"Unexpected download size for {name}")
        extracted = staging / name
        with zipfile.ZipFile(archive) as bundle:
            members = bundle.infolist()
            if sum(member.file_size for member in members) > 300_000_000:
                raise ValueError(f"Model archive is unexpectedly large: {name}")
            for member in members:
                path = PurePosixPath(member.filename)
                if not path.parts or ".." in path.parts or path.is_absolute():
                    raise ValueError(f"Unsafe model archive entry: {member.filename}")
            for relative in expected:
                suffix = PurePosixPath(relative).parts
                matches = [
                    member
                    for member in members
                    if PurePosixPath(member.filename).parts[-len(suffix) :] == suffix
                ]
                if len(matches) != 1:
                    raise ValueError(f"Required model file is missing: {relative}")
                destination = extracted / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                with (
                    bundle.open(matches[0]) as source,
                    destination.open("wb") as output,
                ):
                    shutil.copyfileobj(source, output)
        validate_model(extracted, expected)
        extracted.replace(target)
        print(f"Installed and verified: {name}")
    finally:
        archive.unlink(missing_ok=True)
        if staging.exists():
            shutil.rmtree(staging)


def main() -> int:
    installed = OfflineModelRegistry().models()
    if all(pair in installed for pair in MODELS):
        print("Offline EN ↔ RU translation is ready.")
        return 0
    root = model_directory()
    for pair, model in MODELS.items():
        if pair in installed:
            print(f"{pair[0].upper()} → {pair[1].upper()} is already installed.")
            continue
        install_model(
            model["name"],
            model["url"],
            model["archive_size"],
            model["files"],
            root,
        )
    print("Offline EN ↔ RU translation is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
