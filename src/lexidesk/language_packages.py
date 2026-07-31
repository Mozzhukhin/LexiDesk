from __future__ import annotations

import json
import shutil
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .config import data_dir
from .languages import normalize_language_code

PACKAGE_INDEX_URL = (
    "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"
)
MAX_DOWNLOAD_SIZE = 500_000_000
MAX_EXTRACTED_SIZE = 1_200_000_000
REQUIRED_RUNTIME_FILES = (
    "model/model.bin",
    "metadata.json",
)
TOKENIZER_FILES = ("sentencepiece.model", "bpe.model")


@dataclass(frozen=True, slots=True)
class LanguagePackage:
    source: str
    target: str
    source_name: str
    target_name: str
    version: str
    url: str
    code: str

    @property
    def identity(self) -> str:
        safe_version = self.version.replace(".", "_")
        return f"translate-{self.source}_{self.target}-{safe_version}"


def package_cache_dir() -> Path:
    path = data_dir() / "language-packages"
    path.mkdir(parents=True, exist_ok=True)
    return path


def model_install_dir() -> Path:
    path = data_dir() / "translation-models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def refresh_catalog(timeout: float = 20) -> tuple[LanguagePackage, ...]:
    request = urllib.request.Request(
        PACKAGE_INDEX_URL,
        headers={"User-Agent": "LexiDesk language package manager"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(5_000_001)
    if len(payload) > 5_000_000:
        raise ValueError("The language package index is unexpectedly large.")
    records = json.loads(payload)
    packages = _parse_catalog(records)
    cache = package_cache_dir() / "index.json"
    cache.write_bytes(payload)
    return packages


def cached_catalog() -> tuple[LanguagePackage, ...]:
    path = package_cache_dir() / "index.json"
    if not path.is_file():
        return ()
    return _parse_catalog(json.loads(path.read_text(encoding="utf-8")))


def install_package(
    package: LanguagePackage,
    progress: Callable[[int], None] | None = None,
) -> Path:
    root = model_install_dir()
    target = root / package.identity
    if target.is_dir():
        _validate_installed(target, package)
        return target
    archive = root / f".{package.identity}.download"
    staging = root / f".{package.identity}.staging"
    archive.unlink(missing_ok=True)
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    try:
        request = urllib.request.Request(
            package.url,
            headers={"User-Agent": "LexiDesk language package manager"},
        )
        downloaded = 0
        with (
            urllib.request.urlopen(request, timeout=30) as response,
            archive.open("wb") as output,
        ):
            declared = int(response.headers.get("Content-Length", "0") or 0)
            if declared > MAX_DOWNLOAD_SIZE:
                raise ValueError("The language package is too large.")
            while chunk := response.read(1024 * 1024):
                downloaded += len(chunk)
                if downloaded > MAX_DOWNLOAD_SIZE:
                    raise ValueError("The language package is too large.")
                output.write(chunk)
                if progress is not None and declared:
                    progress(min(99, round(downloaded * 100 / declared)))
        extracted = staging / package.identity
        with zipfile.ZipFile(archive) as bundle:
            members = bundle.infolist()
            if sum(member.file_size for member in members) > MAX_EXTRACTED_SIZE:
                raise ValueError("The extracted language package is too large.")
            for member in members:
                path = PurePosixPath(member.filename)
                if not path.parts or path.is_absolute() or ".." in path.parts:
                    raise ValueError("The language package contains an unsafe path.")
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("The language package contains a symbolic link.")
            located = {
                relative: _locate_unique_member(members, relative)
                for relative in REQUIRED_RUNTIME_FILES
            }
            metadata_parts = PurePosixPath(located["metadata.json"].filename).parts
            root_parts = metadata_parts[:-1]
            tokenizer: zipfile.ZipInfo | None = None
            for tokenizer_name in TOKENIZER_FILES:
                tokenizer_candidate = _member_at_relative_path(
                    members, root_parts, PurePosixPath(tokenizer_name).parts
                )
                if tokenizer_candidate is not None:
                    tokenizer = tokenizer_candidate
                    break
            if tokenizer is None:
                raise ValueError(
                    "This package has no compatible SentencePiece tokenizer "
                    "(sentencepiece.model or bpe.model)."
                )
            for member in members:
                parts = PurePosixPath(member.filename).parts
                if (
                    len(parts) <= len(root_parts)
                    or parts[: len(root_parts)] != root_parts
                ):
                    continue
                relative_parts = parts[len(root_parts) :]
                if not (
                    relative_parts[0] == "model"
                    or member == located["metadata.json"]
                    or member == tokenizer
                ):
                    continue
                if member.is_dir():
                    continue
                destination = (
                    extracted / "sentencepiece.model"
                    if member == tokenizer
                    else extracted.joinpath(*relative_parts)
                )
                destination.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(member) as source, destination.open("wb") as out:
                    shutil.copyfileobj(source, out)
        _validate_installed(extracted, package)
        extracted.replace(target)
        if progress is not None:
            progress(100)
        return target
    finally:
        archive.unlink(missing_ok=True)
        if staging.exists():
            shutil.rmtree(staging)


def package_for_pair(
    packages: tuple[LanguagePackage, ...], source: str, target: str
) -> LanguagePackage | None:
    source = normalize_language_code(source)
    target = normalize_language_code(target)
    matches = [
        package
        for package in packages
        if package.source == source and package.target == target
    ]
    return matches[-1] if matches else None


def _validate_installed(path: Path, package: LanguagePackage) -> None:
    required = (*REQUIRED_RUNTIME_FILES, "sentencepiece.model")
    if any(not (path / relative).is_file() for relative in required):
        raise ValueError("The installed language package is incomplete.")
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    if (
        str(metadata.get("from_code", "")).casefold() != package.source
        or str(metadata.get("to_code", "")).casefold() != package.target
    ):
        raise ValueError("The downloaded model metadata does not match its pair.")


def _locate_unique_member(
    members: list[zipfile.ZipInfo], relative: str
) -> zipfile.ZipInfo:
    suffix = PurePosixPath(relative).parts
    matches = [
        member
        for member in members
        if PurePosixPath(member.filename).parts[-len(suffix) :] == suffix
    ]
    if len(matches) != 1:
        raise ValueError(
            "This package is not compatible with the compact "
            f"LexiDesk runtime: {relative} is missing or ambiguous."
        )
    return matches[0]


def _member_at_relative_path(
    members: list[zipfile.ZipInfo],
    root_parts: tuple[str, ...],
    relative_parts: tuple[str, ...],
) -> zipfile.ZipInfo | None:
    expected = root_parts + relative_parts
    matches = [
        member for member in members if PurePosixPath(member.filename).parts == expected
    ]
    if len(matches) > 1:
        raise ValueError("The language package contains duplicate runtime files.")
    return matches[0] if matches else None


def _parse_catalog(value: object) -> tuple[LanguagePackage, ...]:
    if not isinstance(value, list):
        raise ValueError("The language package index has an invalid format.")
    packages: list[LanguagePackage] = []
    for record in value:
        if not isinstance(record, dict):
            continue
        links = record.get("links")
        if not isinstance(links, list):
            continue
        url = next(
            (str(link) for link in links if str(link).startswith("https://")), ""
        )
        if not url:
            continue
        try:
            source = normalize_language_code(str(record["from_code"]))
            target = normalize_language_code(str(record["to_code"]))
        except (KeyError, ValueError):
            continue
        packages.append(
            LanguagePackage(
                source=source,
                target=target,
                source_name=str(record.get("from_name", source.upper())),
                target_name=str(record.get("to_name", target.upper())),
                version=str(record.get("package_version", "unknown")),
                url=url,
                code=str(record.get("code", f"translate-{source}_{target}")),
            )
        )
    return tuple(packages)
