"""Normalize agent model identifiers to friendly display names."""

from __future__ import annotations

import re

_ALIASES: dict[str, str] = {
    "claude-opus-4-7": "Opus 4.7",
    "claude-opus-4-6": "Opus 4.6",
    "claude-opus-4-5": "Opus 4.5",
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-sonnet-4-5": "Sonnet 4.5",
    "claude-haiku-4-5": "Haiku 4.5",
}

_CLAUDE_ID_RE = re.compile(
    r"^claude-(opus|sonnet|haiku)-(\d+)-(\d+)(?:-\d{6,})?$", re.IGNORECASE
)
_CLAUDE_PREFIX_RE = re.compile(r"^claude\s+", re.IGNORECASE)
_GPT_RE = re.compile(r"^gpt-([\d.]+)(.*)$", re.IGNORECASE)
_GEMINI_RE = re.compile(r"^gemini-([\d.]+)(?:-(.+))?$", re.IGNORECASE)


def canonical_model_name(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    key = value.lower()
    if key in _ALIASES:
        return _ALIASES[key]
    claude_match = _CLAUDE_ID_RE.match(value)
    if claude_match:
        family = claude_match.group(1).capitalize()
        return f"{family} {claude_match.group(2)}.{claude_match.group(3)}"
    stripped = _CLAUDE_PREFIX_RE.sub("", value)
    if stripped != value:
        return stripped
    gpt_match = _GPT_RE.match(value)
    if gpt_match:
        suffix = gpt_match.group(2).strip(" -")
        version = f"GPT-{gpt_match.group(1)}"
        return f"{version} {suffix}".strip() if suffix else version
    gemini_match = _GEMINI_RE.match(value)
    if gemini_match:
        version = gemini_match.group(1)
        variant = (gemini_match.group(2) or "").replace("-", " ").strip()
        label = f"Gemini {version}"
        return f"{label} {variant.title()}".strip() if variant else label
    return value
