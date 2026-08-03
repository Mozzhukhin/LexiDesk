from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from lexidesk.api import quiz_variants
from lexidesk.database import WordRepository
from lexidesk.language_dialog import LanguagePackagesDialog
from lexidesk.language_packages import (
    LanguagePackage,
    cached_catalog,
    install_package,
    package_for_pair,
    refresh_catalog,
    remove_language,
)
from lexidesk.model_translation import OfflineModelRegistry
from lexidesk.translation import OfflineTranslator


class FakeModel:
    def __init__(self, suffix: str) -> None:
        self.suffix = suffix

    def hypotheses(self, text: str) -> tuple[str, ...]:
        return (f"{text}-{self.suffix}", f"{text}-{self.suffix}-alternative")


class Response(io.BytesIO):
    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}


def package(source: str = "de", target: str = "fr") -> LanguagePackage:
    return LanguagePackage(
        source,
        target,
        source.upper(),
        target.upper(),
        "1.9",
        f"https://example.test/{source}_{target}.argosmodel",
        f"translate-{source}_{target}",
    )


def model_archive(
    source: str = "de",
    target: str = "fr",
    *,
    tokenizer_name: str = "sentencepiece.model",
    include_config: bool = True,
) -> bytes:
    output = io.BytesIO()
    metadata = json.dumps({"from_code": source, "to_code": target}).encode()
    with zipfile.ZipFile(output, "w") as bundle:
        bundle.writestr("translate/model/model.bin", b"model")
        if include_config:
            bundle.writestr("translate/model/config.json", b"{}")
        bundle.writestr("translate/model/shared_vocabulary.json", b"{}")
        bundle.writestr(f"translate/{tokenizer_name}", b"tokenizer")
        bundle.writestr("translate/metadata.json", metadata)
    return output.getvalue()


def test_registry_routes_through_an_installed_pivot(tmp_path: Path) -> None:
    registry = OfflineModelRegistry((tmp_path,))
    registry._models = {
        ("uk", "en"): FakeModel("english"),  # type: ignore[assignment]
        ("en", "de"): FakeModel("german"),  # type: ignore[assignment]
        ("uk", "de"): FakeModel("direct"),  # type: ignore[assignment]
    }

    assert registry.route("uk", "de") == ("uk", "de")
    assert registry.candidates("слово", "uk", "de")[0].endswith("direct")
    del registry._models[("uk", "de")]
    assert registry.route("uk", "de") == ("uk", "en", "de")
    assert registry.candidates("слово", "uk", "de")[0].endswith("english-german")
    assert registry.route("de", "uk") is None
    assert registry.reachable_targets("uk") == ("de", "en")
    assert registry.installed_languages() == ("de", "en", "uk")
    with pytest.raises(LookupError, match="No installed offline route"):
        registry.candidates("Wort", "de", "uk")

    translated = OfflineTranslator(model_registry=registry).translate(
        "слово", "uk", "de"
    )
    assert translated.source_language == "uk"
    assert translated.target_language == "de"
    assert translated.translation.endswith("english-german")


def test_database_and_quizzes_support_arbitrary_pairs(tmp_path: Path) -> None:
    repository = WordRepository(tmp_path / "multilingual.db")
    ids = [
        repository.add_word(
            source_text=source,
            source_lang="de",
            target_text=target,
            target_lang="fr",
            example=f"Das Wort {source} steht hier.",
            example_translation=f"Le mot {target} apparaît ici.",
        )
        for source, target in (
            ("Haus", "maison"),
            ("Zeit", "temps"),
            ("Arbeit", "travail"),
            ("Frage", "question"),
        )
    ]
    repository.add_word(
        source_text="Haus",
        source_lang="de",
        target_text="house",
        target_lang="en",
    )

    word = repository.get_word(ids[0])
    variants = quiz_variants(word, repository)
    assert word.direction == "DE → FR"
    assert word.target_lang == "fr"
    assert set(variants["translation"]["choices"]) == {
        "maison",
        "temps",
        "travail",
        "question",
    }
    repository.close()


def test_catalog_refresh_cache_and_lookup(tmp_path: Path, monkeypatch) -> None:
    records = [
        {
            "from_code": "de",
            "to_code": "fr",
            "from_name": "German",
            "to_name": "French",
            "package_version": "1.9",
            "code": "translate-de_fr",
            "links": ["ipfs://ignored", "https://example.test/model"],
        },
        {"broken": True},
    ]
    payload = json.dumps(records).encode()
    monkeypatch.setattr(
        "lexidesk.language_packages.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(payload),
    )
    monkeypatch.setattr("lexidesk.language_packages.data_dir", lambda: tmp_path)

    packages = refresh_catalog()

    assert len(packages) == 1
    assert packages[0].source_name == "German"
    assert cached_catalog() == packages
    assert package_for_pair(packages, "DE", "fr") == packages[0]
    assert package_for_pair(packages, "fr", "de") is None


