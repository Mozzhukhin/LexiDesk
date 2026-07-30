from __future__ import annotations

import json
import sys
from typing import Any

SERVICE_NAME = "io.github.lexidesk"
OBJECT_PATH = "/LexiDesk"
INTERFACE_NAME = "io.github.lexidesk.Service"


def request_service(request: dict[str, Any]) -> dict[str, Any] | None:
    if sys.platform == "win32":
        return None

    # QtDBus is a Unix-only optional Qt module. Import it lazily so the
    # standalone desktop application can start normally on Windows.
    from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

    bus = QDBusConnection.sessionBus()
    interface = QDBusInterface(
        SERVICE_NAME,
        OBJECT_PATH,
        INTERFACE_NAME,
        bus,
    )
    if not interface.isValid():
        return None
    reply = interface.call(
        "Request",
        json.dumps(request, ensure_ascii=False, separators=(",", ":")),
    )
    if reply.type() == QDBusMessage.MessageType.ErrorMessage:
        return None
    arguments = reply.arguments()
    if not arguments:
        return None
    payload = json.loads(str(arguments[0]))
    return payload if isinstance(payload, dict) else None


def schedule_example_enrichment(word_id: int) -> bool:
    response = request_service({"command": "enrich", "word_id": word_id})
    return bool(response and response.get("scheduled"))
