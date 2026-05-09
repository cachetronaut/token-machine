"""Typed domain models for Token Machine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import StrEnum
from pathlib import Path
from typing import Mapping, TypedDict, cast

SCHEMA_VERSION = 1

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


class RawRecord(TypedDict, total=False):
    """Raw JSON object loaded from a source log."""

    type: object
    payload: object
    timestamp: object
    sessionId: object
    message: object


class AgentSource(StrEnum):
    CODEX = "codex"
    CLAUDE_CODE = "claudecode"
    GEMINI = "gemini"
    ZED = "zed"
    UNKNOWN = "unknown"


class EventType(StrEnum):
    SESSION_META = "session_meta"
    TURN_CONTEXT = "turn_context"
    MESSAGE = "message"
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    CLI_COMMAND = "cli_command"


class ToolCategory(StrEnum):
    READ = "Read"
    EDIT = "Edit"
    SEARCH = "Search"
    SHELL = "Shell"
    BROWSER = "Browser"
    PLANNING = "Planning"
    DELEGATION = "Delegation"
    NETWORK = "Network"
    GIT = "Git"
    TEST = "Test"
    OTHER = "Other"


class IngestStatus(StrEnum):
    OK = "ok"
    SKIPPED = "skipped"
    ERROR = "error"


class ModelFamily(StrEnum):
    CLAUDE = "Claude"
    GEMINI = "Gemini"
    OPENAI = "OpenAI"
    QWEN = "Qwen"
    OTHER = "Other"


class MetricOrigin(StrEnum):
    RECORDED = "recorded"
    COMPUTED = "computed"
    INFERRED = "inferred"
    MISSING = "missing"


TOKEN_KEYS = {
    "input_tokens": ("input_tokens", "prompt_tokens", "inputTokens", "input"),
    "cached_input_tokens": (
        "cached_input_tokens",
        "cache_read_input_tokens",
        "cacheReadInputTokens",
        "cached",
    ),
    "cache_creation_input_tokens": (
        "cache_creation_input_tokens",
        "cacheCreationInputTokens",
    ),
    "output_tokens": ("output_tokens", "completion_tokens", "outputTokens", "output"),
    "reasoning_output_tokens": (
        "reasoning_output_tokens",
        "reasoningOutputTokens",
        "thoughts",
    ),
    "total_tokens": ("total_tokens", "totalTokens", "total"),
}


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_mapping(cls, data: Mapping[str, object] | None) -> "TokenUsage":
        if not isinstance(data, Mapping):
            return cls()
        values: dict[str, int] = {}
        for target, aliases in TOKEN_KEYS.items():
            values[target] = first_int(data, aliases)

        cache_creation = data.get("cache_creation") or data.get("cacheCreation")
        if isinstance(cache_creation, Mapping):
            cache_mapping = cast(Mapping[str, object], cache_creation)
            bucket_total = sum(
                safe_int(cache_mapping.get(key))
                for key in ("ephemeral_1h_input_tokens", "ephemeral_5m_input_tokens")
            )
            if bucket_total:
                values["cache_creation_input_tokens"] = bucket_total

        if not values["total_tokens"]:
            values["total_tokens"] = (
                values["input_tokens"]
                + values["cached_input_tokens"]
                + values["cache_creation_input_tokens"]
                + values["output_tokens"]
                + values["reasoning_output_tokens"]
            )
        return cls(**values)

    @property
    def context_tokens(self) -> int:
        return (
            self.input_tokens
            + self.cached_input_tokens
            + self.cache_creation_input_tokens
        )


@dataclass(frozen=True)
class AnalyticsEvent:
    event_id: str
    event_type: EventType
    source: AgentSource
    source_path: str
    session_id: str
    timestamp: str = ""
    project_path: str = ""
    model: str = ""
    tool_name: str = ""
    tool_description: str = ""
    cli_name: str = ""
    command: str = ""
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    metadata: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class IngestResult:
    source_path: str
    source: AgentSource
    session_id: str
    event_count: int
    status: IngestStatus
    error: str = ""


@dataclass(frozen=True)
class SessionRollup:
    session_id: str
    source: AgentSource
    source_path: str
    project_path: str
    started_at: str
    ended_at: str
    event_count: int
    model_calls: int
    tool_calls: int
    cli_commands: int
    messages: int
    models: dict[str, int]
    tools: dict[str, int]
    clis: dict[str, int]
    tokens: TokenUsage


@dataclass(frozen=True)
class DashboardSummary:
    generated_at: str
    event_count: int
    sessions: int
    sources: dict[str, int]
    models: dict[str, int]
    tools: dict[str, int]
    clis: dict[str, int]
    event_types: dict[str, int]
    tokens: TokenUsage
    descriptions: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DailySummary:
    day: str
    summary: DashboardSummary


@dataclass(frozen=True)
class ToolMixItem:
    category: str
    count: int
    percent: int
    description: str = ""


@dataclass(frozen=True)
class SessionProfile:
    rollup: SessionRollup
    duration_seconds: int
    time_to_first_tool_seconds: int
    time_to_first_edit_seconds: int
    tool_mix: list[ToolMixItem]
    workflow_role: str
    scouting_report: str


@dataclass(frozen=True)
class ModelProfile:
    model: str
    model_family: ModelFamily
    source: AgentSource
    sources: dict[str, int]
    intelligence_level: str
    reasoning_level: str
    session_count: int
    project_count: int
    projects: list[dict[str, JsonValue]]
    model_calls: int
    tool_calls: int
    cli_commands: int
    tokens: TokenUsage
    tools: dict[str, int]
    clis: dict[str, int]
    tool_mix: list[ToolMixItem]
    workflow_role: str
    scouting_report: str
    stats: dict[str, int | str]


@dataclass(frozen=True)
class DashboardData:
    generated_at: str
    summary: DashboardSummary
    daily: list[DailySummary]
    hourly: list[DailySummary]
    model_profiles: list[ModelProfile]
    recent_sessions: list[SessionProfile]


def safe_int(value: object) -> int:
    if value is None or not isinstance(value, str | int | float):
        return 0
    try:
        return int(value)
    except TypeError, ValueError:
        return 0


def first_int(data: Mapping[str, object], aliases: tuple[str, ...]) -> int:
    for alias in aliases:
        value = data.get(alias)
        if value is not None:
            return safe_int(value)
    return 0


def jsonable(value: object) -> JsonValue:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


_AGENT_SOURCE_ALIASES: dict[str, str] = {
    "claude": AgentSource.CLAUDE_CODE.value,
}


def _parse_agent_source(raw: str) -> AgentSource:
    normalized = _AGENT_SOURCE_ALIASES.get(raw, raw)
    try:
        return AgentSource(normalized)
    except ValueError:
        return AgentSource.UNKNOWN


def event_from_mapping(data: Mapping[str, object]) -> AnalyticsEvent:
    token_data = data.get("token_usage")
    token_mapping = (
        cast(Mapping[str, object], token_data)
        if isinstance(token_data, Mapping)
        else None
    )
    token_usage = TokenUsage.from_mapping(token_mapping)
    raw_metadata = data.get("metadata")
    event_metadata: dict[str, JsonValue] = {}
    if isinstance(raw_metadata, Mapping):
        for key, value in raw_metadata.items():
            event_metadata[str(key)] = jsonable(value)
    return AnalyticsEvent(
        event_id=str(data.get("event_id", "")),
        event_type=EventType(str(data.get("event_type", EventType.MESSAGE.value))),
        source=_parse_agent_source(str(data.get("source", AgentSource.UNKNOWN.value))),
        source_path=str(data.get("source_path", "")),
        session_id=str(data.get("session_id", "")),
        timestamp=str(data.get("timestamp", "")),
        project_path=str(data.get("project_path", "")),
        model=str(data.get("model", "")),
        tool_name=str(data.get("tool_name", "")),
        tool_description=str(data.get("tool_description", "")),
        cli_name=str(data.get("cli_name", "")),
        command=str(data.get("command", "")),
        token_usage=token_usage,
        metadata=event_metadata,
    )
