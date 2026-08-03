#!/usr/bin/env python
from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import lexidesk.language_dialog as language_dialog_module
from lexidesk.database import WordRepository
from lexidesk.insights import AnalyticsDialog
from lexidesk.language_dialog import LanguagePackagesDialog
from lexidesk.language_packages import LanguagePackage
from lexidesk.library import LibraryDialog
from lexidesk.scheduling import ReviewRating
from lexidesk.settings import SettingsStore
from lexidesk.themes import stylesheet
from lexidesk.translation import OfflineTranslator
from lexidesk.window import LexiDeskWindow


def sample_repository(path: Path) -> WordRepository:
    repository = WordRepository(path)
    cards = (
        (
            "opportunity",
            "возможность",
            "noun",
            "This is a good opportunity.",
            "Это хорошая возможность.",
        ),
        (
            "look forward to",
            "ждать с нетерпением",
            "phrase",
            "I look forward to our next meeting.",
            "Я с нетерпением жду нашей следующей встречи.",
        ),
        (
            "reliable",
            "надёжный",
            "adjective",
            "We need a reliable solution.",
            "Нам нужно надёжное решение.",
        ),
        (
            "improve",
            "улучшать",
            "verb",
            "Small habits improve your memory.",
            "Небольшие привычки улучшают память.",
        ),
        (
            "achievement",
            "достижение",
            "noun",
            "Finishing the project was an achievement.",
            "Завершение проекта было достижением.",
        ),
        (
            "thoughtful",
            "вдумчивый",
            "adjective",
            "She gave a thoughtful answer.",
            "Она дала вдумчивый ответ.",
        ),
    )
    ids = [
        repository.add_word(
            source_text=source,
            source_lang="en",
            target_text=target,
            part_of_speech=part_of_speech,
            example=example,
            example_translation=translation,
            tags=["demo"],
        )
        for source, target, part_of_speech, example, translation in cards
    ]
    opportunity_id, phrase_id = ids[:2]
    repository.review(opportunity_id, ReviewRating.GOOD)
    repository.review(phrase_id, ReviewRating.HARD)
    return repository


def demo_packages() -> tuple[LanguagePackage, ...]:
    names = {
        "en": "English",
        "de": "German",
        "es": "Spanish",
        "fr": "French",
        "ru": "Russian",
        "uk": "Ukrainian",
    }
    packages = []
    for code in ("de", "es", "fr", "ru", "uk"):
        for source, target in (("en", code), (code, "en")):
            packages.append(
                LanguagePackage(
                    source,
                    target,
                    names[source],
                    names[target],
                    "1.9",
                    f"https://example.invalid/{source}_{target}.argosmodel",
                    f"translate-{source}_{target}",
                )
            )
    return tuple(packages)


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
    card_repository.close()

    quiz_repository = sample_repository(temporary / "quiz.db")
    quiz_window = LexiDeskWindow(
        quiz_repository,
        SettingsStore(temporary / "quiz-settings.json"),
        translator,
    )
    quiz_window.show()
    app.processEvents()
    quiz_window.current_word = quiz_repository.get_word(1)
    quiz_window.set_practice_mode("translation")
    quiz = quiz_window._current_quiz
    if quiz is not None:
        wrong = next(choice for choice in quiz["choices"] if choice != quiz["answer"])
        quiz_window.choose_answer(str(wrong))
        quiz_window.advance_timer.stop()
    app.processEvents()
    QTest.qWait(180)
    quiz_window.grab().save(str(output / "quiz.png"))
    quiz_window.close()
    quiz_repository.close()

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

    class DemoRegistry:
        def installed_pairs(self) -> tuple[tuple[str, str], ...]:
            return (("en", "ru"), ("ru", "en"), ("en", "uk"), ("uk", "en"))

        def route(self, source: str, target: str) -> tuple[str, ...] | None:
            installed = {"en", "ru", "uk"}
            if source == target:
                return (source,)
            if source in installed and target in installed:
                return (
                    (source, target)
                    if "en" in {source, target}
                    else (source, "en", target)
                )
            return None

    language_dialog_module.cached_catalog = demo_packages
    language_dialog_module.OfflineModelRegistry = DemoRegistry
    language_dialog_module.installed_package_size = lambda _code: 195_000_000
    languages = LanguagePackagesDialog()
    languages.setStyleSheet(style)
    languages.show()
    app.processEvents()
    QTest.qWait(120)
    languages.grab().save(str(output / "languages.png"))
    languages.close()

    print(f"Saved screenshots to {output}")


if __name__ == "__main__":
    main()
