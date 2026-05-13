"""Aggregate event metrics."""

from __future__ import annotations

from collections import Counter, defaultdict

from token_machine.metrics.tools import (
    ACTION_EVENT_TYPES,
    build_description_map,
    command_fingerprint,
    observed_executable_counts,
    observed_skill_counts,
    observed_tool_counts,
)
from token_machine.models import (
    AgentSource,
    AnalyticsEvent,
    DailySummary,
    DashboardSummary,
    EventType,
    SessionRollup,
    TokenUsage,
)
from token_machine.utils.time import seconds_between, utc_now


def empty_rollup(source_path: str = "") -> SessionRollup:
    return SessionRollup(
        session_id="",
        source=AgentSource.UNKNOWN,
        source_path=source_path,
        project_path="",
        started_at="",
        ended_at="",
        event_count=0,
        model_calls=0,
        tool_calls=0,
        skill_calls=0,
        command_calls=0,
        cli_commands=0,
        messages=0,
        models={},
        tools={},
        skills={},
        executables={},
        clis={},
        tokens=TokenUsage(),
    )


def rollup_events(events: list[AnalyticsEvent], source_path: str = "") -> SessionRollup:
    if not events:
        return empty_rollup(source_path)
    timestamps = sorted(event.timestamp for event in events if event.timestamp)
    tokens = TokenUsage(
        input_tokens=sum(event.token_usage.input_tokens for event in events),
        cached_input_tokens=sum(
            event.token_usage.cached_input_tokens for event in events
        ),
        cache_creation_input_tokens=sum(
            event.token_usage.cache_creation_input_tokens for event in events
        ),
        output_tokens=sum(event.token_usage.output_tokens for event in events),
        reasoning_output_tokens=sum(
            event.token_usage.reasoning_output_tokens for event in events
        ),
        total_tokens=sum(event.token_usage.total_tokens for event in events),
    )
    executables = dict(observed_executable_counts(events))
    tools = dict(observed_tool_counts(events))
    skills = dict(observed_skill_counts(events))
    command_fingerprints = {
        command_fingerprint(event)
        for event in events
        if event.command and event.event_type in ACTION_EVENT_TYPES
    }
    return SessionRollup(
        session_id=events[0].session_id,
        source=events[0].source,
        source_path=events[0].source_path,
        project_path=next(
            (event.project_path for event in events if event.project_path), ""
        ),
        started_at=timestamps[0] if timestamps else "",
        ended_at=timestamps[-1] if timestamps else "",
        event_count=len(events),
        model_calls=sum(event.event_type == EventType.MODEL_CALL for event in events),
        tool_calls=sum(tools.values()),
        skill_calls=sum(skills.values()),
        command_calls=len(command_fingerprints),
        cli_commands=sum(event.event_type == EventType.CLI_COMMAND for event in events),
        messages=sum(event.event_type == EventType.MESSAGE for event in events),
        models=dict(
            Counter(
                event.model
                for event in events
                if event.model and event.event_type == EventType.MODEL_CALL
            )
        ),
        tools=tools,
        skills=skills,
        executables=executables,
        clis=executables,
        tokens=tokens,
    )


def group_sessions(
    events: list[AnalyticsEvent],
) -> dict[tuple[AgentSource, str], list[AnalyticsEvent]]:
    grouped: dict[tuple[AgentSource, str], list[AnalyticsEvent]] = defaultdict(list)
    for event in events:
        grouped[(event.source, event.session_id)].append(event)
    return grouped


def dashboard_summary(events: list[AnalyticsEvent]) -> DashboardSummary:
    tokens = rollup_events(events).tokens if events else TokenUsage()
    summary_rollup = rollup_events(events)
    return DashboardSummary(
        generated_at=utc_now(),
        event_count=len(events),
        sessions=len({(event.source, event.session_id) for event in events}),
        sources=dict(Counter(event.source.value for event in events)),
        models=dict(
            Counter(
                event.model
                for event in events
                if event.model and event.event_type == EventType.MODEL_CALL
            )
        ),
        skill_calls=summary_rollup.skill_calls,
        command_calls=summary_rollup.command_calls,
        tools=summary_rollup.tools,
        skills=summary_rollup.skills,
        executables=summary_rollup.executables,
        clis=summary_rollup.clis,
        event_types=dict(Counter(event.event_type.value for event in events)),
        tokens=tokens,
        descriptions=build_description_map(events),
    )


def bucket_series(
    events: list[AnalyticsEvent], *, width: int, limit: int
) -> list[DailySummary]:
    by_bucket: dict[str, list[AnalyticsEvent]] = defaultdict(list)
    for event in events:
        bucket = (event.timestamp or utc_now())[:width]
        by_bucket[bucket].append(event)
    return [
        DailySummary(day=bucket, summary=dashboard_summary(bucket_events))
        for bucket, bucket_events in sorted(by_bucket.items())[-limit:]
    ]


def session_duration_seconds(events: list[AnalyticsEvent]) -> int:
    timestamps = sorted(event.timestamp for event in events if event.timestamp)
    if len(timestamps) < 2:
        return 0
    return seconds_between(timestamps[0], timestamps[-1])
