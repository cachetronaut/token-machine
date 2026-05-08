"""Observed tool and command metrics."""

from __future__ import annotations

import re
from collections import Counter

from token_machine.models import AnalyticsEvent, EventType, ToolMixItem

ACTION_EVENT_TYPES = {EventType.TOOL_CALL, EventType.CLI_COMMAND}


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
    """Return the observed action label for a tool or command event."""
    raw = ""
    if event.cli_name:
        raw = event.cli_name
    else:
        raw = event.tool_name or event.command
    return normalize_label(raw)


def observed_tool_counts(events: list[AnalyticsEvent]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        if event.event_type not in ACTION_EVENT_TYPES:
            continue
        label = event_tool_label(event).strip()
        if label:
            counts[label] += 1
    return counts


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

        label = event_tool_label(event)
        if not label:
            continue

        if event.tool_description and label not in explicit:
            explicit[label] = event.tool_description.lower()

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
            desc = explicit[label]
            if len(desc) > 60:
                desc = desc[:57] + "..."
            result[label] = f"E.g., {desc}"
        elif label in examples:
            best = min(examples[label], key=len)
            if len(best) > 60:
                best = best[:57] + "..."
            result[label] = f"E.g., {best}"

    return result


def tool_mix(events: list[AnalyticsEvent], limit: int = 5) -> list[ToolMixItem]:
    counts = observed_tool_counts(events)
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
