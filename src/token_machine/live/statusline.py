"""Statusline payload capture for live usage snapshots."""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Mapping, Sequence, cast

from token_machine.config import DEFAULT_STORE
from token_machine.live.models import (
    LiveContextWindow,
    LiveProbeStatus,
    LiveRateLimit,
    LiveSessionLimit,
    LiveSnapshotOrigin,
    LiveUsageSnapshot,
)
from token_machine.live.store import LiveUsageStore
from token_machine.models import AgentSource, safe_int
from token_machine.sources.base import session_id_from_path
from token_machine.utils.time import utc_now


def capture_claude_statusline(
    payload: Mapping[str, object],
    store: Path = DEFAULT_STORE,
) -> LiveUsageSnapshot:
    """Persist a Claude statusline snapshot, merging with transcript data."""
    live_store = LiveUsageStore(store)
    statusline_snapshot = claude_statusline_snapshot(payload)
    existing = _matching_snapshot(live_store.load_snapshots(), statusline_snapshot)
    snapshot = (
        _merge_statusline_snapshot(existing, statusline_snapshot)
        if existing is not None
        else statusline_snapshot
    )
    live_store.write_snapshot(snapshot)
    return snapshot


def claude_statusline_snapshot(payload: Mapping[str, object]) -> LiveUsageSnapshot:
    now = utc_now()
    transcript_path = _string_path(payload, "transcript_path", "transcriptPath")
    session_id = _statusline_session_id(payload, transcript_path)
    workspace = _statusline_workspace(payload)
    session_name = _first_string(
        payload, "session_name", "sessionName", "title", "name"
    )
    model = _statusline_model(payload)
    rate_limits = _claude_rate_limits(payload)
    context = _claude_statusline_context(payload)
    metrics = _claude_statusline_metrics(payload)

    return LiveUsageSnapshot(
        source=AgentSource.CLAUDE_CODE,
        session_id=session_id,
        source_path=transcript_path or f"claude-statusline:{session_id}",
        session_name=session_name,
        project_path=workspace,
        model=model,
        updated_at=now,
        observed_at=now,
        status=LiveProbeStatus.ACTIVE,
        context=context,
        current_metrics=metrics,
        rate_limits=rate_limits,
        session_limits=_session_limits_from_rate_limits(rate_limits),
        origin=LiveSnapshotOrigin.STATUSLINE.value,
    )


def run_chained_statusline(command: Sequence[str], input_text: str) -> int:
    if not command:
        return 0
    completed = subprocess.run(  # noqa: S603 - user-provided statusline command.
        list(command),
        input=input_text,
        text=True,
        check=False,
    )
    return completed.returncode


def _merge_statusline_snapshot(
    existing: LiveUsageSnapshot, statusline: LiveUsageSnapshot
) -> LiveUsageSnapshot:
    status_context = statusline.context
    existing_context = existing.context
    has_status_context = bool(
        status_context.used_percent
        or status_context.used_tokens
        or status_context.window_tokens
    )
    context = (
        LiveContextWindow(
            window_tokens=status_context.window_tokens
            or existing_context.window_tokens,
            used_tokens=status_context.used_tokens or existing_context.used_tokens,
            used_percent=status_context.used_percent or existing_context.used_percent,
            origin=status_context.origin,
        )
        if has_status_context
        else existing_context
    )
    current_metrics = {
        **existing.current_metrics,
        **{
            key: value
            for key, value in statusline.current_metrics.items()
            if value not in {"", 0}
        },
    }
    return replace(
        existing,
        source_path=existing.source_path or statusline.source_path,
        session_name=_statusline_display_name(statusline, existing.session_name),
        project_path=statusline.project_path or existing.project_path,
        model=statusline.model or existing.model,
        updated_at=statusline.updated_at,
        observed_at=statusline.observed_at,
        status=LiveProbeStatus.ACTIVE,
        context=context,
        current_metrics=current_metrics,
        rate_limits=statusline.rate_limits or existing.rate_limits,
        session_limits=statusline.session_limits or existing.session_limits,
        origin=LiveSnapshotOrigin.STATUSLINE.value,
    )


def _matching_snapshot(
    snapshots: Sequence[LiveUsageSnapshot],
    statusline: LiveUsageSnapshot,
) -> LiveUsageSnapshot | None:
    source_snapshots = [
        snapshot
        for snapshot in snapshots
        if snapshot.source == AgentSource.CLAUDE_CODE
        and snapshot.session_id == statusline.session_id
    ]
    if source_snapshots:
        return source_snapshots[-1]

    if statusline.source_path:
        source_snapshots = [
            snapshot
            for snapshot in snapshots
            if snapshot.source == AgentSource.CLAUDE_CODE
            and snapshot.source_path == statusline.source_path
        ]
        if source_snapshots:
            return source_snapshots[-1]

    if statusline.project_path:
        source_snapshots = [
            snapshot
            for snapshot in snapshots
            if snapshot.source == AgentSource.CLAUDE_CODE
            and snapshot.project_path == statusline.project_path
        ]
        if source_snapshots:
            return sorted(source_snapshots, key=lambda item: item.updated_at)[-1]

    return None


