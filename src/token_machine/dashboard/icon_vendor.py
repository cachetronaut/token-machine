"""Download and cache dashboard icons."""

from __future__ import annotations

import io
import json
import tarfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from token_machine.dashboard.icons import LOBE_ICONS_PACKAGE
from token_machine.models import AgentSource, ModelFamily

NPM_REGISTRY = "https://registry.npmjs.org"

DownloadBytes = Callable[[str], bytes]


@dataclass(frozen=True)
class IconRefreshResult:
    package: str
    version: str
    icon_count: int
    icons_dir: Path
    icons_json: Path


def refresh_icon_cache(
    store: Path,
    requested: str | None = None,
    download_bytes: DownloadBytes | None = None,
) -> IconRefreshResult:
    """Fetch the icon package and refresh the local dashboard icon cache."""
    downloader = download_bytes or _download_bytes
    version, tarball_url = _resolve_version(requested, downloader)
    tarball = downloader(tarball_url)
    slug_map = _discover_slugs(tarball, _candidate_names())

    icons_dir = store / "cache" / "icons"
    icons_json = store / "cache" / "icons.json"
    _extract_svgs(tarball, slug_map, icons_dir)
    icons_json.parent.mkdir(parents=True, exist_ok=True)
    icons_json.write_text(
        json.dumps(
            {"package": LOBE_ICONS_PACKAGE, "version": version, "icons": slug_map},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return IconRefreshResult(
        package=LOBE_ICONS_PACKAGE,
        version=version,
        icon_count=len(slug_map),
        icons_dir=icons_dir,
        icons_json=icons_json,
    )


def _download_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url) as resp:
        return resp.read()


def _resolve_version(
    requested: str | None, download_bytes: DownloadBytes
) -> tuple[str, str]:
    tag = requested or "latest"
    meta = json.loads(download_bytes(f"{NPM_REGISTRY}/{LOBE_ICONS_PACKAGE}/{tag}"))
    return str(meta["version"]), str(meta["dist"]["tarball"])


def _candidate_names() -> list[str]:
    """Derive icon names from AgentSource and ModelFamily, excluding sentinels."""
    skip = {AgentSource.UNKNOWN, ModelFamily.OTHER}
    names: dict[str, None] = {}
    for enum_cls in (AgentSource, ModelFamily):
        for member in enum_cls:
            if member not in skip:
                names[member.value.lower()] = None
    names["geminicli"] = None
    return list(names)


def _discover_slugs(tarball: bytes, names: list[str]) -> dict[str, str]:
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tar:
        available = {
            member.name for member in tar.getmembers() if member.name.endswith(".svg")
        }

    mapping: dict[str, str] = {}
    for name in names:
        for candidate in (f"{name}-color.svg", f"{name}.svg"):
            if f"package/icons/{candidate}" in available:
                mapping[f"{name}.svg"] = candidate
                break
    return mapping


def _extract_svgs(tarball: bytes, slug_map: dict[str, str], icons_dir: Path) -> None:
    icons_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tar:
        for local_name, upstream_slug in slug_map.items():
            icon_file = tar.extractfile(f"package/icons/{upstream_slug}")
            if icon_file:
                (icons_dir / local_name).write_bytes(icon_file.read())
