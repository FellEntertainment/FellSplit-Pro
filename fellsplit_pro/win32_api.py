from __future__ import annotations

import ctypes
import ntpath
import os
from ctypes import wintypes
from dataclasses import dataclass

from .models import MonitorInfo, TargetRect, WindowInfo


IS_WINDOWS = os.name == "nt"


class Win32Error(RuntimeError):
    def __init__(self, action: str, code: int | None = None) -> None:
        self.code = ctypes.get_last_error() if code is None else code
        detail = ctypes.FormatError(self.code).strip() if self.code else "Unbekannter Fehler"
        super().__init__(f"{action} fehlgeschlagen (Windows-Fehler {self.code}: {detail}).")


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", POINT),
        ("ptMaxPosition", POINT),
        ("rcNormalPosition", RECT),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


@dataclass(slots=True, frozen=True)
class PlacementSnapshot:
    flags: int
    show_cmd: int
    min_x: int
    min_y: int
    max_x: int
    max_y: int
    normal_left: int
    normal_top: int
    normal_right: int
    normal_bottom: int


@dataclass(slots=True, frozen=True)
class WindowSnapshot:
    hwnd: int
    style: int
    exstyle: int
    left: int
    top: int
    right: int
    bottom: int
    placement: PlacementSnapshot


@dataclass(slots=True, frozen=True)
class WindowMeasurement:
    """Measured outer/client bounds plus the current non-client style state."""

    outer: TargetRect
    client: TargetRect
    has_decorations: bool


@dataclass(slots=True, frozen=True)
class TaskbarSnapshot:
    hwnd: int
    was_visible: bool


# Window style constants.
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_BORDER = 0x00800000
WS_DLGFRAME = 0x00400000
WS_CAPTION = WS_BORDER | WS_DLGFRAME
WS_SYSMENU = 0x00080000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_MAXIMIZE = 0x01000000
WS_MINIMIZE = 0x20000000
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_DLGMODALFRAME = 0x00000001
WS_EX_TOPMOST = 0x00000008
WS_EX_WINDOWEDGE = 0x00000100
WS_EX_CLIENTEDGE = 0x00000200
WS_EX_STATICEDGE = 0x00020000

WINDOW_DECORATION_MASK = (
    WS_CAPTION | WS_SYSMENU | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
)
WINDOW_STATE_MASK = WS_MAXIMIZE | WS_MINIMIZE
EXTENDED_DECORATION_MASK = (
    WS_EX_DLGMODALFRAME | WS_EX_WINDOWEDGE | WS_EX_CLIENTEDGE | WS_EX_STATICEDGE
)

# SetWindowPos / ShowWindow constants.
HWND_TOP = 0
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040
SWP_NOOWNERZORDER = 0x0200
SW_RESTORE = 9
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4

