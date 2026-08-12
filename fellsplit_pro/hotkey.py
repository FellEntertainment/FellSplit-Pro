from __future__ import annotations

import ctypes
import os
import queue
import threading
from ctypes import wintypes
from dataclasses import dataclass


WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
PM_NOREMOVE = 0x0000
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
HOTKEY_ID = 0x534C

KEY_CODES = {
    **{f"F{number}": 0x6F + number for number in range(1, 13)},
    "PAUSE": 0x13,
    "HOME": 0x24,
    "END": 0x23,
    "INSERT": 0x2D,
}


@dataclass(slots=True, frozen=True)
class HotkeySpec:
    ctrl: bool = True
    alt: bool = True
    shift: bool = False
    key: str = "F10"

    @property
    def modifiers(self) -> int:
        value = MOD_NOREPEAT
        if self.ctrl:
            value |= MOD_CONTROL
        if self.alt:
            value |= MOD_ALT
        if self.shift:
            value |= MOD_SHIFT
        return value

    @property
    def vk_code(self) -> int:
        key = self.key.upper()
        if key not in KEY_CODES:
            raise ValueError(f"Nicht unterstuetzte Hotkey-Taste: {self.key}")
        return KEY_CODES[key]

    @property
    def label(self) -> str:
        parts: list[str] = []
        if self.ctrl:
            parts.append("Strg")
        if self.alt:
            parts.append("Alt")
        if self.shift:
            parts.append("Umschalt")
        parts.append(self.key.upper())
        return "+".join(parts)

    def validate(self) -> None:
        _ = self.vk_code
        if not (self.ctrl or self.alt or self.shift):
            raise ValueError("Der globale Hotkey benoetigt mindestens eine Modifikatortaste.")


if os.name == "nt":
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", POINT),
        ]

    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.RegisterHotKey.restype = wintypes.BOOL
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = wintypes.BOOL
    user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.restype = ctypes.c_int
    user32.PeekMessageW.argtypes = [
        ctypes.POINTER(MSG),
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
        wintypes.UINT,
    ]
    user32.PeekMessageW.restype = wintypes.BOOL
    user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostThreadMessageW.restype = wintypes.BOOL
    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD


class GlobalHotkeyManager:
    """Registers a Win32 hotkey without keyboard hooks or extra dependencies."""

    def __init__(self, events: queue.Queue[str]) -> None:
        self._events = events
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._registered = False
        self._error_code = 0

    @property
    def registered(self) -> bool:
        return self._registered

    def start(self, spec: HotkeySpec) -> tuple[bool, str]:
        if os.name != "nt":
            return False, "Globale Hotkeys sind nur unter Windows verfuegbar."
        spec.validate()
        self.stop()

        self._ready.clear()
        self._registered = False
        self._error_code = 0
        self._thread = threading.Thread(
            target=self._message_loop,
            args=(spec,),
            name="FellSplitProHotkey",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=1.5):
            return False, "Die Hotkey-Registrierung hat nicht rechtzeitig geantwortet."
        if not self._registered:
            detail = ctypes.FormatError(self._error_code).strip() if self._error_code else "Hotkey belegt"
            return False, f"{spec.label} konnte nicht registriert werden: {detail}."
        return True, f"Globaler Hotkey aktiv: {spec.label}"

    def stop(self) -> None:
        if os.name == "nt" and self._thread is not None and self._thread.is_alive():
            if self._thread_id:
                user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self._thread.join(timeout=1.5)
        self._thread = None
        self._thread_id = 0
        self._registered = False

    def _message_loop(self, spec: HotkeySpec) -> None:
        self._thread_id = int(kernel32.GetCurrentThreadId())
        message = MSG()
        # Explicitly create the thread message queue before another thread may post WM_QUIT.
        user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_NOREMOVE)

        ctypes.set_last_error(0)
        if not user32.RegisterHotKey(None, HOTKEY_ID, spec.modifiers, spec.vk_code):
            self._error_code = ctypes.get_last_error()
            self._ready.set()
            return

        self._registered = True
        self._ready.set()
        try:
            while True:
                result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result <= 0:
                    break
                if message.message == WM_HOTKEY and message.wParam == HOTKEY_ID:
                    self._events.put("toggle")
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID)
            self._registered = False
