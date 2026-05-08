"""Package asset loading for the dashboard."""

from __future__ import annotations

from importlib import resources
from pathlib import PurePosixPath

from fastapi import HTTPException
from fastapi.responses import Response

from token_machine.dashboard.icons import ICON_NAMES

_ASSET_SUFFIXES = {
    "css": ".css",
    "js": ".js",
    "icons": ".svg",
}

_MEDIA_TYPES = {
    "css": "text/css; charset=utf-8",
    "js": "text/javascript; charset=utf-8",
    "icons": "image/svg+xml; charset=utf-8",
}


def dashboard_asset_response(kind: str, name: str) -> Response:
    if kind not in _ASSET_SUFFIXES:
        raise HTTPException(status_code=404)
    if PurePosixPath(name).name != name or not name.endswith(_ASSET_SUFFIXES[kind]):
        raise HTTPException(status_code=404)
    if kind == "icons" and name not in ICON_NAMES:
        raise HTTPException(status_code=404)

    asset = resources.files("token_machine.dashboard").joinpath(
        "assets",
        kind,
        name,
    )
    if not asset.is_file():
        raise HTTPException(status_code=404)

    return Response(asset.read_text(encoding="utf-8"), media_type=_MEDIA_TYPES[kind])
