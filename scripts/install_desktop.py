#!/usr/bin/env python
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    project = Path(__file__).resolve().parent.parent
    launcher = project / "scripts" / "run.sh"
    icon = project / "assets" / "lexidesk.svg"
    local_bin = Path.home() / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)
    gui_wrapper = local_bin / "lexidesk-gui"
    bridge_wrapper = local_bin / "lexidesk-bridge"
    service_wrapper = local_bin / "lexidesk-service"
    python = project / ".venv" / "bin" / "python"

    gui_wrapper.write_text(
        f'#!/usr/bin/env bash\nexec "{python}" -m lexidesk.main "$@"\n',
        encoding="utf-8",
    )
    bridge_wrapper.write_text(
        f'#!/usr/bin/env bash\nexec "{python}" -m lexidesk.cli "$@"\n',
        encoding="utf-8",
    )
    service_wrapper.write_text(
        f'#!/usr/bin/env bash\nexec "{python}" -m lexidesk.service "$@"\n',
        encoding="utf-8",
    )
    os.chmod(gui_wrapper, 0o755)
    os.chmod(bridge_wrapper, 0o755)
    os.chmod(service_wrapper, 0o755)

    systemd_user = Path.home() / ".config" / "systemd" / "user"
    systemd_user.mkdir(parents=True, exist_ok=True)
    service_unit = systemd_user / "lexidesk.service"
    service_unit.write_text(
        f"""[Unit]
Description=LexiDesk local vocabulary service
After=graphical-session.target

[Service]
Type=simple
ExecStart={service_wrapper}
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
""",
        encoding="utf-8",
    )

    dbus_services = Path.home() / ".local" / "share" / "dbus-1" / "services"
    dbus_services.mkdir(parents=True, exist_ok=True)
    dbus_service = dbus_services / "io.github.lexidesk.service"
    dbus_service.write_text(
        f"""[D-BUS Service]
Name=io.github.lexidesk
Exec={service_wrapper}
SystemdService=lexidesk.service
""",
        encoding="utf-8",
    )

    systemctl = shutil.which("systemctl")
    if systemctl:
        subprocess.run(
            [systemctl, "--user", "daemon-reload"],
            check=False,
            stdout=subprocess.DEVNULL,
        )
        service_result = subprocess.run(
            [systemctl, "--user", "enable", "--now", "lexidesk.service"],
            check=False,
            text=True,
            capture_output=True,
        )
        if service_result.returncode:
            print("Could not start the optional LexiDesk background service.")
        else:
            print("Started local LexiDesk service.")

    applications = Path.home() / ".local" / "share" / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    target = applications / "io.github.lexidesk.desktop"
    target.write_text(
        f"""[Desktop Entry]
Type=Application
Name=LexiDesk
GenericName=Vocabulary Widget
Comment=Learn English and Russian words offline
Exec={gui_wrapper}
Icon={icon}
Terminal=false
Categories=Education;Languages;
StartupNotify=false
Actions=AddClipboard;Library;

[Desktop Action AddClipboard]
Name=Add word from clipboard
Exec={gui_wrapper} --add-clipboard
Icon=list-add

[Desktop Action Library]
Name=Open vocabulary library
Exec={gui_wrapper} --library
Icon=view-list-details
""",
        encoding="utf-8",
    )

    add_target = applications / "io.github.lexidesk.add.desktop"
    add_target.write_text(
        f"""[Desktop Entry]
Type=Application
Name=LexiDesk — Add from Clipboard
Comment=Translate and save the current clipboard text
Exec={gui_wrapper} --add-clipboard
Icon={icon}
Terminal=false
Categories=Education;Languages;
NoDisplay=true
X-KDE-Shortcuts=Ctrl+Alt+L
""",
        encoding="utf-8",
    )
    os.chmod(launcher, 0o755)
    print(f"Installed desktop entry: {target}")
    cache_builder = shutil.which("kbuildsycoca6")
    if cache_builder:
        subprocess.run([cache_builder], check=False, stdout=subprocess.DEVNULL)

    gdbus = shutil.which("gdbus")
    if gdbus:
        from PySide6.QtGui import QKeySequence

        shortcut_code = QKeySequence("Ctrl+Alt+L")[0].toCombined()
        action_id = (
            "['io.github.lexidesk.add.desktop','_launch',"
            "'LexiDesk — Add from Clipboard','LexiDesk — Add from Clipboard']"
        )
        shortcut_result = subprocess.run(
            [
                gdbus,
                "call",
                "--session",
                "--dest",
                "org.kde.kglobalaccel",
                "--object-path",
                "/kglobalaccel",
                "--method",
                "org.kde.KGlobalAccel.setShortcut",
                action_id,
                f"[{shortcut_code}]",
                "4",
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        if str(shortcut_code) in shortcut_result.stdout:
            print("Registered shortcut: Ctrl+Alt+L")
        else:
            print("Could not register Ctrl+Alt+L (it may already be in use).")

    package_tool = shutil.which("kpackagetool6")
    plasmoid_source = project / "plasma" / "io.github.lexidesk"
    plasmoid_target = (
        Path.home() / ".local" / "share" / "plasma" / "plasmoids" / "io.github.lexidesk"
    )
    if package_tool:
        operation = "--upgrade" if plasmoid_target.exists() else "--install"
        result = subprocess.run(
            [
                package_tool,
                "--type",
                "Plasma/Applet",
                operation,
                str(plasmoid_source),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        output = (result.stdout + result.stderr).strip()
        if output:
            print(output)
        if result.returncode:
            raise SystemExit("Could not install the Plasma widget.")
        print("Installed Plasma widget: LexiDesk")
    else:
        print("kpackagetool6 was not found; skipped Plasma widget installation.")


if __name__ == "__main__":
    main()
