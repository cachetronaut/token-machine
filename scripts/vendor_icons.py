"""Vendor SVG icons into the local store cache.

Usage:
    python scripts/vendor_icons.py                     # fetch latest, default store
    python scripts/vendor_icons.py 1.91.0              # pin a version
    python scripts/vendor_icons.py latest /path/store  # custom store path
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


def main() -> None:
    from token_machine.dashboard.icon_vendor import refresh_icon_cache
    from token_machine.dashboard.icons import LOBE_ICONS_PACKAGE
    from token_machine.utils.paths import user_data_dir

    args = sys.argv[1:]
    requested = args[0] if args else None
    store = Path(args[1]) if len(args) > 1 else user_data_dir()

    print(f"Store: {store}")
    print(f"Resolving {LOBE_ICONS_PACKAGE}@{requested or 'latest'} ...")
    result = refresh_icon_cache(store, requested)
    print(f"  -> {result.version}")
    print(f"Extracted {result.icon_count} icon(s) to {result.icons_dir}")
    print(f"Wrote {result.icons_json}")


if __name__ == "__main__":
    main()
