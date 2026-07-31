#!/usr/bin/env python
from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from lexidesk.database import WordRepository
from lexidesk.insights import AnalyticsDialog
from lexidesk.library import LibraryDialog
from lexidesk.scheduling import ReviewRating
from lexidesk.settings import SettingsStore
from lexidesk.themes import stylesheet
from lexidesk.translation import OfflineTranslator
from lexidesk.window import LexiDeskWindow


def sample_repository(path: Path) -> WordRepository:
    repository = WordRepository(path)
    opportunity_id = repository.add_word(
        source_text="opportunity",
        source_lang="en",
        target_text="возможность",
        alternatives=["шанс"],
        part_of_speech="noun",
        example="This is a good opportunity.",
        example_translation="Это хорошая возможность.",
        tags=["career"],
    )
    phrase_id = repository.add_word(
        source_text="look forward to",
        source_lang="en",
        target_text="ждать с нетерпением",
        alternatives=["предвкушать"],
        part_of_speech="phrase",
        tags=["work", "phrases"],
    )
    repository.review(opportunity_id, ReviewRating.GOOD)
    repository.review(phrase_id, ReviewRating.HARD)
    return repository


def main() -> None:
    app = QApplication([])
    project = Path(__file__).resolve().parent.parent
    output = project / "docs" / "images"
    output.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="lexidesk-screenshots-"))
    translator = OfflineTranslator()
    style = stylesheet("Breeze Dark")

    card_repository = sample_repository(temporary / "card.db")
    window = LexiDeskWindow(
        card_repository,
        SettingsStore(temporary / "settings.json"),
        translator,
    )
    window.show()
    app.processEvents()
    QTest.qWait(220)
    window.grab().save(str(output / "desktop-window.png"))
    window.close()

    library_repository = sample_repository(temporary / "library.db")
    library = LibraryDialog(library_repository, translator)
    library.setStyleSheet(style)
    library.show()
    app.processEvents()
    library.grab().save(str(output / "library.png"))
    library.close()
    library_repository.close()

    analytics_repository = sample_repository(temporary / "analytics.db")
    analytics = AnalyticsDialog(analytics_repository, daily_goal=10)
    analytics.setStyleSheet(style)
    analytics.show()
    app.processEvents()
    analytics.grab().save(str(output / "analytics.png"))
    analytics.close()
    analytics_repository.close()

    print(f"Saved screenshots to {output}")


if __name__ == "__main__":
    main()
