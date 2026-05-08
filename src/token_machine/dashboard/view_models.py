"""Dashboard view-model helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StaticAsset:
    path: str
    media_type: str


@dataclass(frozen=True)
class DashboardViewModel:
    title: str
    subtitle: str
    css_assets: tuple[str, ...]
    js_entrypoint: str
