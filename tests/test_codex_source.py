from pathlib import Path

from token_machine.models import EventType
from token_machine.sources.codex import CodexSource


def test_codex_parser_emits_session_meta_tool_calls_and_model_calls() -> None:
    source = CodexSource()
    events = source.parse(
        Path("/tmp/.codex/session.jsonl"),
        [
            {
                "type": "session_meta",
                "timestamp": "2026-05-08T10:00:00Z",
                "payload": {"id": "s1", "cwd": "/work/project"},
            },
            {
                "type": "turn_context",
                "timestamp": "2026-05-08T10:00:01Z",
                "payload": {"model": "gpt-5.4", "cwd": "/work/project"},
            },
            {
                "type": "response_item",
                "timestamp": "2026-05-08T10:00:02Z",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": '{"cmd":"uv run pytest"}',
                },
            },
            {
                "type": "event_msg",
                "timestamp": "2026-05-08T10:00:03Z",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {"input_tokens": 3, "output_tokens": 4}
                    },
                },
            },
        ],
    )

    assert [event.event_type for event in events] == [
        EventType.SESSION_META,
        EventType.TURN_CONTEXT,
        EventType.TOOL_CALL,
        EventType.MODEL_CALL,
    ]
    assert events[2].command == "uv run pytest"
    assert events[3].token_usage.total_tokens == 7
