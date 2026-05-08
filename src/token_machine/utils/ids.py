"""Stable id helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_event_id(*parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
