"""Typer command line interface."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from token_machine.config import DEFAULT_STORE, DEFAULT_WATCH_PATHS
from token_machine.dashboard.app import create_app
from token_machine.dashboard.icon_vendor import refresh_icon_cache
from token_machine.ingest.pipeline import ingest as ingest_paths
from token_machine.metrics.profiles import dashboard_data
from token_machine.models import IngestStatus
from token_machine.storage.repository import AnalyticsRepository

app = typer.Typer(help="Local analytics for CLI coding agents.")


StoreOption = Annotated[
    Path,
    typer.Option("--store", help="Analytics store path."),
]


def _store_option_default() -> Path:
    return DEFAULT_STORE


@app.command()
def paths() -> None:
    """Print default store and watch paths."""
    typer.echo(f"Store: {DEFAULT_STORE}")
    for path in DEFAULT_WATCH_PATHS:
        typer.echo(f"Watch: {path}")


@app.command()
def ingest(
    paths: Annotated[list[Path], typer.Argument(help="Session files or directories.")],
    store: StoreOption = DEFAULT_STORE,
) -> None:
    """Import session files into the local store."""
    results = ingest_paths(paths, store)
    ok = sum(result.status == IngestStatus.OK for result in results)
    skipped = sum(result.status == IngestStatus.SKIPPED for result in results)
    errors = sum(result.status == IngestStatus.ERROR for result in results)
    typer.echo(f"Ingested {ok} file(s), skipped {skipped}, errors {errors}.")
    typer.echo(f"Store: {store}")
    for result in results:
        if result.status != IngestStatus.OK:
            typer.echo(f"{result.status.value}: {result.source_path} ({result.error})")
    if errors:
        raise typer.Exit(1)


@app.command()
def report(store: StoreOption = DEFAULT_STORE) -> None:
    """Print an aggregate report."""
    repository = AnalyticsRepository(store)
    summary = dashboard_data(repository.load_events()).summary
    typer.echo("Token Machine")
    typer.echo(f"Store: {store}")
    typer.echo(f"Sessions: {summary.sessions:,}")
    typer.echo(f"Events: {summary.event_count:,}")
    typer.echo(f"Model calls: {summary.event_types.get('model_call', 0):,}")
    typer.echo(f"Tool calls: {summary.event_types.get('tool_call', 0):,}")
    typer.echo(f"CLI commands: {summary.event_types.get('cli_command', 0):,}")
    typer.echo(f"Total tokens: {summary.tokens.total_tokens:,}")
    _print_counter("Models", summary.models)
    _print_counter("Tools", summary.tools)
    _print_counter("CLIs", summary.clis)


@app.command()
def serve(
    store: StoreOption = DEFAULT_STORE,
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port")] = 8765,
    ingest: Annotated[
        bool,
        typer.Option(
            "--ingest/--no-ingest",
            help="Ingest default agent paths once before serving.",
        ),
    ] = True,
    watch: Annotated[bool, typer.Option("--watch")] = False,
    watch_interval: Annotated[int, typer.Option("--watch-interval")] = 30,
    refresh_icons: Annotated[
        bool,
        typer.Option(
            "--refresh-icons/--no-refresh-icons",
            help="Refresh dashboard icons from the vendored icon source before serving.",
        ),
    ] = True,
) -> None:
    """Serve the browser dashboard."""
    if refresh_icons:
        try:
            result = refresh_icon_cache(store)
            typer.echo(
                f"Refreshed {result.icon_count} dashboard icon(s) "
                f"from {result.package}@{result.version}."
            )
        except Exception as exc:  # noqa: BLE001 - keep serving with cached icons.
            typer.echo(f"Icon refresh failed; using cached icons if present: {exc}")
    if ingest:
        results = ingest_paths(list(DEFAULT_WATCH_PATHS), store)
        ok = sum(result.status == IngestStatus.OK for result in results)
        skipped = sum(result.status == IngestStatus.SKIPPED for result in results)
        errors = sum(result.status == IngestStatus.ERROR for result in results)
        typer.echo(f"Initial ingest: {ok} file(s), skipped {skipped}, errors {errors}.")
    if watch:
        start_watch_loop(list(DEFAULT_WATCH_PATHS), store, watch_interval)
        joined = ", ".join(str(path) for path in DEFAULT_WATCH_PATHS)
        typer.echo(f"Watching {joined} every {max(5, watch_interval)} seconds")
    typer.echo(f"Serving Token Machine at http://{host}:{port}/")
    uvicorn.run(create_app(store), host=host, port=port, log_level="debug")


@app.command()
def watch(
    paths: Annotated[
        list[Path] | None,
        typer.Argument(help="Optional watch paths. Defaults to known agent paths."),
    ] = None,
    store: StoreOption = DEFAULT_STORE,
    interval: Annotated[int, typer.Option("--interval")] = 30,
) -> None:
    """Poll and ingest session files until stopped."""
    watch_paths = paths or list(DEFAULT_WATCH_PATHS)
    typer.echo(f"Watching {', '.join(str(path) for path in watch_paths)}")
    while True:
        ingest_paths(watch_paths, store)
        time.sleep(max(5, interval))


def start_watch_loop(paths: list[Path], store: Path, interval_seconds: int) -> None:
    def watch_target() -> None:
        while True:
            try:
                ingest_paths(paths, store)
            except Exception as exc:  # noqa: BLE001 - background watcher reports and continues.
                typer.echo(f"watch ingest failed: {exc}", err=True)
            time.sleep(max(5, interval_seconds))

    thread = threading.Thread(target=watch_target, daemon=True)
    thread.start()


def _print_counter(label: str, values: dict[str, int]) -> None:
    typer.echo(f"\n{label}:")
    if not values:
        typer.echo("  (none)")
        return
    for name, count in sorted(values.items(), key=lambda item: item[1], reverse=True)[
        :12
    ]:
        typer.echo(f"  {name}: {count:,}")


def main() -> None:
    app()
