"""Source adapter contracts and shared parser helpers."""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Sequence
from pathlib import Path
from typing import Mapping, Protocol, cast

from token_machine.models import (
    AgentSource,
    AnalyticsEvent,
    EventType,
    JsonValue,
    TokenUsage,
)
from token_machine.utils.ids import stable_event_id


class SessionSource(Protocol):
    name: AgentSource

    def default_paths(self) -> tuple[Path, ...]: ...

    def discover_files(self, root: Path) -> list[Path]: ...

    def detect(self, objects: Sequence[Mapping[str, object]], path: Path) -> bool: ...

    def parse(
        self, path: Path, objects: Sequence[Mapping[str, object]]
    ) -> list[AnalyticsEvent]: ...


def load_json_records(path: Path) -> list[Mapping[str, object]]:
    records: list[Mapping[str, object]] = []
    with path.open("r", encoding="utf-8") as file:
        if path.suffix == ".json":
            data = json.load(file)
            candidates = data if isinstance(data, list) else [data]
            return [item for item in candidates if isinstance(item, Mapping)]
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                item = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(item, Mapping):
                records.append(item)
    return records


def discover_jsonl_files(root: Path) -> list[Path]:
    if root.is_file() and root.suffix in {".json", ".jsonl"}:
        return [root]
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.jsonl") if path.is_file())


def session_id_from_path(path: Path) -> str:
    return path.stem


def clean_command(command: str) -> str:
    return re.sub(r"\s+", " ", command).strip()


def executable_from_command(command: str) -> str:
    cleaned = clean_command(command)
    if not cleaned:
        return ""
    try:
        parts = shlex.split(cleaned)
    except ValueError:
        parts = cleaned.split()
    if not parts:
        return ""
    if parts[0] in {"env", "/usr/bin/env"} and len(parts) > 1:
        for part in parts[1:]:
            if "=" not in part:
                return Path(part).name
    if parts[0] in {"bash", "zsh", "sh", "/bin/bash", "/bin/zsh", "/bin/sh"}:
        for option in ("-lc", "-c"):
            if option in parts:
                index = parts.index(option)
                if index + 1 < len(parts):
                    return executable_from_command(parts[index + 1])
    return Path(parts[0]).name


def cli_from_command(command: str) -> str:
    return executable_from_command(command)


def mapping_value(data: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = data.get(key)
    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else {}


def string_value(data: Mapping[str, object], key: str, default: str = "") -> str:
    value = data.get(key)
    return value if isinstance(value, str) else default


def list_value(data: Mapping[str, object], key: str) -> list[object]:
    value = data.get(key)
    return cast(list[object], value) if isinstance(value, list) else []


def metadata(**values: object) -> dict[str, JsonValue]:
    output: dict[str, JsonValue] = {}
    for key, value in values.items():
        if isinstance(value, str | int | float | bool) or value is None:
            output[key] = value
        elif isinstance(value, Mapping):
            output[key] = metadata(
                **{str(inner_key): inner for inner_key, inner in value.items()}
            )
        elif isinstance(value, list):
            output[key] = [
                item
                if isinstance(item, str | int | float | bool) or item is None
                else str(item)
                for item in value
            ]
        else:
            output[key] = str(value)
    return output


def make_event(
    *,
    source: AgentSource,
    source_path: Path,
    session_id: str,
    event_type: EventType,
    position: int,
    timestamp: str = "",
    project_path: str = "",
    model: str = "",
    tool_name: str = "",
    tool_description: str = "",
    skill_name: str = "",
    skill_description: str = "",
    command: str = "",
    token_usage: TokenUsage | None = None,
    event_metadata: dict[str, JsonValue] | None = None,
) -> AnalyticsEvent:
    cli_name = executable_from_command(command)
    return AnalyticsEvent(
        event_id=stable_event_id(
            source_path,
            session_id,
            event_type.value,
            position,
            timestamp,
            tool_name,
            skill_name,
            command,
        ),
        event_type=event_type,
        source=source,
        source_path=str(source_path),
        session_id=session_id,
        timestamp=timestamp,
        project_path=project_path,
        model=model,
        tool_name=tool_name,
        tool_description=tool_description,
        skill_name=skill_name,
        skill_description=skill_description,
        cli_name=cli_name,
        command=clean_command(command),
        token_usage=token_usage or TokenUsage(),
        metadata=event_metadata or {},
    )