def test_package_install_extracts_only_runtime_files(
    tmp_path: Path, monkeypatch
) -> None:
    payload = model_archive()
    monkeypatch.setattr(
        "lexidesk.language_packages.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(payload),
    )
    monkeypatch.setattr("lexidesk.language_packages.data_dir", lambda: tmp_path)
    progress: list[int] = []

    installed = install_package(package(), progress.append)

    assert (installed / "model/model.bin").read_bytes() == b"model"
    assert (installed / "sentencepiece.model").is_file()
    assert progress[-1] == 100
    assert install_package(package()) == installed


def test_package_install_accepts_legacy_bpe_layout(tmp_path: Path, monkeypatch) -> None:
    payload = model_archive(tokenizer_name="bpe.model", include_config=False)
    monkeypatch.setattr(
        "lexidesk.language_packages.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(payload),
    )
    monkeypatch.setattr("lexidesk.language_packages.data_dir", lambda: tmp_path)

    installed = install_package(package())

    assert (installed / "model/model.bin").read_bytes() == b"model"
    assert (installed / "sentencepiece.model").read_bytes() == b"tokenizer"
    assert not (installed / "bpe.model").exists()
    assert not (installed / "model/config.json").exists()


def test_package_install_rejects_archive_without_tokenizer(
    tmp_path: Path, monkeypatch
) -> None:
    payload = model_archive(tokenizer_name="unrelated.model")
    monkeypatch.setattr(
        "lexidesk.language_packages.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(payload),
    )
    monkeypatch.setattr("lexidesk.language_packages.data_dir", lambda: tmp_path)

    with pytest.raises(ValueError, match="no compatible SentencePiece tokenizer"):
        install_package(package())


def test_removing_language_keeps_other_models_and_user_content(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "translation-models"
    for source, target in (("en", "uk"), ("uk", "en"), ("en", "de")):
        path = root / f"translate-{source}_{target}"
        path.mkdir(parents=True)
        (path / "metadata.json").write_text(
            json.dumps({"from_code": source, "to_code": target}), encoding="utf-8"
        )
        (path / "payload.bin").write_bytes(b"model")
    vocabulary = tmp_path / "lexidesk.db"
    vocabulary.write_bytes(b"cards")
    monkeypatch.setattr("lexidesk.language_packages.data_dir", lambda: tmp_path)

    assert remove_language("uk") == 2
    assert not (root / "translate-en_uk").exists()
    assert not (root / "translate-uk_en").exists()
    assert (root / "translate-en_de").exists()
    assert vocabulary.read_bytes() == b"cards"
    with pytest.raises(ValueError, match="cannot be removed"):
        remove_language("en")


def test_language_dialog_groups_installed_languages_first(
    qapp: QApplication, monkeypatch
) -> None:
    packages = (
        package("en", "ru"),
        package("ru", "en"),
        package("en", "de"),
        package("de", "en"),
        package("en", "fr"),
        package("fr", "en"),
    )
    monkeypatch.setattr("lexidesk.language_dialog.cached_catalog", lambda: packages)

    class Registry:
        def installed_pairs(self) -> tuple[tuple[str, str], ...]:
            return (("en", "ru"), ("ru", "en"))

        def route(self, source: str, target: str) -> tuple[str, ...] | None:
            if source == target:
                return (source,)
            if {source, target} == {"en", "ru"}:
                return (source, target)
            return None

    monkeypatch.setattr("lexidesk.language_dialog.OfflineModelRegistry", Registry)
    dialog = LanguagePackagesDialog()

    rows = [
        dialog.page.languages.topLevelItem(index)
        for index in range(dialog.page.languages.topLevelItemCount())
    ]
    codes = [item.data(0, 256) for item in rows]
    assert codes == ["en", "ru", "fr", "de"]
    assert rows[0].text(1).startswith("✓ Installed")
    assert rows[1].text(1).startswith("✓ Installed")
    assert rows[2].text(1) == "Not installed"
    dialog.page.languages.setCurrentItem(rows[2])
    assert dialog.page.install_button.isEnabled()
    dialog.close()
