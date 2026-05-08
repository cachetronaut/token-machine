from pathlib import Path

from token_machine.models import EventType
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
