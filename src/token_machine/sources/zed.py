"""Zed Agent Panel thread source adapter."""

from __future__ import annotations

import json
import sqlite3
from io import BytesIO
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Mapping, cast

import zstandard as zstd

from token_machine.config import default_zed_threads_db
from token_machine.models import AgentSource, AnalyticsEvent, EventType, TokenUsage
from token_machine.sources.base import make_event, metadata, string_value


class ZedSource:
    name = AgentSource.ZED

    def default_paths(self) -> tuple[Path, ...]:
        return (default_zed_threads_db(),)

    def discover_files(self, root: Path) -> list[Path]:
        if root.is_file() and root.name == "threads.db":
            return [root]
        if not root.exists():
            return []
        candidates = (root / "threads.db", root / "threads" / "threads.db")
        return [path for path in candidates if path.is_file()]

    def detect(self, objects: Sequence[Mapping[str, object]], path: Path) -> bool:
        return path.name == "threads.db"

    def parse(
        self, path: Path, objects: Sequence[Mapping[str, object]]
    ) -> list[AnalyticsEvent]:
        return parse_zed_threads_db(path, self.name)


def parse_zed_threads_db(path: Path, source: AgentSource) -> list[AnalyticsEvent]:
    events: list[AnalyticsEvent] = []
    for row in _zed_thread_rows(path):
        session_id = str(row["id"])
        updated_at = str(row.get("updated_at") or "")
        created_at = str(row.get("created_at") or "")
        stable_timestamp = created_at or updated_at
        try:
            thread = decode_zed_thread(str(row["data_type"]), row["data"])
        except UnicodeDecodeError, json.JSONDecodeError, zstd.ZstdError:
            continue

        model = zed_model_name(thread)
        project_path = zed_project_path(thread)
        events.append(
            make_event(
                source=source,
                source_path=path,
                session_id=session_id,
                event_type=EventType.SESSION_META,
                position=0,
                timestamp=stable_timestamp,
                project_path=project_path,
                model=model,
                event_metadata=metadata(
                    summary=row.get("summary", ""),
                    title=thread.get("title", ""),
                    created_at=created_at,
                    updated_at=thread.get("updated_at") or updated_at,
                    parent_id=row.get("parent_id", ""),
                    zed_data_type=row.get("data_type", ""),
                    version=thread.get("version", ""),
                    imported=thread.get("imported", False),
                    profile=thread.get("profile", ""),
                    speed=thread.get("speed", ""),
                    thinking_enabled=thread.get("thinking_enabled", False),
                    thinking_effort=thread.get("thinking_effort", ""),
                ),
            )
        )
        events.extend(
            parse_zed_thread_events(
                source=source,
                source_path=path,
                session_id=session_id,
                thread=thread,
                fallback_timestamp=stable_timestamp,
                project_path=project_path,
                model=model,
            )
        )
    return events


def _zed_thread_rows(path: Path) -> list[dict[str, object]]:
    uri = f"file:{path}?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        db.row_factory = sqlite3.Row
        columns = {
            str(row["name"])
            for row in db.execute("pragma table_info(threads)").fetchall()
        }
        optional_columns = [
            column
            for column in ("parent_id", "folder_paths", "created_at")
            if column in columns
        ]
        selected = [
            "id",
            "summary",
            "updated_at",
            "data_type",
            "data",
            *optional_columns,
        ]
        rows = db.execute(
            f"select {', '.join(selected)} from threads order by updated_at desc"
        ).fetchall()
    return [dict(row) for row in rows]


def decode_zed_thread(data_type: str, blob: object) -> Mapping[str, object]:
    if isinstance(blob, memoryview):
        raw_data = blob.tobytes()
    elif isinstance(blob, bytes):
        raw_data = blob
    elif isinstance(blob, str):
        raw_data = blob.encode("utf-8")
    else:
        raw_data = b""

    if data_type == "zstd":
        with zstd.ZstdDecompressor().stream_reader(BytesIO(raw_data)) as reader:
            raw_data = reader.read()

    decoded = json.loads(raw_data.decode("utf-8"))
    return cast(Mapping[str, object], decoded) if isinstance(decoded, Mapping) else {}


def zed_model_name(thread: Mapping[str, object]) -> str:
    model = thread.get("model")
    if isinstance(model, str):
        return model
    if not isinstance(model, Mapping):
        return ""
    model_map = cast(Mapping[str, object], model)

    for key in ("model", "id", "name", "display_name"):
        value = model_map.get(key)
        if isinstance(value, str) and value:
            return value

    provider = model_map.get("provider")
    model_id = model_map.get("model_id") or model_map.get("id")
    if isinstance(provider, str) and isinstance(model_id, str) and model_id:
        return f"{provider}/{model_id}"
    return ""


