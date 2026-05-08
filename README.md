# Token Machine

Token Machine imports local CLI coding-agent session logs into a local analytics
store and serves a browser dashboard for token, model, tool, and command usage.

The package is built for public reuse. The core parser, storage, and metrics
modules are typed Python code. Typer powers the command line interface. FastAPI
serves the local dashboard.

## Install

```bash
pip install token-machine
```

For local development:

```bash
uv sync
uv run token-machine --help
```

## Commands

```bash
uv run token-machine paths
uv run token-machine ingest ~/.codex ~/.claude ~/.gemini
uv run token-machine report
uv run token-machine serve --watch
uv run token-machine watch
```

The default store is platform-specific and local to the current user. Use
`--store` to write somewhere else. `serve` performs one initial ingest from the
default agent paths before starting the dashboard. Add `--no-ingest` when you
want to inspect only the data already in the store.

## Development

Run the checks before sending changes:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run ty check
```

Read `ARCHITECTURE.md` before adding a source adapter, metric, or dashboard
field.
