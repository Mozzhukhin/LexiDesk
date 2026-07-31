from __future__ import annotations

import json
import logging
import queue
import sys
import threading
from typing import Any

from .config import database_path
from .enrichment import enrich_example

SERVICE_NAME = "io.github.lexidesk"
OBJECT_PATH = "/LexiDesk"
INTERFACE_NAME = "io.github.lexidesk.Service"
_enrichment_queue: queue.Queue[int] = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()
logger = logging.getLogger(__name__)


def request_service(request: dict[str, Any]) -> dict[str, Any] | None:
    if sys.platform == "win32":
        return None

    # QtDBus is a Unix-only optional Qt module. Import it lazily so the
    # standalone desktop application can start normally on Windows.
    try:
        from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
    except ImportError:
        return None

    bus = QDBusConnection.sessionBus()
    interface = QDBusInterface(
        SERVICE_NAME,
        OBJECT_PATH,
        INTERFACE_NAME,
        bus,
    )
    if not interface.isValid():
        return None
    interface.setTimeout(1500)
    reply = interface.call(
        "Request",
        json.dumps(request, ensure_ascii=False, separators=(",", ":")),
    )
    if reply.type() == QDBusMessage.MessageType.ErrorMessage:
        return None
    arguments = reply.arguments()
    if not arguments:
        return None
    try:
        payload = json.loads(str(arguments[0]))
    except (json.JSONDecodeError, TypeError):
        logger.warning("The local D-Bus service returned invalid JSON")
        return None
    return payload if isinstance(payload, dict) else None


def schedule_example_enrichment(word_id: int) -> bool:
    response = request_service({"command": "enrich", "word_id": word_id})
    if response and response.get("scheduled"):
        return True
    _start_local_worker()
    _enrichment_queue.put(word_id)
    return True


def _start_local_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        thread = threading.Thread(
            target=_run_local_enrichment,
            name="lexidesk-example-worker",
            daemon=True,
        )
        thread.start()
        _worker_started = True


def _run_local_enrichment() -> None:
    while True:
        word_id = _enrichment_queue.get()
        try:
            enrich_example(database_path(), word_id)
        finally:
            _enrichment_queue.task_done()
