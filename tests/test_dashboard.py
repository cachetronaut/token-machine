from pathlib import Path

from fastapi.testclient import TestClient

from token_machine.dashboard.app import create_app
from token_machine.models import AgentSource, AnalyticsEvent, EventType, TokenUsage
from token_machine.storage.repository import AnalyticsRepository


def test_fastapi_dashboard_routes_return_html_and_summary(tmp_path: Path) -> None:
    repository = AnalyticsRepository(tmp_path)
    repository.write_events(
        [
            AnalyticsEvent(
                event_id="e1",
                event_type=EventType.MODEL_CALL,
                source=AgentSource.CODEX,
                source_path="/tmp/session.jsonl",
                session_id="s1",
                timestamp="2026-05-08T10:00:00Z",
                model="gpt-5.4",
                token_usage=TokenUsage(input_tokens=1, total_tokens=1),
            )
        ],
        [],
    )

    client = TestClient(create_app(tmp_path))
    html_response = client.get("/")
    summary_response = client.get("/api/summary")

    assert html_response.status_code == 200
    assert "Token Machine" in html_response.text
    assert summary_response.status_code == 200
    assert summary_response.json()["summary"]["sessions"] == 1
