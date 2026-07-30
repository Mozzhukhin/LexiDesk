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
after the card is committed, so loading Argos never blocks Save.

The dictionary installer also builds a reverse index. A direct translation is
ranked against independently matching entries in the opposite direction;
confirmed headwords are preferred while markup, stress characters, mixed-script
notes, and likely spelling variants are removed or demoted. This improves
single-word quality without adding network access or Argos latency.

All repository write paths normalize card meanings. Sentence-ending periods are
removed from single-card translations and alternatives are de-duplicated after
normalization, so GUI entry, batch import, and JSON/CSV import behave the same.

The background example task validates both halves of every example. The source
must contain the card headword and the translated sentence must contain the
selected target meaning. WordNet examples from another sense and inconsistent
Argos output are rejected. Quoted definition terms can be aligned safely; when
that is not possible, the service stores a compact explicit fallback.

Card rotation is deterministic until meaningful ties: unseen cards come first,
then the oldest `last_shown_at` across the entire deck, followed by due state,
miss rate, FSRS difficulty, and due time. This prevents overdue cards from
starving future cards during passive browsing. Random ordering is only the final
tie-breaker.

The selector excludes the five most recently displayed card IDs. Its SQL limit
is `min(5, deck_size - 1)`, so decks containing fewer than six cards remain
usable while still cycling through every other word before a repeat. A one-card
deck is the only intentional immediate-repeat case.
