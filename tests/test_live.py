from pathlib import Path

from fastapi.testclient import TestClient

from token_machine.dashboard.app import create_app
from token_machine.live.models import LiveProbeStatus, LiveUsageSnapshot
from token_machine.live.probes import claude_snapshot, codex_snapshot, gemini_snapshot
from token_machine.live.service import live_data, refresh_live_snapshots
from token_machine.live.statusline import (
    capture_claude_statusline,
    claude_statusline_snapshot,
)
from token_machine.live.store import LiveUsageStore
from token_machine.models import AgentSource, TokenUsage
from token_machine.utils.time import utc_now


def test_codex_live_snapshot_extracts_context_queries_and_current_tools() -> None:
    snapshot = codex_snapshot(
        Path("/tmp/.codex/sessions/session.jsonl"),
        [
            {
                "type": "session_meta",
                "timestamp": "2026-05-11T10:00:00Z",
                "payload": {"id": "s1", "cwd": "/work/project"},
            },
            {
                "type": "turn_context",
                "timestamp": "2026-05-11T10:00:01Z",
                "payload": {"model": "gpt-5.4", "cwd": "/work/project"},
            },
            {
                "type": "response_item",
                "timestamp": "2026-05-11T10:00:02Z",
                "payload": {
                    "type": "function_call",
                    "call_id": "call-1",
                    "name": "exec_command",
                    "arguments": '{"cmd":"uv run pytest"}',
                },
            },
            {
                "type": "event_msg",
                "timestamp": "2026-05-11T10:00:03Z",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "model_context_window": 100,
                        "last_token_usage": {
                            "input_tokens": 40,
                            "cached_input_tokens": 10,
                            "output_tokens": 5,
                        },
                        "total_token_usage": {"total_tokens": 200},
                    },
                    "rate_limits": {
                        "plan_type": "team",
                        "primary": {"used_percentage": 25},
                    },
                },
            },
        ],
    )

    assert snapshot is not None
    assert snapshot.source == AgentSource.CODEX
    assert snapshot.session_name == "session"
    assert snapshot.user_queries["count"] == 1
    assert snapshot.context.window_tokens == 100
    assert snapshot.context.used_tokens == 50
    assert snapshot.context.used_percent == 50
    assert snapshot.current_metrics["latest_turn_tokens"] == 55
    assert snapshot.current_metrics["session_total_tokens"] == 200
    assert snapshot.session_limits[0].remaining_percent == 75
    assert snapshot.live_tool_calls[0].status == "current"
    assert snapshot.live_tool_calls[0].command == "uv run pytest"
    assert snapshot.rate_limits[0].used_percent == 25


def test_codex_live_snapshot_uses_latest_human_prompt_as_session_name() -> None:
    snapshot = codex_snapshot(
        Path("/tmp/.codex/sessions/rollout-2026-05-11T11-30-34-s1.jsonl"),
        [
            {
                "type": "last-prompt",
                "lastPrompt": "none",
                "timestamp": "2026-05-11T10:00:00Z",
            },
            {
                "type": "session_meta",
                "timestamp": "2026-05-11T10:00:00Z",
                "payload": {"id": "s1", "cwd": "/work/project"},
            },
            {
                "type": "response_item",
                "timestamp": "2026-05-11T10:00:01Z",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Initial setup"}],
                },
            },
            {
                "type": "response_item",
                "timestamp": "2026-05-11T10:00:02Z",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Tighten user prompt counting semantics across Codex",
                        }
                    ],
                },
            },
        ],
    )

    assert snapshot is not None
    assert (
        snapshot.session_name == "Tighten user prompt counting semantics across Codex"
    )


def test_claude_live_snapshot_extracts_usage_queries_and_tools() -> None:
    snapshot = claude_snapshot(
        Path("/tmp/.claude/projects/project/session.jsonl"),
        [
            {
                "sessionId": "c1",
                "cwd": "/work/project",
                "timestamp": "2026-05-11T10:00:00Z",
                "message": {"role": "user", "content": "hello"},
            },
            {
                "sessionId": "c1",
                "cwd": "/work/project",
                "timestamp": "2026-05-11T10:00:00Z",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool-1",
                            "content": "done",
                        }
                    ],
                },
            },
            {
                "sessionId": "c1",
                "cwd": "/work/project",
                "timestamp": "2026-05-11T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-6",
                    "usage": {"input_tokens": 5, "output_tokens": 6},
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"cmd": "git status --short"},
                        }
                    ],
                },
            },
            {
                "type": "system",
                "subtype": "compact_boundary",
                "content": "Conversation compacted",
                "timestamp": "2026-05-11T10:00:02Z",
                "compactMetadata": {
                    "trigger": "auto",
                    "preTokens": 100000,
                    "postTokens": 5000,
                    "durationMs": 1234,
                },
            },
        ],
    )

    assert snapshot is not None
    assert snapshot.source == AgentSource.CLAUDE_CODE
    assert snapshot.user_queries["count"] == 1
    assert snapshot.context.used_tokens == 5
    assert snapshot.current_metrics["latest_turn_tokens"] == 11
    assert snapshot.compaction.count == 1
    assert snapshot.compaction.trigger == "auto"
    assert snapshot.compaction.pre_tokens == 100000
    assert snapshot.live_tool_calls[0].name == "Bash"


