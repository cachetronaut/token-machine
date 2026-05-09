"""Dashboard icon metadata.

Icons are fetched from ``@lobehub/icons-static-svg`` and cached in the local
store at ``store/cache/icons/``.  To populate or refresh the cache::

    python scripts/vendor_icons.py            # latest
    python scripts/vendor_icons.py 1.91.0     # pin a version

The script auto-discovers icon names from AgentSource and ModelFamily.
"""

from __future__ import annotations

LOBE_ICONS_PACKAGE = "@lobehub/icons-static-svg"

EXTRA_ICON_NAMES = frozenset(
    {
        "cohere",
        "deepseek",
        "groq",
        "meta",
        "mistral",
        "moonshot",
        "openrouter",
        "perplexity",
        "xai",
    }
)


def icon_filenames() -> frozenset[str]:
    """Return expected icon filenames derived from AgentSource and ModelFamily enums."""
    from token_machine.models import AgentSource, ModelFamily

    skip = {AgentSource.UNKNOWN, ModelFamily.OTHER}
    names: set[str] = set()
    for enum_cls in (AgentSource, ModelFamily):
        for member in enum_cls:
            if member not in skip:
                names.add(f"{member.value.lower()}.svg")
    names.add("geminicli.svg")
    names.update(f"{name}.svg" for name in EXTRA_ICON_NAMES)
    return frozenset(names)
