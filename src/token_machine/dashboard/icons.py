"""Dashboard icon metadata."""

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
