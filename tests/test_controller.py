from __future__ import annotations

import unittest
from unittest.mock import patch
import time

from fellsplit_pro import win32_api as win32
from fellsplit_pro.controller import GameWindowController, RunState
from fellsplit_pro.models import (
    GAME_SIDE_RIGHT,
    LAYOUT_AUTOMATIC,
    LAYOUT_CUSTOM,
    AppConfig,
    MonitorInfo,
    TargetRect,
    WindowInfo,
)


def fake_snapshot(hwnd: int) -> win32.WindowSnapshot:
    return win32.WindowSnapshot(
        hwnd=hwnd,
        style=0x10CF0000,
        exstyle=0,
        left=100,
        top=100,
        right=1380,
        bottom=820,
        placement=win32.PlacementSnapshot(
            flags=0,
            show_cmd=1,
            min_x=-1,
            min_y=-1,
            max_x=-1,
            max_y=-1,
            normal_left=100,
            normal_top=100,
            normal_right=1380,
            normal_bottom=820,
        ),
    )


def fake_measurement(
    outer: TargetRect = TargetRect(),
    *,
    client: TargetRect | None = None,
    decorated: bool = False,
) -> win32.WindowMeasurement:
    return win32.WindowMeasurement(
        outer=outer,
        client=client or outer,
        has_decorations=decorated,
    )


