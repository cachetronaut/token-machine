"""Observed tool and command metrics."""

from __future__ import annotations

import re
from collections import Counter

from token_machine.models import AnalyticsEvent, EventType, ToolMixItem
from token_machine.sources.base import clean_command, executable_from_command

TOOL_EVENT_TYPES = {EventType.TOOL_CALL}
SKILL_EVENT_TYPES = {EventType.SKILL_CALL}
COMMAND_EVENT_TYPES = {EventType.CLI_COMMAND}
ACTION_EVENT_TYPES = TOOL_EVENT_TYPES | SKILL_EVENT_TYPES | COMMAND_EVENT_TYPES


def normalize_label(name: str) -> str:
    """Convert snake_case, camelCase, or PascalCase into Title Case."""
    if not name:
        return ""
    # Add space before capitals (camel/Pascal)
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1 \2", name)
    # Add space before capital sequences
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1 \2", s1)
    # Replace underscores and hyphens with spaces
    s3 = s2.replace("_", " ").replace("-", " ")
    # Clean up double spaces and title case
    return " ".join(part.capitalize() for part in s3.split() if part)


def event_tool_label(event: AnalyticsEvent) -> str:
    """Return the observed tool label for a tool event."""
    return normalize_label(event.tool_name)


def event_skill_label(event: AnalyticsEvent) -> str:
    """Return the observed skill label for a skill event."""
    return event.skill_name.strip()


def event_executable_label(event: AnalyticsEvent) -> str:
    """Return the executable detected from a command-bearing event."""
    return normalize_label(event.cli_name or executable_from_command(event.command))


def event_action_label(event: AnalyticsEvent) -> str:
    """Return a mixed action label without erasing action kind."""
    if event.event_type == EventType.SKILL_CALL:
        label = event_skill_label(event)
        return f"Skill: {label}" if label else ""
    if event.event_type == EventType.TOOL_CALL and event_tool_label(event) == "Skill":
        return "Skill"
    if event.command:
        label = event_executable_label(event)
        return f"Exec: {label}" if label else ""
    if event.event_type == EventType.TOOL_CALL:
        return event_tool_label(event)
    return ""


def command_fingerprint(event: AnalyticsEvent) -> tuple[str, str, str, str, str]:
    """Return a stable identity for a command facet across duplicate event rows."""
    return (
        event.source.value,
        event.session_id,
        event.timestamp,
        event.tool_name,
        clean_command(event.command),
    )


def observed_tool_counts(events: list[AnalyticsEvent]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        if event.event_type != EventType.TOOL_CALL:
            continue
        label = event_tool_label(event).strip()
        if label == "Skill":
            continue
        if label:
            counts[label] += 1
    return counts


def observed_skill_counts(events: list[AnalyticsEvent]) -> Counter[str]:
    counts: Counter[str] = Counter()
    has_explicit_skills = any(
        event.event_type == EventType.SKILL_CALL and event.skill_name
        for event in events
    )
    for event in events:
        if event.event_type == EventType.SKILL_CALL:
            label = event_skill_label(event)
        elif (
            not has_explicit_skills
            and event.event_type == EventType.TOOL_CALL
            and event_tool_label(event) == "Skill"
        ):
            label = "Skill"
        else:
            continue
        if label:
            counts[label] += 1
    return counts


def observed_executable_counts(events: list[AnalyticsEvent]) -> Counter[str]:
    counts: Counter[str] = Counter()
    seen: set[tuple[str, str, str, str, str]] = set()
    for event in events:
        if event.event_type not in ACTION_EVENT_TYPES or not event.command:
            continue
        fingerprint = command_fingerprint(event)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        label = event_executable_label(event)
        if label:
            counts[label] += 1
    return counts


def observed_action_counts(events: list[AnalyticsEvent]) -> Counter[str]:
    counts: Counter[str] = Counter()
    seen_commands: set[tuple[str, str, str, str, str]] = set()
    for event in events:
        if event.event_type not in ACTION_EVENT_TYPES:
            continue
        if event.command:
            fingerprint = command_fingerprint(event)
            if fingerprint in seen_commands:
                continue
            seen_commands.add(fingerprint)
        label = event_action_label(event).strip()
        if label:
            counts[label] += 1
    return counts


def _truncate(text: str, limit: int = 60) -> str:
    """Truncate text to limit with ellipsis."""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def build_description_map(events: list[AnalyticsEvent]) -> dict[str, str]:
    """Build a map of tool labels to their best available description or example."""
    # We want to find both explicit descriptions and shortest command examples.
    # explicit[label] = "captured description"
    # examples[label] = ["cmd1", "cmd2", ...]
    explicit: dict[str, str] = {}
    examples: dict[str, list[str]] = {}

    for event in events:
        if event.event_type not in ACTION_EVENT_TYPES:
            continue

        label = event_action_label(event)
        if not label:
            continue

        description = event.skill_description or event.tool_description
        if description and label not in explicit:
            explicit[label] = description.lower()

        if event.command:
            cmd = event.command.strip()
            if cmd.lower() != label.lower():
                if label not in examples:
                    examples[label] = []
                examples[label].append(cmd)

    # Combine results
    result: dict[str, str] = {}
    all_labels = set(explicit.keys()) | set(examples.keys())

    for label in all_labels:
        if label in explicit:
            result[label] = f"E.g., {_truncate(explicit[label])}"
        elif label in examples:
            best = str(min(examples[label], key=len))
            result[label] = f"E.g., {_truncate(best)}"

    return result


def tool_mix(events: list[AnalyticsEvent], limit: int = 5) -> list[ToolMixItem]:
    counts = observed_action_counts(events)
    total = sum(counts.values()) or 1
    desc_map = build_description_map(events)
    return [
        ToolMixItem(
            category=label,
            count=count,
            percent=round(count / total * 100),
            description=desc_map.get(label, ""),
        )
        for label, count in counts.most_common(limit)
    ]
