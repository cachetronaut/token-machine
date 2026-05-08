"""Vendor SVG icons from @lobehub/icons-static-svg into the local store cache.

Icons land at ``store/cache/icons/*.svg`` and the slug mapping at
``store/cache/icons.json``.  Icon names are derived automatically from
AgentSource and ModelFamily — add a new enum value and re-run.

Usage:
    python scripts/vendor_icons.py                     # fetch latest, default store
    python scripts/vendor_icons.py 1.91.0              # pin a version
    python scripts/vendor_icons.py latest /path/store  # custom store path
"""

from __future__ import annotations

import io
import json
import sys
import tarfile
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NPM_REGISTRY = "https://registry.npmjs.org"
PACKAGE = "@lobehub/icons-static-svg"


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def download_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url) as resp:
        return resp.read()


def resolve_version(requested: str | None) -> tuple[str, str]:
    tag = requested or "latest"
    meta = fetch_json(f"{NPM_REGISTRY}/{PACKAGE}/{tag}")
    return meta["version"], meta["dist"]["tarball"]


def default_store() -> Path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from token_machine.utils.paths import user_data_dir

    return user_data_dir()


def candidate_names() -> list[str]:
    """Derive icon names from AgentSource and ModelFamily, excluding sentinel values."""
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from token_machine.models import AgentSource, ModelFamily

    skip = {AgentSource.UNKNOWN, ModelFamily.OTHER}
    names: dict[str, None] = {}  # ordered dedup
    for enum_cls in (AgentSource, ModelFamily):
        for member in enum_cls:
            if member not in skip:
                names[member.value.lower()] = None
    return list(names)


def discover_slugs(tarball: bytes, names: list[str]) -> dict[str, str]:
    """For each name, find the best matching slug in the tarball."""
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tf:
        available = {m.name for m in tf.getmembers() if m.name.endswith(".svg")}

    mapping: dict[str, str] = {}
    for name in names:
        for candidate in (f"{name}-color.svg", f"{name}.svg"):
            if f"package/icons/{candidate}" in available:
                mapping[f"{name}.svg"] = candidate
                print(f"  {name} -> {candidate}")
                break
        else:
            print(f"  WARNING: no icon found for {name!r} — skipping")
    return mapping


def extract_svgs(tarball: bytes, slug_map: dict[str, str], icons_dir: Path) -> None:
    icons_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tf:
        for local_name, upstream_slug in slug_map.items():
            f = tf.extractfile(f"package/icons/{upstream_slug}")
            if f:
                (icons_dir / local_name).write_bytes(f.read())


def main() -> None:
    args = sys.argv[1:]
    requested = args[0] if args else None
    store = Path(args[1]) if len(args) > 1 else default_store()

    icons_dir = store / "cache" / "icons"
    icons_json = store / "cache" / "icons.json"

    print(f"Store: {store}")
    print(f"Resolving {PACKAGE}@{requested or 'latest'} ...")
    version, tarball_url = resolve_version(requested)
    print(f"  -> {version}")

    print("Downloading tarball ...")
    tarball = download_bytes(tarball_url)

    print("Discovering icons from AgentSource + ModelFamily ...")
    names = candidate_names()
    slug_map = discover_slugs(tarball, names)

    print(f"Extracting SVGs to {icons_dir} ...")
    extract_svgs(tarball, slug_map, icons_dir)

    print(f"Writing {icons_json} ...")
    icons_json.write_text(
        json.dumps(
            {"package": PACKAGE, "version": version, "icons": slug_map}, indent=2
        )
        + "\n"
    )

    print(f"\nDone. {len(slug_map)} icon(s) vendored at v{version}.")


if __name__ == "__main__":
    main()
