# Changelog

## Unreleased

## 1.2.0 — 2026-08-03

- Introduce LexiDesk Lite packages with no bundled language models, dictionary,
  or example corpus, reducing download size and letting users choose languages.
- Add first-run language setup, persistent in-widget setup access, package-size
  reporting, compatibility validation, and safe language removal.
- Keep downloaded language models outside application bundles so upgrades retain
  offline languages, vocabulary, and learning progress.
- Add compact Windows/Linux desktop-widget modes and retain the native Plasma 6
  widget.
- Add multilingual model routing, bidirectional decks, independent directional
  FSRS state, strict Mixed-mode quiz cadence, and a five-card cooldown.
- Refresh project documentation and screenshots for the Lite language manager,
  quizzes, vocabulary library, and analytics.

- Run Windows and standalone Linux builds as interactive desktop widgets that
  stay out of the taskbar, with Desktop and Floating placement modes.
- Keep the Windows installer and in-app autostart setting synchronized.
- Made the widget header responsive at its compact 330 px width.
- Fixed high-DPI clipping in settings, add-card, analytics, and support dialogs.
- Added themed progress bars and consistent combo/spin input styling.
- Kept the add-card form scrollable while its Save and Cancel actions stay visible.
- Keep card edit, delete, and library actions visible without requiring hover.
- Keep the same card actions permanently visible in the Plasma widget.
- Remove the redundant Hide for now action; Next remains the single skip control.

- Apply themes at application scope with a cross-platform Fusion palette so
  Windows combo popups, menus, tabs, lists, tables, inputs, and disabled states
  keep readable, consistent foreground and background colors.
- Restore the language-deck chooser on the header direction and place a
  persistent `⇄` direction switch beside it in Plasma and standalone windows;
  reversing the prompt and translation keeps one shared vocabulary deck.
- Enforce a strict five-presentation cadence in Mixed mode so a backlog of
  FSRS-due cards cannot produce consecutive quizzes.
- Remove redundant correct/incorrect captions from choice quizzes and rely on
  green/red option highlighting before the automatic advance.
- Unify opposite directions into one bidirectional vocabulary card while
  scheduling, scoring, and tracking each recall direction independently.
- Keep independent progress for both sides and prevent an exact reverse entry
  from creating a duplicate card.
- Separate the vocabulary library into source-to-target deck views, default to
  the widget's active pair, and keep learning-status filtering independent.
- Make the current language direction a compact header control in both the
  Plasma and standalone interfaces.
- Keep card rotation, adaptive scheduling, and quizzes inside the explicitly
  selected source-to-target deck; persist the latest added pair and provide a
  dedicated deck chooser without merging language data.
- Accept both current and legacy Argos model layouts, including `bpe.model`
  tokenizers and packages without an optional CTranslate2 `config.json`.
- Move language management into a dedicated Languages tab behind the + button;
  group the full catalog by installed status and alphabetize both groups.
- Add a multilingual card schema with automatic migration from EN/RU cards.
- Discover installed translation models as a directed graph, prefer direct
  models, and support one-hop offline pivot routes between arbitrary languages.
- Add an in-app manager for explicitly downloading compatible language models
  from the official Argos package catalog.
- Add explicit source and target selectors to single-card and batch workflows;
  retain automatic EN/RU detection for backward compatibility.
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