def zed_project_path(thread: Mapping[str, object]) -> str:
    snapshot = thread.get("initial_project_snapshot")
    if not isinstance(snapshot, Mapping):
        return ""
    snapshot_map = cast(Mapping[str, object], snapshot)

    worktree_snapshots = snapshot_map.get("worktree_snapshots")
    if isinstance(worktree_snapshots, list):
        for item in worktree_snapshots:
            if not isinstance(item, Mapping):
                continue
            item_map = cast(Mapping[str, object], item)
            worktree_path = item_map.get("worktree_path")
            if isinstance(worktree_path, str) and worktree_path:
                return worktree_path

    for key in ("root_path", "worktree_root_path", "path"):
        value = snapshot_map.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def parse_zed_thread_events(
    *,
    source: AgentSource,
    source_path: Path,
    session_id: str,
    thread: Mapping[str, object],
    fallback_timestamp: str,
    project_path: str,
    model: str,
) -> list[AnalyticsEvent]:
    messages = thread.get("messages")
    if not isinstance(messages, list):
        return _cumulative_usage_events(
            source=source,
            source_path=source_path,
            session_id=session_id,
            thread=thread,
            fallback_timestamp=fallback_timestamp,
            project_path=project_path,
            model=model,
            request_usage_emitted=False,
        )

    events: list[AnalyticsEvent] = []
    request_usage = thread.get("request_token_usage")
    request_usage_map = (
        cast(Mapping[str, object], request_usage)
        if isinstance(request_usage, Mapping)
        else {}
    )
    used_request_ids: set[str] = set()

    for index, message in enumerate(messages, start=1):
        if not isinstance(message, Mapping):
            continue

        message_map = cast(Mapping[str, object], message)
        role, content, message_id = zed_message_parts(message_map)
        timestamp = zed_message_timestamp(message_map) or fallback_timestamp

        events.append(
            make_event(
                source=source,
                source_path=source_path,
                session_id=session_id,
                event_type=EventType.MESSAGE,
                position=index,
                timestamp=timestamp,
                project_path=project_path,
                model=model,
                event_metadata=metadata(role=role, message_id=message_id),
            )
        )

        usage = zed_usage_for_request(message_id, request_usage_map)
        if usage.total_tokens:
            used_request_ids.add(message_id)
            events.append(
                make_event(
                    source=source,
                    source_path=source_path,
                    session_id=session_id,
                    event_type=EventType.MODEL_CALL,
                    position=index,
                    timestamp=timestamp,
                    project_path=project_path,
                    model=model,
                    token_usage=usage,
                    event_metadata=metadata(request_id=message_id),
                )
            )

        for tool_index, tool in enumerate(zed_tool_uses(content)):
            tool_name = string_value(tool, "name")
            command = zed_command_from_tool_input(
                tool.get("input"), tool.get("raw_input")
            )
            event_position = (index * 1000) + tool_index
            events.append(
                make_event(
                    source=source,
                    source_path=source_path,
                    session_id=session_id,
                    event_type=EventType.TOOL_CALL,
                    position=event_position,
                    timestamp=timestamp,
                    project_path=project_path,
                    model=model,
                    tool_name=tool_name,
                    command=command,
                    event_metadata=metadata(
                        tool_id=tool.get("id", ""),
                        is_input_complete=tool.get("is_input_complete", ""),
                    ),
                )
            )
            if command:
                events.append(
                    make_event(
                        source=source,
                        source_path=source_path,
                        session_id=session_id,
                        event_type=EventType.CLI_COMMAND,
                        position=event_position,
                        timestamp=timestamp,
                        project_path=project_path,
                        model=model,
                        tool_name=tool_name,
                        command=command,
                    )
                )

    events.extend(
        _unmatched_request_usage_events(
            source=source,
            source_path=source_path,
            session_id=session_id,
            request_usage_map=request_usage_map,
            used_request_ids=used_request_ids,
            fallback_timestamp=fallback_timestamp,
            project_path=project_path,
            model=model,
        )
    )
    request_usage_emitted = any(
        event.event_type == EventType.MODEL_CALL
        and event.metadata.get("usage_scope") != "cumulative"
        for event in events
    )
    events.extend(
        _cumulative_usage_events(
            source=source,
            source_path=source_path,
            session_id=session_id,
            thread=thread,
            fallback_timestamp=fallback_timestamp,
            project_path=project_path,
            model=model,
            request_usage_emitted=request_usage_emitted,
        )
    )
    return events


