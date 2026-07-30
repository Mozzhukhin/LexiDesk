from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, QRunnable, QThreadPool, Slot
from PySide6.QtDBus import QDBusConnection

from .api import execute_request
from .backup import ensure_daily_backup
from .config import APP_NAME, database_path, settings_path
from .database import WordRepository
from .examples import MAX_EXAMPLE_LENGTH, example_is_suitable
from .service_client import INTERFACE_NAME, OBJECT_PATH, SERVICE_NAME
from .settings import SettingsStore
from .translation import OfflineTranslator


class ExampleEnrichmentTask(QRunnable):
    def __init__(self, database: Path, word_id: int) -> None:
        super().__init__()
        self.database = database
        self.word_id = word_id

    def run(self) -> None:
        repository = WordRepository(self.database)
        try:
            word = repository.get_word(self.word_id)
            example = word.example
            translation = word.example_translation
            translator = OfflineTranslator()
            refresh_example = (
                not example
                or len(example) > MAX_EXAMPLE_LENGTH
                or not example_is_suitable(
                    example,
                    word.source_text,
                    allow_inflection=word.source_lang == "ru",
                )
                or (
                    word.source_lang == "en"
                    and example.casefold().startswith(
                        f"{word.source_text.casefold()} means "
                    )
                )
            )
            if refresh_example:
                generated = translator.generate_example(
                    word.source_text,
                    word.source_lang,
                    word.part_of_speech,
                    word.target_text,
                )
                example = generated.source
                translation = generated.translation
            elif not example_is_suitable(
                translation,
                word.target_text,
                allow_inflection=True,
            ):
                completed = translator.complete_example(
                    example,
                    word.source_text,
                    word.source_lang,
                    word.target_text,
                )
                example = completed.source
                translation = completed.translation
            if example:
                repository.update_example(word.id, example, translation)
        except Exception as error:
            print(
                f"Could not enrich card {self.word_id}: {error}",
                file=sys.stderr,
            )
        finally:
            repository.close()


class LexiDeskService(QObject):
    def __init__(self, repository: WordRepository) -> None:
        super().__init__()
        self.repository = repository
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(1)
        for word in self.repository.list_words():
            self.thread_pool.start(ExampleEnrichmentTask(self.repository.path, word.id))

    @Slot(str, result=str)
    def Request(self, raw_request: str) -> str:  # noqa: N802
        payload: dict[str, Any]
        try:
            decoded = json.loads(raw_request)
            if not isinstance(decoded, dict):
                raise ValueError("The request must be a JSON object.")
            if decoded.get("command") == "enrich":
                word_id = int(decoded["word_id"])
                self.repository.get_word(word_id)
                self.thread_pool.start(
                    ExampleEnrichmentTask(self.repository.path, word_id)
                )
                payload = {"scheduled": True, "word_id": word_id}
            else:
                payload = execute_request(self.repository, decoded)
        except Exception as error:
            payload = {"error": str(error), "type": type(error).__name__}
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def main() -> int:
    app = QCoreApplication(sys.argv)
    app.setApplicationName(f"{APP_NAME} Service")
    settings = SettingsStore(settings_path()).load()
    repository = WordRepository(
        database_path(),
        desired_retention=settings.desired_retention,
    )
    ensure_daily_backup(repository)

    bus = QDBusConnection.sessionBus()
    if not bus.registerService(SERVICE_NAME):
        repository.close()
        return 1
    service = LexiDeskService(repository)
    registration = QDBusConnection.RegisterOption.ExportAllSlots
    if not bus.registerObject(OBJECT_PATH, INTERFACE_NAME, service, registration):
        bus.unregisterService(SERVICE_NAME)
        repository.close()
        return 1
    result = app.exec()
    repository.close()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
