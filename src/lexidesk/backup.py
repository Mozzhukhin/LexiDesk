from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .database import WordRepository


def ensure_daily_backup(repository: WordRepository, keep: int = 7) -> Path:
    backup_dir = repository.path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"lexidesk-{datetime.now().date().isoformat()}.db"
    if not target.exists():
        repository.backup_to(target)

    backups = sorted(backup_dir.glob("lexidesk-????-??-??.db"), reverse=True)
    for obsolete in backups[max(1, keep) :]:
        obsolete.unlink(missing_ok=True)
    return target