# Enumeration / monitor constants.
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
DWMWA_CLOAKED = 14
MONITOR_DEFAULTTOPRIMARY = 1
MONITOR_DEFAULTTONEAREST = 2
MONITORINFOF_PRIMARY = 1
GA_ROOT = 2
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    try:
        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
    except OSError:
        dwmapi = None
    try:
        shcore = ctypes.WinDLL("shcore", use_last_error=True)
    except OSError:
        shcore = None

    LONG_PTR = ctypes.c_ssize_t
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(RECT),
        wintypes.LPARAM,
    )

    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowExW.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
    ]
    user32.FindWindowExW.restype = wintypes.HWND
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
    user32.ClientToScreen.restype = wintypes.BOOL
    user32.GetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWPLACEMENT)]
    user32.GetWindowPlacement.restype = wintypes.BOOL
    user32.SetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWPLACEMENT)]
    user32.SetWindowPlacement.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.MoveWindow.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.BOOL,
    ]
    user32.MoveWindow.restype = wintypes.BOOL
    user32.ClipCursor.argtypes = [ctypes.POINTER(RECT)]
    user32.ClipCursor.restype = wintypes.BOOL
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetSystemMetrics.restype = ctypes.c_int
    user32.MonitorFromPoint.argtypes = [POINT, wintypes.DWORD]
    user32.MonitorFromPoint.restype = wintypes.HANDLE
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.EnumDisplayMonitors.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(RECT),
        MONITORENUMPROC,
        wintypes.LPARAM,
    ]
    user32.EnumDisplayMonitors.restype = wintypes.BOOL

    if ctypes.sizeof(ctypes.c_void_p) == 8:
        _get_window_long = user32.GetWindowLongPtrW
        _set_window_long = user32.SetWindowLongPtrW
    else:
        _get_window_long = user32.GetWindowLongW
        _set_window_long = user32.SetWindowLongW
    _get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
    _get_window_long.restype = LONG_PTR
    _set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
    _set_window_long.restype = LONG_PTR

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    shell32.IsUserAnAdmin.argtypes = []
    shell32.IsUserAnAdmin.restype = wintypes.BOOL

    if dwmapi is not None:
        dwmapi.DwmGetWindowAttribute.argtypes = [
            wintypes.HWND,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        dwmapi.DwmGetWindowAttribute.restype = ctypes.HRESULT


def require_windows() -> None:
    if not IS_WINDOWS:
        raise RuntimeError("FellSplit Pro kann nur unter Windows 10/11 laufen.")


def enable_dpi_awareness() -> None:
    """Use physical pixels, including on monitors with Windows scaling enabled."""

    require_windows()
    try:
        set_context = user32.SetProcessDpiAwarenessContext
        set_context.argtypes = [ctypes.c_void_p]
        set_context.restype = wintypes.BOOL
        if set_context(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass

    if shcore is not None:
        try:
            shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
            shcore.SetProcessDpiAwareness.restype = ctypes.c_long
            result = shcore.SetProcessDpiAwareness(2)
            if (int(result) & 0xFFFFFFFF) in (0, 0x80070005):
                return
        except (AttributeError, OSError):
            pass

    try:
        user32.SetProcessDPIAware()
    except AttributeError:
        pass


def is_admin() -> bool:
    require_windows()
    try:
        return bool(shell32.IsUserAnAdmin())
    except OSError:
        return False


def is_window(hwnd: int) -> bool:
    return bool(IS_WINDOWS and hwnd and user32.IsWindow(hwnd))


def get_foreground_window() -> int:
    require_windows()
    return int(user32.GetForegroundWindow() or 0)


def get_root_window(hwnd: int) -> int:
    require_windows()
    if not hwnd:
        return 0
    return int(user32.GetAncestor(hwnd, GA_ROOT) or hwnd)


def get_window_pid(hwnd: int) -> int:
    require_windows()
    if not hwnd:
        return 0
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def get_window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(max(1, length + 1))
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value.strip()


def get_process_name(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        capacity = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(capacity.value)
        if not kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(capacity)
        ):
            return ""
        return ntpath.basename(buffer.value)
    finally:
        kernel32.CloseHandle(handle)


def _is_cloaked(hwnd: int) -> bool:
    if dwmapi is None:
        return False
    cloaked = wintypes.DWORD(0)
    result = dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
    )
    return result == 0 and bool(cloaked.value)


def enumerate_windows(exclude_pid: int | None = None) -> list[WindowInfo]:
    require_windows()
    windows: list[WindowInfo] = []

    @WNDENUMPROC
    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd) or _is_cloaked(hwnd):
            return True

        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value or (exclude_pid is not None and pid.value == exclude_pid):
            return True

        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        width = max(0, rect.right - rect.left)
        height = max(0, rect.bottom - rect.top)
        if width < 160 or height < 120:
            return True

        title = get_window_title(hwnd)
        process_name = get_process_name(pid.value)
        if not title and not process_name:
            return True

        windows.append(
            WindowInfo(
                hwnd=int(hwnd),
                pid=int(pid.value),
                process_name=process_name,
                title=title or "<Fenster ohne Titel>",
                width=width,
                height=height,
            )
        )
        return True

    ctypes.set_last_error(0)
    if not user32.EnumWindows(callback, 0):
        code = ctypes.get_last_error()
        if code:
            raise Win32Error("Fensterliste abrufen", code)

    windows.sort(key=lambda item: (item.process_name.casefold(), item.title.casefold()))
    return windows


