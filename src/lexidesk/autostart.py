from __future__ import annotations

import shlex
import subprocess
import sys

from .config import autostart_path


def set_autostart(enabled: bool) -> None:
    path = autostart_path()
    if not enabled:
        path.unlink(missing_ok=True)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    arguments = (
        [sys.executable]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-m", "lexidesk.main"]
    )
    if sys.platform == "win32":
        command = subprocess.list2cmdline(arguments)
        content = f'@start "" {command}\n'
    else:
        command = shlex.join(arguments)
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
