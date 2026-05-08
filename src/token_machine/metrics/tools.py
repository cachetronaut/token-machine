"""Tool and command categorization."""

from __future__ import annotations

from collections import Counter

from token_machine.models import AnalyticsEvent, EventType, ToolCategory, ToolMixItem
from token_machine.sources.base import cli_from_command

EDIT_TOOLS = {"Edit", "Write", "apply_patch"}
SEARCH_TOOLS = {"Grep", "Glob", "rg", "grep_search"}
READ_TOOLS = {
    "Read",
    "view_image",
    "cat",
    "sed",
    "nl",
    "ls",
    "find",
    "read_file",
    "list_directory",
}
SHELL_TOOLS = {"Bash", "exec_command", "write_stdin", "exec", "run_shell_command"}
PLANNING_TOOLS = {"update_plan", "TodoWrite", "update_topic"}
DELEGATION_TOOLS = {
    "Task",
    "TaskCreate",
    "TaskUpdate",
    "spawn_agent",
    "send_input",
    "wait_agent",
}
BROWSER_TOOLS = {
    "WebFetch",
    "WebSearch",
    "web",
    "browser",
    "screenshot",
    "click",
    "open",
}
NETWORK_CLIS = {"curl", "wget", "gh"}
TEST_CLIS = {
    "pytest",
    "cargo",
    "pnpm",
    "npm",
    "uv",
    "ruff",
    "ty",
    "playwright",
    "vitest",
}
GIT_CLIS = {"git", "gh"}


def event_tool_label(event: AnalyticsEvent) -> str:
    return event.tool_name or event.cli_name


def tool_category(name: str, command: str = "") -> ToolCategory | None:
    cleaned = name.strip()
    cli = cli_from_command(command) if command else cleaned
    lowered = cleaned.lower()
    lowered_cli = cli.lower()
    if cleaned in EDIT_TOOLS or lowered_cli == "apply_patch":
        return ToolCategory.EDIT
    if cleaned in SEARCH_TOOLS or lowered_cli in {"rg", "grep", "find"}:
        return ToolCategory.SEARCH
    if cleaned in READ_TOOLS or lowered_cli in {
        "cat",
        "sed",
        "nl",
        "ls",
        "find",
        "head",
        "tail",
    }:
        return ToolCategory.READ
    if lowered_cli in GIT_CLIS:
        return ToolCategory.GIT
    if lowered_cli in NETWORK_CLIS:
        return ToolCategory.NETWORK
    if lowered_cli in TEST_CLIS or any(
        part in command
        for part in (
            "pytest",
            "cargo test",
            "pnpm test",
            "npm test",
            "ruff",
            "ty check",
        )
    ):
        return ToolCategory.TEST
    if cleaned in SHELL_TOOLS:
        return ToolCategory.SHELL
    if cleaned in PLANNING_TOOLS:
        return ToolCategory.PLANNING
    if cleaned in DELEGATION_TOOLS:
        return ToolCategory.DELEGATION
    if cleaned in BROWSER_TOOLS or lowered.startswith("web"):
        return ToolCategory.BROWSER
    if cleaned:
        return ToolCategory.OTHER
    return None


def tool_category_counts(events: list[AnalyticsEvent]) -> Counter[ToolCategory]:
    counts: Counter[ToolCategory] = Counter()
    for event in events:
        if event.event_type not in {EventType.TOOL_CALL, EventType.CLI_COMMAND}:
            continue
        category = tool_category(event_tool_label(event), event.command)
        if category:
            counts[category] += 1
    return counts


def tool_mix(events: list[AnalyticsEvent], limit: int = 5) -> list[ToolMixItem]:
    counts = tool_category_counts(events)
    total = sum(counts.values()) or 1
    return [
        ToolMixItem(category=category, count=count, percent=round(count / total * 100))
        for category, count in counts.most_common(limit)
    ]