def test_claude_live_snapshot_uses_ai_title_and_counts_subagent_files(
    tmp_path: Path,
) -> None:
    session_path = tmp_path / "project" / "c1.jsonl"
    subagents_dir = tmp_path / "project" / "c1" / "subagents"
    subagents_dir.mkdir(parents=True)
    (subagents_dir / "agent-a.jsonl").write_text("{}", encoding="utf-8")
    (subagents_dir / "agent-b.jsonl").write_text("{}", encoding="utf-8")

    snapshot = claude_snapshot(
        session_path,
        [
            {
                "type": "ai-title",
                "aiTitle": "Review source and destination agnosticism",
                "sessionId": "c1",
                "timestamp": "2026-05-11T10:00:00Z",
            },
            {
                "sessionId": "c1",
                "cwd": "/work/project",
                "timestamp": "2026-05-11T10:00:01Z",
                "message": {"role": "user", "content": "do the review"},
            },
        ],
    )

    assert snapshot is not None
    assert snapshot.session_name == "Review source and destination agnosticism"
    assert snapshot.current_metrics["subagent_sessions"] == 2


def test_claude_statusline_snapshot_extracts_session_limits() -> None:
    snapshot = claude_statusline_snapshot(
        {
            "session_id": "c1",
            "transcript_path": "/tmp/.claude/projects/project/c1.jsonl",
            "model": {"display_name": "Claude Sonnet 4.6"},
            "workspace": {"current_dir": "/work/project"},
            "context_window": {"used_percentage": 81},
            "session_cost_usd": 1.23,
            "rate_limits": {
                "five_hour": {"used_percentage": 86, "resets_at": 1776621600},
                "seven_day": {"used_percentage": 9, "resets_at": 1777208400},
            },
        }
    )

    assert snapshot.source == AgentSource.CLAUDE_CODE
    assert snapshot.session_id == "c1"
    assert snapshot.source_path == "/tmp/.claude/projects/project/c1.jsonl"
    assert snapshot.model == "Claude Sonnet 4.6"
    assert snapshot.project_path == "/work/project"
    assert snapshot.context.used_percent == 81
    assert snapshot.session_limits[0].name == "five_hour"
    assert snapshot.session_limits[0].remaining_percent == 14
    assert snapshot.session_limits[1].remaining_percent == 91
    assert snapshot.current_metrics["session_cost_usd"] == "1.23"


def test_claude_statusline_capture_merges_transcript_snapshot(tmp_path: Path) -> None:
    store = LiveUsageStore(tmp_path)
    store.write_snapshot(
        LiveUsageSnapshot(
            source=AgentSource.CLAUDE_CODE,
            session_id="c1",
            source_path="/tmp/.claude/projects/project/c1.jsonl",
            project_path="/work/project",
            model="claude-sonnet-4-6",
            updated_at="2026-05-11T10:00:00Z",
            observed_at="2026-05-11T10:00:00Z",
            status=LiveProbeStatus.ACTIVE,
            user_queries={"count": 3, "last_at": "2026-05-11T10:00:00Z"},
            live_tool_calls=[],
            token_usage=TokenUsage(input_tokens=10, total_tokens=20),
        )
    )

    snapshot = capture_claude_statusline(
        {
            "session_id": "c1",
            "workspace": {"current_dir": "/work/project"},
            "context_window": {"used_percentage": 75},
            "rate_limits": {
                "five_hour": {"used_percentage": 60, "resets_at": 1776621600}
            },
        },
        tmp_path,
    )

    assert snapshot.user_queries["count"] == 3
    assert snapshot.token_usage.total_tokens == 20
    assert snapshot.context.used_percent == 75
    assert snapshot.session_limits[0].remaining_percent == 40
    assert snapshot.origin == "statusline"


