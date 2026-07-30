from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    theme: str = "Breeze Dark"
    rotation_seconds: int = 90
    opacity: float = 0.96
    font_scale: int = 100
    x: int | None = None
    y: int | None = None
    width: int = 390
    height: int = 330
    reveal_mode: str = "both"
    daily_goal: int = 20
    desired_retention: float = 0.9
    autocorrect: bool = True
    autostart: bool = False


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Settings:
        if not self.path.exists():
            return Settings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return Settings()
            defaults = Settings()
            return Settings(
                theme=raw["theme"]
                if isinstance(raw.get("theme"), str)
                else defaults.theme,
                rotation_seconds=_bounded_int(
                    raw.get("rotation_seconds"), defaults.rotation_seconds, 30, 3600
                ),
                opacity=_bounded_float(raw.get("opacity"), defaults.opacity, 0.5, 1.0),
                font_scale=_bounded_int(
                    raw.get("font_scale"), defaults.font_scale, 80, 150
                ),
                x=_optional_int(raw.get("x")),
                y=_optional_int(raw.get("y")),
                width=_bounded_int(raw.get("width"), defaults.width, 330, 2400),
                height=_bounded_int(raw.get("height"), defaults.height, 310, 1600),
                reveal_mode=(
                    raw["reveal_mode"]
                    if raw.get("reveal_mode") in {"both", "quiz", "typing"}
                    else defaults.reveal_mode
                ),
                daily_goal=_bounded_int(
                    raw.get("daily_goal"), defaults.daily_goal, 1, 500
                ),
                desired_retention=_bounded_float(
                    raw.get("desired_retention"),
                    defaults.desired_retention,
                    0.7,
                    0.99,
                ),
                autocorrect=(
                    raw["autocorrect"]
                    if isinstance(raw.get("autocorrect"), bool)
                    else defaults.autocorrect
                ),
                autostart=(
                    raw["autostart"]
                    if isinstance(raw.get("autostart"), bool)
                    else defaults.autostart
                ),
            )
        except (OSError, ValueError, TypeError):
            return Settings()

    def save(self, settings: Settings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(settings), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(self.path)


def _bounded_int(value: object, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(minimum, min(value, maximum))


def _bounded_float(
    value: object, default: float, minimum: float, maximum: float
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return max(minimum, min(float(value), maximum))


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
