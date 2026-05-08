"""Gemini CLI session source adapter."""

from __future__ import annotations

import json
import shlex
from collections.abc import Sequence
from pathlib import Path
from typing import Mapping, cast

from token_machine.config import DEFAULT_WATCH_PATHS
from token_machine.models import AgentSource, AnalyticsEvent, EventType, TokenUsage
from token_machine.sources.base import (
    make_event,
    mapping_value,
    metadata,
    session_id_from_path,
    string_value,
)

GEMINI_PROJECTS_PATH = Path.home() / ".gemini" / "projects.json"


class GeminiSource:
    name = AgentSource.GEMINI

    def default_paths(self) -> tuple[Path, ...]:
        return (DEFAULT_WATCH_PATHS[2],)

    def discover_files(self, root: Path) -> list[Path]:
        if root.is_file() and root.suffix in {".json", ".jsonl"}:
            return [root]
        if not root.exists():
            return []
        if root.name == ".gemini":
            return sorted(
                path
                for path in (root / "tmp").glob("*/chats/session-*.json*")
                if path.is_file() and path.suffix in {".json", ".jsonl"}
            )
        return sorted(path for path in root.rglob("session-*.json*") if path.is_file())

    def detect(self, objects: Sequence[Mapping[str, object]], path: Path) -> bool:
        if ".gemini" in str(path):
            return True
        return any(
            "projectHash" in obj or obj.get("type") in {"gemini", "assistant"}
            for obj in objects[:20]
        )

    def parse(
        self, path: Path, objects: Sequence[Mapping[str, object]]
    ) -> list[AnalyticsEvent]:
        session_records = _gemini_session_records(objects)
        if not session_records:
            return []

        first_record = session_records[0]
        session_id = str(first_record.get("sessionId") or session_id_from_path(path))
        project_path = _gemini_project_path(path)
        model = ""
        events: list[AnalyticsEvent] = []

        for position, obj in enumerate(session_records):
            session_id = str(obj.get("sessionId") or session_id)
            timestamp = (
                string_value(obj, "timestamp")
                or string_value(obj, "startTime")
                or string_value(obj, "lastUpdated")
            )
            record_type = string_value(obj, "type")

            if obj.get("kind") == "main" or obj.get("startTime"):
                events.append(
                    make_event(
                        source=self.name,
                        source_path=path,
                        session_id=session_id,
                        event_type=EventType.SESSION_META,
                        position=position,
                        timestamp=timestamp,
                        project_path=project_path,
                        event_metadata=metadata(
                            project_hash=obj.get("projectHash", ""),
                            kind=obj.get("kind", ""),
                        ),
                    )
                )
                continue

            if record_type in {"user", "gemini", "assistant"}:
                role = "assistant" if record_type in {"gemini", "assistant"} else "user"
                events.append(
                    make_event(
                        source=self.name,
                        source_path=path,
                        session_id=session_id,
                        event_type=EventType.MESSAGE,
                        position=position,
                        timestamp=timestamp,
                        project_path=project_path,
                        model=model,
                        event_metadata=metadata(role=role),
                    )
                )

            if record_type not in {"gemini", "assistant"}:
                continue

            model = string_value(obj, "model", model)
            tokens = obj.get("tokens")
            usage = TokenUsage.from_mapping(
                cast(Mapping[str, object], tokens)
                if isinstance(tokens, Mapping)
                else None
            )
            if usage.total_tokens:
                events.append(
                    make_event(
                        source=self.name,
                        source_path=path,
                        session_id=session_id,
                        event_type=EventType.MODEL_CALL,
                        position=position,
                        timestamp=timestamp,
                        project_path=project_path,
                        model=model,
                        token_usage=usage,
                    )
                )

            for tool_index, tool in enumerate(_gemini_tool_calls(obj)):
                tool_name = string_value(tool, "name")
                command = _gemini_command_from_tool(tool)
                event_position = (position * 1000) + tool_index
                events.append(
                    make_event(
                        source=self.name,
                        source_path=path,
                        session_id=session_id,
                        event_type=EventType.TOOL_CALL,
                        position=event_position,
                        timestamp=string_value(tool, "timestamp") or timestamp,
                        project_path=project_path,
                        model=model,
                        tool_name=tool_name,
                        command=command,
                        event_metadata=metadata(
                            tool_id=tool.get("id", ""),
                            status=tool.get("status", ""),
                            display_name=tool.get("displayName", ""),
                        ),
                    )
                )
                if command:
                    events.append(
                        make_event(
                            source=self.name,
                            source_path=path,
                            session_id=session_id,
                            event_type=EventType.CLI_COMMAND,
                            position=event_position,
                            timestamp=string_value(tool, "timestamp") or timestamp,
                            project_path=project_path,
                            model=model,
                            tool_name=tool_name,
                            command=command,
                            event_metadata=metadata(tool_id=tool.get("id", "")),
                        )
                    )
        return events


