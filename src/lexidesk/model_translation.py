from __future__ import annotations

import json
import os
import re
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from platformdirs import user_data_path

from .config import bundled_language_data_dir, data_dir

SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[^\s])")


def translation_model_roots() -> tuple[Path, ...]:
    """Return bundled, LexiDesk-owned, and legacy Argos model locations."""
    roots: list[Path] = []
    configured = os.environ.get("LEXIDESK_MODELS_DIR") or os.environ.get(
        "ARGOS_PACKAGES_DIR"
    )
    if configured:
        roots.append(Path(configured))
    bundled = bundled_language_data_dir()
    if bundled is not None:
        roots.append(bundled / "argos-translate" / "packages")
    roots.append(data_dir() / "translation-models")
    roots.append(Path(user_data_path("argos-translate")) / "packages")
    legacy = Path.home() / ".local" / "share" / "argos-translate" / "packages"
    roots.append(legacy)
    return tuple(dict.fromkeys(roots))


def split_short_text(text: str) -> list[str]:
    """Split compact card text without loading a neural NLP framework."""
    paragraphs = text.splitlines() or [text]
    sentences: list[str] = []
    for paragraph in paragraphs:
        cleaned = paragraph.strip()
        if not cleaned:
            continue
        sentences.extend(
            part.strip() for part in SENTENCE_BOUNDARY_RE.split(cleaned) if part.strip()
        )
    return sentences or [text]


@dataclass(slots=True)
class TranslationModel:
    path: Path
    source_language: str
    target_language: str
    target_prefix: str = ""
    _translator: Any = None
    _tokenizer: Any = None

    @classmethod
    def load(cls, path: Path) -> TranslationModel | None:
        metadata_path = path / "metadata.json"
        model_path = path / "model"
        tokenizer_path = path / "sentencepiece.model"
        if not (
            metadata_path.is_file() and model_path.is_dir() and tokenizer_path.is_file()
        ):
            return None
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            source = str(metadata["from_code"])
            target = str(metadata["to_code"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        return cls(
            path=path,
            source_language=source,
            target_language=target,
            target_prefix=str(metadata.get("target_prefix", "")),
        )

    def hypotheses(self, text: str, count: int = 4) -> tuple[str, ...]:
        if self._translator is None or self._tokenizer is None:
            self._load_runtime()
        sentences = split_short_text(text)
        tokenized = [
            self._tokenizer.encode(sentence, out_type=str) for sentence in sentences
        ]
        prefix = [[self.target_prefix]] * len(tokenized) if self.target_prefix else None
        batches = self._translator.translate_batch(
            tokenized,
            target_prefix=prefix,
            replace_unknowns=True,
            max_batch_size=32,
            batch_type="tokens",
            beam_size=max(4, count),
            num_hypotheses=count,
            length_penalty=0.2,
            return_scores=True,
        )
        results: list[str] = []
        for index in range(count):
            pieces: list[str] = []
            for batch in batches:
                pieces.extend(batch.hypotheses[index])
            value = self._tokenizer.decode(pieces).replace("▁", " ").replace("_", " ")
            value = value.strip()
            if self.target_prefix and value.startswith(self.target_prefix):
                value = value[len(self.target_prefix) :].lstrip()
            results.append(value)
        return tuple(results)

    def _load_runtime(self) -> None:
        # CTranslate2's public package imports model-conversion helpers (and
        # NumPy) eagerly. LexiDesk only needs the compiled inference API, so
        # provide empty namespaces for those unrelated tools before import.
        for name in (
            "ctranslate2.converters",
            "ctranslate2.models",
            "ctranslate2.specs",
        ):
            sys.modules.setdefault(name, types.ModuleType(name))
        try:
            import ctranslate2
            import sentencepiece
        except ImportError as error:
            raise RuntimeError(
                "The compact offline translation runtime is not installed."
            ) from error
        self._translator = ctranslate2.Translator(
            str(self.path / "model"),
            device="cpu",
            inter_threads=1,
            intra_threads=0,
            compute_type="auto",
        )
        self._tokenizer = sentencepiece.SentencePieceProcessor(
            model_file=str(self.path / "sentencepiece.model")
        )


class OfflineModelRegistry:
    def __init__(self, roots: tuple[Path, ...] | None = None) -> None:
        self.roots = roots or translation_model_roots()
        self._models: dict[tuple[str, str], TranslationModel] | None = None

    def candidates(self, text: str, source: str, target: str) -> tuple[str, ...]:
        route = self.route(source, target)
        if route is None:
            raise LookupError(
                f"No installed offline route from {source.upper()} to {target.upper()}."
            )
        value = text
        hypotheses: tuple[str, ...] = ()
        for start, end in zip(route, route[1:], strict=False):
            hypotheses = self.models()[(start, end)].hypotheses(value)
            if not hypotheses:
                return ()
            value = hypotheses[0]
        return hypotheses

    def route(self, source: str, target: str) -> tuple[str, ...] | None:
        """Find the shortest installed route, preferring a direct model."""
        source = source.casefold()
        target = target.casefold()
        if source == target:
            return (source,)
        edges = self.models()
        queue: list[tuple[str, ...]] = [(source,)]
        visited = {source}
        while queue:
            route = queue.pop(0)
            if len(route) > 3:
                continue
            neighbours = sorted(end for start, end in edges if start == route[-1])
            for neighbour in neighbours:
                candidate = (*route, neighbour)
                if neighbour == target:
                    return candidate
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append(candidate)
        return None

    def installed_pairs(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self.models()))

    def installed_languages(self) -> tuple[str, ...]:
        return tuple(sorted({code for pair in self.models() for code in pair}))

    def reachable_targets(self, source: str) -> tuple[str, ...]:
        languages = self.installed_languages()
        return tuple(
            target
            for target in languages
            if target != source and self.route(source, target) is not None
        )

    def models(self) -> dict[tuple[str, str], TranslationModel]:
        if self._models is not None:
            return self._models
        found: dict[tuple[str, str], TranslationModel] = {}
        for root in self.roots:
            if not root.is_dir():
                continue
            for path in sorted(root.iterdir()):
                if not path.is_dir():
                    continue
                model = TranslationModel.load(path)
                if model is not None:
                    found.setdefault(
                        (model.source_language, model.target_language), model
                    )
        self._models = found
        return found
