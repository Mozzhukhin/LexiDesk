from __future__ import annotations

import hashlib
import importlib.util
import urllib.request
import zipfile
from pathlib import Path
from types import ModuleType

import pytest


def _installer() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "install_models.py"
    spec = importlib.util.spec_from_file_location("lexidesk_install_models", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_model_installer_verifies_and_extracts_pinned_files(tmp_path: Path) -> None:
    installer = _installer()
    source = tmp_path / "source"
    package = source / "translate-en_ru-test"
    (package / "model").mkdir(parents=True)
    files = {
        "model/model.bin": b"compact-model",
        "model/config.json": b"{}",
        "model/shared_vocabulary.json": b"[]",
        "sentencepiece.model": b"tokenizer",
        "metadata.json": b'{"from_code":"en","to_code":"ru"}',
    }
    for relative, content in files.items():
        target = package / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (package / "stanza").mkdir()
    (package / "stanza" / "unused.bin").write_bytes(b"unused NLP data")
    archive = tmp_path / "model.argosmodel"
    with zipfile.ZipFile(archive, "w") as bundle:
        for path in package.rglob("*"):
            if path.is_file():
                bundle.write(path, path.relative_to(source))
    expected = {
        relative: hashlib.sha256(content).hexdigest()
        for relative, content in files.items()
    }
    destination = tmp_path / "installed"

    installer.install_model(
        "translate-en_ru-test",
        archive.as_uri(),
        archive.stat().st_size,
        expected,
        destination,
    )

    assert (destination / "translate-en_ru-test" / "model" / "model.bin").is_file()
    assert not (destination / "translate-en_ru-test" / "stanza").exists()


def test_model_download_identifies_lexidesk_to_the_package_host(
    tmp_path: Path,
    monkeypatch,
) -> None:
    installer = _installer()
    source = tmp_path / "source.argosmodel"
    source.write_bytes(b"not-an-archive")
    captured: list[urllib.request.Request] = []

    def open_request(request: urllib.request.Request, timeout: int):
        captured.append(request)
        assert timeout == 120
        return source.open("rb")

    monkeypatch.setattr(installer.urllib.request, "urlopen", open_request)

    with pytest.raises(zipfile.BadZipFile):
        installer.install_model(
            "test-model",
            "https://example.test/model.argosmodel",
            source.stat().st_size,
            {},
            tmp_path / "models",
        )

    assert captured
    assert captured[0].get_header("User-agent") == ("LexiDesk offline model installer")
