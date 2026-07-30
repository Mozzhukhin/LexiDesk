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
    uv pip install torch --index-url https://download.pytorch.org/whl/cpu
    uv pip install argostranslate nltk platformdirs pytest hatchling
    uv pip install --no-deps --editable .
else
    echo "No system PySide6 found; installing the portable Qt wheel."
    uv sync --extra dev
fi
"$PROJECT_DIR/.venv/bin/python" scripts/install_models.py
"$PROJECT_DIR/.venv/bin/python" scripts/install_dictionary.py
"$PROJECT_DIR/.venv/bin/python" scripts/install_examples.py
"$PROJECT_DIR/.venv/bin/python" scripts/install_desktop.py

echo
echo "LexiDesk is ready. Start it from the application menu or run:"
echo "$PROJECT_DIR/scripts/run.sh"
