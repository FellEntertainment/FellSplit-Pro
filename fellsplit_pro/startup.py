from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "FellSplit Pro"
LEGACY_VALUE_NAME = "SplitLock"


def sync_windows_startup(enabled: bool, start_minimized: bool) -> str:
    """Create or remove the per-user Run entry; administrator rights are not needed."""

    if os.name != "nt":
        raise RuntimeError("Windows-Autostart ist nur unter Windows verfuegbar.")
    import winreg

    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        RUN_KEY,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        try:
            winreg.DeleteValue(key, LEGACY_VALUE_NAME)
        except FileNotFoundError:
            pass
        if not enabled:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
            return "Windows-Autostart ist deaktiviert."

        command = build_startup_command(start_minimized)
        if len(command) > 260:
            raise ValueError(
                "Der Installationspfad ist fuer den Windows-Run-Eintrag zu lang. "
                "Verschiebe FellSplit Pro in einen kuerzeren Ordner."
            )
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
        mode = "minimiert im Tray" if start_minimized else "mit geoeffnetem Fenster"
        return f"Windows-Autostart ist aktiv ({mode})."


def build_startup_command(start_minimized: bool) -> str:
    arguments: list[str]
    if getattr(sys, "frozen", False):
        arguments = [str(Path(sys.executable).resolve())]
    else:
        interpreter = _windowed_interpreter(Path(sys.executable))
        launcher = Path(__file__).resolve().parents[1] / "FellSplitPro.pyw"
        arguments = [str(interpreter), str(launcher)]
    if start_minimized:
        arguments.append("--minimized")
    return subprocess.list2cmdline(arguments)


def _windowed_interpreter(interpreter: Path) -> Path:
    if interpreter.name.casefold() in {"python.exe", "python3.exe"}:
        candidate = interpreter.with_name("pythonw.exe")
        if candidate.exists():
            return candidate
    return interpreter
