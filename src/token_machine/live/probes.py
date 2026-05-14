"""Source-specific live usage probes."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Mapping, cast

from token_machine.live.model_names import canonical_model_name
from token_machine.live.models import (
    LiveContextWindow,
    LiveCompaction,
    LiveProbeStatus,
    LiveRateLimit,
    LiveSnapshotOrigin,
    LiveSessionLimit,
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
from token_machine.sources.codex import _codex_skill_name_from_command
from token_machine.sources.gemini import _gemini_command_from_tool, _gemini_project_path
from token_machine.utils.time import utc_now

SESSION_NAME_MAX = 86
CLAUDE_CONTEXT_WINDOW_TOKENS = 200_000
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)
_XML_TAG_RE = re.compile(r"<[^>]+>")


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
    compaction = LiveCompaction(origin=LiveSnapshotOrigin.MISSING.value)

    for obj in objects:
        timestamp = string_value(obj, "timestamp")
        if timestamp:
            updated_at = timestamp
        payload = mapping_value(obj, "payload")
        obj_type = string_value(obj, "type")
        compaction = _latest_compaction(compaction, obj, timestamp)

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
                command = _codex_command(payload)
                skill_name = _codex_skill_name_from_command(command)
                tool_calls[call_id] = LiveToolCall(
                    name=skill_name or name,
                    status="current",
                    command=command,
                    kind="skill" if skill_name else _command_kind(command),
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
                        kind=previous.kind,
                        executable=previous.executable,
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
    rate_limits = _codex_rate_limits(objects)
    return LiveUsageSnapshot(
        source=AgentSource.CODEX,
        session_id=session_id,
        source_path=str(path),
        session_name=_session_name(path, objects),
        project_path=project_path,
        model=canonical_model_name(model),
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
        live_actions=visible_tools,
        rate_limits=rate_limits,
        session_limits=_session_limits_from_rate_limits(rate_limits),
        compaction=compaction,
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
    subagent_sessions = _claude_subagent_count(path)
    compaction = LiveCompaction(origin=LiveSnapshotOrigin.MISSING.value)

    for obj in objects:
        timestamp = string_value(obj, "timestamp")
        if timestamp:
            updated_at = timestamp
        compaction = _latest_compaction(compaction, obj, timestamp)
        session_id = string_value(obj, "sessionId", session_id)
        project_path = string_value(obj, "cwd", project_path)
        message = mapping_value(obj, "message")
        role = string_value(message, "role") or string_value(obj, "type")
        if role == "user" and _is_human_claude_prompt(message):
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
            command = clean_command(
                string_value(tool_input, "cmd") or string_value(tool_input, "command")
            )
            tools.append(
                LiveToolCall(
                    name=string_value(tool, "name"),
                    status="observed",
                    command=command,
                    kind=_command_kind(command),
                    updated_at=timestamp,
                )
            )

    if not updated_at and not objects:
        return None

    return LiveUsageSnapshot(
        source=AgentSource.CLAUDE_CODE,
        session_id=session_id,
        source_path=str(path),
        session_name=_session_name(path, objects),
        project_path=project_path,
        model=canonical_model_name(model),
        updated_at=updated_at,
        observed_at=utc_now(),
        status=LiveProbeStatus.ACTIVE,
        user_queries={"count": user_count, "last_at": last_user_at},
        context=_context_from_usage(
            latest_usage, window_tokens=CLAUDE_CONTEXT_WINDOW_TOKENS
        ),
        current_metrics={
            **_metrics(latest_usage, session_total, len(objects), len(tools)),
            "subagent_sessions": subagent_sessions,
        },
        live_tool_calls=tools[-8:],
        live_actions=tools[-8:],
        compaction=compaction,
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
    subagent_sessions = _gemini_subagent_count(records)
    compaction = LiveCompaction(origin=LiveSnapshotOrigin.MISSING.value)

    for record in records:
        timestamp = (
            string_value(record, "timestamp")
            or string_value(record, "startTime")
            or string_value(record, "lastUpdated")
        )
        if timestamp:
            updated_at = timestamp
        compaction = _latest_compaction(compaction, record, timestamp)
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
            command = clean_command(_gemini_command_from_tool(tool))
            tools.append(
                LiveToolCall(
                    name=string_value(tool, "name"),
                    status="observed",
                    command=command,
                    kind=_command_kind(command),
                    updated_at=string_value(tool, "timestamp") or timestamp,
                )
            )

    return LiveUsageSnapshot(
        source=AgentSource.GEMINI,
        session_id=session_id,
        source_path=str(path),
        session_name=_session_name(path, records),
        project_path=project_path,
        model=canonical_model_name(model),
        updated_at=updated_at,
        observed_at=utc_now(),
        status=LiveProbeStatus.ACTIVE,
        user_queries={"count": user_count, "last_at": last_user_at},
        context=_context_from_usage(latest_usage),
        current_metrics={
            **_metrics(latest_usage, session_total, len(records), len(tools)),
            "subagent_sessions": subagent_sessions,
        },
        live_tool_calls=tools[-8:],
        live_actions=tools[-8:],
        compaction=compaction,
        token_usage=latest_usage,
        origin=LiveSnapshotOrigin.TRANSCRIPT.value,
    )


def _codex_rate_limits(objects: Sequence[Mapping[str, object]]) -> list[LiveRateLimit]:
    for obj in reversed(objects):
        payload = mapping_value(obj, "payload")
        if string_value(obj, "type") != "event_msg":
            continue
        if string_value(payload, "type") != "token_count":
            continue
        raw_rate_limits = mapping_value(payload, "rate_limits")
        rate_limits: list[LiveRateLimit] = []
        for name in ("primary", "secondary", "credits"):
            limit = mapping_value(raw_rate_limits, name)
            if not limit:
                continue
            rate_limits.append(
                LiveRateLimit(
                    name=name,
                    used_percent=_used_percent_from_limit(limit),
                    resets_at=str(
                        limit.get("resets_at") or limit.get("reset_at") or ""
                    ),
                    limit_id=str(raw_rate_limits.get("limit_id", "")),
                    plan_type=str(raw_rate_limits.get("plan_type", "")),
                    origin=LiveSnapshotOrigin.TRANSCRIPT.value,
                )
            )
        if rate_limits:
            return rate_limits
    return []


def _session_limits_from_rate_limits(
    rate_limits: Sequence[LiveRateLimit],
) -> list[LiveSessionLimit]:
    limits: list[LiveSessionLimit] = []
    for limit in rate_limits:
        limits.append(
            LiveSessionLimit(
                name=limit.name,
                used_percent=limit.used_percent,
                remaining_percent=max(0, 100 - limit.used_percent),
                resets_at=limit.resets_at,
                origin=limit.origin,
            )
        )
    return limits


def _used_percent_from_limit(limit: Mapping[str, object]) -> int:
    used_percent = safe_int(
        limit.get("used_percentage")
        or limit.get("used_percent")
        or limit.get("percent_used")
        or limit.get("used")
    )
    if used_percent:
        return used_percent
    remaining_percent = safe_int(
        limit.get("remaining_percentage")
        or limit.get("remaining_percent")
        or limit.get("percent_remaining")
        or limit.get("remaining")
    )
    if remaining_percent:
        return max(0, 100 - remaining_percent)
    return safe_int(limit.get("percent"))


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


def _command_kind(command: str) -> str:
    return "command" if command else "tool"


def _context_from_usage(
    usage: TokenUsage, *, window_tokens: int = 0
) -> LiveContextWindow:
    used_tokens = usage.context_tokens
    used_percent = int((used_tokens / window_tokens) * 100) if window_tokens else 0
    return LiveContextWindow(
        window_tokens=window_tokens if used_tokens else 0,
        used_tokens=used_tokens,
        used_percent=used_percent,
        origin=LiveSnapshotOrigin.COMPUTED.value
        if used_tokens
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


def _is_human_claude_prompt(message: Mapping[str, object]) -> bool:
    content = message.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, Mapping):
                continue
            typed_item = cast(Mapping[str, object], item)
            if typed_item.get("type") == "tool_result":
                return False
        return True
    if not isinstance(content, str):
        return False
    stripped = content.strip()
    if not stripped:
        return False
    synthetic_prefixes = (
        "<local-command-caveat>",
        "<local-command-stdout>",
        "<local-command-stderr>",
        "<command-name>",
    )
    return not stripped.startswith(synthetic_prefixes)


def _latest_compaction(
    current: LiveCompaction, obj: Mapping[str, object], timestamp: str
) -> LiveCompaction:
    payload = mapping_value(obj, "payload")
    subtype = string_value(obj, "subtype")
    payload_type = string_value(payload, "type")
    payload_subtype = string_value(payload, "subtype")
    content = string_value(obj, "content") or string_value(payload, "content")
    obj_type = string_value(obj, "type")
    compact_metadata = _compaction_metadata(obj, payload)
    if _is_compact_summary(obj, payload) and current.count:
        return current
    content_key = content.strip().lower()
    is_compaction = (
        subtype == "compact_boundary"
        or payload_subtype == "compact_boundary"
        or _is_compact_summary(obj, payload)
        or content_key == "conversation compacted"
        or payload_type in {"context_compacted", "compact", "compaction"}
        or obj_type.lower() in {"compact", "compaction", "compact_boundary"}
    )
    if not is_compaction:
        return current
    count = current.count + 1
    return LiveCompaction(
        count=count,
        last_at=timestamp or current.last_at,
        trigger=string_value(compact_metadata, "trigger", current.trigger),
        pre_tokens=_metadata_int(compact_metadata, "preTokens", "pre_tokens")
        or current.pre_tokens,
        post_tokens=_metadata_int(compact_metadata, "postTokens", "post_tokens")
        or current.post_tokens,
        duration_ms=_metadata_int(compact_metadata, "durationMs", "duration_ms")
        or current.duration_ms,
        origin=LiveSnapshotOrigin.TRANSCRIPT.value,
    )


def _is_compact_summary(
    obj: Mapping[str, object], payload: Mapping[str, object]
) -> bool:
    return (
        obj.get("isCompactSummary") is True or payload.get("isCompactSummary") is True
    )


def _compaction_metadata(
    obj: Mapping[str, object], payload: Mapping[str, object]
) -> Mapping[str, object]:
    for key in ("compactMetadata", "compact_metadata", "compaction"):
        metadata = mapping_value(obj, key)
        if metadata:
            return metadata
        metadata = mapping_value(payload, key)
        if metadata:
            return metadata
    return {}


def _metadata_int(metadata: Mapping[str, object], *keys: str) -> int:
    for key in keys:
        value = safe_int(metadata.get(key))
        if value:
            return value
    return 0


def _optional_mapping(value: object) -> Mapping[str, object] | None:
    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else None


def _session_name(path: Path, objects: Sequence[Mapping[str, object]]) -> str:
    for obj in objects:
        explicit = _explicit_session_name(obj)
        if explicit:
            return explicit
    for obj in reversed(objects):
        prompt_name = _prompt_session_name(obj)
        if prompt_name:
            return prompt_name
    return path.stem


def _explicit_session_name(obj: Mapping[str, object]) -> str:
    if string_value(obj, "type") == "ai-title":
        value = _normalize_session_name(string_value(obj, "aiTitle"))
        return value if _is_readable_session_name(value) else ""
    if string_value(obj, "type") == "last-prompt":
        value = _normalize_session_name(string_value(obj, "lastPrompt"))
        return value if _is_prompt_like_session_name(value) else ""
    for key in ("sessionName", "session_name", "title", "summary"):
        value = _normalize_session_name(string_value(obj, key))
        if value and _is_readable_session_name(value):
            return value
    payload = mapping_value(obj, "payload")
    for key in ("sessionName", "session_name", "title", "summary"):
        value = _normalize_session_name(string_value(payload, key))
        if value and _is_readable_session_name(value):
            return value
    return ""


def _prompt_session_name(obj: Mapping[str, object]) -> str:
    payload = mapping_value(obj, "payload")
    obj_type = string_value(obj, "type")
    if obj_type == "response_item" and string_value(payload, "type") == "message":
        role = string_value(payload, "role")
        if role == "user":
            return _normalize_prompt_name(_content_text(payload.get("content")))

    message = mapping_value(obj, "message")
    role = string_value(message, "role") or obj_type
    if role == "user" and _is_human_claude_prompt(message):
        return _normalize_prompt_name(_content_text(message.get("content")))

    record_type = string_value(obj, "type")
    if record_type == "user":
        return _normalize_prompt_name(_content_text(obj.get("content")))
    return ""


def _content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    pieces: list[str] = []
    for item in content:
        if isinstance(item, str):
            pieces.append(item)
        elif isinstance(item, Mapping):
            typed_item = cast(Mapping[str, object], item)
            text = typed_item.get("text") or typed_item.get("content")
            if isinstance(text, str):
                pieces.append(text)
    return " ".join(pieces)


def _normalize_prompt_name(value: str) -> str:
    normalized = _normalize_session_name(value)
    if not normalized or not _is_prompt_like_session_name(normalized):
        return ""
    return normalized


def _normalize_session_name(value: str) -> str:
    cleaned = _XML_TAG_RE.sub(" ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:\t\r\n")
    if not cleaned:
        return ""
    if len(cleaned) <= SESSION_NAME_MAX:
        return cleaned
    return cleaned[: SESSION_NAME_MAX - 1].rstrip() + "..."


def _is_readable_session_name(value: str) -> bool:
    if value.lower() in {"none", "null", "unknown", "untitled"}:
        return False
    if _UUID_RE.match(value):
        return False
    if value.startswith(("rollout-", "session-")):
        return False
    return bool(re.search(r"[A-Za-z]{3}", value))


def _is_prompt_like_session_name(value: str) -> bool:
    synthetic_prefixes = (
        "Caveat:",
        "The messages below were generated",
        "permissions instructions",
        "# AGENTS.md instructions",
        "AGENTS.md instructions",
        "Knowledge cutoff:",
        "You are Codex",
        "You are Claude",
        "## Memory",
    )
    if value.startswith(synthetic_prefixes):
        return False
    if value.startswith(("[", "{")) and "tool_use_id" in value:
        return False
    return _is_readable_session_name(value)


def _claude_subagent_count(path: Path) -> int:
    if "subagents" in path.parts:
        return 0
    subagents_dir = path.with_suffix("") / "subagents"
    if not subagents_dir.exists():
        return 0
    try:
        return sum(1 for item in subagents_dir.glob("*.jsonl") if item.is_file())
    except OSError:
        return 0


def _gemini_subagent_count(records: Sequence[Mapping[str, object]]) -> int:
    agent_ids: set[str] = set()
    for record in records:
        for key in ("agentId", "subagentId", "agent_id", "subagent_id"):
            value = string_value(record, key)
            if value:
                agent_ids.add(value)
    return len(agent_ids)


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
