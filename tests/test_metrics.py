from token_machine.metrics.aggregate import dashboard_summary
from token_machine.metrics.profiles import dashboard_data
from token_machine.metrics.tools import observed_tool_counts, tool_mix
from token_machine.models import (
    AgentSource,
    AnalyticsEvent,
    DashboardData,
    EventType,
    TokenUsage,
)


def test_dashboard_data_returns_dataclasses_until_route_serialization() -> None:
    data = dashboard_data(
        [
            AnalyticsEvent(
                event_id="e1",
                event_type=EventType.MODEL_CALL,
                source=AgentSource.CODEX,
                source_path="/tmp/session.jsonl",
                session_id="s1",
                timestamp="2026-05-08T10:00:00Z",
                model="gpt-5.4",
                token_usage=TokenUsage(input_tokens=3, total_tokens=3),
            )
        ]
    )

    assert isinstance(data, DashboardData)
    assert data.summary.sessions == 1
    assert data.model_profiles[0].model == "gpt-5.4"


def test_tool_mix_uses_observed_tool_and_cli_labels() -> None:
    events = [
        AnalyticsEvent(
            event_id="e1",
            event_type=EventType.TOOL_CALL,
            source=AgentSource.CODEX,
            source_path="/tmp/session.jsonl",
            session_id="s1",
            tool_name="custom_repo_scan",
        ),
        AnalyticsEvent(
            event_id="e2",
            event_type=EventType.CLI_COMMAND,
            source=AgentSource.CODEX,
            source_path="/tmp/session.jsonl",
            session_id="s1",
            tool_name="exec_command",
            cli_name="rg",
            command="rg token_machine src",
        ),
    ]

    assert observed_tool_counts(events) == {"Custom Repo Scan": 1, "Rg": 1}
    assert [item.category for item in tool_mix(events)] == ["Custom Repo Scan", "Rg"]


def test_cli_counts_include_commands_attached_to_tool_calls() -> None:
    data = dashboard_summary(
        [
            AnalyticsEvent(
                event_id="e1",
                event_type=EventType.TOOL_CALL,
                source=AgentSource.CLAUDE_CODE,
                source_path="/tmp/session.jsonl",
                session_id="s1",
                tool_name="Bash",
                cli_name="git",
                command="git status --short",
            )
        ]
    )

    assert data.tools == {"Bash": 1}
    assert data.clis == {"Git": 1}


def test_tool_mix_populates_descriptions() -> None:
    events = [
        AnalyticsEvent(
            event_id="e1",
            event_type=EventType.TOOL_CALL,
            source=AgentSource.GEMINI,
            source_path="/tmp/s1.json",
            session_id="s1",
            tool_name="ls",
            tool_description="Specific list",
        ),
        AnalyticsEvent(
            event_id="e2",
            event_type=EventType.CLI_COMMAND,
            source=AgentSource.CODEX,
            source_path="/tmp/s1.jsonl",
            session_id="s1",
            cli_name="bash",
            command="git status",
        ),
    ]

    mix = tool_mix(events)
    # Priority 1: Captured description from Gemini
    ls_item = next(item for item in mix if item.category == "Ls")
    assert ls_item.description == "E.g., specific list"

    # Priority 2: Real command example from Codex event
    bash_item = next(item for item in mix if item.category == "Bash")
    assert bash_item.description == "E.g., git status"


def test_tool_mix_prefers_shortest_command() -> None:
    events = [
        AnalyticsEvent(
            event_id="e1",
            event_type=EventType.CLI_COMMAND,
            source=AgentSource.CODEX,
            source_path="/tmp/s1.jsonl",
            session_id="s1",
            cli_name="rg",
            command='rg -n "very long pattern that we want to avoid showing in the UI"',
        ),
        AnalyticsEvent(
            event_id="e2",
            event_type=EventType.CLI_COMMAND,
            source=AgentSource.CODEX,
            source_path="/tmp/s1.jsonl",
            session_id="s1",
            cli_name="rg",
            command="rg short",
        ),
    ]

    mix = tool_mix(events)
    rg_item = next(item for item in mix if item.category == "Rg")
    # Should pick 'rg short' even if it appeared later
    assert rg_item.description == "E.g., rg short"


def test_tool_mix_truncates_long_descriptions() -> None:
    events = [
        AnalyticsEvent(
            event_id="e1",
            event_type=EventType.CLI_COMMAND,
            source=AgentSource.CODEX,
            source_path="/tmp/s1.jsonl",
            session_id="s1",
            cli_name="long-cli",
            command="a" * 100,
        ),
    ]

    mix = tool_mix(events)
    item = next(item for item in mix if item.category == "Long Cli")
    # 60 chars content + 6 chars "E.g., " = 66
    assert len(item.description) <= 66
    assert item.description.endswith("...")
