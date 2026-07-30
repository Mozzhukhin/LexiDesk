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
