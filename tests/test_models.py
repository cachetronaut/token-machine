from token_machine.models import TokenUsage, jsonable


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