def test_gemini_live_snapshot_extracts_newest_tokens_and_tools() -> None:
    snapshot = gemini_snapshot(
        Path("/tmp/.gemini/tmp/project/chats/session-1.json"),
        [
            {
                "sessionId": "g1",
                "startTime": "2026-05-11T10:00:00Z",
                "kind": "main",
                "messages": [
                    {"id": "m1", "type": "user", "timestamp": "2026-05-11T10:00:01Z"},
                    {
                        "id": "m2",
                        "type": "gemini",
                        "timestamp": "2026-05-11T10:00:02Z",
                        "model": "gemini-3-flash-preview",
                        "tokens": {"input": 3, "cached": 2, "output": 7},
                        "toolCalls": [
                            {
                                "name": "run_shell_command",
                                "args": {"command": "ls"},
                            }
                        ],
                    },
                ],
            }
        ],
    )

    assert snapshot is not None
    assert snapshot.source == AgentSource.GEMINI
    assert snapshot.user_queries["count"] == 1
    assert snapshot.context.used_tokens == 5
    assert snapshot.current_metrics["latest_turn_tokens"] == 12
    assert snapshot.live_tool_calls[0].command == "ls"


def test_live_store_round_trips_snapshot(tmp_path: Path) -> None:
    store = LiveUsageStore(tmp_path)
    store.write_snapshot(
        LiveUsageSnapshot(
            source=AgentSource.CODEX,
            session_id="s1",
            source_path="/tmp/session.jsonl",
            model="gpt-5.4",
            status=LiveProbeStatus.ACTIVE,
            token_usage=TokenUsage(input_tokens=1, total_tokens=1),
        )
    )

    snapshots = store.load_snapshots()

    assert len(snapshots) == 1
    assert snapshots[0].source == AgentSource.CODEX
    assert snapshots[0].token_usage.total_tokens == 1


def test_live_data_marks_old_snapshots_stale() -> None:
    data = live_data(
        [
            LiveUsageSnapshot(
                source=AgentSource.CODEX,
                session_id="s1",
                source_path="/tmp/session.jsonl",
                observed_at="2000-01-01T00:00:00Z",
                status=LiveProbeStatus.ACTIVE,
            )
        ],
        stale_after_seconds=1,
    )

    assert data.active_count == 0
    assert data.stale_count == 1
    assert data.snapshots[0].status == LiveProbeStatus.STALE


def test_live_api_returns_snapshots_and_debug_reload(tmp_path: Path) -> None:
    store = LiveUsageStore(tmp_path)
    store.write_snapshot(
        LiveUsageSnapshot(
            source=AgentSource.CODEX,
            session_id="s1",
            source_path="/tmp/session.jsonl",
            observed_at=utc_now(),
            updated_at=utc_now(),
            status=LiveProbeStatus.ACTIVE,
        )
    )
    client = TestClient(create_app(tmp_path))

    live_response = client.get("/api/live")
    reload_response = client.get("/api/debug/reload")

    assert live_response.status_code == 200
    assert live_response.json()["active_count"] == 1
    assert live_response.json()["snapshots"][0]["source"] == "codex"
    assert reload_response.status_code == 200
    assert "reload_token" in reload_response.json()


def test_refresh_live_snapshots_discovers_active_codex_file(tmp_path: Path) -> None:
    codex_root = tmp_path / ".codex"
    session_path = codex_root / "sessions" / "session.jsonl"
    session_path.parent.mkdir(parents=True)
    session_path.write_text(
        "\n".join(
            [
                f'{{"type":"session_meta","timestamp":"{utc_now()}","payload":{{"id":"s1"}}}}',
                f'{{"type":"turn_context","timestamp":"{utc_now()}","payload":{{"model":"gpt-5.4"}}}}',
            ]
        ),
        encoding="utf-8",
    )

    data = refresh_live_snapshots([codex_root], tmp_path / "store")

    assert data.active_count == 1
    assert data.snapshots[0].source == AgentSource.CODEX


def test_live_data_marks_recently_observed_inactive_session_stale() -> None:
    data = live_data(
        [
            LiveUsageSnapshot(
                source=AgentSource.CODEX,
                session_id="s1",
                source_path="/tmp/session.jsonl",
                observed_at=utc_now(),
                updated_at="2000-01-01T00:00:00Z",
                status=LiveProbeStatus.ACTIVE,
            )
        ],
        stale_after_seconds=20,
        session_active_seconds=60,
    )

    assert data.active_count == 0
    assert data.stale_count == 1
