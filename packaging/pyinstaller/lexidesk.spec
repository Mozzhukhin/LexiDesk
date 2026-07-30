# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).parents[1]

datas = [(str(root / "assets" / "lexidesk.svg"), "assets")]
binaries = []
hiddenimports = []

language_data = root / "bundle-data"
if language_data.is_dir():
    datas.append((str(language_data), "language-data"))

# Argos loads translation engines and tokenizers through package metadata and
# dynamic imports. Collecting its package data keeps downloaded language models
# usable in the frozen application.
for package in ("argostranslate", "ctranslate2", "sentencepiece"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

analysis = Analysis(
    [str(root / "packaging" / "pyinstaller" / "lexidesk_entry.py")],
    pathex=[str(root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="LexiDesk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
bundle = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    name="LexiDesk",
)
