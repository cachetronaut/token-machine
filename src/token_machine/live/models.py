"""Typed models for live session usage snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping, cast

from token_machine.models import AgentSource, TokenUsage, safe_int
from token_machine.sources.base import executable_from_command


class LiveProbeStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    MISSING = "missing"
    ERROR = "error"


class LiveSnapshotOrigin(StrEnum):
    TRANSCRIPT = "transcript"
    STATUSLINE = "statusline"
    COMPUTED = "computed"
    MISSING = "missing"


@dataclass(frozen=True)
class LiveContextWindow:
    window_tokens: int = 0
    used_tokens: int = 0
    used_percent: int = 0
    origin: str = LiveSnapshotOrigin.MISSING.value


@dataclass(frozen=True)
class LiveRateLimit:
    name: str
    used_percent: int = 0
    resets_at: str = ""
    limit_id: str = ""
    plan_type: str = ""
    origin: str = LiveSnapshotOrigin.MISSING.value


@dataclass(frozen=True)
class LiveSessionLimit:
    name: str
    used_percent: int = 0
    remaining_percent: int = 0
    resets_at: str = ""
    origin: str = LiveSnapshotOrigin.MISSING.value


@dataclass(frozen=True)
class LiveCompaction:
    count: int = 0
    last_at: str = ""
    trigger: str = ""
    pre_tokens: int = 0
    post_tokens: int = 0
    duration_ms: int = 0
    origin: str = LiveSnapshotOrigin.MISSING.value


@dataclass(frozen=True)
class LiveToolCall:
    name: str
    status: str = "observed"
    command: str = ""
    kind: str = "tool"
    executable: str = ""
    started_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class LiveUsageSnapshot:
    source: AgentSource
    session_id: str
    source_path: str
    session_name: str = ""
    project_path: str = ""
    model: str = ""
    updated_at: str = ""
    observed_at: str = ""
    status: LiveProbeStatus = LiveProbeStatus.ACTIVE
    user_queries: dict[str, int | str] = field(default_factory=dict)
    context: LiveContextWindow = field(default_factory=LiveContextWindow)
    current_metrics: dict[str, int | str] = field(default_factory=dict)
    live_tool_calls: list[LiveToolCall] = field(default_factory=list)
    live_actions: list[LiveToolCall] = field(default_factory=list)
    rate_limits: list[LiveRateLimit] = field(default_factory=list)
    session_limits: list[LiveSessionLimit] = field(default_factory=list)
    compaction: LiveCompaction = field(default_factory=LiveCompaction)
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    origin: str = LiveSnapshotOrigin.MISSING.value
    error: str = ""


@dataclass(frozen=True)
class LiveData:
    generated_at: str
    active_count: int
    stale_count: int
    snapshots: list[LiveUsageSnapshot]


def snapshot_from_mapping(data: Mapping[str, object]) -> LiveUsageSnapshot:
    context_data = _mapping(data.get("context"))
    token_data = _mapping(data.get("token_usage"))
    source = _agent_source(str(data.get("source", AgentSource.UNKNOWN.value)))
    live_tool_calls = [
        _live_tool_call(item) for item in _mapping_list(data.get("live_tool_calls"))
    ]
    live_actions = [
        _live_tool_call(item) for item in _mapping_list(data.get("live_actions"))
    ]
    return LiveUsageSnapshot(
        source=source,
        session_id=str(data.get("session_id", "")),
        source_path=str(data.get("source_path", "")),
        session_name=str(data.get("session_name", "")),
        project_path=str(data.get("project_path", "")),
        model=str(data.get("model", "")),
        updated_at=str(data.get("updated_at", "")),
        observed_at=str(data.get("observed_at", "")),
        status=_probe_status(str(data.get("status", LiveProbeStatus.MISSING.value))),
        user_queries=_int_string_dict(_mapping(data.get("user_queries"))),
        context=LiveContextWindow(
            window_tokens=safe_int(context_data.get("window_tokens")),
            used_tokens=safe_int(context_data.get("used_tokens")),
            used_percent=safe_int(context_data.get("used_percent")),
            origin=str(context_data.get("origin", LiveSnapshotOrigin.MISSING.value)),
        ),
        current_metrics=_int_string_dict(_mapping(data.get("current_metrics"))),
        live_tool_calls=live_tool_calls,
        live_actions=live_actions or live_tool_calls,
        rate_limits=[
            LiveRateLimit(
                name=str(item.get("name", "")),
                used_percent=safe_int(item.get("used_percent")),
                resets_at=str(item.get("resets_at", "")),
                limit_id=str(item.get("limit_id", "")),
                plan_type=str(item.get("plan_type", "")),
                origin=str(item.get("origin", LiveSnapshotOrigin.MISSING.value)),
            )
            for item in _mapping_list(data.get("rate_limits"))
        ],
        session_limits=[
            LiveSessionLimit(
                name=str(item.get("name", "")),
                used_percent=safe_int(item.get("used_percent")),
                remaining_percent=safe_int(item.get("remaining_percent")),
                resets_at=str(item.get("resets_at", "")),
                origin=str(item.get("origin", LiveSnapshotOrigin.MISSING.value)),
            )
            for item in _mapping_list(data.get("session_limits"))
        ],
        compaction=LiveCompaction(
            count=safe_int(_mapping(data.get("compaction")).get("count")),
            last_at=str(_mapping(data.get("compaction")).get("last_at", "")),
            trigger=str(_mapping(data.get("compaction")).get("trigger", "")),
            pre_tokens=safe_int(_mapping(data.get("compaction")).get("pre_tokens")),
            post_tokens=safe_int(_mapping(data.get("compaction")).get("post_tokens")),
            duration_ms=safe_int(_mapping(data.get("compaction")).get("duration_ms")),
            origin=str(
                _mapping(data.get("compaction")).get(
                    "origin", LiveSnapshotOrigin.MISSING.value
                )
            ),
        ),
        token_usage=TokenUsage.from_mapping(token_data),
        origin=str(data.get("origin", LiveSnapshotOrigin.MISSING.value)),
        error=str(data.get("error", "")),
    )


def _agent_source(raw: str) -> AgentSource:
    if raw == "claude":
        raw = AgentSource.CLAUDE_CODE.value
    try:
        return AgentSource(raw)
    except ValueError:
        return AgentSource.UNKNOWN


def _probe_status(raw: str) -> LiveProbeStatus:
    try:
        return LiveProbeStatus(raw)
    except ValueError:
        return LiveProbeStatus.MISSING


def _mapping(value: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else {}


def _mapping_list(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    return [
        cast(Mapping[str, object], item) for item in value if isinstance(item, Mapping)
    ]


def _live_tool_call(item: Mapping[str, object]) -> LiveToolCall:
    command = str(item.get("command", ""))
    executable = str(item.get("executable", "")) or executable_from_command(command)
    kind = str(item.get("kind", "")) or _default_live_action_kind(command)
    return LiveToolCall(
        name=str(item.get("name", "")),
        status=str(item.get("status", "observed")),
        command=command,
        kind=kind,
        executable=executable,
        started_at=str(item.get("started_at", "")),
        updated_at=str(item.get("updated_at", "")),
    )


def _default_live_action_kind(command: str) -> str:
    return "command" if command else "tool"


def _int_string_dict(data: Mapping[str, object]) -> dict[str, int | str]:
    output: dict[str, int | str] = {}
    for key, value in data.items():
        if isinstance(value, int | str):
            output[str(key)] = value
        elif isinstance(value, float):
            output[str(key)] = int(value)
        elif isinstance(value, bool):
            output[str(key)] = int(value)
        elif value is None:
            output[str(key)] = ""
        elif isinstance(value, str | int | float | bool):
            output[str(key)] = str(value)
    return output
