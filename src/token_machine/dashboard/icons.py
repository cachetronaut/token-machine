"""Dashboard icon metadata.

Icons are vendored from ``@lobehub/icons-static-svg`` and committed to
``assets/icons/``.  To re-vendor (e.g. after a version bump):

1. Download the npm tarball::

       curl -fsSL $(npm pack --dry-run --json @lobehub/icons-static-svg@<version> \
           | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['filename'])") \
           -o lobe-icons.tgz

   Or simply::

       npm pack @lobehub/icons-static-svg@<version>

2. For each entry in ``ICON_SOURCE_SLUGS``, copy the matching file from the
   tarball's ``package/svgs/`` directory to ``assets/icons/``, renaming it
   to the local key::

       tar -xOzf lobe-icons.tgz package/svgs/<upstream-slug> \
           > src/token_machine/dashboard/assets/icons/<local-name>

3. Update ``LOBE_ICONS_VERSION`` below and the entry in ``THIRD_PARTY_NOTICES.md``.
"""

from __future__ import annotations

LOBE_ICONS_PACKAGE = "@lobehub/icons-static-svg"
LOBE_ICONS_VERSION = "1.90.0"

ICON_SOURCE_SLUGS = {
    "claude.svg": "claude-color.svg",
    "codex.svg": "codex-color.svg",
    "gemini.svg": "gemini-color.svg",
    "openai.svg": "openai.svg",
    "qwen.svg": "qwen-color.svg",
}

ICON_NAMES = frozenset(
    {
        "claude.svg",
        "codex.svg",
        "gemini.svg",
        "openai.svg",
        "qwen.svg",
    }
)
