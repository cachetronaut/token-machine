---
status: active
date: 2026-05-08
description: Public architecture for the Token Machine CLI-agent analytics package.
keywords: token-machine, cli agents, analytics, architecture, ingestion, dashboard
---

# Architecture

## Purpose

Token Machine turns local CLI-agent session logs into local analytics and a browser dashboard. It is built for developers who want to inspect token usage, model usage, tool activity, command activity, and recent sessions across multiple coding agents.

## Design principles

- Keep the core pure Python. Parsing, storage, metrics, and models do not import Typer or FastAPI.
- Use dataclasses and enums for domain data. Use JSON only at file, CLI, and HTTP boundaries.
- Keep source adapters isolated. Agent-specific log shapes live in `src/token_machine/sources/`.
- Store data locally by default. The app does not send session data to a remote service.
- Keep public artifacts generic. No private project or user-specific product names belong in code, docs, tests, dashboard text, or generated files.

## Repository layout

- `src/token_machine/models.py` defines public domain types, enums, and dataclasses.
- `src/token_machine/config.py` owns default paths and app settings.
- `src/token_machine/sources/` contains one adapter per supported CLI agent.
- `src/token_machine/ingest/` finds files, detects sources, parses records, and writes ingest results.
- `src/token_machine/storage/` reads and writes the local event store.
- `src/token_machine/metrics/` aggregates events into summaries, profiles, and tool categories.
- `src/token_machine/dashboard/` builds the FastAPI app and generated dashboard page.
- `tests/` contains focused tests for models, adapters, storage, metrics, CLI, and public naming.

## Data flow

```text
Configured paths
  -> discover session files
  -> load JSON or JSONL records
  -> detect source adapter
  -> parse records into AnalyticsEvent dataclasses
  -> write append-only event store
  -> build session and daily rollups
  -> compute dashboard dataclasses
  -> serialize response at FastAPI route boundary
```

## Source adapters

Each source adapter implements `SessionSource` from `src/token_machine/sources/base.py`. The adapter owns default paths, file discovery, detection, and parsing for one CLI agent.

To add an agent, create a new module in `sources/`, register it in `sources/__init__.py`, and add a parser fixture test. The adapter must return `AnalyticsEvent` values and must not write files.

## Storage model

The local store is inspectable and append-only where practical:

```text
store/
  events/YYYY-MM.jsonl
  sessions/{source}-{session_id}.json
  daily/YYYY-MM-DD.json
  manifest.jsonl
  cache/icons/*.svg
```

Monthly event files hold normalized events. Session files and daily files are derived rollups. The manifest records each ingest attempt. Session rollup filenames include both source and session id so different agents cannot collide.

## Dashboard model

FastAPI serves the dashboard through focused routes:

- `/` returns Jinja-rendered HTML from `dashboard/render.py`.
- `/api/summary` returns serialized `DashboardData`.
- `/assets/css/{name}.css`, `/assets/js/{name}.js`, and
  `/assets/icons/{name}.svg` return packaged dashboard assets.

Dashboard HTML lives in Jinja templates under `dashboard/templates/`. CSS and browser-native JavaScript modules live under `dashboard/assets/`. There is no frontend build system in v1.

Dashboard icons are a small vendored Lobe Icons SVG subset served through the same local asset route. Runtime dashboard rendering must not depend on CDN, network, npm, or Node tooling.

The `serve` command performs one initial ingest from default agent paths before
starting the HTTP server. If `--watch` is set, it also starts a polling ingest
loop. If `--no-ingest` is set, it serves only data already present in the store.

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
