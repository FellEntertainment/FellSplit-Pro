from __future__ import annotations

import os
import time
from dataclasses import dataclass, replace
from enum import Enum

from .layout import calculate_layout
from .models import (
    LAYOUT_CUSTOM,
    AppConfig,
    TargetRect,
    WindowInfo,
    window_matches,
)
from . import win32_api as win32


AUTO_DETECT_EXCLUSIONS = frozenset(
    {
        "applicationframehost.exe",
        "battle.net.exe",
        "blender.exe",
        "brave.exe",
        "chrome.exe",
        "cmd.exe",
        "code.exe",
        "devenv.exe",
        "discord.exe",
        "dwm.exe",
        "eadesktop.exe",
        "epicgameslauncher.exe",
        "excel.exe",
        "explorer.exe",
        "firefox.exe",
        "galaxyclient.exe",
        "idea64.exe",
        "msedge.exe",
        "notepad.exe",
        "nvidia app.exe",
        "nvidia overlay.exe",
        "obs32.exe",
        "obs64.exe",
        "opera.exe",
        "outlook.exe",
        "photoshop.exe",
        "powershell.exe",
        "pwsh.exe",
        "python.exe",
        "pythonw.exe",
        "searchhost.exe",
        "shellexperiencehost.exe",
        "sihost.exe",
        "splitlock.exe",
        "fellsplitpro.exe",
        "startmenuexperiencehost.exe",
        "steam.exe",
        "steamwebhelper.exe",
        "spotify.exe",
        "streamlabs obs.exe",
        "systemsettings.exe",
        "taskhostw.exe",
        "taskmgr.exe",
        "textinputhost.exe",
        "teams.exe",
        "ms-teams.exe",
        "upc.exe",
        "riotclientux.exe",
        "riotclientuxrender.exe",
        "vivaldi.exe",
        "windowsterminal.exe",
        "winword.exe",
        "xboxpcapp.exe",
    }
)


class RunState(str, Enum):
    OFF = "off"
    WAITING = "waiting"
    POSITIONING = "positioning"
    ACTIVE = "active"
    ERROR = "error"


@dataclass(slots=True, frozen=True)
class ControllerStatus:
    state: RunState
    message: str
    window: WindowInfo | None = None


