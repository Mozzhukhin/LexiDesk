# LexiDesk architecture

```text
Plasma widget ── narrow JSON CLI ──┐
                                   ▼
Standalone PySide6 UI ───────► D-Bus service
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
                  SQLite       FSRS 6       offline language data
               cards/reviews   scheduler   FreeDict + Argos + WordNet
```

The session D-Bus service owns the long-lived repository connection. The CLI
bridge talks to it and falls back to a short-lived repository connection if the
service is unavailable. This keeps the Plasma package simple QML while ensuring
the learning core remains Python-testable.

SQLite uses WAL mode, foreign keys, transactional reviews, and a five-second
busy timeout. Schema migrations are additive except for the pre-FSRS review log,
which is copied into the v4 schema inside a transaction. Legacy reviews remain
visible in analytics but are intentionally not undoable.

The application stores no vocabulary in the plasmoid package. Removing or
upgrading a widget instance therefore cannot remove the user's data.

Card creation performs the primary lookup and a fast SQLite WordNet example
lookup in the UI. Translation of that example is queued in the D-Bus service
after the card is committed, so loading Argos never blocks Save. If D-Bus is
unavailable—or on Windows—the application uses one local background worker with
an isolated SQLite connection. Existing cards are not needlessly regenerated at
every service start.

The dictionary installer also builds a reverse index. A direct translation is
ranked against independently matching entries in the opposite direction;
confirmed headwords are preferred while markup, stress characters, mixed-script
notes, and likely spelling variants are removed or demoted. This improves
single-word quality without adding network access or Argos latency.

All repository write paths normalize card meanings. Sentence-ending periods are
removed from single-card translations while periods in abbreviations such as
`U.S.` are preserved. Alternatives are de-duplicated after normalization, so
GUI entry, batch import, and JSON/CSV import behave the same.

Runtime translation forces Stanza resource discovery into offline-only mode and
sets the Hugging Face offline flags before Argos is imported. Language files are
downloaded only by the explicit installation scripts. Neural hypotheses are
cached for the current process; dictionary lookups remain the fast first path.

Daily SQLite snapshots keep seven days of recoverable state. Manual full backup
and restore use SQLite's online backup API, validate `integrity_check` and the
LexiDesk schema, and create a timestamped safety backup before replacement.

The background example task validates both halves of every example. The source
must contain the card headword and the translated sentence must contain the
selected target meaning. WordNet examples from another sense and inconsistent
Argos output are rejected. Quoted definition terms can be aligned safely; when
that is not possible, the service stores a compact explicit fallback.

Card rotation is deterministic until meaningful ties. Passive browsing covers
unseen and least-recently-shown cards across the complete deck. Adaptive Mixed
mode introduces each new card once, then prioritizes its first recall check and
later FSRS-due reviews by miss rate and difficulty. A failed recall enters an
explicit ten-minute learning/relearning step. Random ordering is only the final
tie-breaker.

Quiz distractors come from one bounded, indexed repository query instead of
materializing the complete vocabulary for every card. Same-part-of-speech and
previously difficult candidates remain first, while the query stays responsive
for vocabularies containing thousands of cards.

Batch preview owns a dedicated `QThread`. Translation progress is delivered by
signals, and cancellation is checked between records so closing or cancelling
the operation never blocks the GUI event loop.

The selector excludes the five most recently displayed card IDs. Its SQL limit
is `min(5, deck_size - 1)`, so decks containing fewer than six cards remain
usable while still cycling through every other word before a repeat. A one-card
deck is the only intentional immediate-repeat case.
