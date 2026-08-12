from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from fellsplit_pro import win32_api as win32
from fellsplit_pro.models import TargetRect


class Win32ApiTests(unittest.TestCase):
    def test_borderless_style_clears_maximized_and_minimized_state(self) -> None:
        original = (
            win32.WS_CAPTION
            | win32.WS_THICKFRAME
            | win32.WS_MAXIMIZE
            | win32.WS_MINIMIZE
        )

        result = win32.make_borderless_style(original)

        self.assertEqual(result & win32.WINDOW_DECORATION_MASK, 0)
        self.assertEqual(result & win32.WINDOW_STATE_MASK, 0)
        self.assertTrue(result & win32.WS_POPUP)
        self.assertTrue(result & win32.WS_VISIBLE)

    def test_framed_style_restores_caption_and_window_controls(self) -> None:
        original = win32.WS_POPUP | win32.WS_MAXIMIZE | win32.WS_VISIBLE

        result = win32.make_framed_style(original)

        self.assertEqual(result & win32.WS_POPUP, 0)
        self.assertEqual(result & win32.WINDOW_STATE_MASK, 0)
        self.assertEqual(
            result & win32.WINDOW_DECORATION_MASK,
            win32.WINDOW_DECORATION_MASK,
        )

    def test_rect_match_uses_small_configurable_tolerance(self) -> None:
        expected = TargetRect(0, 0, 2560, 1440)
        one_pixel_off = TargetRect(1, -1, 2559, 1441)

        self.assertTrue(win32.rect_matches(expected, expected))
        self.assertFalse(win32.rect_matches(one_pixel_off, expected))
        self.assertTrue(win32.rect_matches(one_pixel_off, expected, tolerance=1))
        self.assertFalse(win32.rect_matches(TargetRect(0, 0, 5120, 1440), expected))

    def test_borderless_measurement_requires_full_client_area(self) -> None:
        expected = TargetRect()
        with_titlebar = win32.WindowMeasurement(
            outer=expected,
            client=TargetRect(8, 31, 2544, 1401),
            has_decorations=True,
        )
        borderless = win32.WindowMeasurement(
            outer=expected,
            client=expected,
            has_decorations=False,
        )

        self.assertFalse(
            win32.measurement_matches(
                with_titlebar,
                expected,
                require_borderless=True,
            )
        )
        self.assertTrue(
            win32.measurement_matches(
                borderless,
                expected,
                require_borderless=True,
            )
        )

    def test_force_position_restores_state_and_uses_movewindow(self) -> None:
        fake_user32 = Mock()
        fake_user32.MoveWindow.return_value = True
        style = win32.WS_CAPTION | win32.WS_MAXIMIZE | win32.WS_VISIBLE
        exstyle = win32.WS_EX_WINDOWEDGE
        target = TargetRect()

        with (
            patch.object(win32, "user32", fake_user32, create=True),
            patch.object(win32, "require_windows"),
            patch.object(win32, "is_window", return_value=True),
            patch.object(
                win32,
                "_get_window_long_checked",
                side_effect=lambda _hwnd, index: (
                    style if index == win32.GWL_STYLE else exstyle
                ),
            ),
            patch.object(win32, "_set_window_long_checked") as set_style,
            patch.object(win32, "position_window") as position_window,
        ):
            win32.force_position_window(
                55,
                target,
                remove_borders=True,
                always_on_top=False,
            )

        fake_user32.ShowWindow.assert_called_once_with(55, win32.SW_RESTORE)
        set_style.assert_any_call(
            55,
            win32.GWL_STYLE,
            win32.make_borderless_style(style),
        )
        set_style.assert_any_call(55, win32.GWL_EXSTYLE, 0)
        position_window.assert_called_once_with(
            55,
            target,
            always_on_top=False,
            frame_changed=True,
        )
        fake_user32.MoveWindow.assert_called_once_with(55, 0, 0, 2560, 1440, True)

    def test_taskbar_visibility_is_snapshotted_and_restored(self) -> None:
        fake_user32 = Mock()
        fake_user32.IsWindowVisible.return_value = True

        with (
            patch.object(win32, "user32", fake_user32, create=True),
            patch.object(win32, "require_windows"),
            patch.object(win32, "get_taskbar_windows", return_value=[10, 20]),
        ):
            snapshots = win32.hide_taskbars()

        self.assertEqual(
            snapshots,
            (
                win32.TaskbarSnapshot(10, True),
                win32.TaskbarSnapshot(20, True),
            ),
        )
        fake_user32.ShowWindow.assert_any_call(10, win32.SW_HIDE)
        fake_user32.ShowWindow.assert_any_call(20, win32.SW_HIDE)

        fake_user32.reset_mock()
        with (
            patch.object(win32, "user32", fake_user32, create=True),
            patch.object(win32, "require_windows"),
            patch.object(win32, "is_window", return_value=True),
        ):
            win32.restore_taskbars(snapshots)

        fake_user32.ShowWindow.assert_any_call(10, win32.SW_SHOWNOACTIVATE)
        fake_user32.ShowWindow.assert_any_call(20, win32.SW_SHOWNOACTIVATE)

    def test_integrated_emergency_action_shows_all_taskbars(self) -> None:
        fake_user32 = Mock()
        with (
            patch.object(win32, "user32", fake_user32, create=True),
            patch.object(win32, "require_windows"),
            patch.object(win32, "get_taskbar_windows", return_value=[10, 20]),
        ):
            win32.show_all_taskbars()

        fake_user32.ShowWindow.assert_any_call(10, win32.SW_SHOWNOACTIVATE)
        fake_user32.ShowWindow.assert_any_call(20, win32.SW_SHOWNOACTIVATE)


if __name__ == "__main__":
    unittest.main()
