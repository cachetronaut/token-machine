"""Local analytics repository."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from token_machine.metrics.aggregate import bucket_series, group_sessions, rollup_events
from token_machine.models import (
    AgentSource,
    AnalyticsEvent,
    IngestResult,
    event_from_mapping,
    jsonable,
)
from token_machine.storage.jsonl import append_jsonl, read_jsonl, write_json
from token_machine.utils.time import utc_now


class AnalyticsRepository:
    def __init__(self, store: Path) -> None:
        self.store = store

    @property
    def events_dir(self) -> Path:
        return self.store / "events"

    @property
    def sessions_dir(self) -> Path:
        return self.store / "sessions"

    @property
    def daily_dir(self) -> Path:
        return self.store / "daily"

    def ensure(self) -> None:
        for path in (
            self.events_dir,
            self.sessions_dir,
            self.daily_dir,
            self.store / "cache" / "icons",
        ):
            path.mkdir(parents=True, exist_ok=True)

    def load_events(self) -> list[AnalyticsEvent]:
        events: list[AnalyticsEvent] = []
        if not self.events_dir.exists():
            return events
        for path in sorted(self.events_dir.glob("*.jsonl")):
            for row in read_jsonl(path):
                events.append(event_from_mapping(row))
        return events

    def load_existing_event_ids(self) -> set[str]:
        return {event.event_id for event in self.load_events()}

    def write_events(
        self, events: list[AnalyticsEvent], results: list[IngestResult]
    ) -> None:
        self.ensure()
        existing_ids = self.load_existing_event_ids()
        monthly_events: dict[str, list[AnalyticsEvent]] = defaultdict(list)
        for event in events:
            if event.event_id in existing_ids:
                continue
            month = (event.timestamp or utc_now())[:7]
            monthly_events[month].append(event)

        for month, rows in monthly_events.items():
            append_jsonl(self.events_dir / f"{month}.jsonl", rows)

        by_session = group_sessions(events)
        for (source, session_id), session_events in by_session.items():
            rollup = rollup_events(session_events)
            write_json(self.session_path(source, session_id), rollup)

        manifest_rows: list[dict[str, object]] = []
        for result in results:
            result_data = jsonable(result)
            row: dict[str, object] = {"ingested_at": utc_now(), "schema_version": 1}
            if isinstance(result_data, dict):
                row.update(result_data)
            manifest_rows.append(row)
        append_jsonl(self.store / "manifest.jsonl", manifest_rows)
        self.write_daily_rollups()

    def write_daily_rollups(self) -> None:
        events = self.load_events()
        for row in bucket_series(events, width=10, limit=10_000):
            write_json(self.daily_dir / f"{row.day}.json", row.summary)

    def session_path(self, source: AgentSource, session_id: str) -> Path:
        safe_session_id = "".join(
            char if char.isalnum() or char in {"-", "_", "."} else "-"
            for char in session_id
        )
        return self.sessions_dir / f"{source.value}-{safe_session_id}.json"
