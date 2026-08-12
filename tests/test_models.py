from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fellsplit_pro.config_store import load_config, save_config
from fellsplit_pro.models import (
    GAME_SIDE_RIGHT,
    LAYOUT_AUTOMATIC,
    LAYOUT_CUSTOM,
    LAYOUT_GAME_16_9,
    AppConfig,
    MonitorInfo,
    TargetRect,
    WindowInfo,
    normalize_process_name,
    window_matches,
)


class ModelTests(unittest.TestCase):
    def test_process_normalization_accepts_escaped_dot_and_path(self) -> None:
        self.assertEqual(normalize_process_name(r"wow\.exe"), "wow.exe")
        self.assertEqual(normalize_process_name(r"C:\Games\Wow.exe"), "wow.exe")
        self.assertEqual(normalize_process_name("C:/Games/Wow.exe"), "wow.exe")

    def test_window_matching_uses_exact_process_and_partial_title(self) -> None:
        window = WindowInfo(
            hwnd=123,
            pid=55,
            process_name="Wow.exe",
            title="World of Warcraft",
            width=1920,
            height=1080,
        )
        self.assertTrue(window_matches(window, "wow.exe", "Warcraft"))
        self.assertTrue(window_matches(window, r"wow\.exe", ""))
        self.assertFalse(window_matches(window, "wow", ""))
        self.assertFalse(window_matches(window, "wow.exe", "Overwatch"))
        self.assertFalse(window_matches(window, "", ""))

    def test_target_rect_validation(self) -> None:
        TargetRect(0, 0, 2560, 1440).validate()
        with self.assertRaises(ValueError):
            TargetRect(0, 0, 100, 100).validate()

    def test_config_roundtrip_and_transient_hwnd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            config = AppConfig(
                process_name="game.exe",
                selected_hwnd=999,
                layout_mode=LAYOUT_GAME_16_9,
                monitor_id=r"\\.\DISPLAY2",
                game_side=GAME_SIDE_RIGHT,
                target_rect=TargetRect(-2560, 0, 2560, 1440),
                secondary_enabled=True,
                secondary_process_name="obs64.exe",
                secondary_selected_hwnd=1000,
                secondary_target_rect=TargetRect(0, 0, 2560, 1440),
                secondary_show_frame_when_focused=False,
                hide_taskbar_while_game_focused=False,
            )
            save_config(config, path)
            loaded = load_config(path)
            self.assertEqual(loaded.process_name, "game.exe")
            self.assertEqual(loaded.layout_mode, LAYOUT_GAME_16_9)
            self.assertEqual(loaded.monitor_id, r"\\.\DISPLAY2")
            self.assertEqual(loaded.game_side, GAME_SIDE_RIGHT)
            self.assertEqual(loaded.target_rect.x, -2560)
            self.assertEqual(loaded.selected_hwnd, 0)
            self.assertTrue(loaded.secondary_enabled)
            self.assertEqual(loaded.secondary_process_name, "obs64.exe")
            self.assertEqual(loaded.secondary_target_rect, TargetRect(0, 0, 2560, 1440))
            self.assertEqual(loaded.secondary_selected_hwnd, 0)
            self.assertFalse(loaded.secondary_show_frame_when_focused)
            self.assertFalse(loaded.hide_taskbar_while_game_focused)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["selected_hwnd"], 0)
            self.assertEqual(raw["secondary_selected_hwnd"], 0)

    def test_invalid_config_falls_back_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text('{"target_rect":{"width":"bad"}}', encoding="utf-8")
            loaded = load_config(path)
            self.assertEqual(loaded.target_rect, TargetRect())

    def test_legacy_splitlock_config_is_migrated_to_fellsplit_pro(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            legacy_path = Path(temp_dir) / "SplitLock" / "config.json"
            legacy_path.parent.mkdir(parents=True)
            legacy_path.write_text(
                json.dumps({"process_name": "legacy-game.exe"}),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"APPDATA": temp_dir}):
                loaded = load_config()
            migrated_path = Path(temp_dir) / "FellSplit Pro" / "config.json"
            self.assertEqual(loaded.process_name, "legacy-game.exe")
            self.assertTrue(migrated_path.exists())
            self.assertEqual(
                json.loads(migrated_path.read_text(encoding="utf-8"))["process_name"],
                "legacy-game.exe",
            )

    def test_v1_config_migrates_to_alt_tab_safe_cursor_lock(self) -> None:
        old = AppConfig.from_dict({"foreground_only": False})
        self.assertTrue(old.foreground_only)
        self.assertEqual(old.schema_version, 6)

    def test_v2_config_preserves_explicit_cursor_choice(self) -> None:
        current = AppConfig.from_dict({"schema_version": 2, "foreground_only": False})
        self.assertFalse(current.foreground_only)

    def test_v5_factory_geometry_migrates_to_automatic_layout(self) -> None:
        old = AppConfig.from_dict(
            {
                "schema_version": 5,
                "target_rect": {"x": 0, "y": 0, "width": 2560, "height": 1440},
                "secondary_target_rect": {
                    "x": 2560,
                    "y": 0,
                    "width": 2560,
                    "height": 1440,
                },
            }
        )
        self.assertEqual(old.layout_mode, LAYOUT_AUTOMATIC)

    def test_v5_custom_geometry_remains_custom(self) -> None:
        old = AppConfig.from_dict(
            {
                "schema_version": 5,
                "target_rect": {"x": 40, "y": 20, "width": 1920, "height": 1080},
                "secondary_target_rect": {
                    "x": 1960,
                    "y": 20,
                    "width": 1000,
                    "height": 1080,
                },
            }
        )
        self.assertEqual(old.layout_mode, LAYOUT_CUSTOM)

    def test_monitor_display_name_contains_resolution_and_device(self) -> None:
        monitor = MonitorInfo(
            identifier=r"\\.\DISPLAY2",
            rect=TargetRect(-3440, 0, 3440, 1440),
            is_primary=False,
        )
        self.assertIn("3440 x 1440", monitor.display_name)
        self.assertIn("DISPLAY2", monitor.display_name)


if __name__ == "__main__":
    unittest.main()
