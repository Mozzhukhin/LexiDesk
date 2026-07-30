# LexiDesk

LexiDesk is an offline English–Russian vocabulary companion for KDE Plasma 6
and other Linux desktops. Its application core is written in Python with
PySide6, and its native Plasma widget uses QML.

The app starts with an empty vocabulary. Add an English or Russian word/phrase,
let the local model suggest a translation, review it, and save it. Cards rotate
every 90 seconds by default.

![LexiDesk desktop card](docs/images/desktop-window.png)

![LexiDesk vocabulary library](docs/images/library.png)

![LexiDesk learning analytics](docs/images/analytics.png)

## Features

- Fully offline EN ↔ RU translation after initial language-data installation
- A 99,000-headword FreeDict index for precise word meanings and parts of speech
- Argos neural translation fallback for phrases and missing dictionary entries
- Conservative offline autocorrection for misspelled English and Russian words
- Words and short phrases in either language
- Editable translations, meanings, transcription, forms, frequency, and sources
- Three modes: always visible, click-to-reveal, and typed translation
- Official FSRS 6 scheduling with **Again**, **Hard**, **Good**, and **Easy**
- One-click undo for the most recent review
- Automatic 90-second card rotation
- A native Plasma 6 widget with system, OLED, Forest, and Purple themes
- A portable frameless desktop application with five themes
- Searchable vocabulary library with New/Learning/Known filters
- Tags, editable examples, alternative meanings, and parts of speech
- Daily goals, 30-day activity, recall accuracy, streak, and review forecast
- Difficult-card ranking based on FSRS difficulty and stability
- Batch creation from lines, translated pairs, or words extracted from text
- JSON/CSV import and export
- Daily SQLite backups with seven-day retention
- KDE shortcut `Ctrl+Alt+L` to add the current clipboard text
- Compact JSON CLI used by the widget and available for automation
- Persistent local D-Bus service with automatic direct-database fallback
- Local SQLite storage with no account, telemetry, or network calls at runtime
- Desktop-menu actions for adding cards and opening the library

## Learning model

LexiDesk uses the official FSRS 6 implementation with 90% desired retention by
default. Each card tracks memory stability, difficulty, state, and its latest
review. **Again**, **Hard**, **Good**, and **Easy** produce individualized
intervals instead of a fixed ladder. The desired retention can be adjusted
between 70% and 99%.

Legacy review history is migrated automatically. LexiDesk prioritizes due cards;
when nothing is due, it displays the least recently shown card so the desktop
never becomes empty. **Next** does not alter learning history, and **Undo**
restores the complete state before the most recent new-format review.

## Install on Arch Linux

Requirements:

- KDE Plasma 6 or another Linux desktop
- [`uv`](https://docs.astral.sh/uv/)
- an internet connection for the one-time dependency and language-model download

```bash
./scripts/setup.sh
```

On Arch, setup reuses the distribution's PySide6 package through an isolated
environment and installs CPU-only translation dependencies. It does not modify
Arch's system Python. On other distributions it installs a portable Qt wheel.

Run:

```bash
./scripts/run.sh
```

The installer also registers the native widget. Add it from:

`Right-click desktop → Enter Edit Mode → Add Widgets → LexiDesk`.

Useful commands:

```bash
# Add a card, prefilled from the clipboard
~/.local/bin/lexidesk-gui --add-clipboard

# Open the searchable library
~/.local/bin/lexidesk-gui --library

# Batch add and analytics
~/.local/bin/lexidesk-gui --batch
~/.local/bin/lexidesk-gui --analytics

# Read widget data as JSON
~/.local/bin/lexidesk-bridge stats
~/.local/bin/lexidesk-bridge card
~/.local/bin/lexidesk-bridge analytics
```

After setup, translation works without an internet connection. Application data
is stored in `~/.local/share/LexiDesk`, and settings in
`~/.config/LexiDesk`. Automatic backups are stored under
`~/.local/share/LexiDesk/backups`.

## Development

```bash
uv sync --extra dev
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -q
uv run lexidesk
```

The GitHub Actions workflow runs the same formatting, lint, type, and test
checks on every push and pull request.

Release tags build a wheel, source archive, and Plasma archive automatically.
Packaging sources for Arch/AUR and Flatpak are under `packaging/`; see
`packaging/flatpak/README.md` for the sandbox-specific language-data step.

## Repair and diagnostics

Setup is idempotent, so it can safely repair wrappers, desktop entries,
shortcuts, or the Plasma package without resetting vocabulary:

```bash
./scripts/setup.sh
```

Check the local bridge independently from Plasma:

```bash
~/.local/bin/lexidesk-bridge card
~/.local/bin/lexidesk-bridge stats
```

If Plasma still displays a cached widget after an upgrade, log out and back in,
or remove and add only the widget instance. Vocabulary and review history remain
in `~/.local/share/LexiDesk` and are not stored inside the widget.

## Architecture

```text
Native Plasma widget (QML)
           │ executable DataSource / JSON
           ▼
Python CLI bridge ─────► local D-Bus service ◄───── PySide6 application
           │                       │                   ├── typed practice
           │ direct fallback       │                   ├── batch importer
           └───────────────────────┤                   └── analytics
                                   ▼
Application core
    ├── FSRS 6 scheduler and answer checker
    ├── offline Argos translator
    ├── import/export and backups
    └── SQLite repository + review history
```

See [the architecture document](docs/ARCHITECTURE.md) for migration and
service details.

Argos provides a translation suggestion, not a guarantee of a single correct
meaning. LexiDesk deliberately asks the learner to verify and edit a translation
before saving it.

For an unknown single word, LexiDesk compares nearby dictionary spellings with
the offline model's translation and automatically substitutes a correction only
when the evidence is strong. Typical inflected English forms such as `cars`,
`worked`, and `working` are protected from overcorrection. Multi-word phrases
are translated as entered.

## Privacy and offline behavior

The regular application, widget, CLI, database, review system, and translation
engine run locally. Network access is used only by `scripts/install_models.py`
during the initial EN↔RU model installation and by
`scripts/install_dictionary.py` while building the local FreeDict index.
LexiDesk has no account, analytics, advertising, or telemetry. See
[THIRD_PARTY.md](THIRD_PARTY.md) for data attribution and licenses.

## Plasma implementation

Plasma 6 requires widgets to use QML. The QML package never accesses the
database directly: it invokes a narrow Python CLI and parses its JSON response.
This keeps the learning logic testable in Python while giving Plasma ownership
of placement, resizing, theming, and lifecycle.

## License

MIT
