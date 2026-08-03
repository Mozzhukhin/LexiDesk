#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

command -v uv >/dev/null 2>&1 || {
    echo "LexiDesk requires uv: https://docs.astral.sh/uv/" >&2
    exit 1
}

if python -c "import PySide6" >/dev/null 2>&1; then
    echo "Using the PySide6 package provided by the Linux distribution."
    uv venv --allow-existing --python python --system-site-packages
    uv pip install 'ctranslate2>=4,<5' 'sentencepiece>=0.2,<0.3'
    uv pip install fsrs platformdirs pytest hatchling
    uv pip install --no-deps --editable .
else
    echo "No system PySide6 found; installing the compact portable runtime."
    uv sync --extra dev
fi
"$PROJECT_DIR/.venv/bin/python" scripts/install_desktop.py

echo
echo "LexiDesk is ready. Start it from the application menu or run:"
echo "$PROJECT_DIR/scripts/run.sh"
echo "Choose your offline languages in LexiDesk when it starts."
