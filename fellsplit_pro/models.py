from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


LAYOUT_AUTOMATIC = "automatic"
LAYOUT_EQUAL_HALVES = "equal_halves"
LAYOUT_GAME_16_9 = "game_16_9"
LAYOUT_CUSTOM = "custom"
LAYOUT_MODES = frozenset(
    {
        LAYOUT_AUTOMATIC,
        LAYOUT_EQUAL_HALVES,
        LAYOUT_GAME_16_9,
        LAYOUT_CUSTOM,
    }
)

GAME_SIDE_LEFT = "left"
GAME_SIDE_RIGHT = "right"
GAME_SIDES = frozenset({GAME_SIDE_LEFT, GAME_SIDE_RIGHT})


@dataclass(slots=True, frozen=True)
class TargetRect:
    """A rectangle in physical virtual-screen coordinates."""

    x: int = 0
    y: int = 0
    width: int = 2560
    height: int = 1440

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def validate(self) -> None:
        if self.width < 320 or self.height < 240:
            raise ValueError("Die Zielgroesse muss mindestens 320 x 240 Pixel betragen.")
        if self.width > 32768 or self.height > 32768:
            raise ValueError("Die Zielgroesse ist unplausibel gross.")
        if not (-32768 <= self.x <= 32767 and -32768 <= self.y <= 32767):
            raise ValueError("X/Y liegen ausserhalb des unterstuetzten Bildschirmbereichs.")


@dataclass(slots=True, frozen=True)
class MonitorInfo:
    """A physical monitor exposed by Windows in virtual-screen coordinates."""

    identifier: str
    rect: TargetRect
    is_primary: bool = False

    @property
    def display_name(self) -> str:
        role = "Hauptmonitor" if self.is_primary else "Monitor"
        device = self.identifier.removeprefix("\\\\.\\")
        return (
            f"{role} - {self.rect.width} x {self.rect.height} bei "
            f"({self.rect.x}, {self.rect.y}) [{device}]"
        )


