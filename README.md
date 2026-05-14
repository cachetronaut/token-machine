# Token Machine

Token Machine imports local coding-agent session logs into a local analytics store and serves a browser dashboard for token, model, source, tool, skill, executable, command, and session usage.

The package is built for public reuse. The core parser, storage, and metrics modules are typed Python code. Typer powers the command line interface. FastAPI serves the local dashboard. Supported sources currently include Codex, Claude Code, Gemini CLI, OpenCode, and Zed Agent Panel logs.

Tools are the broad action layer. Skills are tracked separately when a source log exposes an explicit skill signal. Executables are detected programmatically from command strings, so shell usage is shown as a command facet instead of a fixed CLI list.

## Install

Token Machine requires Python 3.14. It is not published to PyPI yet. Install it from a local clone to expose the `token-machine` command:

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
token-machine ingest ~/.codex ~/.claude ~/.gemini ~/.local/share/opencode/opencode.db
token-machine report
token-machine serve --watch
token-machine watch
```

The default store is platform-specific and local to the current user:

- macOS: `~/Library/Application Support/token-machine`
- Windows: `%LOCALAPPDATA%\token-machine` or `%APPDATA%\token-machine`
- Linux and other Unix systems: `$XDG_DATA_HOME/token-machine` or `~/.local/share/token-machine`

Use `--store` to write somewhere else. `paths` prints the default store and known agent paths. `ingest` accepts session files, log directories, OpenCode `opencode.db`, and Zed `threads.db`. `report` prints an aggregate terminal summary from the store.

`serve` refreshes dashboard icons, performs one initial ingest from the default agent paths, and starts the dashboard at `http://127.0.0.1:8765/` by default. Use `--no-ingest` to inspect only existing store data, `--no-refresh-icons` to avoid the network icon refresh, `--host` and `--port` to change the bind address, and `--watch` to keep polling default paths while the server runs.

## Assets

The dashboard serves packaged CSS, JavaScript, images, and SVG icons from local FastAPI routes. It includes packaged fallback assets and can cache a small `@lobehub/icons-static-svg` subset under `store/cache/icons/`. `serve` refreshes that local icon cache on startup by default; use `--no-refresh-icons` to skip the network refresh and use cached or packaged icons only. See `THIRD_PARTY_NOTICES.md` for attribution and license details.

Dashboard browser code is written in TypeScript under `src/token_machine/dashboard/assets/ts/`. The generated JavaScript served by FastAPI lives under `src/token_machine/dashboard/assets/js/`.

## Development

Run the checks before sending changes:

```bash
pnpm check:dashboard
uv run pytest
uv run ruff check
uv run ruff format --check
uv run ty check
```

Use `pnpm format:dashboard` to format dashboard TypeScript and related JavaScript tooling. `pnpm check:dashboard` runs Biome lint/format checks, TypeScript typechecking, and the generated JavaScript stale-build guard.

Read `reference/ARCHITECTURE.md` before adding a source adapter, metric, or dashboard field.