def capture_window(hwnd: int) -> WindowSnapshot:
    require_windows()
    if not is_window(hwnd):
        raise Win32Error("Fenster erfassen", 1400)

    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise Win32Error("Fensterposition lesen")

    placement = WINDOWPLACEMENT()
    placement.length = ctypes.sizeof(WINDOWPLACEMENT)
    if not user32.GetWindowPlacement(hwnd, ctypes.byref(placement)):
        raise Win32Error("Fensterstatus lesen")

    return WindowSnapshot(
        hwnd=hwnd,
        style=_get_window_long_checked(hwnd, GWL_STYLE),
        exstyle=_get_window_long_checked(hwnd, GWL_EXSTYLE),
        left=rect.left,
        top=rect.top,
        right=rect.right,
        bottom=rect.bottom,
        placement=PlacementSnapshot(
            flags=placement.flags,
            show_cmd=placement.showCmd,
            min_x=placement.ptMinPosition.x,
            min_y=placement.ptMinPosition.y,
            max_x=placement.ptMaxPosition.x,
            max_y=placement.ptMaxPosition.y,
            normal_left=placement.rcNormalPosition.left,
            normal_top=placement.rcNormalPosition.top,
            normal_right=placement.rcNormalPosition.right,
            normal_bottom=placement.rcNormalPosition.bottom,
        ),
    )


def get_window_rect(hwnd: int) -> TargetRect:
    """Return the real outer window rectangle in physical screen pixels."""

    require_windows()
    if not is_window(hwnd):
        raise Win32Error("Fensterposition lesen", 1400)

    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise Win32Error("Fensterposition lesen")
    return TargetRect(
        x=rect.left,
        y=rect.top,
        width=max(0, rect.right - rect.left),
        height=max(0, rect.bottom - rect.top),
    )


def get_client_rect(hwnd: int) -> TargetRect:
    """Return the drawable client area in physical screen coordinates."""

    require_windows()
    if not is_window(hwnd):
        raise Win32Error("Spielflaeche lesen", 1400)

    rect = RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise Win32Error("Spielflaeche lesen")
    top_left = POINT(rect.left, rect.top)
    bottom_right = POINT(rect.right, rect.bottom)
    if not user32.ClientToScreen(hwnd, ctypes.byref(top_left)):
        raise Win32Error("Spielflaeche umrechnen")
    if not user32.ClientToScreen(hwnd, ctypes.byref(bottom_right)):
        raise Win32Error("Spielflaeche umrechnen")
    return TargetRect(
        x=top_left.x,
        y=top_left.y,
        width=max(0, bottom_right.x - top_left.x),
        height=max(0, bottom_right.y - top_left.y),
    )


def has_window_decorations(hwnd: int) -> bool:
    require_windows()
    style = _get_window_long_checked(hwnd, GWL_STYLE)
    exstyle = _get_window_long_checked(hwnd, GWL_EXSTYLE)
    return bool(
        style & WINDOW_DECORATION_MASK
        or exstyle & EXTENDED_DECORATION_MASK
    )


def measure_window(hwnd: int) -> WindowMeasurement:
    return WindowMeasurement(
        outer=get_window_rect(hwnd),
        client=get_client_rect(hwnd),
        has_decorations=has_window_decorations(hwnd),
    )


def rect_matches(actual: TargetRect, expected: TargetRect, tolerance: int = 0) -> bool:
    """Compare measured and requested bounds without hiding large resize failures."""

    if tolerance < 0:
        raise ValueError("Die Toleranz darf nicht negativ sein.")
    return all(
        abs(actual_value - expected_value) <= tolerance
        for actual_value, expected_value in (
            (actual.x, expected.x),
            (actual.y, expected.y),
            (actual.width, expected.width),
            (actual.height, expected.height),
        )
    )


