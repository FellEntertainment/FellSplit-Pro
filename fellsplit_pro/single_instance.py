from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0
# Keep the legacy object names so FellSplit Pro cannot run beside an older
# SplitLock tray instance during an in-place upgrade.
MUTEX_NAME = r"Local\SplitLock-Fell-Entertainment-v1"
SHOW_EVENT_NAME = r"Local\SplitLock-Fell-Entertainment-Show-v1"


class SingleInstance:
    def __init__(self) -> None:
        self._handle = None
        self._show_event = None

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateEventW.argtypes = [
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        kernel32.CreateEventW.restype = wintypes.HANDLE
        self._show_event = kernel32.CreateEventW(None, False, False, SHOW_EVENT_NAME)
        ctypes.set_last_error(0)
        self._handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not self._handle or not self._show_event:
            return False
        return ctypes.get_last_error() != ERROR_ALREADY_EXISTS

    def signal_show_request(self) -> None:
        if os.name != "nt" or not self._show_event:
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.SetEvent.argtypes = [wintypes.HANDLE]
        kernel32.SetEvent.restype = wintypes.BOOL
        kernel32.SetEvent(self._show_event)

    def consume_show_request(self) -> bool:
        if os.name != "nt" or not self._show_event:
            return False
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        return kernel32.WaitForSingleObject(self._show_event, 0) == WAIT_OBJECT_0

    def release(self) -> None:
        if os.name != "nt":
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        if self._handle:
            kernel32.CloseHandle(self._handle)
            self._handle = None
        if self._show_event:
            kernel32.CloseHandle(self._show_event)
            self._show_event = None
