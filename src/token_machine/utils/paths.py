"""Path helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def user_data_dir(app_name: str = "token-machine") -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_name
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if root:
            return Path(root) / app_name
    root = os.environ.get("XDG_DATA_HOME")
    if root:
        return Path(root) / app_name
    return Path.home() / ".local" / "share" / app_name


def short_path(path: str) -> str:
    if not path:
        return ""
    return path.replace(str(Path.home()), "~", 1)
