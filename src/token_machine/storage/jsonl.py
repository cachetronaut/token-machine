"""JSON and JSONL edge serialization."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Mapping

from token_machine.models import JsonValue, jsonable


def dumps_json(value: object, *, indent: int | None = None) -> str:
    return json.dumps(jsonable(value), indent=indent, sort_keys=True) + "\n"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_json(value, indent=2), encoding="utf-8")


def append_jsonl(path: Path, rows: Sequence[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        for row in rows:
            file.write(dumps_json(row))


def read_jsonl(path: Path) -> list[Mapping[str, JsonValue]]:
    rows: list[Mapping[str, JsonValue]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, Mapping):
                rows.append(value)
    return rows
