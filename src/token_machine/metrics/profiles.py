"""Derived model and session profiles."""

from __future__ import annotations

from collections import Counter, defaultdict

from token_machine.metrics.aggregate import (
    dashboard_summary,
    group_sessions,
    rollup_events,
    session_duration_seconds,
)
from token_machine.metrics.tools import (
    ACTION_EVENT_TYPES,
    observed_tool_counts,
    tool_mix,
)
from token_machine.models import (
    AgentSource,
    AnalyticsEvent,
    DashboardData,
    EventType,
    ModelFamily,
    ModelProfile,
    SessionProfile,
)
from token_machine.utils.time import seconds_between, utc_now


def dashboard_data(events: list[AnalyticsEvent]) -> DashboardData:
    session_groups = group_sessions(events)
    recent_sessions = sorted(
        [session_profile(session_events) for session_events in session_groups.values()],
        key=lambda profile: profile.rollup.ended_at or profile.rollup.started_at,
        reverse=True,
    )[:25]
    from token_machine.metrics.aggregate import bucket_series

    return DashboardData(
        generated_at=utc_now(),
        summary=dashboard_summary(events),
        daily=bucket_series(events, width=10, limit=30),
        hourly=bucket_series(events, width=13, limit=24),
        model_profiles=model_profiles(events),
        recent_sessions=recent_sessions,
    )


def session_profile(events: list[AnalyticsEvent]) -> SessionProfile:
    return SessionProfile(
        rollup=rollup_events(events),
        duration_seconds=session_duration_seconds(events),
        time_to_first_tool_seconds=time_to_first(events, ACTION_EVENT_TYPES),
        time_to_first_edit_seconds=time_to_first(events, ACTION_EVENT_TYPES),
        tool_mix=tool_mix(events),
        workflow_role=dominant_workflow_role(events),
        scouting_report=scouting_report(events),
    )


def time_to_first(
    events: list[AnalyticsEvent],
    event_types: set[EventType],
) -> int:
    timestamps = sorted(event.timestamp for event in events if event.timestamp)
    if not timestamps:
        return -1
    started_at = timestamps[0]
    for event in sorted(events, key=lambda item: item.timestamp or ""):
        if event.event_type not in event_types or not event.timestamp:
            continue
        return seconds_between(started_at, event.timestamp)
    return -1


def dominant_workflow_role(events: list[AnalyticsEvent]) -> str:
    actions = [event for event in events if event.event_type in ACTION_EVENT_TYPES]
    if not actions:
        return "Conversation Analyst"
    cli_count = sum(event.event_type == EventType.CLI_COMMAND for event in actions)
    tool_count = sum(event.event_type == EventType.TOOL_CALL for event in actions)
    if cli_count >= max(2, tool_count * 2):
        return "Command-heavy Workflow"
    if tool_count >= max(2, cli_count * 2):
        return "Tool-heavy Workflow"
    return "Mixed Workflow"


def scouting_report(events: list[AnalyticsEvent]) -> str:
    role = dominant_workflow_role(events)
    counts = observed_tool_counts(events)
    top_actions = [label for label, _ in counts.most_common(3)]
    rollup = rollup_events(events)
    if not top_actions:
        return f"{role} profile based on message and token activity."
    scale = "focused"
    if rollup.tokens.total_tokens > 50_000_000:
        scale = "high-context"
    elif rollup.tokens.total_tokens > 5_000_000:
        scale = "substantial-context"
    return f"{scale} {role.lower()} with observed actions: {', '.join(top_actions)}."


