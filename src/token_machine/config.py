"""Configuration defaults."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from token_machine.utils.paths import user_data_dir

DEFAULT_STORE = user_data_dir()


def default_zed_threads_db() -> Path:
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Zed"
            / "threads"
            / "threads.db"
        )
    if sys.platform.startswith("win"):
        return Path.home() / "AppData" / "Local" / "Zed" / "threads" / "threads.db"
    return Path.home() / ".local" / "share" / "zed" / "threads" / "threads.db"


def default_opencode_db() -> Path:
    return Path.home() / ".local" / "share" / "opencode" / "opencode.db"


DEFAULT_WATCH_PATHS = (
    Path.home() / ".codex",
    Path.home() / ".claude",
    Path.home() / ".gemini",
    default_opencode_db(),
    default_zed_threads_db(),
)


@dataclass(frozen=True)
class AppConfig:
    store: Path = DEFAULT_STORE
    watch_paths: tuple[Path, ...] = field(default_factory=lambda: DEFAULT_WATCH_PATHS)
    host: str = "127.0.0.1"
    port: int = 8765
    watch_interval: int = 30
