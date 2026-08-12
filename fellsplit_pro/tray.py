from __future__ import annotations

import queue
import sys
import threading
from collections.abc import Callable
from pathlib import Path


class TrayManager:
    """Small pystray adapter that communicates with Tk only through a queue."""

    def __init__(
        self,
        events: queue.Queue[str],
        is_active: Callable[[], bool],
        version: str = "",
    ) -> None:
        self._events = events
        self._is_active = is_active
        self._version = version
        self._icon = None
        self._thread: threading.Thread | None = None
        self._available = False
        self._pystray = None
        self._ready = threading.Event()
        self._start_error = ""

    @property
    def available(self) -> bool:
        return self._available

    def start(self) -> tuple[bool, str]:
        if self._available and self._icon is not None:
            self.update()
            return True, "System-Tray ist aktiv."
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ModuleNotFoundError as exc:
            return False, f"Tray-Abhaengigkeit fehlt: {exc.name}"

        try:
            bundle_root = Path(
                getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])
            )
            with Image.open(bundle_root / "assets" / "FellSplitPro.ico") as icon_file:
                image = icon_file.convert("RGBA").resize(
                    (64, 64), Image.Resampling.LANCZOS
                )
        except Exception:
            image = Image.new("RGBA", (64, 64), "#08101D")
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((4, 4, 60, 60), radius=14, fill="#0EA5E9")
            draw.rectangle((14, 14, 23, 50), fill="#E0F2FE")
            draw.rectangle((14, 14, 34, 22), fill="#E0F2FE")
            draw.rectangle((14, 28, 31, 36), fill="#E0F2FE")
            draw.rounded_rectangle((39, 14, 52, 50), radius=3, outline="#E0F2FE")

        self._pystray = pystray
        self._icon = pystray.Icon(
            "FellSplitPro",
            icon=image,
            title=self._base_title,
            menu=self._build_menu(),
        )
        self._ready.clear()
        self._start_error = ""
        try:
            # FellSplit Pro is Windows-only. The pystray documentation explicitly
            # permits the Windows backend to run its message loop in a worker thread.
            self._thread = threading.Thread(
                target=self._run_icon,
                name="FellSplitProTray",
                daemon=True,
            )
            self._thread.start()
        except Exception as exc:
            self._icon = None
            return False, f"System-Tray konnte nicht gestartet werden: {exc}"

        if not self._ready.wait(timeout=2.0) or self._start_error:
            error = self._start_error or "Das Tray-Symbol hat nicht rechtzeitig geantwortet."
            self.stop()
            return False, f"System-Tray konnte nicht gestartet werden: {error}"

        self._available = True
        return True, "System-Tray ist aktiv."

    def update(self, status_text: str = "") -> None:
        if not self._available or self._icon is None:
            return
        active = self._is_active()
        self._icon.title = (
            f"{self._base_title} - Aktiv" if active else f"{self._base_title} - Aus"
        )
        if status_text:
            self._icon.title = self._icon.title[:80]
        self._icon.menu = self._build_menu()
        try:
            self._icon.update_menu()
        except Exception:
            pass

    def notify(self, message: str, title: str = "FellSplit Pro") -> None:
        if not self._available or self._icon is None:
            return
        try:
            if getattr(self._icon, "HAS_NOTIFICATION", False):
                self._icon.notify(message, title)
        except Exception:
            pass

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        self._icon = None
        self._available = False

    def _build_menu(self):
        assert self._pystray is not None
        toggle_text = (
            "FellSplit Pro deaktivieren"
            if self._is_active()
            else "FellSplit Pro aktivieren"
        )
        return self._pystray.Menu(
            self._pystray.MenuItem(
                f"{self._base_title} oeffnen",
                self._show,
                default=True,
            ),
            self._pystray.MenuItem(toggle_text, self._toggle),
            self._pystray.Menu.SEPARATOR,
            self._pystray.MenuItem("Beenden", self._exit),
        )

    @property
    def _base_title(self) -> str:
        return (
            f"FellSplit Pro {self._version}"
            if self._version
            else "FellSplit Pro"
        )

    def _run_icon(self) -> None:
        assert self._icon is not None
        try:
            self._icon.run(setup=self._tray_ready)
        except Exception as exc:
            self._start_error = str(exc)
            self._ready.set()

    def _tray_ready(self, icon) -> None:
        try:
            icon.visible = True
        finally:
            self._ready.set()

    def _show(self, _icon=None, _item=None) -> None:
        self._events.put("show")

    def _toggle(self, _icon=None, _item=None) -> None:
        self._events.put("toggle")

    def _exit(self, _icon=None, _item=None) -> None:
        self._events.put("exit")
