from __future__ import annotations

from pathlib import Path
from time import monotonic

from PySide6.QtWidgets import QApplication, QMessageBox

from lexidesk.batch import BatchAddDialog, prepare_batch_records
from lexidesk.database import WordRepository
from lexidesk.dictionary import DictionaryEntry
from lexidesk.translation import TranslationError, TranslationResult


class StubDictionary:
    def lookup(self, text: str, language: str) -> DictionaryEntry | None:
        if text.casefold() == "reliable":
            return DictionaryEntry("reliable", language, ("надёжный",), "adjective")
        return None


class StubTranslator:
    dictionary = StubDictionary()

    def translate(self, text: str) -> TranslationResult:
        if text == "broken":
            raise TranslationError("not found")
        return TranslationResult(
            "en",
            "ru",
            f"перевод-{text}",
            part_of_speech="noun",
        )

    def example_sentence(
        self,
        source: str,
        _language: str,
        _part_of_speech: str,
    ) -> str:
        return f"The {source} changed our plans."


def test_prepare_batch_records_supports_supplied_values_and_cancel() -> None:
    progress: list[int] = []
    prepared = prepare_batch_records(
        [("first", ""), ("second", "готовый"), ("third", "")],
        StubTranslator(),  # type: ignore[arg-type]
        cancelled=lambda: len(progress) >= 2,
        progress=progress.append,
    )

    assert [record[0] for record in prepared] == ["first", "second"]
    assert prepared[1][1] == "готовый"
    assert progress == [1, 2]


def test_batch_extract_and_async_preview(
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    repository = WordRepository(tmp_path / "batch.db")
    dialog = BatchAddDialog(
        repository,
        StubTranslator(),  # type: ignore[arg-type]
    )
    dialog.mode.setCurrentIndex(dialog.mode.findData("extract"))
    dialog.input.setPlainText("Reliable reliable unknown and reliable")
    assert dialog._sources() == [("reliable", "надёжный")]

    dialog.mode.setCurrentIndex(dialog.mode.findData("lines"))
    dialog.input.setPlainText("first\nsecond = второй\nbroken")
    dialog.build_preview()
    deadline = monotonic() + 3
    while dialog._preview_worker is not None and monotonic() < deadline:
        qapp.processEvents()

    assert dialog._preview_worker is None
    assert dialog.table.rowCount() == 2
    assert dialog.table.item(1, 2).text() == "второй"
    repository.close()


def test_batch_save_selected_records(
    tmp_path: Path,
    qapp: QApplication,
    monkeypatch,
) -> None:
    repository = WordRepository(tmp_path / "save.db")
    dialog = BatchAddDialog(
        repository,
        StubTranslator(),  # type: ignore[arg-type]
    )
    dialog._preview_ready(
        [
            (
                "reliable",
                "надёжный",
                "en",
                "adjective",
                "The source seemed reliable today.",
                "",
            )
        ],
        False,
    )
    scheduled: list[int] = []
    monkeypatch.setattr(
        "lexidesk.batch.schedule_example_enrichment",
        lambda word_id: scheduled.append(word_id),
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)

    dialog.save_selected()
    qapp.processEvents()

    assert repository.count() == 1
    assert scheduled == [1]
    repository.close()
