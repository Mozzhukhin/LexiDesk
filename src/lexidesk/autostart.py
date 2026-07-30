from __future__ import annotations

import shlex
import sys

from .config import autostart_path


def set_autostart(enabled: bool) -> None:
    path = autostart_path()
    if not enabled:
        path.unlink(missing_ok=True)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    command = shlex.join([sys.executable, "-m", "lexidesk.main"])
    content = f"""[Desktop Entry]
Type=Application
Name=LexiDesk
Comment=Offline vocabulary widget
Exec={command}
Icon=accessories-dictionary
Terminal=false
Categories=Education;Languages;
X-GNOME-Autostart-enabled=true
"""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
