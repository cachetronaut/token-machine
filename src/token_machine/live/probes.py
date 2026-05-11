"""Source-specific live usage probes."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Mapping, cast

from token_machine.live.models import (
    LiveContextWindow,
    LiveProbeStatus,
    LiveRateLimit,
    LiveSnapshotOrigin,
    LiveToolCall,
    LiveUsageSnapshot,
)
from token_machine.models import AgentSource, TokenUsage, safe_int
from token_machine.sources.base import (
    clean_command,
    mapping_value,
    session_id_from_path,
    string_value,
)
from token_machine.sources.gemini import _gemini_command_from_tool, _gemini_project_path
from token_machine.utils.time import utc_now


def codex_snapshot(
    path: Path, objects: Sequence[Mapping[str, object]]
) -> LiveUsageSnapshot | None:
    session_id = session_id_from_path(path)
    project_path = ""
    model = ""
    updated_at = ""
    user_count = 0
    last_user_at = ""
    latest_usage = TokenUsage()
    session_usage = TokenUsage()
    context = LiveContextWindow(origin=LiveSnapshotOrigin.MISSING.value)
    tool_calls: dict[str, LiveToolCall] = {}
    tools_seen = 0

    for obj in objects:
        timestamp = string_value(obj, "timestamp")
        if timestamp:
            updated_at = timestamp
        payload = mapping_value(obj, "payload")
        obj_type = string_value(obj, "type")

        if obj_type == "session_meta":
            session_id = string_value(payload, "id", session_id)
            project_path = string_value(payload, "cwd", project_path)
            continue

        if obj_type == "turn_context":
            model = string_value(payload, "model", model)
            project_path = string_value(payload, "cwd", project_path)
            user_count += 1
            last_user_at = timestamp or last_user_at
            continue

        if obj_type == "response_item":
            response_type = string_value(payload, "type")
            if response_type in {"function_call", "custom_tool_call"}:
                call_id = string_value(payload, "call_id") or f"tool-{tools_seen}"
                name = string_value(payload, "name")
                tool_calls[call_id] = LiveToolCall(
                    name=name,
                    status="current",
                    command=_codex_command(payload),
                    started_at=timestamp,
                    updated_at=timestamp,
                )
                tools_seen += 1
            elif response_type == "function_call_output":
                call_id = string_value(payload, "call_id")
                if call_id in tool_calls:
                    previous = tool_calls[call_id]
                    tool_calls[call_id] = LiveToolCall(
                        name=previous.name,
                        status="complete",
                        command=previous.command,
                        started_at=previous.started_at,
                        updated_at=timestamp,
                    )
            continue

        if obj_type != "event_msg" or string_value(payload, "type") != "token_count":
            continue

        info = mapping_value(payload, "info")
        latest_usage = TokenUsage.from_mapping(
            _optional_mapping(info.get("last_token_usage"))
        )
        session_usage = TokenUsage.from_mapping(
            _optional_mapping(info.get("total_token_usage"))
        )
        window_tokens = safe_int(info.get("model_context_window"))
        used_tokens = latest_usage.context_tokens
        used_percent = int((used_tokens / window_tokens) * 100) if window_tokens else 0
        context = LiveContextWindow(
            window_tokens=window_tokens,
            used_tokens=used_tokens,
            used_percent=used_percent,
            origin=LiveSnapshotOrigin.TRANSCRIPT.value,
        )

    if not updated_at and not objects:
        return None

    visible_tools = sorted(
        tool_calls.values(), key=lambda item: item.updated_at or item.started_at
    )[-8:]
    return LiveUsageSnapshot(
        source=AgentSource.CODEX,
        session_id=session_id,
        source_path=str(path),
        project_path=project_path,
        model=model,
        updated_at=updated_at,
        observed_at=utc_now(),
        status=LiveProbeStatus.ACTIVE,
        user_queries={"count": user_count, "last_at": last_user_at},
        context=context,
        current_metrics={
            "latest_turn_tokens": latest_usage.total_tokens,
            "session_total_tokens": session_usage.total_tokens,
            "input_tokens": latest_usage.input_tokens,
            "cached_input_tokens": latest_usage.cached_input_tokens,
            "cache_creation_input_tokens": latest_usage.cache_creation_input_tokens,
            "output_tokens": latest_usage.output_tokens,
            "reasoning_output_tokens": latest_usage.reasoning_output_tokens,
            "events_seen": len(objects),
            "tools_seen": tools_seen,
        },
        live_tool_calls=visible_tools,
        rate_limits=_codex_rate_limits(objects),
        token_usage=latest_usage,
        origin=LiveSnapshotOrigin.TRANSCRIPT.value,
    )


def claude_snapshot(
    path: Path, objects: Sequence[Mapping[str, object]]
) -> LiveUsageSnapshot | None:
    session_id = session_id_from_path(path)
    project_path = ""
    model = ""
    updated_at = ""
    user_count = 0
    last_user_at = ""
    latest_usage = TokenUsage()
    session_total = 0
    tools: list[LiveToolCall] = []

    for obj in objects:
        timestamp = string_value(obj, "timestamp")
        if timestamp:
            updated_at = timestamp
        session_id = string_value(obj, "sessionId", session_id)
        project_path = string_value(obj, "cwd", project_path)
        message = mapping_value(obj, "message")
        role = string_value(message, "role") or string_value(obj, "type")
        if role == "user":
            user_count += 1
            last_user_at = timestamp or last_user_at
        if role != "assistant":
            continue
        model = string_value(message, "model") or string_value(obj, "model", model)
        usage = TokenUsage.from_mapping(_optional_mapping(message.get("usage")))
        if usage.total_tokens:
            latest_usage = usage
            session_total += usage.total_tokens
        for tool in _claude_tools(message.get("content")):
            tool_input = mapping_value(tool, "input")
            tools.append(
                LiveToolCall(
                    name=string_value(tool, "name"),
                    status="observed",
                    command=clean_command(
                        string_value(tool_input, "cmd")
                        or string_value(tool_input, "command")
                    ),
                    updated_at=timestamp,
                )
            )

    if not updated_at and not objects:
        return None

    return LiveUsageSnapshot(
        source=AgentSource.CLAUDE_CODE,
        session_id=session_id,
        source_path=str(path),
        project_path=project_path,
        model=model,
        updated_at=updated_at,
        observed_at=utc_now(),
        status=LiveProbeStatus.ACTIVE,
        user_queries={"count": user_count, "last_at": last_user_at},
        context=_context_from_usage(latest_usage),
        current_metrics=_metrics(latest_usage, session_total, len(objects), len(tools)),
        live_tool_calls=tools[-8:],
        token_usage=latest_usage,
        origin=LiveSnapshotOrigin.TRANSCRIPT.value,
    )


def gemini_snapshot(
    path: Path, objects: Sequence[Mapping[str, object]]
) -> LiveUsageSnapshot | None:
    records = _gemini_records(objects)
    if not records:
        return None

    session_id = str(records[0].get("sessionId") or session_id_from_path(path))
    project_path = _gemini_project_path(path)
    model = ""
    updated_at = ""
    user_count = 0
    last_user_at = ""
    latest_usage = TokenUsage()
    session_total = 0
    tools: list[LiveToolCall] = []

    for record in records:
        timestamp = (
            string_value(record, "timestamp")
            or string_value(record, "startTime")
            or string_value(record, "lastUpdated")
        )
        if timestamp:
            updated_at = timestamp
        session_id = str(record.get("sessionId") or session_id)
        record_type = string_value(record, "type")
        if record_type == "user":
            user_count += 1
            last_user_at = timestamp or last_user_at
            continue
        if record_type not in {"gemini", "assistant"}:
            continue
        model = string_value(record, "model", model)
        usage = TokenUsage.from_mapping(_optional_mapping(record.get("tokens")))
        if usage.total_tokens:
            latest_usage = usage
            session_total += usage.total_tokens
        for tool in _mapping_list(record.get("toolCalls")):
            tools.append(
                LiveToolCall(
                    name=string_value(tool, "name"),
                    status="observed",
                    command=clean_command(_gemini_command_from_tool(tool)),
                    updated_at=string_value(tool, "timestamp") or timestamp,
                )
            )

    return LiveUsageSnapshot(
        source=AgentSource.GEMINI,
        session_id=session_id,
        source_path=str(path),
        project_path=project_path,
        model=model,
        updated_at=updated_at,
        observed_at=utc_now(),
        status=LiveProbeStatus.ACTIVE,
        user_queries={"count": user_count, "last_at": last_user_at},
        context=_context_from_usage(latest_usage),
        current_metrics=_metrics(latest_usage, session_total, len(records), len(tools)),
        live_tool_calls=tools[-8:],
        token_usage=latest_usage,
        origin=LiveSnapshotOrigin.TRANSCRIPT.value,
    )


def _codex_rate_limits(objects: Sequence[Mapping[str, object]]) -> list[LiveRateLimit]:
    rate_limits: list[LiveRateLimit] = []
    for obj in reversed(objects):
        payload = mapping_value(obj, "payload")
        if string_value(obj, "type") != "event_msg":
            continue
        if string_value(payload, "type") != "token_count":
            continue
        raw_rate_limits = mapping_value(payload, "rate_limits")
        for name in ("primary", "secondary", "credits"):
            limit = mapping_value(raw_rate_limits, name)
            if not limit:
                continue
            rate_limits.append(
                LiveRateLimit(
                    name=name,
                    used_percent=safe_int(
                        limit.get("used_percentage")
                        or limit.get("percent")
                        or limit.get("used_percent")
                    ),
                    resets_at=str(
                        limit.get("resets_at") or limit.get("reset_at") or ""
                    ),
                    limit_id=str(raw_rate_limits.get("limit_id", "")),
                    plan_type=str(raw_rate_limits.get("plan_type", "")),
                    origin=LiveSnapshotOrigin.TRANSCRIPT.value,
                )
            )
        break
    return rate_limits


def _codex_command(payload: Mapping[str, object]) -> str:
    raw_arguments = payload.get("arguments") or payload.get("input")
    if not isinstance(raw_arguments, str):
        return ""
    if '"cmd"' not in raw_arguments and '"command"' not in raw_arguments:
        return ""
    import json

    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, Mapping):
        return ""
    return clean_command(str(parsed.get("cmd") or parsed.get("command") or ""))


def _context_from_usage(usage: TokenUsage) -> LiveContextWindow:
    return LiveContextWindow(
        used_tokens=usage.context_tokens,
        origin=LiveSnapshotOrigin.COMPUTED.value
        if usage.context_tokens
        else LiveSnapshotOrigin.MISSING.value,
    )


def _metrics(
    usage: TokenUsage, session_total: int, events_seen: int, tools_seen: int
) -> dict[str, int | str]:
    return {
        "latest_turn_tokens": usage.total_tokens,
        "session_total_tokens": session_total,
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cached_input_tokens,
        "cache_creation_input_tokens": usage.cache_creation_input_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_output_tokens": usage.reasoning_output_tokens,
        "events_seen": events_seen,
        "tools_seen": tools_seen,
    }


def _optional_mapping(value: object) -> Mapping[str, object] | None:
    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else None


def _mapping_list(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    return [
        cast(Mapping[str, object], item) for item in value if isinstance(item, Mapping)
    ]


def _claude_tools(content: object) -> list[Mapping[str, object]]:
    if not isinstance(content, list):
        return []
    tools: list[Mapping[str, object]] = []
    for item in content:
        if not isinstance(item, Mapping):
            continue
        tool = cast(Mapping[str, object], item)
        if tool.get("type") == "tool_use":
            tools.append(tool)
    return tools


def _gemini_records(
    objects: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    if len(objects) == 1 and isinstance(objects[0].get("messages"), list):
        session = {key: value for key, value in objects[0].items() if key != "messages"}
        messages = _mapping_list(objects[0].get("messages"))
        return [session, *messages]
    return [obj for obj in objects if "$set" not in obj]
