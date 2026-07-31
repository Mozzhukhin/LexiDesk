# Changelog

## Unreleased

- Simplified the widget header and moved practice selection and management
  tools into one compact menu.
- Added hover-only card actions for editing, temporarily skipping, safely
  deleting, and opening the vocabulary library.
- Replaced the countdown text with a compact progress bar and removed the
  `Undo last review` control from both desktop interfaces.
- Stabilized long-card layouts and improved quiz answer emphasis.
- Fixed Plasma settings persistence, made the menu open the widget's own
  configuration, reduced the default height, and removed the recall label.

- Move batch translation to a responsive, cancellable background worker.
- Reduce quiz payload generation from a full-deck scan to a bounded SQL query.
- Replace generic example fallbacks with compact contextual bilingual sentences.
- Remove retained WordNet source corpora after the SQLite index is built.
- Raise branch-aware test coverage above 70% and enforce it in the test suite.

## 1.1.0 — 2026-07-30

- Add native Windows installer and portable Windows build.
- Add universal Linux AppImage and portable Linux archive.
- Publish separate, clearly named Plasma and Python downloads.
- Bundle the offline EN↔RU models, dictionary, and example index.
- Add SHA-256 checksums for every release artifact.
- Make D-Bus integration optional and add native Windows autostart.

## 1.0.0 — 2026-07-30

- Replace fixed intervals with the official FSRS 6 scheduler.
- Add Again, Hard, Good, and Easy ratings with review undo.
- Add typed-answer practice and tolerant offline answer checking.
- Add a persistent local D-Bus service with direct-database fallback.
- Add conservative EN/RU spelling correction with undo.
- Add daily goals, activity analytics, difficult-card ranking, and forecast.
- Add batch translation and vocabulary extraction from pasted text.
- Add transcription, word forms, frequency, and source metadata.
- Add adaptive Plasma controls, direct editing, progress, and shortcuts.
- Add Arch/AUR and Flatpak packaging templates and release automation.
- Preserve and migrate all pre-1.0 vocabulary and review history.