def _claude_rate_limits(payload: Mapping[str, object]) -> list[LiveRateLimit]:
    rate_limits = _mapping(payload.get("rate_limits"))
    limits: list[LiveRateLimit] = []
    for name, aliases in {
        "five_hour": ("five_hour", "5h"),
        "seven_day": ("seven_day", "7d"),
    }.items():
        limit = _first_mapping(rate_limits, aliases)
        if not limit:
            continue
        limits.append(
            LiveRateLimit(
                name=name,
                used_percent=safe_int(
                    limit.get("used_percentage")
                    or limit.get("used_percent")
                    or limit.get("percent")
                ),
                resets_at=str(limit.get("resets_at") or limit.get("reset_at") or ""),
                origin=LiveSnapshotOrigin.STATUSLINE.value,
            )
        )
    return limits


def _session_limits_from_rate_limits(
    rate_limits: Sequence[LiveRateLimit],
) -> list[LiveSessionLimit]:
    return [
        LiveSessionLimit(
            name=limit.name,
            used_percent=limit.used_percent,
            remaining_percent=max(0, 100 - limit.used_percent),
            resets_at=limit.resets_at,
            origin=limit.origin,
        )
        for limit in rate_limits
    ]


def _statusline_display_name(statusline: LiveUsageSnapshot, existing_name: str) -> str:
    if statusline.session_name and statusline.session_name != statusline.session_id:
        return statusline.session_name
    return existing_name


def _claude_statusline_context(payload: Mapping[str, object]) -> LiveContextWindow:
    context_window = _mapping(payload.get("context_window"))
    used_percent = safe_int(
        context_window.get("used_percentage")
        or context_window.get("used_percent")
        or payload.get("context_window_usage_percent")
    )
    used_tokens = safe_int(
        context_window.get("used_tokens")
        or context_window.get("used")
        or payload.get("context_window_used_tokens")
    )
    window_tokens = safe_int(
        context_window.get("window_tokens")
        or context_window.get("total_tokens")
        or context_window.get("limit")
        or payload.get("context_window_tokens")
    )
    origin = (
        LiveSnapshotOrigin.STATUSLINE.value
        if used_percent or used_tokens or window_tokens
        else LiveSnapshotOrigin.MISSING.value
    )
    return LiveContextWindow(
        window_tokens=window_tokens,
        used_tokens=used_tokens,
        used_percent=used_percent,
        origin=origin,
    )


def _claude_statusline_metrics(payload: Mapping[str, object]) -> dict[str, int | str]:
    cost = payload.get("session_cost_usd") or _mapping(payload.get("cost")).get(
        "total_usd"
    )
    output: dict[str, int | str] = {}
    if isinstance(cost, str | int | float):
        output["session_cost_usd"] = str(cost)
    return output


def _statusline_session_id(payload: Mapping[str, object], transcript_path: str) -> str:
    raw = (
        _first_string(payload, "session_id", "sessionId")
        or _first_string(_mapping(payload.get("session")), "id", "session_id")
        or _first_string(_mapping(payload.get("conversation")), "id", "session_id")
    )
    if raw:
        return raw
    if transcript_path:
        return session_id_from_path(Path(transcript_path))
    workspace = _statusline_workspace(payload)
    if workspace:
        return f"claude-statusline-{Path(workspace).name}"
    return "claude-statusline"


def _statusline_model(payload: Mapping[str, object]) -> str:
    model = payload.get("model")
    if isinstance(model, Mapping):
        typed_model = cast(Mapping[str, object], model)
        return _first_string(typed_model, "display_name", "displayName", "id", "name")
    return str(model) if isinstance(model, str) else ""


def _statusline_workspace(payload: Mapping[str, object]) -> str:
    workspace = _mapping(payload.get("workspace"))
    return _first_string(
        workspace, "current_dir", "currentDir", "cwd"
    ) or _first_string(payload, "cwd")


def _string_path(payload: Mapping[str, object], *keys: str) -> str:
    raw = _first_string(payload, *keys)
    return str(Path(raw).expanduser()) if raw else ""


def _first_string(payload: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _first_mapping(
    payload: Mapping[str, object], keys: Sequence[str]
) -> Mapping[str, object]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, Mapping):
            return cast(Mapping[str, object], value)
    return {}


def _mapping(value: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else {}


def loads_statusline_payload(input_text: str) -> Mapping[str, object]:
    data = json.loads(input_text)
    if not isinstance(data, Mapping):
        raise ValueError("statusline payload must be a JSON object")
    return cast(Mapping[str, object], data)
