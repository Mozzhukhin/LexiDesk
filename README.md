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
- Short sense-specific examples that contain the studied word
- Conservative offline autocorrection for misspelled English and Russian words
- Words and short phrases in either language
- Explicit selection among up to four offline translation meanings
- Editable translations, meanings, transcription, forms, frequency, and sources
- Three modes: always visible, click-to-reveal, and typed translation
- Passive **Next** browsing that never changes learning statistics
- On-demand quiz menu: translation, reverse, cloze, context, and typed answer
- Same-part-of-speech distractors weighted toward previously difficult cards
- Soft card-change animations designed for an always-visible desktop widget
- One-click undo for the most recent review
- Automatic 90-second card rotation
- A native Plasma 6 widget with system, OLED, Forest, and Purple themes
- A portable frameless desktop application with five themes
- Searchable vocabulary library with New/Learning/Known filters
- Tags, editable examples, alternative meanings, and parts of speech
- Daily goals, 30-day activity, recall accuracy, streak, and review forecast
- Difficult-card ranking based on FSRS difficulty and stability
- Smart article import that removes stopwords, duplicates, names, and unknown noise
- JSON/CSV import and export
- Daily SQLite backups with seven-day retention
- KDE shortcut `Ctrl+Alt+L` to add the current clipboard text
- Compact JSON CLI used by the widget and available for automation
- Persistent local D-Bus service with automatic direct-database fallback
- Local SQLite storage with no account, telemetry, or network calls at runtime
- Desktop-menu actions for adding cards and opening the library

## Learning model

LexiDesk uses the official FSRS 6 implementation with 90% desired retention by
default. Ordinary cards are passive: **Next** and automatic rotation only
change the visible word. Quizzes never interrupt normal browsing: the user
starts a chosen training mode from the dedicated Practice menu.
A correct choice records a successful review; a wrong choice records a failed
review. Those quiz results produce individualized intervals instead of a fixed
ladder. The desired retention can be adjusted between 70% and 99%.

Legacy review history is migrated automatically. LexiDesk prioritizes due cards;
when nothing is due, it displays the least recently shown card so the desktop
never becomes empty. **Next** does not alter learning history, and **Undo**
restores the complete state before the most recent new-format review.

## Widget workflow

1. At startup the QML widget asks the local D-Bus service for the next card.
   Due cards are preferred; otherwise LexiDesk selects the least recently shown
   card.
2. A regular card shows the source, translation, compact metadata, and a short
   example for the selected meaning. The example must contain the studied term
   and is limited to one compact sentence.
3. **Next** requests another card without recording whether the word is known.
   The 90-second timer performs the same passive change automatically.
4. The Practice button opens a separate menu for translation, reverse
   translation, sentence gap, matching context, or typing. A quiz starts only
   after the user chooses one of these modes.
5. A correct answer turns green. A wrong selected answer turns red while the
   correct answer turns green. The result remains visible for one second.
6. The widget then records only that quiz result in FSRS and advances
   automatically. Statistics, recall, difficulty, and the next due date are
   based on these quiz results.
7. The arrow in the footer undoes the latest recorded quiz result. Adding and
   editing cards opens the Python application, while all vocabulary remains in
   the same local SQLite database.

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
during the initial EN↔RU model installation,
`scripts/install_dictionary.py` while building the local FreeDict index, and
`scripts/install_examples.py` while building the local WordNet example index.
LexiDesk has no account, analytics, advertising, or telemetry. See
[THIRD_PARTY.md](THIRD_PARTY.md) for data attribution and licenses.

## Plasma implementation

Plasma 6 requires widgets to use QML. The QML package never accesses the
database directly: it invokes a narrow Python CLI and parses its JSON response.
This keeps the learning logic testable in Python while giving Plasma ownership
of placement, resizing, theming, and lifecycle.

## License

MIT
