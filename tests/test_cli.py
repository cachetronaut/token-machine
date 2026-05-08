import json
from pathlib import Path
from typing import Any

import token_machine.cli as cli
from typer.testing import CliRunner

from token_machine.dashboard.icon_vendor import IconRefreshResult
from token_machine.cli import app
from token_machine.storage.repository import AnalyticsRepository


def test_cli_ingest_reports_ok_skipped_and_errors(tmp_path: Path) -> None:
    log_path = tmp_path / "session.jsonl"
    log_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-05-08T10:00:00Z",
                        "payload": {"id": "s1", "cwd": "/work/project"},
                    }
                ),
                json.dumps(
                    {
                        "type": "event_msg",
                        "timestamp": "2026-05-08T10:00:01Z",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "last_token_usage": {
                                    "input_tokens": 1,
                                    "output_tokens": 2,
                                }
                            },
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app, ["ingest", str(log_path), "--store", str(tmp_path / "store")]
    )

    assert result.exit_code == 0
    assert "Ingested 1 file(s), skipped 0, errors 0." in result.output


def test_paths_command_prints_defaults() -> None:
    result = CliRunner().invoke(app, ["paths"])

    assert result.exit_code == 0
    assert "Store:" in result.output


def test_serve_help_exposes_initial_ingest_toggle() -> None:
    result = CliRunner().invoke(app, ["serve", "--help"])

    assert result.exit_code == 0
    assert "--ingest" in result.output
    assert "--no-ingest" in result.output
    assert "--refresh-icons" in result.output
    assert "--no-refresh-icons" in result.output


def test_serve_runs_initial_ingest_before_starting_server(
    tmp_path: Path, monkeypatch: Any
) -> None:
    log_dir = tmp_path / ".codex"
    log_dir.mkdir()
    log_path = log_dir / "session.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "timestamp": "2026-05-08T10:00:00Z",
                "payload": {"id": "s1", "cwd": "/work/project"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    store = tmp_path / "store"
    calls: list[object] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    def fake_refresh_icon_cache(path: Path) -> IconRefreshResult:
        return IconRefreshResult(
            package="@lobehub/icons-static-svg",
            version="1.0.0",
            icon_count=1,
            icons_dir=path / "cache" / "icons",
            icons_json=path / "cache" / "icons.json",
        )

    monkeypatch.setattr(cli, "DEFAULT_WATCH_PATHS", (log_dir,))
    monkeypatch.setattr(cli, "refresh_icon_cache", fake_refresh_icon_cache)
    monkeypatch.setattr(cli.uvicorn, "run", fake_run)

    result = CliRunner().invoke(app, ["serve", "--store", str(store)])

    assert result.exit_code == 0
    assert calls
    assert "Refreshed 1 dashboard icon(s)" in result.output
    assert len(AnalyticsRepository(store).load_events()) == 1
