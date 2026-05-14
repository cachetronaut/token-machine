---
status: active
date: 2026-05-14
description: Public architecture for the Token Machine CLI-agent analytics package.
keywords: token-machine, cli agents, analytics, architecture, ingestion, dashboard, live usage, design
---

# Architecture

## Purpose

Token Machine turns local CLI-agent session logs and local agent databases into local analytics and a browser dashboard. It is built for developers who want to inspect token usage, model usage, source activity, tool activity, skill activity, executable usage, command activity, model profiles, and recent sessions across multiple coding agents.

## Design principles

- Keep the core pure Python. Parsing, storage, metrics, and models do not import Typer or FastAPI.
- Use dataclasses and enums for domain data. Use JSON only at file, CLI, and HTTP boundaries.
- Keep source adapters isolated. Agent-specific log shapes live in `src/token_machine/sources/`.
- Store data locally by default. The app does not send session data to a remote service.
- Keep public artifacts generic. No private project or user-specific product names belong in code, docs, tests, dashboard text, or generated files.

## Repository layout

- `src/token_machine/cli.py` defines the Typer application and owns CLI-only behavior.
- `src/token_machine/models.py` defines public domain types, enums, and dataclasses.
- `src/token_machine/config.py` owns default paths and app settings.
- `src/token_machine/sources/` contains one adapter per supported CLI agent.
- `src/token_machine/ingest/` finds files, detects sources, parses records, and writes ingest results.
- `src/token_machine/storage/` reads and writes the local event store.
- `src/token_machine/metrics/` aggregates events into summaries, profiles, and tool categories.
- `src/token_machine/dashboard/` builds the FastAPI app, Jinja dashboard shell, browser-native JavaScript, CSS, packaged assets, and icon cache refresh support.
- `tests/` contains focused tests for models, adapters, storage, metrics, CLI, and public naming.

## Data flow

```text
Configured paths
  -> discover session files
  -> load JSON/JSONL records or read supported SQLite databases
  -> detect source adapter
  -> parse records into AnalyticsEvent dataclasses
  -> write append-only event store
  -> build session rollups and time-bucket summaries
  -> compute dashboard, model-profile, and recent-session dataclasses
  -> serialize response at FastAPI route boundary
```

## Source adapters

Each source adapter implements `SessionSource` from `src/token_machine/sources/base.py`. The adapter owns default paths, file discovery, detection, and parsing for one CLI agent.

The registered adapters are:

- `CodexSource` for JSONL files under `~/.codex`.
- `ClaudeSource` for JSONL files under `~/.claude`.
- `GeminiSource` for Gemini CLI JSON or JSONL session files under `~/.gemini`.
- `OpenCodeSource` for the local OpenCode SQLite database at `~/.local/share/opencode/opencode.db`.
- `ZedSource` for the Zed Agent Panel SQLite database at the platform-specific `threads.db` path.

To add an agent, create a new module in `src/token_machine/sources/`, register it in `src/token_machine/sources/__init__.py`, add a parser fixture test, and include any default path in `src/token_machine/config.py` when it should be part of default ingest. The adapter must return `AnalyticsEvent` values and must not write files.

## Storage model

The local store is inspectable and append-only where practical:

```text
store/
  events/YYYY-MM.jsonl
  sessions/{source}-{session_id}.json
  daily/YYYY-MM-DD.json
  manifest.jsonl
  cache/icons.json
  cache/icons/*.svg
```

Monthly event files hold normalized events. Session files and daily files are derived rollups. The manifest records each ingest attempt. Session rollup filenames include both source and session id so different agents cannot collide. The icon cache is derived from `@lobehub/icons-static-svg` and is safe to refresh.

The repository writes only new event ids to monthly event files. Derived session and daily files are rebuilt from parsed events during ingest.

## Dashboard model

FastAPI serves the dashboard through focused routes:

- `/` returns Jinja-rendered HTML from `src/token_machine/dashboard/render.py`.
- `/api/summary` returns serialized `DashboardData`.
- `/api/live` returns serialized live usage snapshots from the local live store.
- `/api/debug/reload` returns the current script reload token over `GET` and refreshes live snapshots over `POST`.
- `/assets/{kind}/{name}` returns packaged CSS, JavaScript, font, image, and SVG icon assets for `css`, `js`, `fonts`, `img`, and `icons`.

Dashboard HTML lives in Jinja templates under `src/token_machine/dashboard/templates/`. CSS, browser-native JavaScript modules, local fonts, images, and packaged icon fallbacks live under `src/token_machine/dashboard/assets/`. There is no frontend build system in v1.

The dashboard API returns `DashboardData`, including aggregate summary data, daily and hourly series, model profiles, and recent session profiles. Metric and profile code returns dataclasses; JSON conversion happens at the route boundary.

Tools are the broad action layer. Skills are represented as `skill_call` events only when a source exposes an explicit skill signal. Command execution is represented as a command-bearing action, and executable names are derived from command strings through shared parser helpers rather than from a fixed list.

The live dashboard surface uses `LiveData` and `LiveUsageSnapshot` values from `src/token_machine/live/`. It summarizes active sessions, context windows, current tool/action activity, subagent counts, session limits, and compaction events without changing the aggregate `DashboardData` contract.

The visual system is documented in `reference/DESIGN.md`. The current dashboard uses a dark local-operations theme, a blue-to-teal Token Machine wordmark, local Orbitron/Teko/Share Tech Mono fonts, compact telemetry cards, local app/model icons, and reduced-motion-aware animation for live state, charts, sections, recent sessions, and intro playback.

Dashboard icons are served through the same local asset route. `serve` refreshes the store icon cache from `@lobehub/icons-static-svg` by default and falls back to cached or packaged icons when refresh is skipped or unavailable. Runtime dashboard rendering must not depend on CDN, npm, or Node tooling.

The `serve` command performs one initial ingest from default agent paths before starting the HTTP server. If `--watch` is set, it also starts a polling ingest loop. If `--no-ingest` is set, it serves only data already present in the store. The standalone `watch` command polls and ingests until stopped.

## Contributor workflow

- Add a source by implementing `SessionSource` and parser tests.
- Add a metric by returning a dataclass from `metrics/`, then serializing it only
  at the HTTP boundary.
- Add a CLI command in `cli.py`. Do not import Typer in core modules.
- Add a dashboard field by extending the relevant dataclass, metric function,
  route serialization, and dashboard renderer together.

## Verification

Run these commands before sending changes:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run ty check
```
