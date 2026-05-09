"""OpenCode local SQLite source adapter."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping, cast

from token_machine.config import default_opencode_db
from token_machine.models import (
    AgentSource,
    AnalyticsEvent,
    EventType,
    TokenUsage,
    safe_int,
)
from token_machine.sources.base import make_event, metadata, string_value


class OpenCodeSource:
    name = AgentSource.OPENCODE

    def default_paths(self) -> tuple[Path, ...]:
        return (default_opencode_db(),)

    def discover_files(self, root: Path) -> list[Path]:
        if root.is_file() and root.name == "opencode.db":
            return [root]
        if not root.exists():
            return []
        candidate = root / "opencode.db"
        return [candidate] if candidate.is_file() else []

    def detect(self, objects: Sequence[Mapping[str, object]], path: Path) -> bool:
        return path.name == "opencode.db"

    def parse(
        self, path: Path, objects: Sequence[Mapping[str, object]]
    ) -> list[AnalyticsEvent]:
        return parse_opencode_db(path, self.name)


def parse_opencode_db(path: Path, source: AgentSource) -> list[AnalyticsEvent]:
    events: list[AnalyticsEvent] = []
    with closing(_readonly_db(path)) as db:
        for session_index, session in enumerate(_session_rows(db)):
            session_id = string_value(session, "id")
            project_path = (
                string_value(session, "directory")
                or string_value(session, "worktree")
                or string_value(session, "path")
            )
            session_messages = _message_rows(db, session_id)
            model = _first_model(session_messages)
            timestamp = _timestamp(session.get("time_created"))
            events.append(
                make_event(
                    source=source,
                    source_path=path,
                    session_id=session_id,
                    event_type=EventType.SESSION_META,
                    position=session_index * 100_000,
                    timestamp=timestamp,
                    project_path=project_path,
                    model=model,
                    event_metadata=metadata(
                        title=session.get("title", ""),
                        slug=session.get("slug", ""),
                        version=session.get("version", ""),
                        project_id=session.get("project_id", ""),
                        project_name=session.get("project_name", ""),
                    ),
                )
            )
            events.extend(
                _session_events(
                    source=source,
                    source_path=path,
                    session_id=session_id,
                    project_path=project_path,
                    default_model=model,
                    messages=session_messages,
                    parts=_part_rows(db, session_id),
                    base_position=session_index * 100_000,
                )
            )
    return events


def _readonly_db(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    db.row_factory = sqlite3.Row
    return db


def _session_rows(db: sqlite3.Connection) -> list[dict[str, object]]:
    rows = db.execute(
        """
        select
            session.id,
            session.project_id,
            session.slug,
            session.directory,
            session.title,
            session.version,
            session.time_created,
            session.time_updated,
            session.path,
            project.worktree,
            project.name as project_name
        from session
        left join project on project.id = session.project_id
        order by session.time_updated desc
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _message_rows(db: sqlite3.Connection, session_id: str) -> list[dict[str, object]]:
    rows = db.execute(
        """
        select id, session_id, time_created, time_updated, data
        from message
        where session_id = ?
        order by time_created, id
        """,
        (session_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _part_rows(db: sqlite3.Connection, session_id: str) -> list[dict[str, object]]:
    rows = db.execute(
        """
        select id, message_id, session_id, time_created, time_updated, data
        from part
        where session_id = ?
        order by time_created, id
        """,
        (session_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _session_events(
    *,
    source: AgentSource,
    source_path: Path,
    session_id: str,
    project_path: str,
    default_model: str,
    messages: list[dict[str, object]],
    parts: list[dict[str, object]],
    base_position: int,
) -> list[AnalyticsEvent]:
    events: list[AnalyticsEvent] = []
    for index, message in enumerate(messages, start=1):
        data = _json_data(message.get("data"))
        model = _model_name(data) or default_model
        timestamp = _timestamp(message.get("time_created")) or _message_time(data)
        role = string_value(data, "role")
        message_id = string_value(message, "id")
        events.append(
            make_event(
                source=source,
                source_path=source_path,
                session_id=session_id,
                event_type=EventType.MESSAGE,
                position=base_position + index,
                timestamp=timestamp,
                project_path=project_path,
                model=model,
                event_metadata=metadata(
                    role=role,
                    message_id=message_id,
                    provider_id=data.get("providerID", ""),
                    model_id=data.get("modelID", ""),
                    mode=data.get("mode", ""),
                    agent=data.get("agent", ""),
                ),
            )
        )
        usage = _token_usage(data)
        if usage.total_tokens:
            events.append(
                make_event(
                    source=source,
                    source_path=source_path,
                    session_id=session_id,
                    event_type=EventType.MODEL_CALL,
                    position=base_position + index,
                    timestamp=timestamp,
                    project_path=project_path,
                    model=model,
                    token_usage=usage,
                    event_metadata=metadata(
                        message_id=message_id,
                        provider_id=data.get("providerID", ""),
                        model_id=data.get("modelID", ""),
                        cost=data.get("cost", ""),
                    ),
                )
            )

    part_base_position = base_position + 50_000
    for index, part in enumerate(parts):
        data = _json_data(part.get("data"))
        if string_value(data, "type") != "tool":
            continue
        tool_name = string_value(data, "tool")
        state = _mapping(data.get("state"))
        tool_input = _mapping(state.get("input"))
        command = string_value(tool_input, "command")
        timestamp = _timestamp(part.get("time_created")) or _message_time(data)
        position = part_base_position + index
        tool_description = string_value(tool_input, "description") or string_value(
            state, "title"
        )
        events.append(
            make_event(
                source=source,
                source_path=source_path,
                session_id=session_id,
                event_type=EventType.TOOL_CALL,
                position=position,
                timestamp=timestamp,
                project_path=project_path,
                model=default_model,
                tool_name=tool_name,
                tool_description=tool_description,
                command=command,
                event_metadata=metadata(
                    part_id=part.get("id", ""),
                    message_id=part.get("message_id", ""),
                    call_id=data.get("callID", ""),
                    status=state.get("status", ""),
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
                    position=position,
                    timestamp=timestamp,
                    project_path=project_path,
                    model=default_model,
                    tool_name=tool_name,
                    command=command,
                )
            )
    return events


def _first_model(messages: list[dict[str, object]]) -> str:
    for message in messages:
        data = _json_data(message.get("data"))
        model = _model_name(data)
        if model:
            return model
    return ""


def _model_name(data: Mapping[str, object]) -> str:
    provider_id = string_value(data, "providerID")
    model_id = string_value(data, "modelID") or string_value(data, "model")
    if provider_id and model_id:
        return (
            model_id
            if model_id.startswith(f"{provider_id}/")
            else f"{provider_id}/{model_id}"
        )
    return model_id


def _token_usage(data: Mapping[str, object]) -> TokenUsage:
    tokens = _mapping(data.get("tokens"))
    input_tokens = safe_int(tokens.get("input"))
    cached_input_tokens = safe_int(tokens.get("cache", tokens.get("cached")))
    output_tokens = safe_int(tokens.get("output"))
    reasoning_tokens = safe_int(tokens.get("reasoning"))
    total_tokens = safe_int(tokens.get("total")) or (
        input_tokens + cached_input_tokens + output_tokens + reasoning_tokens
    )
    return TokenUsage(
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        reasoning_output_tokens=reasoning_tokens,
        total_tokens=total_tokens,
    )


def _timestamp(value: object) -> str:
    milliseconds = safe_int(value)
    if not milliseconds:
        return ""
    seconds = milliseconds / 1000 if milliseconds > 10_000_000_000 else milliseconds
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace("+00:00", "Z")


def _message_time(data: Mapping[str, object]) -> str:
    return _timestamp(data.get("time")) or string_value(data, "time")


def _json_data(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return cast(Mapping[str, object], parsed) if isinstance(parsed, Mapping) else {}


def _mapping(value: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else {}
