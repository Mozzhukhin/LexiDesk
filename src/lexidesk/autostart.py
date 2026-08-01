from __future__ import annotations

import os
import shlex
import subprocess
import sys

from .config import autostart_path


def autostart_enabled() -> bool:
    path = autostart_path()
    if path.exists():
        return True
    return sys.platform == "win32" and path.with_suffix(".lnk").exists()


def set_autostart(enabled: bool) -> None:
    path = autostart_path()
    if not enabled:
        path.unlink(missing_ok=True)
        if sys.platform == "win32":
            path.with_suffix(".lnk").unlink(missing_ok=True)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    appimage = os.environ.get("APPIMAGE")
    if appimage and sys.platform != "win32":
        # APPDIR is temporary; autostart must point to the persistent AppImage.
        arguments = [appimage]
    elif getattr(sys, "frozen", False):
        arguments = [sys.executable]
    else:
        arguments = [sys.executable, "-m", "lexidesk.main"]
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
