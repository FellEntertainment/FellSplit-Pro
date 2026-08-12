from __future__ import annotations

import json
import os
from pathlib import Path

from .models import AppConfig


APP_FOLDER = "FellSplit Pro"
LEGACY_APP_FOLDER = "SplitLock"
CONFIG_FILENAME = "config.json"
ERROR_LOG_FILENAME = "fellsplit_pro_error.log"


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home())
    return Path(base) / APP_FOLDER


def config_path() -> Path:
    return app_data_dir() / CONFIG_FILENAME


def error_log_path() -> Path:
    return app_data_dir() / ERROR_LOG_FILENAME


def legacy_config_path() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home())
    return Path(base) / LEGACY_APP_FOLDER / CONFIG_FILENAME


def load_config(path: Path | None = None) -> AppConfig:
    target = path or config_path()
    migrating_legacy_config = False
    if path is None and not target.exists():
        legacy = legacy_config_path()
        if legacy.exists():
            target = legacy
            migrating_legacy_config = True
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return AppConfig()
        config = AppConfig.from_dict(raw)
        if migrating_legacy_config:
            try:
                save_config(config)
            except OSError:
                # The legacy settings are still usable even if copying them to
                # the new FellSplit Pro folder is temporarily not possible.
                pass
        return config
    except (OSError, json.JSONDecodeError, UnicodeError):
        return AppConfig()


def save_config(config: AppConfig, path: Path | None = None) -> None:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    temp.write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp, target)
