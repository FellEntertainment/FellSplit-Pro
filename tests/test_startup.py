from __future__ import annotations

import unittest
from pathlib import Path

from fellsplit_pro.startup import build_startup_command


class StartupTests(unittest.TestCase):
    def test_source_startup_uses_windowed_launcher_and_minimized_flag(self) -> None:
        command = build_startup_command(start_minimized=True)
        self.assertIn("FellSplitPro.pyw", command)
        self.assertIn("--minimized", command)

    def test_visible_start_omits_minimized_flag(self) -> None:
        command = build_startup_command(start_minimized=False)
        self.assertNotIn("--minimized", command)

    def test_interactive_launcher_checks_for_old_tray_instance(self) -> None:
        launcher = Path(__file__).resolve().parents[1] / "start_fellsplit_pro.bat"
        self.assertIn("--launch-check", launcher.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
