"""FastAPI routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from token_machine.dashboard.render import render_dashboard
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

    return router
