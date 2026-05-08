import json
from pathlib import Path

from token_machine.ingest.discovery import detect_source
from token_machine.models import AgentSource, EventType
from token_machine.sources.gemini import GeminiSource


def test_gemini_parser_handles_latest_message_records() -> None:
    source = GeminiSource()
    events = source.parse(
        Path("/tmp/.gemini/tmp/project/chats/session-1.json"),
        [
            {
                "sessionId": "g1",
                "startTime": "2026-05-08T10:00:00Z",
                "kind": "main",
                "messages": [
                    {"id": "m1", "type": "user", "timestamp": "2026-05-08T10:00:01Z"},
                    {
                        "id": "m2",
                        "type": "gemini",
                        "timestamp": "2026-05-08T10:00:02Z",
                        "model": "gemini-3-flash-preview",
                        "tokens": {"input": 2, "output": 8},
                        "toolCalls": [
                            {
                                "id": "tool1",
                                "name": "run_shell_command",
                                "args": {"command": "ls"},
                            }
                        ],
                    },
                ],
            }
        ],
    )

    assert any(event.event_type == EventType.SESSION_META for event in events)
    assert any(event.event_type == EventType.MODEL_CALL for event in events)
    assert any(event.event_type == EventType.CLI_COMMAND for event in events)
    assert any(event.command == "ls" for event in events)


def test_gemini_json_file_detects_as_gemini_source(tmp_path: Path) -> None:
    chat_path = tmp_path / ".gemini" / "tmp" / "project" / "chats" / "session-1.json"
    chat_path.parent.mkdir(parents=True)
    chat_path.write_text(
        json.dumps(
            {
                "sessionId": "g1",
                "startTime": "2026-05-08T10:00:00Z",
                "kind": "main",
                "messages": [
                    {"id": "m1", "type": "user", "timestamp": "2026-05-08T10:00:01Z"},
                    {
                        "id": "m2",
                        "type": "gemini",
                        "timestamp": "2026-05-08T10:00:02Z",
                        "model": "gemini-3-flash-preview",
                        "tokens": {"input": 2, "output": 8},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    source, objects = detect_source(chat_path)

    assert source is not None
    assert source.name == AgentSource.GEMINI
    events = source.parse(chat_path, objects)
    assert any(event.event_type == EventType.MODEL_CALL for event in events)
