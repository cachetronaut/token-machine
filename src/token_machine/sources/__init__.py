"""Registered source adapters."""

from __future__ import annotations

from token_machine.sources.base import SessionSource
from token_machine.sources.claude import ClaudeSource
from token_machine.sources.codex import CodexSource
from token_machine.sources.gemini import GeminiSource

DEFAULT_SOURCES: tuple[SessionSource, ...] = (
    CodexSource(),
    ClaudeSource(),
    GeminiSource(),
)

__all__ = [
    "DEFAULT_SOURCES",
    "ClaudeSource",
    "CodexSource",
    "GeminiSource",
    "SessionSource",
]
