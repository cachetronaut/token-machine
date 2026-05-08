"""Configuration defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from token_machine.utils.paths import user_data_dir

DEFAULT_STORE = user_data_dir()
DEFAULT_WATCH_PATHS = (
    Path.home() / ".codex",
    Path.home() / ".claude",
    Path.home() / ".gemini",
)


@dataclass(frozen=True)
class AppConfig:
    store: Path = DEFAULT_STORE
    watch_paths: tuple[Path, ...] = field(default_factory=lambda: DEFAULT_WATCH_PATHS)
    host: str = "127.0.0.1"
    port: int = 8765
    watch_interval: int = 30
