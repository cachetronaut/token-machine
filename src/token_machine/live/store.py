"""Local store for live usage snapshots and file cursors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from token_machine.live.models import LiveUsageSnapshot, snapshot_from_mapping
from token_machine.models import AgentSource, JsonValue, jsonable
from token_machine.storage.jsonl import dumps_json


class LiveUsageStore:
    def __init__(self, store: Path) -> None:
        self.store = store

    @property
    def live_dir(self) -> Path:
        return self.store / "live"

    @property
    def snapshots_dir(self) -> Path:
        return self.live_dir / "snapshots"

    @property
    def cursors_path(self) -> Path:
        return self.live_dir / "cursors.json"

    def ensure(self) -> None:
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def write_snapshot(self, snapshot: LiveUsageSnapshot) -> None:
        self.ensure()
        path = self.snapshot_path(snapshot.source, snapshot.session_id)
        tmp_path = path.with_name(f".{path.name}.tmp")
        tmp_path.write_text(dumps_json(snapshot, indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def load_snapshots(self) -> list[LiveUsageSnapshot]:
        if not self.snapshots_dir.exists():
            return []
        snapshots: list[LiveUsageSnapshot] = []
        for path in sorted(self.snapshots_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except OSError, json.JSONDecodeError:
                continue
            if isinstance(data, Mapping):
                snapshots.append(snapshot_from_mapping(data))
        return snapshots

    def snapshot_path(self, source: AgentSource, session_id: str) -> Path:
        safe_session_id = "".join(
            char if char.isalnum() or char in {"-", "_", "."} else "-"
            for char in session_id
        )
        return self.snapshots_dir / f"{source.value}-{safe_session_id}.json"

    def load_cursors(self) -> dict[str, dict[str, JsonValue]]:
        if not self.cursors_path.exists():
            return {}
        try:
            data = json.loads(self.cursors_path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            return {}
        if not isinstance(data, Mapping):
            return {}
        cursors: dict[str, dict[str, JsonValue]] = {}
        for key, value in data.items():
            if isinstance(value, Mapping):
                cursor = jsonable(value)
                if isinstance(cursor, dict):
                    cursors[str(key)] = cursor
        return cursors

    def write_cursors(self, cursors: Mapping[str, Mapping[str, object]]) -> None:
        self.live_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self.cursors_path.with_name(f".{self.cursors_path.name}.tmp")
        tmp_path.write_text(dumps_json(cursors, indent=2), encoding="utf-8")
        tmp_path.replace(self.cursors_path)
