from __future__ import annotations

from PySide6.QtCore import Qt

WINDOW_MODES = ("desktop", "floating")


def widget_window_flags(mode: str) -> Qt.WindowType:
    """Return interactive widget flags shared by Windows and Linux builds."""
    flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
    if mode == "floating":
        return flags | Qt.WindowType.WindowStaysOnTopHint
    return flags | Qt.WindowType.WindowStaysOnBottomHint


def clamp_widget_position(
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    left: int,
    top: int,
    right: int,
    bottom: int,
) -> tuple[int, int]:
    """Keep a restored widget reachable after display-layout changes."""
    maximum_x = max(left, right - max(1, width) + 1)
    maximum_y = max(top, bottom - max(1, height) + 1)
    return max(left, min(x, maximum_x)), max(top, min(y, maximum_y))
