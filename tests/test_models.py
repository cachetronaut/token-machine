from token_machine.models import EventType, TokenUsage, event_from_mapping, jsonable


def test_token_usage_computes_total_when_missing() -> None:
    usage = TokenUsage.from_mapping(
        {"input_tokens": 10, "cached": 2, "output_tokens": 5, "thoughts": 3}
    )

    assert usage.total_tokens == 20
    assert usage.context_tokens == 12


def test_jsonable_serializes_dataclasses_and_enums() -> None:
    usage = TokenUsage(input_tokens=1, total_tokens=1)

    assert jsonable(usage) == {
        "input_tokens": 1,
        "cached_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 1,
    }


def test_event_from_mapping_defaults_new_skill_fields_for_old_events() -> None:
    event = event_from_mapping(
        {
            "event_id": "e1",
            "event_type": "tool_call",
            "source": "codex",
            "source_path": "/tmp/session.jsonl",
            "session_id": "s1",
            "tool_name": "exec_command",
        }
    )

    assert event.event_type == EventType.TOOL_CALL
    assert event.skill_name == ""
    assert event.skill_description == ""
