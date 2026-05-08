from token_machine.metrics.profiles import dashboard_data
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
