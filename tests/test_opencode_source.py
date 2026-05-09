import json
import sqlite3
from pathlib import Path

from token_machine.ingest.discovery import detect_source
from token_machine.models import AgentSource, EventType
from token_machine.sources.opencode import OpenCodeSource


def test_opencode_source_discovers_db_from_file_or_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "opencode.db"
    db_path.touch()
    source = OpenCodeSource()

    assert source.discover_files(db_path) == [db_path]
    assert source.discover_files(tmp_path) == [db_path]


def test_opencode_db_detects_without_json_loading(tmp_path: Path) -> None:
    db_path = _write_opencode_db(tmp_path)

    source, objects = detect_source(db_path)

    assert source is not None
    assert source.name == AgentSource.OPENCODE
    assert objects == []


def test_opencode_parser_emits_usage_tools_and_commands(tmp_path: Path) -> None:
    db_path = _write_opencode_db(tmp_path)

    events = OpenCodeSource().parse(db_path, [])

    assert [event.event_type for event in events] == [
        EventType.SESSION_META,
        EventType.MESSAGE,
        EventType.MESSAGE,
        EventType.MODEL_CALL,
        EventType.TOOL_CALL,
        EventType.CLI_COMMAND,
    ]
    assert events[0].source == AgentSource.OPENCODE
    assert events[0].project_path == "/work/project"
    assert events[0].model == "opencode/big-pickle"
    assert events[3].token_usage.input_tokens == 10
    assert events[3].token_usage.output_tokens == 4
    assert events[3].token_usage.total_tokens == 15
    assert events[4].tool_name == "bash"
    assert events[4].command == "uv run pytest"
    assert events[5].cli_name == "uv"


def _write_opencode_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "opencode.db"
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            create table project (
                id text primary key,
                worktree text not null,
                name text,
                time_created integer not null,
                time_updated integer not null
            )
            """
        )
        db.execute(
            """
            create table session (
                id text primary key,
                project_id text not null,
                slug text not null,
                directory text not null,
                title text not null,
                version text not null,
                time_created integer not null,
                time_updated integer not null,
                path text
            )
            """
        )
        db.execute(
            """
            create table message (
                id text primary key,
                session_id text not null,
                time_created integer not null,
                time_updated integer not null,
                data text not null
            )
            """
        )
        db.execute(
            """
            create table part (
                id text primary key,
                message_id text not null,
                session_id text not null,
                time_created integer not null,
                time_updated integer not null,
                data text not null
            )
            """
        )
        db.execute(
            """
            insert into project (
                id, worktree, name, time_created, time_updated
            ) values (
                'proj-1', '/work/project', 'Project', 1770000000000, 1770000005000
            )
            """
        )
        db.execute(
            """
            insert into session (
                id, project_id, slug, directory, title, version, time_created,
                time_updated, path
            ) values (
                'ses-1', 'proj-1', 'slug', '/work/project', 'OpenCode session',
                '1.14.33', 1770000000000, 1770000005000, null
            )
            """
        )
        db.executemany(
            """
            insert into message (
                id, session_id, time_created, time_updated, data
            ) values (
                :id, :session_id, :time_created, :time_updated, :data
            )
            """,
            [
                {
                    "id": "msg-1",
                    "session_id": "ses-1",
                    "time_created": 1770000001000,
                    "time_updated": 1770000001000,
                    "data": json.dumps({"role": "user", "time": 1770000001000}),
                },
                {
                    "id": "msg-2",
                    "session_id": "ses-1",
                    "time_created": 1770000002000,
                    "time_updated": 1770000002000,
                    "data": json.dumps(
                        {
                            "role": "assistant",
                            "providerID": "opencode",
                            "modelID": "big-pickle",
                            "time": 1770000002000,
                            "tokens": {
                                "input": 10,
                                "output": 4,
                                "reasoning": 1,
                            },
                        }
                    ),
                },
            ],
        )
        db.execute(
            """
            insert into part (
                id, message_id, session_id, time_created, time_updated, data
            ) values (
                'prt-1', 'msg-2', 'ses-1', 1770000003000, 1770000003000, ?
            )
            """,
            (
                json.dumps(
                    {
                        "type": "tool",
                        "tool": "bash",
                        "callID": "call-1",
                        "state": {
                            "status": "completed",
                            "title": "Run tests",
                            "input": {
                                "command": "uv run pytest",
                                "description": "Run test suite",
                            },
                        },
                    }
                ),
            ),
        )
    return db_path
