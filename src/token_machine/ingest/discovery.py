"""File discovery and source detection."""

from __future__ import annotations

from pathlib import Path

from token_machine.models import AgentSource
from token_machine.sources import DEFAULT_SOURCES
from token_machine.sources.base import SessionSource, load_json_records


def discover_files(
    targets: list[Path], sources: tuple[SessionSource, ...] = DEFAULT_SOURCES
) -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    for target in targets:
        for source in sources:
            for path in source.discover_files(target):
                if path not in seen:
                    seen.add(path)
                    files.append(path)
    return sorted(files)


def detect_source(
    path: Path, sources: tuple[SessionSource, ...] = DEFAULT_SOURCES
) -> tuple[SessionSource | None, list[dict[str, object]]]:
    objects = [dict(item) for item in load_json_records(path)]
    for source in sources:
        if source.detect(objects, path):
            return source, objects
    return None, objects


def source_names(
    sources: tuple[SessionSource, ...] = DEFAULT_SOURCES,
) -> list[AgentSource]:
    return [source.name for source in sources]
