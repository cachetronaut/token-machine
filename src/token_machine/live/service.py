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
from token_machine.live.models import LiveData, LiveProbeStatus, LiveSnapshotOrigin
from token_machine.live.models import LiveUsageSnapshot
from token_machine.live.probes import codex_snapshot, gemini_snapshot, claude_snapshot
from token_machine.live.statusline import capture_configured_claude_statusline
from token_machine.live.store import LiveUsageStore
from token_machine.models import AgentSource, JsonValue, jsonable
from token_machine.sources import ClaudeSource, CodexSource, GeminiSource
from token_machine.sources.base import SessionSource
from token_machine.utils.time import parse_timestamp, utc_now

LIVE_SOURCES: tuple[SessionSource, ...] = (
    CodexSource(),
    ClaudeSource(),
    GeminiSource(),
)
ACTIVE_WINDOW_SECONDS = 6 * 60 * 60
PROBE_STALE_SECONDS = 20
SESSION_ACTIVE_SECONDS = 10 * 60
LIVE_SNAPSHOT_TTL_SECONDS = 60 * 60
CLAUDE_STATUSLINE_REFRESH_SECONDS = 30
CLAUDE_STATUSLINE_TIMEOUT_SECONDS = 2.0


def refresh_live_snapshots(
    targets: Sequence[Path] = DEFAULT_WATCH_PATHS,
    store: Path | None = None,
    *,
    active_window_seconds: int = ACTIVE_WINDOW_SECONDS,
    live_snapshot_ttl_seconds: int = LIVE_SNAPSHOT_TTL_SECONDS,
    sources: tuple[SessionSource, ...] = LIVE_SOURCES,
) -> LiveData:
    if store is None:
        from token_machine.config import DEFAULT_STORE

        store = DEFAULT_STORE

    live_store = LiveUsageStore(store)
    live_store.ensure()
    live_store.prune_expired_snapshots(live_snapshot_ttl_seconds)
    discovered = discover_files(list(targets), sources)
    now = time.time()
    now_at = datetime.now(UTC)
    cursors = live_store.load_cursors()
    existing_snapshots = live_store.load_snapshots()
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
        snapshot = _preserve_existing_claude_limits(snapshot, existing_snapshots)
        if not snapshot.updated_at:
            continue
        if _snapshot_cache_expired(snapshot, now_at, live_snapshot_ttl_seconds):
            continue
        live_store.write_snapshot(snapshot)
        snapshots.append(snapshot)

    claude_snapshots = [
        snapshot
        for snapshot in snapshots
        if snapshot.source == AgentSource.CLAUDE_CODE
        and snapshot.origin != LiveSnapshotOrigin.STATUSLINE.value
    ]
    if claude_snapshots:
        for claude_root in _claude_roots_from_targets(targets):
            maybe_capture_claude_statusline(
                claude_root,
                live_store,
                now=now_at,
                current_snapshots=claude_snapshots,
                cursors=cursors,
            )

    live_store.write_cursors(cursors)
    return live_data(live_store.load_snapshots())


def maybe_capture_claude_statusline(
    claude_root: Path,
    store: LiveUsageStore,
    *,
    now: datetime,
    min_interval_seconds: int = CLAUDE_STATUSLINE_REFRESH_SECONDS,
    current_snapshots: Sequence[LiveUsageSnapshot] = (),
    cursors: dict[str, dict[str, JsonValue]] | None = None,
) -> None:
    if not current_snapshots:
        return
    should_write_cursors = cursors is None
    active_cursors = cursors if cursors is not None else store.load_cursors()
    cursor_key = _claude_statusline_cursor_key(claude_root)
    if not _should_refresh_claude_statusline(
        store.load_snapshots(),
        active_cursors,
        cursor_key=cursor_key,
        now=now,
        min_interval_seconds=min_interval_seconds,
    ):
        return
    active_cursors[cursor_key] = {
        "source_path": cursor_key,
        "last_seen_at": utc_now(),
    }
    if should_write_cursors:
        store.write_cursors(active_cursors)
    snapshot = _latest_snapshot(current_snapshots)
    capture_configured_claude_statusline(
        claude_root,
        store.store,
        payload=_claude_statusline_payload(snapshot),
        timeout_seconds=CLAUDE_STATUSLINE_TIMEOUT_SECONDS,
    )