def measurement_matches(
    measurement: WindowMeasurement,
    expected: TargetRect,
    *,
    require_borderless: bool,
) -> bool:
    if not rect_matches(measurement.outer, expected):
        return False
    if not require_borderless:
        return True
    return (
        not measurement.has_decorations
        and rect_matches(measurement.client, expected)
    )


def make_borderless_style(style: int) -> int:
    """Remove decorations and stale minimized/maximized state flags."""

    return (
        style & ~WINDOW_DECORATION_MASK & ~WINDOW_STATE_MASK
    ) | WS_POPUP | WS_VISIBLE


def make_framed_style(style: int) -> int:
    """Create a normal resizable frame with caption and window controls."""

    return (
        style & ~WS_POPUP & ~WINDOW_STATE_MASK
    ) | WINDOW_DECORATION_MASK | WS_VISIBLE


def apply_borderless(hwnd: int, target: TargetRect, always_on_top: bool = False) -> None:
    force_position_window(
        hwnd,
        target,
        remove_borders=True,
        always_on_top=always_on_top,
    )


def position_window(
    hwnd: int,
    target: TargetRect,
    *,
    always_on_top: bool = False,
    frame_changed: bool = False,
) -> None:
    require_windows()
    if not is_window(hwnd):
        raise Win32Error("Fenster positionieren", 1400)

    # Deliberately synchronous: the caller verifies GetWindowRect immediately
    # afterwards and must never clip the cursor for a resize that is only queued.
    flags = SWP_NOACTIVATE | SWP_NOOWNERZORDER | SWP_SHOWWINDOW
    insert_after = HWND_TOP
    if frame_changed:
        flags |= SWP_FRAMECHANGED
    if always_on_top:
        insert_after = HWND_TOPMOST
    else:
        flags |= SWP_NOZORDER

    if not user32.SetWindowPos(
        hwnd,
        insert_after,
        target.x,
        target.y,
        target.width,
        target.height,
        flags,
    ):
        raise Win32Error("Fenster positionieren")


def force_position_window(
    hwnd: int,
    target: TargetRect,
    *,
    remove_borders: bool,
    always_on_top: bool = False,
) -> None:
    """Normalize the window state and synchronously force the requested bounds.

    Some games keep the ``WS_MAXIMIZE`` flag when leaving fullscreen. A plain
    SetWindowPos request can then appear successful while Windows or the game
    immediately retains the full-monitor rectangle. Restoring first, clearing
    the stale state bits, applying a synchronous frame change and following up
    with MoveWindow gives those windows a proper normal-mode resize sequence.
    """

    require_windows()
    if not is_window(hwnd):
        raise Win32Error("Fenstergroesse erzwingen", 1400)

    user32.ShowWindow(hwnd, SW_RESTORE)

    style = _get_window_long_checked(hwnd, GWL_STYLE)
    new_style = (
        make_borderless_style(style)
        if remove_borders
        else style & ~WINDOW_STATE_MASK
    )
    if new_style != style:
        _set_window_long_checked(hwnd, GWL_STYLE, new_style)

    if remove_borders:
        exstyle = _get_window_long_checked(hwnd, GWL_EXSTYLE)
        new_exstyle = exstyle & ~EXTENDED_DECORATION_MASK
        if new_exstyle != exstyle:
            _set_window_long_checked(hwnd, GWL_EXSTYLE, new_exstyle)

    position_window(
        hwnd,
        target,
        always_on_top=always_on_top,
        frame_changed=True,
    )
    if not user32.MoveWindow(
        hwnd,
        target.x,
        target.y,
        target.width,
        target.height,
        True,
    ):
        raise Win32Error("Fenstergroesse erzwingen")


def show_window_frame(
    hwnd: int,
    snapshot: WindowSnapshot,
    target: TargetRect,
) -> None:
    """Show a normal title bar for a temporarily focused managed window."""

    require_windows()
    if not is_window(hwnd):
        raise Win32Error("Fensterleiste anzeigen", 1400)

    user32.ShowWindow(hwnd, SW_RESTORE)
    current_style = _get_window_long_checked(hwnd, GWL_STYLE)
    framed_style = make_framed_style(snapshot.style or current_style)
    current_exstyle = _get_window_long_checked(hwnd, GWL_EXSTYLE)
    framed_exstyle = snapshot.exstyle & ~WS_EX_TOPMOST
    if framed_style != current_style:
        _set_window_long_checked(hwnd, GWL_STYLE, framed_style)
    if framed_exstyle != current_exstyle:
        _set_window_long_checked(hwnd, GWL_EXSTYLE, framed_exstyle)
    position_window(
        hwnd,
        target,
        always_on_top=False,
        frame_changed=True,
    )


