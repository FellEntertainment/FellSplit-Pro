from __future__ import annotations

import unittest

from fellsplit_pro.layout import calculate_layout
from fellsplit_pro.models import (
    GAME_SIDE_LEFT,
    GAME_SIDE_RIGHT,
    LAYOUT_AUTOMATIC,
    LAYOUT_CUSTOM,
    LAYOUT_EQUAL_HALVES,
    LAYOUT_GAME_16_9,
    TargetRect,
)


class LayoutTests(unittest.TestCase):
    def test_automatic_5120_x_1440_creates_two_16_9_halves(self) -> None:
        layout = calculate_layout(
            TargetRect(0, 0, 5120, 1440),
            LAYOUT_AUTOMATIC,
        )
        self.assertEqual(layout.effective_mode, LAYOUT_EQUAL_HALVES)
        self.assertEqual(layout.game, TargetRect(0, 0, 2560, 1440))
        self.assertEqual(layout.secondary, TargetRect(2560, 0, 2560, 1440))

    def test_automatic_3840_x_1080_creates_two_16_9_halves(self) -> None:
        layout = calculate_layout(
            TargetRect(0, 0, 3840, 1080),
            LAYOUT_AUTOMATIC,
        )
        self.assertEqual(layout.effective_mode, LAYOUT_EQUAL_HALVES)
        self.assertEqual(layout.game.width, 1920)
        self.assertEqual(layout.secondary.width, 1920)

    def test_automatic_3440_x_1440_preserves_16_9_game(self) -> None:
        layout = calculate_layout(
            TargetRect(0, 0, 3440, 1440),
            LAYOUT_AUTOMATIC,
        )
        self.assertEqual(layout.effective_mode, LAYOUT_GAME_16_9)
        self.assertEqual(layout.game, TargetRect(0, 0, 2560, 1440))
        self.assertEqual(layout.secondary, TargetRect(2560, 0, 880, 1440))

    def test_automatic_2560_x_1080_preserves_16_9_game(self) -> None:
        layout = calculate_layout(
            TargetRect(0, 0, 2560, 1080),
            LAYOUT_AUTOMATIC,
        )
        self.assertEqual(layout.game.width, 1920)
        self.assertEqual(layout.secondary.width, 640)

    def test_explicit_equal_halves_on_21_9_is_available(self) -> None:
        layout = calculate_layout(
            TargetRect(0, 0, 3440, 1440),
            LAYOUT_EQUAL_HALVES,
        )
        self.assertEqual(layout.game, TargetRect(0, 0, 1720, 1440))
        self.assertEqual(layout.secondary, TargetRect(1720, 0, 1720, 1440))

    def test_game_can_be_placed_on_right_with_remaining_zone_left(self) -> None:
        layout = calculate_layout(
            TargetRect(0, 0, 3440, 1440),
            LAYOUT_GAME_16_9,
            GAME_SIDE_RIGHT,
        )
        self.assertEqual(layout.secondary, TargetRect(0, 0, 880, 1440))
        self.assertEqual(layout.game, TargetRect(880, 0, 2560, 1440))

    def test_non_primary_monitor_origin_is_preserved(self) -> None:
        layout = calculate_layout(
            TargetRect(-3440, 120, 3440, 1440),
            LAYOUT_AUTOMATIC,
            GAME_SIDE_LEFT,
        )
        self.assertEqual(layout.game, TargetRect(-3440, 120, 2560, 1440))
        self.assertEqual(layout.secondary, TargetRect(-880, 120, 880, 1440))

    def test_odd_width_is_fully_covered_without_overlap(self) -> None:
        monitor = TargetRect(100, 50, 3441, 1440)
        layout = calculate_layout(monitor, LAYOUT_EQUAL_HALVES)
        self.assertEqual(layout.game.right, layout.secondary.x)
        self.assertEqual(layout.secondary.right, monitor.right)
        self.assertEqual(layout.game.width + layout.secondary.width, monitor.width)

    def test_custom_mode_requires_user_coordinates(self) -> None:
        with self.assertRaises(ValueError):
            calculate_layout(TargetRect(0, 0, 3440, 1440), LAYOUT_CUSTOM)


if __name__ == "__main__":
    unittest.main()
