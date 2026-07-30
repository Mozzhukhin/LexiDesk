import json
from pathlib import Path

from lexidesk.database import WordRepository
from lexidesk.service import LexiDeskService


def test_service_processes_json_requests(tmp_path: Path) -> None:
    repository = WordRepository(tmp_path / "service.db")
    repository.add_word(
        source_text="reliable",
        source_lang="en",
        target_text="надёжный",
    )
    service = LexiDeskService(repository)
    stats = json.loads(service.Request('{"command":"stats"}'))
    assert stats["total"] == 1
    invalid = json.loads(service.Request("[]"))
    assert invalid["type"] == "ValueError"
    repository.close()