def set_window_topmost(hwnd: int, enabled: bool) -> None:
    """Change only the topmost state without activating or moving the window."""

    require_windows()
    if not is_window(hwnd):
        return
    insert_after = HWND_TOPMOST if enabled else HWND_NOTOPMOST
    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER
    if not user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags):
        raise Win32Error("Vordergrundstatus aendern")


def get_taskbar_windows() -> list[int]:
    """Return the primary and any secondary Explorer taskbar windows."""

    require_windows()
    handles: list[int] = []
    primary = int(user32.FindWindowW("Shell_TrayWnd", None) or 0)
    if primary:
        handles.append(primary)

    previous = 0
    while True:
        current = int(
            user32.FindWindowExW(
                None,
                previous or None,
                "Shell_SecondaryTrayWnd",
                None,
            )
            or 0
        )
        if not current:
            break
        handles.append(current)
        previous = current
    return handles


def hide_taskbars(
    snapshots: tuple[TaskbarSnapshot, ...] = (),
) -> tuple[TaskbarSnapshot, ...]:
    """Hide Explorer taskbars without changing the user's auto-hide setting."""

    require_windows()
    known = {item.hwnd: item for item in snapshots}
    for hwnd in get_taskbar_windows():
        if hwnd not in known:
            known[hwnd] = TaskbarSnapshot(
                hwnd=hwnd,
                was_visible=bool(user32.IsWindowVisible(hwnd)),
            )
        if user32.IsWindowVisible(hwnd):
            user32.ShowWindow(hwnd, SW_HIDE)
    return tuple(known.values())


def restore_taskbars(snapshots: tuple[TaskbarSnapshot, ...]) -> None:
    """Restore each taskbar to the visibility it had before FellSplit Pro hid it."""

    require_windows()
    for snapshot in snapshots:
        if not is_window(snapshot.hwnd):
            continue
        command = SW_SHOWNOACTIVATE if snapshot.was_visible else SW_HIDE
        user32.ShowWindow(snapshot.hwnd, command)


def show_all_taskbars() -> None:
    """Show every Explorer taskbar for the integrated emergency action."""

    require_windows()
    for hwnd in get_taskbar_windows():
        user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)


def restore_window(snapshot: WindowSnapshot) -> None:
    require_windows()
    hwnd = snapshot.hwnd
    if not is_window(hwnd):
        return

    _set_window_long_checked(hwnd, GWL_STYLE, snapshot.style)
    _set_window_long_checked(hwnd, GWL_EXSTYLE, snapshot.exstyle)

    was_topmost = bool(snapshot.exstyle & WS_EX_TOPMOST)
    insert_after = HWND_TOPMOST if was_topmost else HWND_NOTOPMOST
    width = max(1, snapshot.right - snapshot.left)
    height = max(1, snapshot.bottom - snapshot.top)
    flags = SWP_NOACTIVATE | SWP_NOOWNERZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW
    if not user32.SetWindowPos(
        hwnd,
        insert_after,
        snapshot.left,
        snapshot.top,
        width,
        height,
        flags,
    ):
        raise Win32Error("Fensterrahmen wiederherstellen")

    source = snapshot.placement
    placement = WINDOWPLACEMENT()
    placement.length = ctypes.sizeof(WINDOWPLACEMENT)
    placement.flags = source.flags
    placement.showCmd = source.show_cmd
    placement.ptMinPosition = POINT(source.min_x, source.min_y)
    placement.ptMaxPosition = POINT(source.max_x, source.max_y)
    placement.rcNormalPosition = RECT(
        source.normal_left,
        source.normal_top,
        source.normal_right,
        source.normal_bottom,
    )
    if not user32.SetWindowPlacement(hwnd, ctypes.byref(placement)):
        raise Win32Error("Urspruenglichen Fensterstatus wiederherstellen")