def _should_refresh_claude_statusline(
    snapshots: Sequence[LiveUsageSnapshot],
    cursors: Mapping[str, Mapping[str, object]],
    *,
    cursor_key: str,
    now: datetime,
    min_interval_seconds: int,
) -> bool:
    last_attempt = parse_timestamp(str(cursors.get(cursor_key, {}).get("last_seen_at")))
    if (
        last_attempt is not None
        and (now - last_attempt).total_seconds() < min_interval_seconds
    ):
        return False
    latest_limits = _latest_claude_limit_snapshot(snapshots)
    if latest_limits is None:
        return True
    observed_at = parse_timestamp(latest_limits.observed_at) or parse_timestamp(
        latest_limits.updated_at
    )
    if observed_at is None:
        return True
    return (now - observed_at).total_seconds() >= min_interval_seconds


def _claude_roots_from_targets(targets: Sequence[Path]) -> list[Path]:
    roots: list[Path] = []
    for target in targets:
        parts = target.expanduser().parts
        if ".claude" not in parts:
            continue
        root = Path(*parts[: parts.index(".claude") + 1])
        if root not in roots:
            roots.append(root)
    return roots


def _claude_statusline_cursor_key(claude_root: Path) -> str:
    return f"claude-statusline:{claude_root.expanduser()}"


def _claude_statusline_payload(snapshot: LiveUsageSnapshot) -> dict[str, object]:
    payload: dict[str, object] = {
        "session_id": snapshot.session_id,
        "transcript_path": snapshot.source_path,
    }
    if snapshot.model:
        payload["model"] = {"id": snapshot.model, "display_name": snapshot.model}
    if snapshot.project_path:
        payload["workspace"] = {"current_dir": snapshot.project_path}
        payload["cwd"] = snapshot.project_path
    if snapshot.context.used_percent or snapshot.context.used_tokens:
        payload["context_window"] = {
            "used_percentage": snapshot.context.used_percent,
            "used_tokens": snapshot.context.used_tokens,
            "window_tokens": snapshot.context.window_tokens,
        }
    rate_limits = _claude_statusline_rate_limits_payload(snapshot)
    if rate_limits:
        payload["rate_limits"] = rate_limits
    return payload


def _claude_statusline_rate_limits_payload(
    snapshot: LiveUsageSnapshot,
) -> dict[str, dict[str, object]]:
    output: dict[str, dict[str, object]] = {}
    for limit in snapshot.rate_limits:
        output[limit.name] = _claude_limit_payload(
            used_percent=limit.used_percent,
            resets_at=limit.resets_at,
        )
    for limit in snapshot.session_limits:
        used_percent = limit.used_percent
        if not used_percent and limit.remaining_percent:
            used_percent = max(0, 100 - limit.remaining_percent)
        payload = _claude_limit_payload(
            used_percent=used_percent,
            resets_at=limit.resets_at,
        )
        if limit.remaining_percent:
            payload["remaining_percent"] = limit.remaining_percent
        output[limit.name] = {**output.get(limit.name, {}), **payload}
    return output


def _claude_limit_payload(*, used_percent: int, resets_at: str) -> dict[str, object]:
    payload: dict[str, object] = {"used_percentage": used_percent}
    if resets_at:
        payload["resets_at"] = resets_at
    return payload


def _latest_snapshot(
    snapshots: Sequence[LiveUsageSnapshot],
) -> LiveUsageSnapshot:
    return sorted(
        snapshots,
        key=lambda item: (
            parse_timestamp(item.observed_at)
            or parse_timestamp(item.updated_at)
            or datetime.min.replace(tzinfo=UTC)
        ),
    )[-1]


def live_data(
    snapshots: Sequence[object],
    *,
    stale_after_seconds: int = PROBE_STALE_SECONDS,
    session_active_seconds: int = SESSION_ACTIVE_SECONDS,
) -> LiveData:
    typed = [
        snapshot for snapshot in snapshots if isinstance(snapshot, LiveUsageSnapshot)
    ]
    now = datetime.now(UTC)
    typed = [
        _mark_stale(snapshot, now, stale_after_seconds, session_active_seconds)
        for snapshot in typed
    ]
    typed = _apply_latest_claude_limits(typed)
    typed = _visible_snapshots(typed)
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


def _visible_snapshots(
    snapshots: Sequence[LiveUsageSnapshot],
) -> list[LiveUsageSnapshot]:
    return [
        snapshot
        for snapshot in snapshots
        if not _is_claude_statusline_carrier(snapshot)
    ]