@dataclass(slots=True)
class AppConfig:
    schema_version: int = 6
    process_name: str = "Wow.exe"
    title_contains: str = ""
    selected_hwnd: int = 0
    auto_detect_games: bool = True
    auto_detect_delay_seconds: float = 1.5
    auto_excluded_processes: str = ""
    layout_mode: str = LAYOUT_AUTOMATIC
    monitor_id: str = "primary"
    game_side: str = GAME_SIDE_LEFT
    target_rect: TargetRect = TargetRect()
    secondary_enabled: bool = False
    secondary_process_name: str = "obs64.exe"
    secondary_title_contains: str = ""
    secondary_selected_hwnd: int = 0
    secondary_target_rect: TargetRect = TargetRect(2560, 0, 2560, 1440)
    secondary_remove_borders: bool = True
    secondary_show_frame_when_focused: bool = True
    remove_borders: bool = True
    lock_cursor: bool = True
    restore_window: bool = True
    keep_position: bool = True
    # Focus-aware clipping is the safe default: Alt+Tab immediately frees the mouse.
    foreground_only: bool = True
    hide_taskbar_while_game_focused: bool = True
    always_on_top: bool = False
    hotkey_enabled: bool = True
    hotkey_ctrl: bool = True
    hotkey_alt: bool = True
    hotkey_shift: bool = False
    hotkey_key: str = "F10"
    tray_enabled: bool = True
    close_to_tray: bool = True
    minimize_to_tray: bool = True
    start_with_windows: bool = False
    start_minimized: bool = True
    activate_on_launch: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["target_rect"] = asdict(self.target_rect)
        data["secondary_target_rect"] = asdict(self.secondary_target_rect)
        # HWND values are only valid for the current Windows session.
        data["selected_hwnd"] = 0
        data["secondary_selected_hwnd"] = 0
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        defaults = cls()
        schema_version = _safe_int(data.get("schema_version"), 1)
        rect_data = data.get("target_rect", {})
        if not isinstance(rect_data, dict):
            rect_data = {}

        rect = TargetRect(
            x=_safe_int(rect_data.get("x"), defaults.target_rect.x),
            y=_safe_int(rect_data.get("y"), defaults.target_rect.y),
            width=_safe_int(rect_data.get("width"), defaults.target_rect.width),
            height=_safe_int(rect_data.get("height"), defaults.target_rect.height),
        )
        try:
            rect.validate()
        except ValueError:
            rect = defaults.target_rect

        secondary_rect_data = data.get("secondary_target_rect", {})
        if not isinstance(secondary_rect_data, dict):
            secondary_rect_data = {}
        secondary_rect = TargetRect(
            x=_safe_int(
                secondary_rect_data.get("x"),
                defaults.secondary_target_rect.x,
            ),
            y=_safe_int(
                secondary_rect_data.get("y"),
                defaults.secondary_target_rect.y,
            ),
            width=_safe_int(
                secondary_rect_data.get("width"),
                defaults.secondary_target_rect.width,
            ),
            height=_safe_int(
                secondary_rect_data.get("height"),
                defaults.secondary_target_rect.height,
            ),
        )
        try:
            secondary_rect.validate()
        except ValueError:
            secondary_rect = defaults.secondary_target_rect

        if schema_version < 6:
            # The shipped 1.2.2 defaults map exactly to automatic dual-zone
            # mode. Preserve genuinely customized legacy coordinates instead.
            legacy_uses_factory_geometry = (
                rect == defaults.target_rect
                and secondary_rect == defaults.secondary_target_rect
            )
            layout_mode = (
                LAYOUT_AUTOMATIC
                if legacy_uses_factory_geometry
                else LAYOUT_CUSTOM
            )
        else:
            layout_mode = _safe_choice(
                data.get("layout_mode"),
                defaults.layout_mode,
                LAYOUT_MODES,
            )

        monitor_id = _safe_str(data.get("monitor_id"), defaults.monitor_id).strip()
        if not monitor_id:
            monitor_id = defaults.monitor_id

        game_side = _safe_choice(
            data.get("game_side"),
            defaults.game_side,
            GAME_SIDES,
        )

        return cls(
            schema_version=defaults.schema_version,
            process_name=_safe_str(data.get("process_name"), defaults.process_name),
            title_contains=_safe_str(data.get("title_contains"), defaults.title_contains),
            selected_hwnd=0,
            auto_detect_games=_safe_bool(
                data.get("auto_detect_games"), defaults.auto_detect_games
            ),
            auto_detect_delay_seconds=_safe_float(
                data.get("auto_detect_delay_seconds"),
                defaults.auto_detect_delay_seconds,
                minimum=0.5,
                maximum=10.0,
            ),
            auto_excluded_processes=_safe_str(
                data.get("auto_excluded_processes"), defaults.auto_excluded_processes
            ),
            layout_mode=layout_mode,
            monitor_id=monitor_id,
            game_side=game_side,
            target_rect=rect,
            secondary_enabled=_safe_bool(
                data.get("secondary_enabled"), defaults.secondary_enabled
            ),
            secondary_process_name=_safe_str(
                data.get("secondary_process_name"),
                defaults.secondary_process_name,
            ),
            secondary_title_contains=_safe_str(
                data.get("secondary_title_contains"),
                defaults.secondary_title_contains,
            ),
            secondary_selected_hwnd=0,
            secondary_target_rect=secondary_rect,
            secondary_remove_borders=_safe_bool(
                data.get("secondary_remove_borders"),
                defaults.secondary_remove_borders,
            ),
            secondary_show_frame_when_focused=_safe_bool(
                data.get("secondary_show_frame_when_focused"),
                defaults.secondary_show_frame_when_focused,
            ),
            remove_borders=_safe_bool(data.get("remove_borders"), defaults.remove_borders),
            lock_cursor=_safe_bool(data.get("lock_cursor"), defaults.lock_cursor),
            restore_window=_safe_bool(data.get("restore_window"), defaults.restore_window),
            keep_position=_safe_bool(data.get("keep_position"), defaults.keep_position),
            # Version 1.0 kept the cursor clipped after Alt+Tab. Migrate every
            # legacy configuration to the focus-aware behaviour once.
            foreground_only=(
                True
                if schema_version < 2
                else _safe_bool(data.get("foreground_only"), defaults.foreground_only)
            ),
            hide_taskbar_while_game_focused=_safe_bool(
                data.get("hide_taskbar_while_game_focused"),
                defaults.hide_taskbar_while_game_focused,
            ),
            always_on_top=_safe_bool(data.get("always_on_top"), defaults.always_on_top),
            hotkey_enabled=_safe_bool(data.get("hotkey_enabled"), defaults.hotkey_enabled),
            hotkey_ctrl=_safe_bool(data.get("hotkey_ctrl"), defaults.hotkey_ctrl),
            hotkey_alt=_safe_bool(data.get("hotkey_alt"), defaults.hotkey_alt),
            hotkey_shift=_safe_bool(data.get("hotkey_shift"), defaults.hotkey_shift),
            hotkey_key=_safe_str(data.get("hotkey_key"), defaults.hotkey_key).upper(),
            tray_enabled=_safe_bool(data.get("tray_enabled"), defaults.tray_enabled),
            close_to_tray=_safe_bool(data.get("close_to_tray"), defaults.close_to_tray),
            minimize_to_tray=_safe_bool(
                data.get("minimize_to_tray"), defaults.minimize_to_tray
            ),
            start_with_windows=_safe_bool(
                data.get("start_with_windows"), defaults.start_with_windows
            ),
            start_minimized=_safe_bool(
                data.get("start_minimized"), defaults.start_minimized
            ),
            activate_on_launch=_safe_bool(
                data.get("activate_on_launch"), defaults.activate_on_launch
            ),
        )


@dataclass(slots=True, frozen=True)
class WindowInfo:
    hwnd: int
    pid: int
    process_name: str
    title: str
    width: int
    height: int

    @property
    def display_name(self) -> str:
        title = self.title if len(self.title) <= 72 else f"{self.title[:69]}..."
        process = self.process_name or f"PID {self.pid}"
        return f"[{process}] {title}"


def normalize_process_name(value: str) -> str:
    """Normalize common user input such as ``wow\\.exe`` to ``wow.exe``."""

    normalized = value.strip().strip('"').replace("\\.", ".")
    normalized = normalized.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    return normalized.casefold()


def window_matches(info: WindowInfo, process_name: str, title_contains: str) -> bool:
    process_query = normalize_process_name(process_name)
    title_query = title_contains.strip().casefold()

    if not process_query and not title_query:
        return False
    if process_query and normalize_process_name(info.process_name) != process_query:
        return False
    if title_query and title_query not in info.title.casefold():
        return False
    return True


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_str(value: Any, default: str) -> str:
    return value if isinstance(value, str) else default


def _safe_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _safe_choice(value: Any, default: str, choices: frozenset[str]) -> str:
    if not isinstance(value, str):
        return default
    normalized = value.strip().casefold()
    return normalized if normalized in choices else default


def _safe_float(
    value: Any,
    default: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return parsed if minimum <= parsed <= maximum else default