def _gemini_session_records(
    objects: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    if len(objects) == 1 and isinstance(objects[0].get("messages"), list):
        session = {key: value for key, value in objects[0].items() if key != "messages"}
        messages_value = cast(list[object], objects[0].get("messages"))
        messages = [
            cast(Mapping[str, object], message)
            for message in messages_value
            if isinstance(message, Mapping)
        ]
        return [session, *_latest_gemini_messages(messages)]

    session_records: list[Mapping[str, object]] = []
    messages: list[Mapping[str, object]] = []
    for obj in objects:
        if "$set" in obj:
            continue
        if obj.get("kind") == "main" or obj.get("startTime"):
            session_records.append(obj)
        elif obj.get("id") or obj.get("messageId") is not None:
            messages.append(obj)
    return [*session_records[:1], *_latest_gemini_messages(messages)]


def _latest_gemini_messages(
    messages: list[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    latest: dict[str, Mapping[str, object]] = {}
    order: list[str] = []
    for message in messages:
        key = str(message.get("id") or message.get("messageId") or len(order))
        if key not in latest:
            order.append(key)
        latest[key] = message
    return [latest[key] for key in order]


def _gemini_project_path(path: Path) -> str:
    for parent in [path.parent, *path.parents]:
        marker = parent / ".project_root"
        if marker.exists():
            value = marker.read_text(encoding="utf-8", errors="ignore").strip()
            if value:
                return value
    project_slug = path.parents[1].name if len(path.parents) > 1 else ""
    project_map = _gemini_project_map()
    return next(
        (project for project, slug in project_map.items() if slug == project_slug), ""
    )


def _gemini_project_map() -> dict[str, str]:
    if not GEMINI_PROJECTS_PATH.exists():
        return {}
    try:
        data = json.loads(GEMINI_PROJECTS_PATH.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return {}
    projects = data.get("projects") if isinstance(data, Mapping) else {}
    if not isinstance(projects, Mapping):
        return {}
    return {str(project): str(slug) for project, slug in projects.items()}


def _gemini_tool_calls(obj: Mapping[str, object]) -> list[Mapping[str, object]]:
    tool_calls = obj.get("toolCalls")
    if not isinstance(tool_calls, list):
        return []
    return [
        cast(Mapping[str, object], tool)
        for tool in tool_calls
        if isinstance(tool, Mapping)
    ]


def _gemini_command_from_tool(tool: Mapping[str, object]) -> str:
    args = mapping_value(tool, "args")
    name = string_value(tool, "name")
    if name == "run_shell_command":
        return str(args.get("command") or args.get("cmd") or "")
    if name == "list_directory":
        path = str(args.get("dir_path") or args.get("path") or ".")
        return f"ls {shlex.quote(path)}"
    if name == "read_file":
        path = str(args.get("file_path") or args.get("path") or "")
        return f"cat {shlex.quote(path)}".strip()
    if name == "grep_search":
        pattern = str(args.get("pattern") or args.get("query") or "")
        path = str(args.get("path") or args.get("include") or ".")
        return f"rg {shlex.quote(pattern)} {shlex.quote(path)}".strip()
    return ""
