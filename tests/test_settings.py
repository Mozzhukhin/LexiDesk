import json
from pathlib import Path

from lexidesk.settings import SettingsStore


def test_invalid_settings_are_sanitized(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "theme": ["not", "a", "string"],
                "rotation_seconds": 1,
                "opacity": 8,
                "font_scale": "large",
                "width": -100,
                "height": 99999,
                "reveal_mode": "invalid",
                "daily_goal": 0,
                "desired_retention": 2.0,
                "autocorrect": "yes",
                "autostart": "yes",
            }
        ),
        encoding="utf-8",
    )

    settings = SettingsStore(path).load()
    assert settings.theme == "Breeze Dark"
    assert settings.rotation_seconds == 30
    assert settings.opacity == 1.0
    assert settings.font_scale == 100
    assert settings.width == 330
    assert settings.height == 1600
    assert settings.reveal_mode == "both"
    assert settings.daily_goal == 1
    assert settings.desired_retention == 0.99
    assert settings.autocorrect is True
    assert settings.autostart is False
