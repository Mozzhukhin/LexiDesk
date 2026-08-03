# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.compat import is_win
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parents[1]

datas = [(str(root / "assets" / "lexidesk.svg"), "assets")]
binaries = []
hiddenimports = []
strip_binaries = not is_win

# Only the inference extensions are needed. ``collect_all(ctranslate2)`` also
# follows training/conversion tools into pandas, matplotlib, and test packages.
datas += collect_data_files("sentencepiece")
hiddenimports += ["ctranslate2._ext", "sentencepiece._sentencepiece"]

analysis = Analysis(
    [str(root / "packaging" / "pyinstaller" / "lexidesk_entry.py")],
    pathex=[str(root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "argostranslate",
        "ctranslate2.converters",
        "ctranslate2.models",
        "ctranslate2.specs",
        "minisbd",
        "matplotlib",
        "nltk",
        "numpy",
        "pandas",
        "PIL",
        "pytest",
        "onnx",
        "onnxruntime",
        "spacy",
        "stanza",
        "torch",
    ],
    noarchive=False,
)
# The Linux TIFF image plugin is unused by LexiDesk and depends on an obsolete
# libtiff ABI on several distributions. Omitting only that plugin avoids a
# misleading startup warning without removing any format used by the UI.
analysis.binaries = [
    item
    for item in analysis.binaries
    if not item[0].replace("\\", "/").endswith("imageformats/libqtiff.so")
]
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="LexiDesk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=strip_binaries,
    upx=True,
    console=False,
)
bundle = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=strip_binaries,
    upx=True,
    name="LexiDesk",
)
