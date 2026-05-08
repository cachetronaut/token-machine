"""Time helpers."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def seconds_between(start: str, end: str) -> int:
    start_at = parse_timestamp(start)
    end_at = parse_timestamp(end)
    if not start_at or not end_at:
        return 0
    return max(0, round((end_at - start_at).total_seconds()))
