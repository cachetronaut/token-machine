# Token Machine

Token Machine imports local CLI coding-agent session logs into a local analytics store and serves a browser dashboard for token, model, tool, and command usage.

The package is built for public reuse. The core parser, storage, and metrics modules are typed Python code. Typer powers the command line interface. FastAPI serves the local dashboard.

## Install

Token Machine is not published to PyPI yet. Install it from a local clone to
expose the `token-machine` command:

```bash
git clone <repo-url>
cd token-machine
uv tool install --editable .
token-machine --help
```

`uv tool install --editable .` installs the package's console script from the
current checkout, so changes you make in the clone are reflected when you run
`token-machine`.

For local development without installing the command:

```bash
uv sync
uv run token-machine --help
```

## Commands

```bash
token-machine paths
token-machine ingest ~/.codex ~/.claude ~/.gemini
token-machine report
token-machine serve --watch
token-machine watch
```

The default store is platform-specific and local to the current user. Use `--store` to write somewhere else. `serve` performs one initial ingest from the default agent paths before starting the dashboard. Add `--no-ingest` when you want to inspect only the data already in the store.

## Assets

The dashboard vendors branding assets and a small Lobe Icons SVG subset so it renders offline after installation. `serve` refreshes the local icon cache on startup by default; use `--no-refresh-icons` to skip the network refresh and use cached icons only. See `THIRD_PARTY_NOTICES.md` for attribution and license details.

## Development

Run the checks before sending changes:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run ty check
```

Read `ARCHITECTURE.md` before adding a source adapter, metric, or dashboard field.