def clip_cursor(target: TargetRect) -> None:
    require_windows()
    rect = RECT(target.x, target.y, target.right, target.bottom)
    if not user32.ClipCursor(ctypes.byref(rect)):
        raise Win32Error("Mauszeiger sperren")


def release_cursor() -> None:
    require_windows()
    if not user32.ClipCursor(None):
        raise Win32Error("Mauszeiger freigeben")


def get_virtual_screen_rect() -> TargetRect:
    require_windows()
    return TargetRect(
        x=user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        y=user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        width=user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        height=user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
    )


def get_primary_monitor_rect() -> TargetRect:
    require_windows()
    monitor = user32.MonitorFromPoint(POINT(0, 0), MONITOR_DEFAULTTOPRIMARY)
    return _monitor_rect(monitor)


def enumerate_monitors() -> list[MonitorInfo]:
    """Return all active Windows monitors with stable display-device names."""

    require_windows()
    monitors: list[MonitorInfo] = []
    callback_error: list[int] = []

    @MONITORENUMPROC
    def callback(
        monitor: int,
        _hdc: int,
        _rect: ctypes.POINTER(RECT),
        _lparam: int,
    ) -> bool:
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            callback_error.append(ctypes.get_last_error())
            return False
        rect = TargetRect(
            x=info.rcMonitor.left,
            y=info.rcMonitor.top,
            width=info.rcMonitor.right - info.rcMonitor.left,
            height=info.rcMonitor.bottom - info.rcMonitor.top,
        )
        identifier = str(info.szDevice).strip() or f"HMONITOR-{int(monitor):X}"
        monitors.append(
            MonitorInfo(
                identifier=identifier,
                rect=rect,
                is_primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
            )
        )
        return True

    ctypes.set_last_error(0)
    if not user32.EnumDisplayMonitors(None, None, callback, 0):
        code = callback_error[0] if callback_error else ctypes.get_last_error()
        raise Win32Error("Monitorliste abrufen", code or None)
    if not monitors:
        raise Win32Error("Monitorliste abrufen")
    monitors.sort(
        key=lambda item: (
            not item.is_primary,
            item.rect.x,
            item.rect.y,
            item.identifier.casefold(),
        )
    )
    return monitors


def get_monitor_by_id(identifier: str) -> MonitorInfo:
    """Resolve a configured monitor, falling back to the current primary one."""

    monitors = enumerate_monitors()
    query = identifier.strip().casefold()
    if query and query != "primary":
        selected = next(
            (item for item in monitors if item.identifier.casefold() == query),
            None,
        )
        if selected is not None:
            return selected
    return next((item for item in monitors if item.is_primary), monitors[0])


def get_monitor_rect_for_window(hwnd: int) -> TargetRect:
    require_windows()
    monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    return _monitor_rect(monitor)


def _monitor_rect(monitor: int) -> TargetRect:
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        raise Win32Error("Monitorinformationen lesen")
    return TargetRect(
        x=info.rcMonitor.left,
        y=info.rcMonitor.top,
        width=info.rcMonitor.right - info.rcMonitor.left,
        height=info.rcMonitor.bottom - info.rcMonitor.top,
    )


def _get_window_long_checked(hwnd: int, index: int) -> int:
    ctypes.set_last_error(0)
    result = _get_window_long(hwnd, index)
    code = ctypes.get_last_error()
    if result == 0 and code:
        raise Win32Error("Fensterstil lesen", code)
    return int(result) & 0xFFFFFFFF


def _set_window_long_checked(hwnd: int, index: int, value: int) -> int:
    ctypes.set_last_error(0)
    previous = _set_window_long(hwnd, index, LONG_PTR(value))
    code = ctypes.get_last_error()
    if previous == 0 and code:
        raise Win32Error("Fensterstil aendern", code)
    return int(previous) & 0xFFFFFFFF