def zed_message_parts(
    message: Mapping[str, object],
) -> tuple[str, list[object], str]:
    if "User" in message and isinstance(message["User"], Mapping):
        body = cast(Mapping[str, object], message["User"])
        return "user", _list_value(body.get("content")), string_value(body, "id")
    if "Agent" in message and isinstance(message["Agent"], Mapping):
        body = cast(Mapping[str, object], message["Agent"])
        return "assistant", _list_value(body.get("content")), string_value(body, "id")

    role = str(message.get("role") or message.get("type") or "")
    return role, _list_value(message.get("content")), string_value(message, "id")


def zed_message_timestamp(message: Mapping[str, object]) -> str:
    for value in _message_body_values(message):
        if isinstance(value, Mapping):
            value_map = cast(Mapping[str, object], value)
            timestamp = value_map.get("timestamp") or value_map.get("created_at")
            if isinstance(timestamp, str) and timestamp:
                return timestamp
    return string_value(message, "timestamp") or string_value(message, "created_at")


def zed_usage_for_request(
    request_id: str, request_usage: Mapping[str, object]
) -> TokenUsage:
    usage = request_usage.get(request_id)
    return TokenUsage.from_mapping(
        cast(Mapping[str, object], usage) if isinstance(usage, Mapping) else None
    )


def zed_tool_uses(content: Iterable[object]) -> list[Mapping[str, object]]:
    tools: list[Mapping[str, object]] = []
    for item in content:
        if not isinstance(item, Mapping):
            continue
        item_map = cast(Mapping[str, object], item)
        tool_use = item_map.get("ToolUse")
        if isinstance(tool_use, Mapping):
            tools.append(cast(Mapping[str, object], tool_use))
            continue
        if item_map.get("type") in {"tool_use", "ToolUse"}:
            tools.append(item_map)
    return tools


def zed_command_from_tool_input(input_obj: object, raw_input: object) -> str:
    command = _command_from_mapping(input_obj)
    if command:
        return command

    if not isinstance(raw_input, str) or not raw_input:
        return ""
    try:
        parsed = json.loads(raw_input)
    except json.JSONDecodeError:
        return ""
    return _command_from_mapping(parsed)


def _unmatched_request_usage_events(
    *,
    source: AgentSource,
    source_path: Path,
    session_id: str,
    request_usage_map: Mapping[str, object],
    used_request_ids: set[str],
    fallback_timestamp: str,
    project_path: str,
    model: str,
) -> list[AnalyticsEvent]:
    events: list[AnalyticsEvent] = []
    position = 50_000
    for request_id, usage_data in request_usage_map.items():
        request_id_text = str(request_id)
        if request_id_text in used_request_ids:
            continue
        usage = TokenUsage.from_mapping(
            cast(Mapping[str, object], usage_data)
            if isinstance(usage_data, Mapping)
            else None
        )
        if not usage.total_tokens:
            continue
        events.append(
            make_event(
                source=source,
                source_path=source_path,
                session_id=session_id,
                event_type=EventType.MODEL_CALL,
                position=position,
                timestamp=fallback_timestamp,
                project_path=project_path,
                model=model,
                token_usage=usage,
                event_metadata=metadata(request_id=request_id_text),
            )
        )
        position += 1
    return events


def _cumulative_usage_events(
    *,
    source: AgentSource,
    source_path: Path,
    session_id: str,
    thread: Mapping[str, object],
    fallback_timestamp: str,
    project_path: str,
    model: str,
    request_usage_emitted: bool,
) -> list[AnalyticsEvent]:
    if request_usage_emitted:
        return []

    cumulative = thread.get("cumulative_token_usage")
    usage = TokenUsage.from_mapping(
        cast(Mapping[str, object], cumulative)
        if isinstance(cumulative, Mapping)
        else None
    )
    if not usage.total_tokens:
        return []
    return [
        make_event(
            source=source,
            source_path=source_path,
            session_id=session_id,
            event_type=EventType.MODEL_CALL,
            position=99_999,
            timestamp=fallback_timestamp,
            project_path=project_path,
            model=model,
            token_usage=usage,
            event_metadata=metadata(usage_scope="cumulative"),
        )
    ]


def _message_body_values(message: Mapping[str, object]) -> list[object]:
    values: list[object] = []
    for key in ("User", "Agent"):
        value = message.get(key)
        if value is not None:
            values.append(value)
    values.append(message)
    return values


def _list_value(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def _command_from_mapping(value: object) -> str:
    if not isinstance(value, Mapping):
        return ""
    value_map = cast(Mapping[str, object], value)
    for key in ("command", "cmd", "shell_command"):
        command = value_map.get(key)
        if isinstance(command, str) and command:
            return command
    return ""
