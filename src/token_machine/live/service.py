"""Live usage snapshot refresh service."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from token_machine.config import DEFAULT_WATCH_PATHS
from token_machine.ingest.discovery import detect_source, discover_files
from token_machine.live.models import LiveData, LiveProbeStatus
from token_machine.live.models import LiveUsageSnapshot
from token_machine.live.probes import codex_snapshot, gemini_snapshot, claude_snapshot
from token_machine.live.store import LiveUsageStore
from token_machine.models import AgentSource, jsonable
from token_machine.sources import ClaudeSource, CodexSource, GeminiSource
from token_machine.sources.base import SessionSource
from token_machine.utils.time import parse_timestamp, utc_now

LIVE_SOURCES: tuple[SessionSource, ...] = (
    CodexSource(),
    ClaudeSource(),
    GeminiSource(),
)
ACTIVE_WINDOW_SECONDS = 6 * 60 * 60


def refresh_live_snapshots(
    targets: Sequence[Path] = DEFAULT_WATCH_PATHS,
    store: Path | None = None,
    *,
    active_window_seconds: int = ACTIVE_WINDOW_SECONDS,
    sources: tuple[SessionSource, ...] = LIVE_SOURCES,
) -> LiveData:
    if store is None:
        from token_machine.config import DEFAULT_STORE

        store = DEFAULT_STORE

    live_store = LiveUsageStore(store)
    live_store.ensure()
    discovered = discover_files(list(targets), sources)
    now = time.time()
    cursors = live_store.load_cursors()
    snapshots = []

    for path in discovered:
        try:
            stat = path.stat()
        except OSError:
            continue
        if now - stat.st_mtime > active_window_seconds:
            continue
        cursors[str(path)] = {
            "source_path": str(path),
            "last_size": stat.st_size,
            "last_mtime": stat.st_mtime,
            "last_seen_at": utc_now(),
        }
        try:
            source, objects = detect_source(path, sources)
        except OSError, json.JSONDecodeError, ValueError:
            continue
        if source is None:
            continue
        snapshot = _snapshot_for_source(source.name, path, objects)
        if snapshot is None:
            continue
        live_store.write_snapshot(snapshot)
        snapshots.append(snapshot)

    live_store.write_cursors(cursors)
    if not snapshots:
        snapshots = live_store.load_snapshots()
    return live_data(snapshots)


def live_data(
    snapshots: Sequence[object], *, stale_after_seconds: int = 15
) -> LiveData:
    typed = [
        snapshot for snapshot in snapshots if isinstance(snapshot, LiveUsageSnapshot)
    ]
    now = datetime.now(UTC)
    typed = [_mark_stale(snapshot, now, stale_after_seconds) for snapshot in typed]
    active_count = sum(
        getattr(snapshot, "status", None) == LiveProbeStatus.ACTIVE
        for snapshot in typed
    )
    stale_count = sum(
        getattr(snapshot, "status", None) == LiveProbeStatus.STALE for snapshot in typed
    )
    return LiveData(
        generated_at=utc_now(),
        active_count=active_count,
        stale_count=stale_count,
        snapshots=list(typed),
    )


def start_live_loop(
    paths: Sequence[Path],
    store: Path,
    interval_seconds: int,
    *,
    refresh: Callable[..., LiveData] = refresh_live_snapshots,
) -> None:
    def live_target() -> None:
        while True:
            try:
                refresh(paths, store)
            except Exception:
                pass
            time.sleep(max(2, interval_seconds))

    thread = threading.Thread(target=live_target, daemon=True)
    thread.start()


def reload_state(store: Path) -> dict[str, object]:
    roots = [
        Path(__file__).parents[1] / "dashboard" / "assets",
        Path(__file__).parents[1] / "dashboard" / "templates",
        store / "live" / "snapshots",
    ]
    latest = 0.0
    checked = 0
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            checked += 1
            try:
                latest = max(latest, path.stat().st_mtime)
            except OSError:
                continue
    return {
        "generated_at": utc_now(),
        "reload_token": str(int(latest)),
        "latest_mtime": latest,
        "paths_checked": checked,
    }


def _snapshot_for_source(
    source: AgentSource, path: Path, objects: Sequence[Mapping[str, object]]
):
    if source == AgentSource.CODEX:
        return codex_snapshot(path, objects)
    if source == AgentSource.CLAUDE_CODE:
        return claude_snapshot(path, objects)
    if source == AgentSource.GEMINI:
        return gemini_snapshot(path, objects)
    return None


def live_data_from_store(store: Path) -> LiveData:
    snapshots = LiveUsageStore(store).load_snapshots()
    return live_data(snapshots)


def live_json_from_store(store: Path):
    return jsonable(live_data_from_store(store))


def _mark_stale(
    snapshot: LiveUsageSnapshot, now: datetime, stale_after_seconds: int
) -> LiveUsageSnapshot:
    if snapshot.status != LiveProbeStatus.ACTIVE:
        return snapshot
    observed_at = parse_timestamp(snapshot.observed_at)
    if observed_at is None:
        return replace(snapshot, status=LiveProbeStatus.STALE)
    age = (now - observed_at).total_seconds()
    if age > stale_after_seconds:
        return replace(snapshot, status=LiveProbeStatus.STALE)
    return snapshot
