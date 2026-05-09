import json
import sqlite3
from pathlib import Path

import zstandard as zstd

from token_machine.ingest.discovery import detect_source
from token_machine.models import AgentSource, EventType
from token_machine.sources.zed import ZedSource, decode_zed_thread


def test_zed_source_discovers_threads_db_from_file_or_directory(tmp_path: Path) -> None:
    threads_dir = tmp_path / "threads"
    threads_dir.mkdir()
    db_path = threads_dir / "threads.db"
    db_path.touch()
    source = ZedSource()

    assert source.discover_files(db_path) == [db_path]
    assert source.discover_files(threads_dir) == [db_path]
    assert source.discover_files(tmp_path) == [db_path]


def test_zed_threads_db_detects_without_json_loading(tmp_path: Path) -> None:
    db_path = _write_zed_threads_db(tmp_path, [_thread_row("s1")])

    source, objects = detect_source(db_path)

    assert source is not None
    assert source.name == AgentSource.ZED
    assert objects == []


def test_decode_zed_thread_handles_zstd_payload() -> None:
    payload = {"title": "Compressed thread", "messages": []}
    blob = zstd.ZstdCompressor(write_content_size=False).compress(
        json.dumps(payload).encode("utf-8")
    )

    assert decode_zed_thread("zstd", blob)["title"] == "Compressed thread"


def test_zed_parser_emits_thread_usage_tools_and_commands(tmp_path: Path) -> None:
    thread = _thread(
        request_token_usage={"user-1": {"input_tokens": 5, "output_tokens": 7}},
        cumulative_token_usage={"input_tokens": 100, "output_tokens": 100},
    )
    db_path = _write_zed_threads_db(tmp_path, [_thread_row("s1", thread=thread)])

    events = ZedSource().parse(db_path, [])

    assert [event.event_type for event in events] == [
        EventType.SESSION_META,
        EventType.MESSAGE,
        EventType.MODEL_CALL,
        EventType.MESSAGE,
        EventType.TOOL_CALL,
        EventType.CLI_COMMAND,
    ]
    assert events[0].source == AgentSource.ZED
    assert events[0].project_path == "/work/project"
    assert events[0].model == "openrouter/auto"
    assert events[2].token_usage.total_tokens == 12
    assert events[4].tool_name == "terminal"
    assert events[4].command == "uv run pytest"
    assert events[5].cli_name == "uv"
    assert not any(
        event.metadata.get("usage_scope") == "cumulative" for event in events
    )


def test_zed_parser_uses_cumulative_usage_only_as_fallback(tmp_path: Path) -> None:
    thread = _thread(
        request_token_usage={},
        cumulative_token_usage={"input_tokens": 11, "output_tokens": 13},
    )
    db_path = _write_zed_threads_db(tmp_path, [_thread_row("s1", thread=thread)])

    model_calls = [
        event
        for event in ZedSource().parse(db_path, [])
        if event.event_type == EventType.MODEL_CALL
    ]

    assert len(model_calls) == 1
    assert model_calls[0].token_usage.total_tokens == 24
    assert model_calls[0].metadata["usage_scope"] == "cumulative"


def test_zed_event_ids_are_stable_when_thread_updated_at_changes(
    tmp_path: Path,
) -> None:
    db_path = _write_zed_threads_db(
        tmp_path,
        [
            _thread_row(
                "s1",
                created_at="2026-05-08T10:00:00Z",
                updated_at="2026-05-08T10:05:00Z",
            )
        ],
    )
    source = ZedSource()
    first_ids = [event.event_id for event in source.parse(db_path, [])]

    with sqlite3.connect(db_path) as db:
        db.execute(
            "update threads set updated_at = ? where id = ?",
            ("2026-05-09T10:05:00Z", "s1"),
        )

    second_ids = [event.event_id for event in source.parse(db_path, [])]

    assert second_ids == first_ids


def _write_zed_threads_db(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    db_path = tmp_path / "threads.db"
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            create table threads (
                id text primary key,
                summary text not null,
                updated_at text not null,
                data_type text not null,
                data blob not null,
                parent_id text,
                created_at text
            )
            """
        )
        db.executemany(
            """
            insert into threads (
                id, summary, updated_at, data_type, data, parent_id, created_at
            ) values (
                :id, :summary, :updated_at, :data_type, :data, :parent_id, :created_at
            )
            """,
            rows,
        )
    return db_path


def _thread_row(
    session_id: str,
    *,
    thread: dict[str, object] | None = None,
    created_at: str = "2026-05-08T10:00:00Z",
    updated_at: str = "2026-05-08T10:05:00Z",
) -> dict[str, object]:
    payload = thread or _thread()
    return {
        "id": session_id,
        "summary": "Zed thread",
        "updated_at": updated_at,
        "data_type": "zstd",
        "data": zstd.ZstdCompressor(write_content_size=False).compress(
            json.dumps(payload).encode("utf-8")
        ),
        "parent_id": None,
        "created_at": created_at,
    }


def _thread(
    *,
    request_token_usage: dict[str, object] | None = None,
    cumulative_token_usage: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "title": "Token Machine",
        "version": "1",
        "updated_at": "2026-05-08T10:05:00Z",
        "model": {"provider": "openrouter", "model": "openrouter/auto"},
        "profile": "write",
        "speed": "max",
        "thinking_enabled": True,
        "initial_project_snapshot": {
            "worktree_snapshots": [{"worktree_path": "/work/project"}]
        },
        "request_token_usage": request_token_usage
        if request_token_usage is not None
        else {"user-1": {"input_tokens": 1, "output_tokens": 2}},
        "cumulative_token_usage": cumulative_token_usage or {},
        "messages": [
            {
                "User": {
                    "id": "user-1",
                    "content": [{"Text": "Run tests"}],
                }
            },
            {
                "Agent": {
                    "content": [
                        {"Text": "Running tests"},
                        {
                            "ToolUse": {
                                "id": "tool-1",
                                "name": "terminal",
                                "raw_input": '{"command":"uv run pytest"}',
                                "input": {"command": "uv run pytest"},
                                "is_input_complete": True,
                            }
                        },
                    ]
                }
            },
        ],
    }
