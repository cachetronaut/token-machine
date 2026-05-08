from pathlib import Path

from token_machine.models import AgentSource, AnalyticsEvent, EventType, TokenUsage
from token_machine.storage.repository import AnalyticsRepository


def _event(source: AgentSource, event_id: str = "e1") -> AnalyticsEvent:
    return AnalyticsEvent(
        event_id=event_id,
        event_type=EventType.MODEL_CALL,
        source=source,
        source_path=f"/tmp/{source.value}.jsonl",
        session_id="same-session",
        timestamp="2026-05-08T10:00:00Z",
        model="gpt-5.4",
        token_usage=TokenUsage(input_tokens=1, total_tokens=1),
    )


def test_store_deduplicates_events_by_event_id(tmp_path: Path) -> None:
    repository = AnalyticsRepository(tmp_path)
    event = _event(AgentSource.CODEX)

    repository.write_events([event], [])
    repository.write_events([event], [])

    assert len(repository.load_events()) == 1


def test_rollups_do_not_collide_across_sources(tmp_path: Path) -> None:
    repository = AnalyticsRepository(tmp_path)

    repository.write_events(
        [
            _event(AgentSource.CODEX, "codex-event"),
            _event(AgentSource.CLAUDE, "claude-event"),
        ],
        [],
    )

    assert repository.session_path(AgentSource.CODEX, "same-session").exists()
    assert repository.session_path(AgentSource.CLAUDE, "same-session").exists()