class GameWindowController:
    """Owns reversible Win32 changes for a game and an optional right window."""

    SCAN_INTERVAL = 0.75
    ENFORCE_INTERVAL = 0.35
    FORCE_RESIZE_INTERVAL = 0.75
    ERROR_RETRY_INTERVAL = 1.5

    def __init__(self) -> None:
        self._desired_active = False
        self._config = AppConfig()
        self._current: WindowInfo | None = None
        self._snapshot: win32.WindowSnapshot | None = None
        self._secondary_current: WindowInfo | None = None
        self._secondary_snapshot: win32.WindowSnapshot | None = None
        self._secondary_frame_visible = False
        self._taskbar_snapshots: tuple[win32.TaskbarSnapshot, ...] = ()
        self._cursor_clipped = False
        self._last_scan = 0.0
        self._last_enforce = 0.0
        self._last_force_resize = 0.0
        self._secondary_last_scan = 0.0
        self._secondary_last_force_resize = 0.0
        self._retry_after = 0.0
        self._auto_candidate_hwnd = 0
        self._auto_candidate_since = 0.0
        self._auto_candidate_label = ""
        self._next_attach_is_auto = False
        self._attached_automatically = False
        self._topmost_applied = False
        self._last_status = ControllerStatus(
            RunState.OFF,
            "FellSplit Pro ist ausgeschaltet.",
        )

    @property
    def desired_active(self) -> bool:
        return self._desired_active

    @property
    def status(self) -> ControllerStatus:
        return self._last_status

    @property
    def current_window(self) -> WindowInfo | None:
        return self._current

    @property
    def secondary_window(self) -> WindowInfo | None:
        return self._secondary_current

    def activate(self, config: AppConfig) -> ControllerStatus:
        effective_config = self._resolve_layout(config)
        effective_config.target_rect.validate()
        if effective_config.secondary_enabled:
            effective_config.secondary_target_rect.validate()
            if (
                not effective_config.secondary_process_name.strip()
                and not effective_config.secondary_title_contains.strip()
                and not effective_config.secondary_selected_hwnd
            ):
                raise ValueError("Bitte ein zweites Fenster fuer die zweite Zone angeben.")
            if (
                effective_config.selected_hwnd
                and effective_config.selected_hwnd
                == effective_config.secondary_selected_hwnd
            ):
                raise ValueError(
                    "Spiel und zweite Zone duerfen nicht dasselbe Fenster sein."
                )
            if self._rects_overlap(
                effective_config.target_rect,
                effective_config.secondary_target_rect,
            ):
                raise ValueError("Spiel- und zweite Zielzone duerfen sich nicht ueberlappen.")
        if (
            not effective_config.auto_detect_games
            and not effective_config.process_name.strip()
            and not effective_config.title_contains.strip()
            and not effective_config.selected_hwnd
        ):
            raise ValueError(
                "Bitte ein Zielfenster angeben oder die automatische Spiel-Erkennung aktivieren."
            )

        # Keep a stable copy while the controller is active.
        self._config = replace(
            effective_config,
            target_rect=replace(effective_config.target_rect),
            secondary_target_rect=replace(effective_config.secondary_target_rect),
        )
        self._desired_active = True
        self._last_scan = 0.0
        self._last_force_resize = 0.0
        self._secondary_last_scan = 0.0
        self._secondary_last_force_resize = 0.0
        self._retry_after = 0.0
        self._reset_auto_candidate()
        return self.tick(force=True)

    def deactivate(self) -> ControllerStatus:
        self._desired_active = False
        errors: list[str] = []

        try:
            self._release_cursor_if_needed(force=True)
        except Exception as exc:  # Cursor release must not prevent window restoration.
            errors.append(str(exc))

        try:
            self._restore_taskbars_if_needed()
        except Exception as exc:
            errors.append(f"Taskleiste: {exc}")

        if self._snapshot is not None and self._config.restore_window:
            try:
                win32.restore_window(self._snapshot)
            except Exception as exc:
                errors.append(str(exc))

        if self._secondary_snapshot is not None and self._config.restore_window:
            try:
                win32.restore_window(self._secondary_snapshot)
            except Exception as exc:
                errors.append(f"Rechtes Fenster: {exc}")

        self._current = None
        self._snapshot = None
        self._secondary_current = None
        self._secondary_snapshot = None
        self._secondary_frame_visible = False
        self._taskbar_snapshots = ()
        self._cursor_clipped = False
        self._attached_automatically = False
        self._topmost_applied = False
        self._last_force_resize = 0.0
        self._secondary_last_scan = 0.0
        self._secondary_last_force_resize = 0.0
        self._reset_auto_candidate()

        if errors:
            self._last_status = ControllerStatus(
                RunState.ERROR,
                "Ausgeschaltet, aber die Wiederherstellung war nicht vollstaendig: "
                + " | ".join(errors),
            )
        else:
            self._last_status = ControllerStatus(
                RunState.OFF,
                "Ausgeschaltet: Maus frei und Fensterzustand wiederhergestellt.",
            )
        return self._last_status

    def reconfigure(self, config: AppConfig) -> ControllerStatus:
        was_active = self._desired_active
        if was_active:
            self.deactivate()
            return self.activate(config)
        self._config = replace(
            config,
            target_rect=replace(config.target_rect),
            secondary_target_rect=replace(config.secondary_target_rect),
        )
        return self._last_status

    @staticmethod
    def _resolve_layout(config: AppConfig) -> AppConfig:
        """Turn a monitor-aware profile into physical pixel rectangles."""

        if config.layout_mode == LAYOUT_CUSTOM or not win32.IS_WINDOWS:
            return replace(
                config,
                target_rect=replace(config.target_rect),
                secondary_target_rect=replace(config.secondary_target_rect),
            )
        monitor = win32.get_monitor_by_id(config.monitor_id)
        layout = calculate_layout(
            monitor.rect,
            config.layout_mode,
            config.game_side,
        )
        return replace(
            config,
            target_rect=layout.game,
            secondary_target_rect=layout.secondary,
        )

    def tick(self, force: bool = False) -> ControllerStatus:
        if not self._desired_active:
            return self._last_status

        now = time.monotonic()
        if not force and now < self._retry_after:
            return self._last_status

        try:
            if self._current is not None and not win32.is_window(self._current.hwnd):
                self._current = None
                self._snapshot = None
                self._attached_automatically = False
                self._topmost_applied = False
                self._last_force_resize = 0.0
                self._release_cursor_if_needed(force=True)
                self._restore_taskbars_if_needed()

            if (
                self._secondary_current is not None
                and not win32.is_window(self._secondary_current.hwnd)
            ):
                self._secondary_current = None
                self._secondary_snapshot = None
                self._secondary_frame_visible = False
                self._secondary_last_force_resize = 0.0

            secondary_status = self._manage_secondary(now, force)

            if self._current is None:
                if force or now - self._last_scan >= self.SCAN_INTERVAL:
                    self._last_scan = now
                    target = self._find_target()
                    if target is not None:
                        self._attach(target)

                if self._current is None:
                    self._restore_taskbars_if_needed()
                    self._release_cursor_if_needed(
                        force=self._last_status.state is not RunState.WAITING
                    )
                    self._last_status = ControllerStatus(
                        RunState.WAITING,
                        self._append_secondary_status(
                            self._waiting_message(),
                            secondary_status,
                        ),
                    )
                    return self._last_status

            assert self._current is not None
            foreground = win32.get_foreground_window()
            in_foreground = win32.get_window_pid(foreground) == self._current.pid
            self._sync_taskbar_visibility(in_foreground)
            self._sync_topmost(in_foreground)
            manage_geometry = in_foreground or not self._config.foreground_only
            if manage_geometry:
                if force or (
                    self._config.keep_position
                    and now - self._last_enforce >= self.ENFORCE_INTERVAL
                ):
                    win32.position_window(
                        self._current.hwnd,
                        self._config.target_rect,
                        always_on_top=self._config.always_on_top and in_foreground,
                    )
                    self._last_enforce = now

                measurement = win32.measure_window(self._current.hwnd)
                if not win32.measurement_matches(
                    measurement,
                    self._config.target_rect,
                    require_borderless=self._config.remove_borders,
                ):
                    # Never trap the pointer in only half of a window that still
                    # covers the full monitor. First make an escape possible, then
                    # attempt the stronger normal-state resize sequence.
                    self._release_cursor_if_needed(force=True)
                    may_force = force or (
                        self._config.keep_position
                        and now - self._last_force_resize
                        >= self.FORCE_RESIZE_INTERVAL
                    )
                    if may_force:
                        win32.force_position_window(
                            self._current.hwnd,
                            self._config.target_rect,
                            remove_borders=self._config.remove_borders,
                            always_on_top=(
                                self._config.always_on_top and in_foreground
                            ),
                        )
                        self._last_force_resize = now
                        self._last_enforce = now
                        measurement = win32.measure_window(self._current.hwnd)

                    if not win32.measurement_matches(
                        measurement,
                        self._config.target_rect,
                        require_borderless=self._config.remove_borders,
                    ):
                        self._last_status = ControllerStatus(
                            RunState.POSITIONING,
                            self._append_secondary_status(
                                self._positioning_message(measurement),
                                secondary_status,
                            ),
                            self._current,
                        )
                        return self._last_status

            self._update_cursor_lock(in_foreground)
            source = "automatisch erkannt; " if self._attached_automatically else ""
            focus_mode = (
                "Alt+Tab-sicher"
                if self._config.foreground_only
                else "Maus dauerhaft gesperrt"
            )
            self._last_status = ControllerStatus(
                RunState.ACTIVE,
                self._append_secondary_status(
                    f"Aktiv fuer {self._current.process_name or 'das Spiel'} "
                    f"({source}{focus_mode}) - {self._config.target_rect.width} x "
                    f"{self._config.target_rect.height} bei "
                    f"({self._config.target_rect.x}, {self._config.target_rect.y}).",
                    secondary_status,
                ),
                self._current,
            )
            return self._last_status
        except Exception as exc:
            try:
                self._release_cursor_if_needed(force=True)
            except Exception:
                pass
            try:
                self._restore_taskbars_if_needed()
            except Exception:
                pass
            self._retry_after = now + self.ERROR_RETRY_INTERVAL
            self._last_status = ControllerStatus(
                RunState.ERROR,
                self._friendly_error(exc),
                self._current,
            )
            return self._last_status

    def emergency_release(self) -> None:
        """Best-effort cleanup suitable for atexit and exception paths."""

        try:
            self.deactivate()
        except Exception:
            try:
                win32.release_cursor()
            except Exception:
                pass

    def _find_target(self) -> WindowInfo | None:
        windows = win32.enumerate_windows(exclude_pid=os.getpid())
        self._next_attach_is_auto = False

        if self._config.selected_hwnd:
            selected = next(
                (item for item in windows if item.hwnd == self._config.selected_hwnd),
                None,
            )
            if selected is not None:
                self._reset_auto_candidate()
                return selected

        candidates = [
            item
            for item in windows
            if window_matches(
                item,
                self._config.process_name,
                self._config.title_contains,
            )
        ]
        if candidates:
            self._reset_auto_candidate()
            # Games usually own the largest matching top-level window.
            return max(candidates, key=lambda item: item.width * item.height)

        if not self._config.auto_detect_games:
            self._reset_auto_candidate()
            return None
        return self._find_automatic_candidate(windows)

    def _attach(self, target: WindowInfo) -> None:
        snapshot = win32.capture_window(target.hwnd)
        self._snapshot = snapshot
        self._current = target
        self._attached_automatically = self._next_attach_is_auto
        try:
            if self._config.remove_borders:
                win32.apply_borderless(
                    target.hwnd,
                    self._config.target_rect,
                    always_on_top=self._config.always_on_top,
                )
            else:
                win32.position_window(
                    target.hwnd,
                    self._config.target_rect,
                    always_on_top=self._config.always_on_top,
                    frame_changed=True,
                )
            if not self._config.always_on_top and snapshot.exstyle & win32.WS_EX_TOPMOST:
                win32.set_window_topmost(target.hwnd, False)
            self._last_enforce = time.monotonic()
            self._last_force_resize = 0.0
            self._topmost_applied = self._config.always_on_top
        except Exception:
            # Undo partial style changes before allowing a retry.
            try:
                win32.restore_window(snapshot)
            finally:
                self._current = None
                self._snapshot = None
                self._attached_automatically = False
                self._topmost_applied = False
                self._last_force_resize = 0.0
            raise

    def _manage_secondary(self, now: float, force: bool) -> str:
        if not self._config.secondary_enabled:
            return ""

        if self._secondary_current is None and (
            force or now - self._secondary_last_scan >= self.SCAN_INTERVAL
        ):
            self._secondary_last_scan = now
            target = self._find_secondary_target()
            if target is not None:
                self._attach_secondary(target)

        if self._secondary_current is None:
            wanted = (
                self._config.secondary_process_name
                or self._config.secondary_title_contains
                or "das ausgewaehlte Fenster"
            )
            return f"{self._secondary_zone_label()} wartet auf {wanted}."

        assert self._secondary_snapshot is not None
        secondary_foreground = win32.get_foreground_window()
        secondary_has_focus = (
            win32.get_window_pid(secondary_foreground)
            == self._secondary_current.pid
        )
        show_focused_frame = (
            self._config.secondary_remove_borders
            and self._config.secondary_show_frame_when_focused
            and secondary_has_focus
        )
        measurement = win32.measure_window(self._secondary_current.hwnd)
        if show_focused_frame:
            frame_ready = (
                win32.rect_matches(
                    measurement.outer,
                    self._config.secondary_target_rect,
                )
                and measurement.has_decorations
            )
            if not frame_ready or not self._secondary_frame_visible:
                win32.show_window_frame(
                    self._secondary_current.hwnd,
                    self._secondary_snapshot,
                    self._config.secondary_target_rect,
                )
                self._secondary_frame_visible = True
                self._secondary_last_force_resize = now
                measurement = win32.measure_window(
                    self._secondary_current.hwnd
                )
                frame_ready = (
                    win32.rect_matches(
                        measurement.outer,
                        self._config.secondary_target_rect,
                    )
                    and measurement.has_decorations
                )
            label = (
                self._secondary_current.process_name
                or self._secondary_current.title
            )
            if frame_ready:
                return (
                    f"{self._secondary_zone_label()}: {label} ist aktiv; "
                    "Fensterleiste mit X ist "
                    "eingeblendet."
                )
            return (
                f"{self._secondary_zone_label()}: Fensterleiste fuer {label} "
                "wird noch eingeblendet."
            )

        matches = win32.measurement_matches(
            measurement,
            self._config.secondary_target_rect,
            require_borderless=self._config.secondary_remove_borders,
        )
        may_force = self._secondary_frame_visible or force or (
            self._config.keep_position
            and now - self._secondary_last_force_resize
            >= self.FORCE_RESIZE_INTERVAL
        )
        if (not matches or self._secondary_frame_visible) and may_force:
            win32.force_position_window(
                self._secondary_current.hwnd,
                self._config.secondary_target_rect,
                remove_borders=self._config.secondary_remove_borders,
                always_on_top=False,
            )
            self._secondary_frame_visible = False
            self._secondary_last_force_resize = now
            measurement = win32.measure_window(self._secondary_current.hwnd)
            matches = win32.measurement_matches(
                measurement,
                self._config.secondary_target_rect,
                require_borderless=self._config.secondary_remove_borders,
            )

        label = self._secondary_current.process_name or self._secondary_current.title
        if matches:
            mode = "rahmenlos" if self._config.secondary_remove_borders else "positioniert"
            target = self._config.secondary_target_rect
            return (
                f"{self._secondary_zone_label()}: {label} {mode} in "
                f"{target.width} x {target.height}."
            )
        decoration = (
            " Rahmen/Titelleiste sind noch aktiv."
            if measurement.has_decorations
            else ""
        )
        return (
            f"{self._secondary_zone_label()} wird {label} noch angepasst: Aussen "
            f"{measurement.outer.width} x {measurement.outer.height}, Client "
            f"{measurement.client.width} x {measurement.client.height}."
            f"{decoration}"
        )

    def _find_secondary_target(self) -> WindowInfo | None:
        windows = win32.enumerate_windows(exclude_pid=os.getpid())
        primary_hwnd = self._current.hwnd if self._current is not None else 0

        if self._config.secondary_selected_hwnd:
            selected = next(
                (
                    item
                    for item in windows
                    if item.hwnd == self._config.secondary_selected_hwnd
                    and item.hwnd != primary_hwnd
                ),
                None,
            )
            if selected is not None:
                return selected

        candidates = [
            item
            for item in windows
            if item.hwnd != primary_hwnd
            and window_matches(
                item,
                self._config.secondary_process_name,
                self._config.secondary_title_contains,
            )
        ]
        return max(candidates, key=lambda item: item.width * item.height, default=None)

    def _attach_secondary(self, target: WindowInfo) -> None:
        snapshot = win32.capture_window(target.hwnd)
        self._secondary_snapshot = snapshot
        self._secondary_current = target
        self._secondary_frame_visible = False
        try:
            win32.force_position_window(
                target.hwnd,
                self._config.secondary_target_rect,
                remove_borders=self._config.secondary_remove_borders,
                always_on_top=False,
            )
            if snapshot.exstyle & win32.WS_EX_TOPMOST:
                win32.set_window_topmost(target.hwnd, False)
            self._secondary_last_force_resize = 0.0
        except Exception:
            try:
                win32.restore_window(snapshot)
            finally:
                self._secondary_current = None
                self._secondary_snapshot = None
                self._secondary_frame_visible = False
                self._secondary_last_force_resize = 0.0
            raise

    def _update_cursor_lock(self, in_foreground: bool) -> None:
        if not self._config.lock_cursor or self._current is None:
            self._release_cursor_if_needed()
            return

        should_lock = in_foreground if self._config.foreground_only else True

        if should_lock:
            win32.clip_cursor(self._config.target_rect)
            self._cursor_clipped = True
        else:
            self._release_cursor_if_needed()

    def _release_cursor_if_needed(self, *, force: bool = False) -> None:
        if self._cursor_clipped or force:
            win32.release_cursor()
            self._cursor_clipped = False

    def _find_automatic_candidate(self, windows: list[WindowInfo]) -> WindowInfo | None:
        foreground = win32.get_root_window(win32.get_foreground_window())
        candidate = next((item for item in windows if item.hwnd == foreground), None)
        if candidate is None or not self._is_likely_game(candidate):
            self._reset_auto_candidate()
            return None

        now = time.monotonic()
        if self._auto_candidate_hwnd != candidate.hwnd:
            self._auto_candidate_hwnd = candidate.hwnd
            self._auto_candidate_since = now
            self._auto_candidate_label = candidate.process_name or candidate.title
            return None

        if now - self._auto_candidate_since < self._config.auto_detect_delay_seconds:
            return None

        self._next_attach_is_auto = True
        self._reset_auto_candidate()
        return candidate

    def _is_likely_game(self, candidate: WindowInfo) -> bool:
        if candidate.width < 960 or candidate.height < 540:
            return False
        if not candidate.process_name or candidate.title == "<Fenster ohne Titel>":
            return False

        process = candidate.process_name.casefold()
        custom_exclusions = {
            item.strip().casefold()
            for item in self._config.auto_excluded_processes.replace(";", ",").split(",")
            if item.strip()
        }
        return process not in AUTO_DETECT_EXCLUSIONS and process not in custom_exclusions

    def _sync_topmost(self, in_foreground: bool) -> None:
        if self._current is None or not self._config.always_on_top:
            return
        desired = in_foreground
        if desired == self._topmost_applied:
            return
        # A permanent topmost window can make Alt+Tab look broken even though
        # Windows changed focus. Temporarily demote it while another app is active.
        win32.set_window_topmost(self._current.hwnd, desired)
        self._topmost_applied = desired

    def _sync_taskbar_visibility(self, in_foreground: bool) -> None:
        if not win32.IS_WINDOWS:
            return
        should_hide = (
            self._config.hide_taskbar_while_game_focused and in_foreground
        )
        if should_hide:
            self._taskbar_snapshots = win32.hide_taskbars(
                self._taskbar_snapshots
            )
        else:
            self._restore_taskbars_if_needed()

    def _restore_taskbars_if_needed(self) -> None:
        if not win32.IS_WINDOWS:
            self._taskbar_snapshots = ()
            return
        if not self._taskbar_snapshots:
            return
        win32.restore_taskbars(self._taskbar_snapshots)
        self._taskbar_snapshots = ()

    def _waiting_message(self) -> str:
        if self._auto_candidate_hwnd:
            return (
                f"Automatische Erkennung prueft {self._auto_candidate_label} ... "
                "Fenster kurz im Vordergrund lassen."
            )
        if self._config.auto_detect_games:
            return (
                "Automatische Spiel-Erkennung ist bereit. Starte das Spiel und bringe "
                "sein Fenster kurz in den Vordergrund."
            )
        return "Bereit und wartet auf das eingestellte Spiel-Fenster."

    def _positioning_message(self, measurement: win32.WindowMeasurement) -> str:
        target = self._config.target_rect
        retry = (
            "FellSplit Pro versucht den Resize automatisch weiter."
            if self._config.keep_position
            else "Der Positions-Watchdog ist aus; aktiviere FellSplit Pro erneut."
        )
        decoration = (
            " Windows-Rahmen/Titelleiste sind noch vorhanden."
            if measurement.has_decorations
            else ""
        )
        return (
            f"Fenster wird noch angepasst. Ziel: {target.width} x {target.height} "
            f"bei ({target.x}, {target.y}); Aussen aktuell: "
            f"{measurement.outer.width} x {measurement.outer.height} bei "
            f"({measurement.outer.x}, {measurement.outer.y}); echte Spielflaeche: "
            f"{measurement.client.width} x {measurement.client.height}."
            f"{decoration} Die Maus bleibt bis zur bestaetigten Clientgroesse frei. "
            f"{retry}"
        )

    @staticmethod
    def _append_secondary_status(primary: str, secondary: str) -> str:
        return f"{primary} {secondary}" if secondary else primary

    @staticmethod
    def _rects_overlap(first: TargetRect, second: TargetRect) -> bool:
        return (
            first.x < second.right
            and first.right > second.x
            and first.y < second.bottom
            and first.bottom > second.y
        )

    def _secondary_zone_label(self) -> str:
        second = self._config.secondary_target_rect
        game = self._config.target_rect
        if second.right <= game.x:
            return "Links"
        if second.x >= game.right:
            return "Rechts"
        return "Zweite Zone"

    def _reset_auto_candidate(self) -> None:
        self._auto_candidate_hwnd = 0
        self._auto_candidate_since = 0.0
        self._auto_candidate_label = ""

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        if isinstance(exc, win32.Win32Error) and exc.code == 5:
            return (
                "Zugriff verweigert. Das Spiel laeuft vermutlich als Administrator. "
                "Starte FellSplit Pro ebenfalls als Administrator."
            )
        return f"Fehler: {exc} Das Tool versucht es automatisch erneut."