def model_profiles(events: list[AnalyticsEvent], limit: int = 12) -> list[ModelProfile]:
    rows: list[ModelProfile] = []
    by_model: dict[str, list[AnalyticsEvent]] = defaultdict(list)
    for event in events:
        if event.model and event.event_type in {
            EventType.MODEL_CALL,
            EventType.TOOL_CALL,
            EventType.CLI_COMMAND,
        }:
            by_model[event.model].append(event)

    for model, model_events in by_model.items():
        rollup = rollup_events(model_events)
        projects = Counter(
            event.project_path for event in model_events if event.project_path
        ).most_common(5)
        sources = Counter(event.source for event in model_events if event.source)
        sessions: dict[str, list[AnalyticsEvent]] = defaultdict(list)
        for event in model_events:
            sessions[event.session_id].append(event)
        session_rollups = [rollup_events(items) for items in sessions.values()]
        session_tokens = [item.tokens.total_tokens for item in session_rollups]
        session_model_calls = [item.model_calls for item in session_rollups]
        session_tool_calls = [item.tool_calls for item in session_rollups]
        session_durations = [
            session_duration_seconds(items) for items in sessions.values()
        ]
        first_tool_times = [
            time_to_first(items, {EventType.TOOL_CALL, EventType.CLI_COMMAND})
            for items in sessions.values()
        ]
        first_edit_times = [
            time_to_first(items, ACTION_EVENT_TYPES) for items in sessions.values()
        ]
        rows.append(
            ModelProfile(
                model=model,
                model_family=model_family(model),
                source=sources.most_common(1)[0][0] if sources else AgentSource.UNKNOWN,
                sources={source.value: count for source, count in sources.items()},
                intelligence_level=model_intelligence_level(model),
                reasoning_level=reasoning_level(model_events),
                session_count=len({event.session_id for event in model_events}),
                project_count=len(
                    {event.project_path for event in model_events if event.project_path}
                ),
                projects=[{"path": path, "count": count} for path, count in projects],
                model_calls=rollup.model_calls,
                tool_calls=rollup.tool_calls,
                cli_commands=rollup.cli_commands,
                tokens=rollup.tokens,
                tools=rollup.tools,
                clis=rollup.clis,
                tool_mix=tool_mix(model_events),
                workflow_role=dominant_workflow_role(model_events),
                scouting_report=scouting_report(model_events),
                stats={
                    "mean_tokens_per_session": mean_int(session_tokens),
                    "median_tokens_per_session": median_int(session_tokens),
                    "mean_model_calls_per_session": mean_int(session_model_calls),
                    "median_model_calls_per_session": median_int(session_model_calls),
                    "mean_tool_calls_per_session": mean_int(session_tool_calls),
                    "median_tool_calls_per_session": median_int(session_tool_calls),
                    "mean_duration_seconds": mean_int(session_durations),
                    "median_duration_seconds": median_int(session_durations),
                    "mean_time_to_first_tool_seconds": mean_int(
                        [value for value in first_tool_times if value >= 0]
                    ),
                    "median_time_to_first_tool_seconds": median_int(
                        [value for value in first_tool_times if value >= 0]
                    ),
                    "mean_time_to_first_edit_seconds": mean_int(
                        [value for value in first_edit_times if value >= 0]
                    ),
                    "median_time_to_first_edit_seconds": median_int(
                        [value for value in first_edit_times if value >= 0]
                    ),
                    "mode_project": projects[0][0] if projects else "",
                },
            )
        )
    return sorted(
        rows,
        key=lambda row: (row.model_calls, row.tokens.total_tokens),
        reverse=True,
    )[:limit]


def mean_int(values: list[int]) -> int:
    return round(sum(values) / len(values)) if values else 0


def median_int(values: list[int]) -> int:
    if not values:
        return 0
    sorted_values = sorted(values)
    midpoint = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return sorted_values[midpoint]
    return round((sorted_values[midpoint - 1] + sorted_values[midpoint]) / 2)


def model_family(model: str) -> ModelFamily:
    lowered = model.lower()
    if "claude" in lowered:
        return ModelFamily.CLAUDE
    if "gemini" in lowered:
        return ModelFamily.GEMINI
    if "gpt" in lowered or "openai" in lowered:
        return ModelFamily.OPENAI
    if "qwen" in lowered:
        return ModelFamily.QWEN
    return ModelFamily.OTHER


def model_intelligence_level(model: str) -> str:
    lowered = model.lower()
    if any(value in lowered for value in ("opus", "gpt-5.5", "gpt-5.4", "gemini-3")):
        return "frontier"
    if "sonnet" in lowered or "flash" in lowered:
        return "balanced"
    if any(value in lowered for value in ("haiku", "mini", "qwen2.5-coder:3b")):
        return "fast"
    return "unclassified"


def reasoning_level(events: list[AnalyticsEvent]) -> str:
    candidates: list[str] = []
    for event in events:
        for key in ("reasoning_effort", "reasoning_level", "effort"):
            value = event.metadata.get(key)
            if isinstance(value, str) and value:
                candidates.append(value)
        collaboration_mode = event.metadata.get("collaboration_mode")
        if isinstance(collaboration_mode, dict):
            value = collaboration_mode.get("reasoning_effort")
            if isinstance(value, str) and value:
                candidates.append(value)
    return Counter(candidates).most_common(1)[0][0] if candidates else "not in log"
