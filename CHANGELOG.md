# Changelog

## Unreleased

- Add an optional developer-support page with a copyable USDT TRC20 address.
- Let timed rotation skip unanswered quizzes without recording a review.
- Keep every practice mode selectable while cards rotate.
- Keep one verified bilingual example per card and always build sentence
  completion quizzes from the English sentence and English answer.
- Never replace a selected fixed quiz mode with a normal card; retain the mode
  and provide a clear skip state when a quiz cannot be constructed.
- Reject generic meta sentences and retain only a meaning-bearing bilingual
  example.
- Replace the Argos Python runtime with direct CTranslate2 inference, preserving
  the same models and beam-search output while removing Torch, Stanza, spaCy,
  MiniSBD, and ONNX from Linux and Windows bundles.
- Add packaged-runtime translation smoke tests to both release jobs and verify
  downloaded model contents with pinned SHA-256 hashes.
- Strip Linux debug symbols and omit unused model corpora and the obsolete TIFF
  plugin from standalone packages.
- Simplified the widget header and moved practice selection and management
  tools into one compact menu.
- Added hover-only card actions for editing, temporarily skipping, safely
  deleting, and opening the vocabulary library.
- Replaced the countdown text with a compact progress bar and removed the
  `Undo last review` control from both desktop interfaces.
- Stabilized long-card layouts and improved quiz answer emphasis.
- Fixed Plasma settings persistence, made the menu open the widget's own
  configuration, reduced the default height, and removed the recall label.
- Reject meta-sentences that merely mention a word, generate short contextual
  examples from WordNet meanings, and handle Russian inflections reliably.
- Combine adaptive first-recall and FSRS-due quizzes with a fifth-card
  maintenance fallback while preserving the five-card repetition cooldown.

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