def _is_claude_statusline_carrier(snapshot: LiveUsageSnapshot) -> bool:
    return (
        snapshot.source == AgentSource.CLAUDE_CODE
        and snapshot.origin == LiveSnapshotOrigin.STATUSLINE.value
        and snapshot.source_path.startswith("claude-statusline:")
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
    assets_root = Path(__file__).parents[1] / "dashboard" / "assets"
    templates_root = Path(__file__).parents[1] / "dashboard" / "templates"
    roots = [assets_root, templates_root]
    latest = 0.0
    css_latest = 0.0
    script_latest = 0.0
    checked = 0
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            checked += 1
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            latest = max(latest, mtime)
            if path.suffix == ".css":
                css_latest = max(css_latest, mtime)
            if path.suffix in {".js", ".html"}:
                script_latest = max(script_latest, mtime)
    return {
        "generated_at": utc_now(),
        "reload_token": str(int(latest)),
        "css_reload_token": str(int(css_latest)),
        "script_reload_token": str(int(script_latest)),
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
    live_store = LiveUsageStore(store)
    live_store.prune_expired_snapshots(LIVE_SNAPSHOT_TTL_SECONDS)
    snapshots = live_store.load_snapshots()
    return live_data(snapshots)


def live_json_from_store(store: Path):
    return jsonable(live_data_from_store(store))


def _mark_stale(
    snapshot: LiveUsageSnapshot,
    now: datetime,
    stale_after_seconds: int,
    session_active_seconds: int,
) -> LiveUsageSnapshot:
    if snapshot.status != LiveProbeStatus.ACTIVE:
        return snapshot
    observed_at = parse_timestamp(snapshot.observed_at)
    if observed_at is None:
        return replace(snapshot, status=LiveProbeStatus.STALE)
    observed_age = (now - observed_at).total_seconds()
    if observed_age > stale_after_seconds:
        return replace(snapshot, status=LiveProbeStatus.STALE)

    updated_at = parse_timestamp(snapshot.updated_at)
    if updated_at is None:
        return replace(snapshot, status=LiveProbeStatus.STALE)
    session_age = (now - updated_at).total_seconds()
    if session_age > session_active_seconds:
        return replace(snapshot, status=LiveProbeStatus.STALE)
    return snapshot


def _apply_latest_claude_limits(
    snapshots: Sequence[LiveUsageSnapshot],
) -> list[LiveUsageSnapshot]:
    latest = _latest_claude_limit_snapshot(snapshots)
    if latest is None:
        return list(snapshots)
    output: list[LiveUsageSnapshot] = []
    for snapshot in snapshots:
        if snapshot.source != AgentSource.CLAUDE_CODE or snapshot.session_limits:
            output.append(snapshot)
            continue
        output.append(
            replace(
                snapshot,
                rate_limits=latest.rate_limits,
                session_limits=latest.session_limits,
            )
        )
    return output


def _preserve_existing_claude_limits(
    snapshot: LiveUsageSnapshot, existing_snapshots: Sequence[LiveUsageSnapshot]
) -> LiveUsageSnapshot:
    if snapshot.source != AgentSource.CLAUDE_CODE or snapshot.session_limits:
        return snapshot
    existing = _matching_claude_limit_snapshot(snapshot, existing_snapshots)
    if existing is None:
        return snapshot
    return replace(
        snapshot,
        rate_limits=existing.rate_limits,
        session_limits=existing.session_limits,
    )


def _matching_claude_limit_snapshot(
    snapshot: LiveUsageSnapshot, existing_snapshots: Sequence[LiveUsageSnapshot]
) -> LiveUsageSnapshot | None:
    matches = [
        existing
        for existing in existing_snapshots
        if existing.source == AgentSource.CLAUDE_CODE
        and existing.session_limits
        and (
            existing.session_id == snapshot.session_id
            or (
                bool(existing.source_path)
                and bool(snapshot.source_path)
                and existing.source_path == snapshot.source_path
            )
            or (
                bool(existing.project_path)
                and bool(snapshot.project_path)
                and existing.project_path == snapshot.project_path
            )
        )
    ]
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda item: (
            parse_timestamp(item.observed_at)
            or parse_timestamp(item.updated_at)
            or datetime.min.replace(tzinfo=UTC)
        ),
    )[-1]


def _latest_claude_limit_snapshot(
    snapshots: Sequence[LiveUsageSnapshot],
) -> LiveUsageSnapshot | None:
    with_limits = [
        snapshot
        for snapshot in snapshots
        if snapshot.source == AgentSource.CLAUDE_CODE and snapshot.session_limits
    ]
    if not with_limits:
        return None
    return sorted(
        with_limits,
        key=lambda item: (
            parse_timestamp(item.observed_at)
            or parse_timestamp(item.updated_at)
            or datetime.min.replace(tzinfo=UTC)
        ),
    )[-1]


def _snapshot_cache_expired(
    snapshot: LiveUsageSnapshot, now: datetime, ttl_seconds: int
) -> bool:
    touched_at = parse_timestamp(snapshot.updated_at) or parse_timestamp(
        snapshot.observed_at
    )
    if touched_at is None:
        return False
    return (now - touched_at).total_seconds() > ttl_seconds
