"""FastAPI routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, Response

from token_machine.dashboard.assets import dashboard_asset_response
from token_machine.dashboard.render import render_dashboard
from token_machine.config import DEFAULT_WATCH_PATHS
from token_machine.live.service import (
    live_data_from_store,
    refresh_live_snapshots,
    reload_state,
)
from token_machine.metrics.profiles import dashboard_data
from token_machine.models import jsonable
from token_machine.storage.repository import AnalyticsRepository


def dashboard_router(store: Path) -> APIRouter:
    router = APIRouter()
    repository = AnalyticsRepository(store)

    @router.get("/", response_class=HTMLResponse)
    def index() -> str:
        return render_dashboard()

    @router.get("/api/summary")
    def summary() -> JSONResponse:
        data = dashboard_data(repository.load_events())
        return JSONResponse(jsonable(data))

    @router.get("/api/live")
    def live() -> JSONResponse:
        return JSONResponse(jsonable(live_data_from_store(store)))

    @router.get("/api/debug/reload")
    def debug_reload_state() -> JSONResponse:
        return JSONResponse(reload_state(store))

    @router.post("/api/debug/reload")
    def debug_reload() -> JSONResponse:
        live_data = refresh_live_snapshots(DEFAULT_WATCH_PATHS, store)
        payload = reload_state(store)
        payload["live"] = jsonable(live_data)
        return JSONResponse(payload)

    icons_dir = store / "cache" / "icons"

    @router.get("/assets/{kind}/{name}")
    def asset(kind: str, name: str) -> Response:
        return dashboard_asset_response(kind, name, icons_dir)

    return router