class ControllerTests(unittest.TestCase):
    def test_monitor_profile_is_resolved_before_activation(self) -> None:
        controller = GameWindowController()
        monitor = MonitorInfo(
            identifier=r"\\.\DISPLAY2",
            rect=TargetRect(-3440, 0, 3440, 1440),
            is_primary=False,
        )
        config = AppConfig(
            layout_mode=LAYOUT_AUTOMATIC,
            monitor_id=monitor.identifier,
            game_side=GAME_SIDE_RIGHT,
        )
        with (
            patch.object(win32, "IS_WINDOWS", True),
            patch.object(win32, "get_monitor_by_id", return_value=monitor),
        ):
            resolved = controller._resolve_layout(config)
        self.assertEqual(resolved.target_rect, TargetRect(-2560, 0, 2560, 1440))
        self.assertEqual(
            resolved.secondary_target_rect,
            TargetRect(-3440, 0, 880, 1440),
        )

    def test_missing_game_is_waiting_not_an_error(self) -> None:
        controller = GameWindowController()
        with (
            patch.object(win32, "enumerate_windows", return_value=[]),
            patch.object(win32, "get_foreground_window", return_value=0),
            patch.object(win32, "get_root_window", return_value=0),
            patch.object(win32, "release_cursor"),
        ):
            status = controller.activate(AppConfig(process_name="game.exe"))
        self.assertEqual(status.state, RunState.WAITING)
        self.assertTrue(controller.desired_active)

    def test_activate_and_deactivate_apply_and_restore_everything(self) -> None:
        controller = GameWindowController()
        target = WindowInfo(123, 77, "game.exe", "My Game", 1280, 720)
        snapshot = fake_snapshot(target.hwnd)
        target_rect = TargetRect(0, 0, 1920, 1080)

        with (
            patch.object(win32, "enumerate_windows", return_value=[target]),
            patch.object(win32, "capture_window", return_value=snapshot),
            patch.object(win32, "apply_borderless") as apply_borderless,
            patch.object(win32, "position_window") as position_window,
            patch.object(win32, "clip_cursor") as clip_cursor,
            patch.object(win32, "release_cursor") as release_cursor,
            patch.object(win32, "restore_window") as restore_window,
            patch.object(win32, "get_foreground_window", return_value=target.hwnd),
            patch.object(win32, "get_window_pid", return_value=target.pid),
            patch.object(win32, "measure_window", return_value=fake_measurement(target_rect)),
        ):
            status = controller.activate(AppConfig(process_name="game.exe", target_rect=target_rect, layout_mode=LAYOUT_CUSTOM))
            self.assertEqual(status.state, RunState.ACTIVE)
            apply_borderless.assert_called_once()
            position_window.assert_called_once()
            clip_cursor.assert_called_once()

            stopped = controller.deactivate()
            self.assertEqual(stopped.state, RunState.OFF)
            release_cursor.assert_called_once()
            restore_window.assert_called_once_with(snapshot)

    def test_access_denied_has_actionable_message(self) -> None:
        error = win32.Win32Error.__new__(win32.Win32Error)
        error.code = 5
        RuntimeError.__init__(error, "access denied")
        message = GameWindowController._friendly_error(error)
        self.assertIn("Administrator", message)

    def test_alt_tab_releases_cursor_and_demotes_topmost_window(self) -> None:
        controller = GameWindowController()
        target = WindowInfo(123, 77, "game.exe", "My Game", 1920, 1080)
        snapshot = fake_snapshot(target.hwnd)
        foreground = {"hwnd": target.hwnd, "pid": target.pid}
        target_rect = TargetRect(0, 0, 1920, 1080)

        with (
            patch.object(win32, "enumerate_windows", return_value=[target]),
            patch.object(win32, "capture_window", return_value=snapshot),
            patch.object(win32, "apply_borderless"),
            patch.object(win32, "position_window") as position_window,
            patch.object(win32, "clip_cursor") as clip_cursor,
            patch.object(win32, "release_cursor") as release_cursor,
            patch.object(win32, "get_foreground_window", side_effect=lambda: foreground["hwnd"]),
            patch.object(win32, "get_window_pid", side_effect=lambda _hwnd: foreground["pid"]),
            patch.object(win32, "set_window_topmost") as set_topmost,
            patch.object(win32, "force_position_window") as force_position,
            patch.object(win32, "measure_window", return_value=fake_measurement(target_rect)),
        ):
            config = AppConfig(process_name="game.exe", always_on_top=True, target_rect=target_rect, layout_mode=LAYOUT_CUSTOM)
            self.assertEqual(controller.activate(config).state, RunState.ACTIVE)
            clip_cursor.assert_called_once()

            foreground.update(hwnd=999, pid=88)
            controller.tick(force=True)
            release_cursor.assert_called_once()
            set_topmost.assert_called_once_with(target.hwnd, False)
            force_position.assert_not_called()
            position_window.assert_called_once()

    def test_auto_detect_attaches_stable_foreground_candidate(self) -> None:
        controller = GameWindowController()
        target = WindowInfo(321, 91, "newgame.exe", "New Game", 1920, 1080)
        target_rect = TargetRect(0, 0, 1920, 1080)

        with (
            patch.object(win32, "enumerate_windows", return_value=[target]),
            patch.object(win32, "get_foreground_window", return_value=target.hwnd),
            patch.object(win32, "get_root_window", return_value=target.hwnd),
            patch.object(win32, "capture_window", return_value=fake_snapshot(target.hwnd)),
            patch.object(win32, "apply_borderless"),
            patch.object(win32, "position_window"),
            patch.object(win32, "clip_cursor"),
            patch.object(win32, "get_window_pid", return_value=target.pid),
            patch.object(win32, "measure_window", return_value=fake_measurement(target_rect)),
            patch.object(win32, "release_cursor"),
        ):
            config = AppConfig(
                process_name="",
                auto_detect_games=True,
                auto_detect_delay_seconds=0.5,
                target_rect=target_rect,
                layout_mode=LAYOUT_CUSTOM
            )
            first = controller.activate(config)
            self.assertEqual(first.state, RunState.WAITING)
            controller._auto_candidate_since = time.monotonic() - 1.0
            second = controller.tick(force=True)
            self.assertEqual(second.state, RunState.ACTIVE)
            self.assertIn("automatisch erkannt", second.message)

    def test_auto_detect_rejects_obs_and_browser(self) -> None:
        controller = GameWindowController()
        for process in ("obs64.exe", "chrome.exe"):
            candidate = WindowInfo(44, 12, process, "Large Window", 2560, 1440)
            self.assertFalse(controller._is_likely_game(candidate))

    def test_full_monitor_window_is_not_allowed_to_clip_the_cursor(self) -> None:
        controller = GameWindowController()
        target = WindowInfo(123, 77, "Cookie Clicker.exe", "Cookie Clicker", 5120, 1440)
        snapshot = fake_snapshot(target.hwnd)
        actual_rect = TargetRect(0, 0, 5120, 1440)

        with (
            patch.object(win32, "enumerate_windows", return_value=[target]),
            patch.object(win32, "capture_window", return_value=snapshot),
            patch.object(win32, "apply_borderless"),
            patch.object(win32, "position_window"),
            patch.object(win32, "force_position_window") as force_position,
            patch.object(
                win32,
                "measure_window",
                return_value=fake_measurement(actual_rect),
            ),
            patch.object(win32, "clip_cursor") as clip_cursor,
            patch.object(win32, "release_cursor") as release_cursor,
            patch.object(win32, "get_foreground_window", return_value=target.hwnd),
            patch.object(win32, "get_window_pid", return_value=target.pid),
        ):
            status = controller.activate(AppConfig(process_name=target.process_name, layout_mode=LAYOUT_CUSTOM))

        self.assertEqual(status.state, RunState.POSITIONING)
        force_position.assert_called_once()
        clip_cursor.assert_not_called()
        release_cursor.assert_called_once()

    def test_cursor_is_released_if_game_restores_full_monitor_size(self) -> None:
        controller = GameWindowController()
        target = WindowInfo(123, 77, "game.exe", "My Game", 2560, 1440)
        snapshot = fake_snapshot(target.hwnd)
        target_rect = TargetRect(0, 0, 2560, 1440)
        current_rect = {"value": target_rect}

        with (
            patch.object(win32, "enumerate_windows", return_value=[target]),
            patch.object(win32, "capture_window", return_value=snapshot),
            patch.object(win32, "apply_borderless"),
            patch.object(win32, "position_window"),
            patch.object(win32, "force_position_window"),
            patch.object(
                win32,
                "measure_window",
                side_effect=lambda _hwnd: fake_measurement(current_rect["value"]),
            ),
            patch.object(win32, "clip_cursor") as clip_cursor,
            patch.object(win32, "release_cursor") as release_cursor,
            patch.object(win32, "get_foreground_window", return_value=target.hwnd),
            patch.object(win32, "get_window_pid", return_value=target.pid),
        ):
            self.assertEqual(
                controller.activate(AppConfig(process_name=target.process_name, target_rect=target_rect, layout_mode=LAYOUT_CUSTOM)).state,
                RunState.ACTIVE,
            )
            current_rect["value"] = TargetRect(0, 0, 5120, 1440)
            status = controller.tick(force=True)

        self.assertEqual(status.state, RunState.POSITIONING)
        clip_cursor.assert_called_once()
        self.assertGreaterEqual(release_cursor.call_count, 1)

    def test_cursor_locks_after_force_resize_is_measured_successfully(self) -> None:
        controller = GameWindowController()
        target = WindowInfo(123, 77, "Cookie Clicker.exe", "Cookie Clicker", 5120, 1440)
        snapshot = fake_snapshot(target.hwnd)
        requested = TargetRect(0, 0, 2560, 1440)

        with (
            patch.object(win32, "enumerate_windows", return_value=[target]),
            patch.object(win32, "capture_window", return_value=snapshot),
            patch.object(win32, "apply_borderless"),
            patch.object(win32, "position_window"),
            patch.object(win32, "force_position_window") as force_position,
            patch.object(
                win32,
                "measure_window",
                side_effect=[
                    fake_measurement(TargetRect(0, 0, 5120, 1440)),
                    fake_measurement(requested),
                ],
            ),
            patch.object(win32, "clip_cursor") as clip_cursor,
            patch.object(win32, "release_cursor"),
            patch.object(win32, "get_foreground_window", return_value=target.hwnd),
            patch.object(win32, "get_window_pid", return_value=target.pid),
        ):
            status = controller.activate(AppConfig(process_name=target.process_name, target_rect=requested, layout_mode=LAYOUT_CUSTOM))

        self.assertEqual(status.state, RunState.ACTIVE)
        force_position.assert_called_once()
        clip_cursor.assert_called_once_with(requested)

    def test_titlebar_is_reapplied_as_borderless_even_when_outer_rect_matches(self) -> None:
        controller = GameWindowController()
        target = WindowInfo(123, 77, "game.exe", "My Game", 2560, 1440)
        requested = TargetRect(0, 0, 2560, 1440)
        
        with (
            patch.object(win32, "enumerate_windows", return_value=[target]),
            patch.object(win32, "capture_window", return_value=fake_snapshot(123)),
            patch.object(win32, "apply_borderless"),
            patch.object(win32, "position_window"),
            patch.object(win32, "force_position_window") as force_position,
            patch.object(
                win32,
                "measure_window",
                side_effect=[
                    fake_measurement(
                        requested,
                        client=TargetRect(8, 31, 2544, 1401),
                        decorated=True,
                    ),
                    fake_measurement(requested),
                ],
            ),
            patch.object(win32, "clip_cursor") as clip_cursor,
            patch.object(win32, "release_cursor"),
            patch.object(win32, "get_foreground_window", return_value=123),
            patch.object(win32, "get_window_pid", return_value=77),
        ):
            status = controller.activate(AppConfig(process_name="game.exe", target_rect=requested, layout_mode=LAYOUT_CUSTOM))

        self.assertEqual(status.state, RunState.ACTIVE)
        force_position.assert_called_once()
        clip_cursor.assert_called_once()

    def test_secondary_obs_window_is_borderless_on_right_and_restored(self) -> None:
        controller = GameWindowController()
        game = WindowInfo(123, 77, "game.exe", "My Game", 2560, 1440)
        obs = WindowInfo(456, 88, "obs64.exe", "OBS Studio", 1920, 1080)
        game_snapshot = fake_snapshot(game.hwnd)
        obs_snapshot = fake_snapshot(obs.hwnd)
        
        game_rect = TargetRect(0, 0, 2560, 1440)
        obs_rect = TargetRect(2560, 0, 2560, 1440)
        game_measurement = fake_measurement(game_rect)
        obs_measurement = fake_measurement(obs_rect)

        with (
            patch.object(win32, "enumerate_windows", return_value=[game, obs]),
            patch.object(
                win32,
                "capture_window",
                side_effect=lambda hwnd: (
                    game_snapshot if hwnd == game.hwnd else obs_snapshot
                ),
            ),
            patch.object(win32, "apply_borderless"),
            patch.object(win32, "position_window"),
            patch.object(win32, "force_position_window") as force_position,
            patch.object(
                win32,
                "measure_window",
                side_effect=lambda hwnd: (
                    game_measurement if hwnd == game.hwnd else obs_measurement
                ),
            ),
            patch.object(win32, "clip_cursor"),
            patch.object(win32, "release_cursor"),
            patch.object(win32, "restore_window") as restore_window,
            patch.object(win32, "get_foreground_window", return_value=game.hwnd),
            patch.object(win32, "get_window_pid", return_value=game.pid),
        ):
            status = controller.activate(
                AppConfig(
                    process_name="game.exe",
                    target_rect=game_rect,
                    secondary_enabled=True,
                    secondary_process_name="obs64.exe",
                    secondary_target_rect=obs_rect,
                    layout_mode=LAYOUT_CUSTOM
                )
            )
            stopped = controller.deactivate()

        self.assertEqual(status.state, RunState.ACTIVE)
        self.assertIn("Rechts: obs64.exe", status.message)
        force_position.assert_any_call(
            obs.hwnd,
            obs_rect,
            remove_borders=True,
            always_on_top=False,
        )
        self.assertEqual(stopped.state, RunState.OFF)
        restore_window.assert_any_call(game_snapshot)
        restore_window.assert_any_call(obs_snapshot)

    def test_obs_titlebar_appears_on_focus_and_hides_on_return_to_game(self) -> None:
        controller = GameWindowController()
        game = WindowInfo(123, 77, "game.exe", "My Game", 2560, 1440)
        obs = WindowInfo(456, 88, "obs64.exe", "OBS Studio", 2560, 1440)
        obs_snapshot = fake_snapshot(obs.hwnd)
        foreground = {"hwnd": obs.hwnd}
        obs_frame = {"visible": False}
        
        game_rect = TargetRect(0, 0, 2560, 1440)
        right_rect = TargetRect(2560, 0, 2560, 1440)

        def process_id(hwnd: int) -> int:
            return {game.hwnd: game.pid, obs.hwnd: obs.pid}.get(hwnd, 0)

        def measurement(hwnd: int) -> win32.WindowMeasurement:
            if hwnd == game.hwnd:
                return fake_measurement(game_rect)
            if obs_frame["visible"]:
                return fake_measurement(
                    right_rect,
                    client=TargetRect(2568, 31, 2544, 1401),
                    decorated=True,
                )
            return fake_measurement(right_rect)

        def show_frame(*_args, **_kwargs) -> None:
            obs_frame["visible"] = True

        def force_position(hwnd: int, *_args, **_kwargs) -> None:
            if hwnd == obs.hwnd:
                obs_frame["visible"] = False

        with (
            patch.object(win32, "enumerate_windows", return_value=[game, obs]),
            patch.object(
                win32,
                "capture_window",
                side_effect=lambda hwnd: (
                    fake_snapshot(game.hwnd) if hwnd == game.hwnd else obs_snapshot
                ),
            ),
            patch.object(win32, "apply_borderless"),
            patch.object(win32, "position_window"),
            patch.object(
                win32,
                "force_position_window",
                side_effect=force_position,
            ) as force_window,
            patch.object(
                win32,
                "show_window_frame",
                side_effect=show_frame,
            ) as show_window_frame,
            patch.object(win32, "measure_window", side_effect=measurement),
            patch.object(win32, "clip_cursor"),
            patch.object(win32, "release_cursor"),
            patch.object(
                win32,
                "get_foreground_window",
                side_effect=lambda: foreground["hwnd"],
            ),
            patch.object(win32, "get_window_pid", side_effect=process_id),
        ):
            focused_obs = controller.activate(
                AppConfig(
                    process_name="game.exe",
                    target_rect=game_rect,
                    secondary_enabled=True,
                    secondary_process_name="obs64.exe",
                    secondary_target_rect=right_rect,
                    layout_mode=LAYOUT_CUSTOM
                )
            )
            self.assertIn("wird noch eingeblendet", focused_obs.message)
            show_window_frame.assert_called_once_with(
                obs.hwnd,
                obs_snapshot,
                right_rect,
            )

            foreground["hwnd"] = game.hwnd
            focused_game = controller.tick(force=True)

        self.assertIn("rahmenlos", focused_game.message)
        self.assertFalse(obs_frame["visible"])
        self.assertGreaterEqual(force_window.call_count, 2)

    def test_overlapping_dual_zones_are_rejected(self) -> None:
        controller = GameWindowController()
        with self.assertRaisesRegex(ValueError, "ueberlappen"):
            controller.activate(
                AppConfig(
                    process_name="game.exe",
                    target_rect=TargetRect(0, 0, 2560, 1440),
                    secondary_enabled=True,
                    secondary_process_name="obs64.exe",
                    secondary_target_rect=TargetRect(2000, 0, 4560, 1440),
                    layout_mode=LAYOUT_CUSTOM
                )
            )

    def test_taskbar_is_hidden_only_while_game_has_focus(self) -> None:
        controller = GameWindowController()
        target = WindowInfo(123, 77, "game.exe", "My Game", 2560, 1440)
        foreground = {"pid": target.pid}
        snapshots = (win32.TaskbarSnapshot(900, True),)

        with (
            patch.object(win32, "IS_WINDOWS", True),
            patch.object(
                win32,
                "get_monitor_by_id",
                return_value=MonitorInfo(
                    identifier=r"\\.\DISPLAY1",
                    rect=TargetRect(0, 0, 5120, 1440),
                    is_primary=True,
                ),
            ),
            patch.object(win32, "enumerate_windows", return_value=[target]),
            patch.object(win32, "capture_window", return_value=fake_snapshot(123)),
            patch.object(win32, "apply_borderless"),
            patch.object(win32, "position_window"),
            patch.object(win32, "measure_window", return_value=fake_measurement()),
            patch.object(win32, "clip_cursor"),
            patch.object(win32, "release_cursor"),
            patch.object(win32, "get_foreground_window", return_value=123),
            patch.object(
                win32,
                "get_window_pid",
                side_effect=lambda _hwnd: foreground["pid"],
            ),
            patch.object(
                win32,
                "hide_taskbars",
                return_value=snapshots,
            ) as hide_taskbars,
            patch.object(win32, "restore_taskbars") as restore_taskbars,
        ):
            self.assertEqual(
                controller.activate(AppConfig(process_name="game.exe")).state,
                RunState.ACTIVE,
            )
            hide_taskbars.assert_called_once_with(())

            foreground["pid"] = 88
            controller.tick(force=True)

        restore_taskbars.assert_called_once_with(snapshots)


if __name__ == "__main__":
    unittest.main()
