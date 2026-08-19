from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "Meta-Coder"
APP_SLUG = "meta-coder"
PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_MANUAL_PATH = PACKAGE_DIR / "config" / "default_coding_manual.yml"


def app_data_dir() -> Path:
    override = os.environ.get("META_CODER_HOME", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / APP_SLUG


def projects_dir() -> Path:
    return app_data_dir() / "projects"
