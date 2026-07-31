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
from .diagnostics import configure_logging
from .enrichment import enrich_example, needs_example_enrichment
from .service_client import INTERFACE_NAME, OBJECT_PATH, SERVICE_NAME
from .settings import SettingsStore


class ExampleEnrichmentTask(QRunnable):
    def __init__(self, database: Path, word_id: int) -> None:
        super().__init__()
        self.database = database
        self.word_id = word_id

    def run(self) -> None:
        enrich_example(self.database, self.word_id)


class LexiDeskService(QObject):
    def __init__(self, repository: WordRepository) -> None:
        super().__init__()
        self.repository = repository
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(1)
        self.enrichment_scheduled: set[int] = set()

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
                self.enrichment_scheduled.add(word_id)
                self.thread_pool.start(
                    ExampleEnrichmentTask(self.repository.path, word_id)
                )
                payload = {"scheduled": True, "word_id": word_id}
            else:
                payload = execute_request(self.repository, decoded)
                word_id = int(payload.get("id", 0))
                if (
                    decoded.get("command") in {"card", "get"}
                    and word_id > 0
                    and word_id not in self.enrichment_scheduled
                    and len(self.enrichment_scheduled) < 20
                    and needs_example_enrichment(
                        self.repository, self.repository.get_word(word_id)
                    )
                ):
                    self.enrichment_scheduled.add(word_id)
                    self.thread_pool.start(
                        ExampleEnrichmentTask(self.repository.path, word_id)
                    )
        except Exception as error:
            payload = {"error": str(error), "type": type(error).__name__}
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def main() -> int:
    configure_logging()
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
