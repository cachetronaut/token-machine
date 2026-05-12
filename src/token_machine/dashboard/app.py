"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fastapi import FastAPI

from token_machine.dashboard.routes import dashboard_router


def create_app(store: Path, *, live_targets: Sequence[Path] = ()) -> FastAPI:
    app = FastAPI(title="Token Machine")
    app.include_router(dashboard_router(store, live_targets=live_targets))
    return app
