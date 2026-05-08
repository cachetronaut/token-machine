"""Ingestion pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from token_machine.ingest.discovery import detect_source, discover_files
from token_machine.models import AgentSource, AnalyticsEvent, IngestResult, IngestStatus
from token_machine.sources import DEFAULT_SOURCES
from token_machine.sources.base import SessionSource, session_id_from_path
from token_machine.storage.repository import AnalyticsRepository


def ingest(
    targets: list[Path],
    store: Path,
    sources: tuple[SessionSource, ...] = DEFAULT_SOURCES,
) -> list[IngestResult]:
    repository = AnalyticsRepository(store)
    all_events: list[AnalyticsEvent] = []
    results: list[IngestResult] = []

    discovered = discover_files(targets, sources)
    if not discovered:
        results.extend(
            IngestResult(
                source_path=str(target),
                source=AgentSource.UNKNOWN,
                session_id="",
                event_count=0,
                status=IngestStatus.ERROR,
                error="no session files found",
            )
            for target in targets
        )
        repository.write_events([], results)
        return results

    for path in discovered:
        try:
            source, objects = detect_source(path, sources)
            if source is None:
                results.append(
                    IngestResult(
                        source_path=str(path),
                        source=AgentSource.UNKNOWN,
                        session_id=session_id_from_path(path),
                        event_count=0,
                        status=IngestStatus.SKIPPED,
                        error="no supported source detected",
                    )
                )
                continue
            events = source.parse(path, objects)
            all_events.extend(events)
            results.append(
                IngestResult(
                    source_path=str(path),
                    source=source.name,
                    session_id=events[0].session_id
                    if events
                    else session_id_from_path(path),
                    event_count=len(events),
                    status=IngestStatus.OK if events else IngestStatus.SKIPPED,
                    error="" if events else "no supported events found",
                )
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            results.append(
                IngestResult(
                    source_path=str(path),
                    source=AgentSource.UNKNOWN,
                    session_id=session_id_from_path(path),
                    event_count=0,
                    status=IngestStatus.ERROR,
                    error=str(exc),
                )
            )

    repository.write_events(all_events, results)
    return results
