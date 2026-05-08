from pathlib import Path

from token_machine.models import EventType
from token_machine.sources.claude import ClaudeSource


def test_claude_parser_emits_usage_and_bash_commands() -> None:
    source = ClaudeSource()
    events = source.parse(
        Path("/tmp/.claude/session.jsonl"),
        [
            {
                "sessionId": "c1",
                "cwd": "/work/project",
                "timestamp": "2026-05-08T10:00:00Z",
                "version": "1.0",
                "message": {
                    "role": "user",
                    "content": "<bash-input>git status --short</bash-input>",
                },
            },
            {
                "sessionId": "c1",
                "cwd": "/work/project",
                "timestamp": "2026-05-08T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-6",
                    "usage": {"input_tokens": 5, "output_tokens": 6},
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool1",
                            "name": "Bash",
                            "input": {"cmd": "git status --short"},
                        }
                    ],
                },
            },
        ],
    )

    assert any(event.event_type == EventType.SESSION_META for event in events)
    assert any(event.event_type == EventType.MODEL_CALL for event in events)
    assert any(event.command == "git status --short" for event in events)
    model_event = next(
        event for event in events if event.event_type == EventType.MODEL_CALL
    )
    assert model_event.token_usage.total_tokens == 11


def test_claude_parser_captures_dynamic_tool_descriptions() -> None:
    source = ClaudeSource()
    events = source.parse(
        Path("/tmp/.claude/session.jsonl"),
        [
            {
                "sessionId": "c2",
                "timestamp": "2026-05-08T10:00:00Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_01",
                            "name": "Bash",
                            "input": {
                                "command": 'uv run python -c "print(1)"',
                                "description": "Verify imports are clean",
                            },
                        }
                    ],
                },
            },
        ],
    )

    tool_call = next(e for e in events if e.event_type == EventType.TOOL_CALL)
    assert tool_call.tool_description == "Verify imports are clean"
    # Note: The source parser keeps raw casing, the metrics layer lowercases it.
    assert tool_call.command == 'uv run python -c "print(1)"'
