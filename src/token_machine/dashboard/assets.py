"""Package asset loading for the dashboard."""

from __future__ import annotations

from importlib import resources
from pathlib import Path, PurePosixPath

from fastapi import HTTPException
from fastapi.responses import Response

_ASSET_SUFFIXES = {
    "css": ".css",
    "js": ".js",
    "icons": ".svg",
    "img": ".png",
}

_MEDIA_TYPES = {
    "css": "text/css; charset=utf-8",
    "js": "text/javascript; charset=utf-8",
    "icons": "image/svg+xml; charset=utf-8",
    "img": "image/png",
}


def dashboard_asset_response(
    kind: str, name: str, icons_dir: Path | None = None
) -> Response:
    if kind not in _ASSET_SUFFIXES:
        raise HTTPException(status_code=404)
    if PurePosixPath(name).name != name or not name.endswith(_ASSET_SUFFIXES[kind]):
        raise HTTPException(status_code=404)

    if kind == "icons":
        if icons_dir is not None:
            icon_path = icons_dir / name
            if icon_path.is_file():
                return Response(
                    icon_path.read_text(encoding="utf-8"),
                    media_type=_MEDIA_TYPES["icons"],
                    headers={"Cache-Control": "no-store"},
                )

    asset = resources.files("token_machine.dashboard").joinpath("assets", kind, name)
    if not asset.is_file():
        raise HTTPException(status_code=404)

    if kind == "img":
        return Response(
            asset.read_bytes(),
            media_type=_MEDIA_TYPES[kind],
            headers={"Cache-Control": "no-store"},
        )

    return Response(
        asset.read_text(encoding="utf-8"),
        media_type=_MEDIA_TYPES[kind],
        headers={"Cache-Control": "no-store"},
    )
