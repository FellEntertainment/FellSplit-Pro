from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_pyinstaller_build_uses_fellsplit_identity(self) -> None:
        spec = (ROOT / "FellSplitPro.spec").read_text(encoding="utf-8")
        self.assertIn('["FellSplitPro.pyw"]', spec)
        self.assertIn('name="FellSplitPro"', spec)
        self.assertIn('icon="assets/FellSplitPro.ico"', spec)
        self.assertIn('version="version_info.txt"', spec)
        self.assertIn("a.binaries", spec)
        self.assertIn("a.datas", spec)
        self.assertIn("exclude_binaries=False", spec)
        self.assertNotIn("COLLECT(", spec)

    def test_windows_version_metadata_is_complete(self) -> None:
        metadata = (ROOT / "version_info.txt").read_text(encoding="utf-8")
        self.assertIn("Fell Entertainment & Co.", metadata)
        self.assertIn("FellSplitPro.exe", metadata)
        self.assertIn("ProductVersion', '1.3.0", metadata)

    def test_inno_setup_builds_the_branded_installer(self) -> None:
        script = (ROOT / "FellSplitPro.iss").read_text(encoding="utf-8")
        self.assertIn('#define MyAppName "FellSplit Pro"', script)
        self.assertIn('Source: "dist\\FellSplitPro.exe"', script)
        self.assertIn("FellSplit-Pro-Setup-{#MyAppVersion}", script)
        self.assertIn("AppMutex=Local\\SplitLock-Fell-Entertainment-v1", script)
        self.assertIn("DisableDirPage=no", script)
        self.assertIn('#define MyAppVersion "1.3.0"', script)
        self.assertIn('Parameters: "--emergency-unlock"', script)

    def test_installer_cleans_only_old_packaging_files(self) -> None:
        script = (ROOT / "FellSplitPro.iss").read_text(encoding="utf-8")
        self.assertIn('Name: "{app}\\_internal"', script)
        self.assertNotIn('Name: "{app}\\*"', script)

    def test_required_brand_assets_and_build_scripts_exist(self) -> None:
        for relative in (
            "assets/FellSplitPro.ico",
            "assets/FellSplitPro.png",
            "build_exe.bat",
            "build_installer.bat",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_dwm_uses_hresult_from_ctypes(self) -> None:
        source = (ROOT / "fellsplit_pro" / "win32_api.py").read_text(encoding="utf-8")
        self.assertIn("restype = ctypes.HRESULT", source)
        self.assertNotIn("restype = wintypes.HRESULT", source)


if __name__ == "__main__":
    unittest.main()
