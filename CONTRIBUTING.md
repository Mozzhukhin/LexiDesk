# Contributing

Contributions should preserve LexiDesk's offline-first behaviour and keep both
the standalone PySide6 application and Plasma widget compatible with the shared
SQLite/FSRS core.

```bash
uv sync --extra dev
uv run ruff format .
uv run ruff check .
uv run mypy
QT_QPA_PLATFORM=offscreen uv run pytest -q
```

Add tests for behavioural changes. Translation changes should cover both
directions, ambiguous meanings, punctuation, and offline operation. Database
migrations must be additive or include a tested recovery path. Do not commit
downloaded language models, user databases, logs, virtual environments, or
generated release packages.
