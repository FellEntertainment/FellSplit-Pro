from __future__ import annotations

import atexit
import os
import sys
import traceback
from tkinter import messagebox


def _fatal_error(message: str) -> None:
    try:
        messagebox.showerror("FellSplit Pro - Startfehler", message)
    except Exception:
        print(message, file=sys.stderr)


def main() -> int:
    if os.name != "nt":
        _fatal_error("FellSplit Pro laeuft nur unter Windows 10 oder Windows 11.")
        return 1

    try:
        from fellsplit_pro import win32_api as win32
        from fellsplit_pro.single_instance import SingleInstance

        win32.enable_dpi_awareness()
        if "--emergency-unlock" in sys.argv:
            win32.release_cursor()
            win32.show_all_taskbars()
            messagebox.showinfo(
                "FellSplit Pro - Notfall-Freigabe",
                "Die Maus wurde freigegeben und die Windows-Taskleiste eingeblendet.",
            )
            return 0

        instance = SingleInstance()
        if not instance.acquire():
            instance.signal_show_request()
            instance.release()
            if "--launch-check" in sys.argv:
                messagebox.showwarning(
                    "FellSplit Pro laeuft bereits",
                    "Eine bereits laufende FellSplit-Pro-Instanz wurde geoeffnet.\n\n"
                    "Wichtig nach einem Update: Beende die alte Instanz zuerst "
                    "ueber das Tray-Menue mit 'Beenden' und starte danach erneut. "
                    "Sonst arbeitet weiterhin der alte Code im Hintergrund.",
                )
            return 0
        atexit.register(instance.release)
        from fellsplit_pro.ui import FellSplitProApp

        app = FellSplitProApp(single_instance=instance)
        atexit.register(app.controller.emergency_release)
        app.mainloop()
        return 0
    except ModuleNotFoundError as exc:
        if exc.name == "customtkinter":
            _fatal_error(
                "CustomTkinter fehlt. Oeffne in diesem Ordner ein Terminal und fuehre aus:\n\n"
                "py -m pip install -r requirements.txt"
            )
            return 2
        raise
    except Exception as exc:
        from fellsplit_pro.config_store import error_log_path

        error_log = error_log_path()
        log_written = False
        try:
            error_log.parent.mkdir(parents=True, exist_ok=True)
            error_log.write_text(traceback.format_exc(), encoding="utf-8")
            log_written = True
        except OSError:
            pass
        detail_note = (
            f"Details wurden nach {error_log} geschrieben."
            if log_written
            else "Das Fehlerprotokoll konnte nicht geschrieben werden."
        )
        _fatal_error(
            f"FellSplit Pro ist unerwartet beendet worden: {exc}\n\n"
            f"{detail_note}"
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
