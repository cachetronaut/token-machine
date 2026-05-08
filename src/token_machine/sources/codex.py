"""Codex session source adapter."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Mapping, cast

from token_machine.config import DEFAULT_WATCH_PATHS
from token_machine.models import AgentSource, AnalyticsEvent, EventType, TokenUsage
from token_machine.sources.base import (
    discover_jsonl_files,
    list_value,
    make_event,
    mapping_value,
    metadata,
    session_id_from_path,
    string_value,
)


class CodexSource:
    name = AgentSource.CODEX

    def default_paths(self) -> tuple[Path, ...]:
        return (DEFAULT_WATCH_PATHS[0],)

    def discover_files(self, root: Path) -> list[Path]:
        return discover_jsonl_files(root)

    def detect(self, objects: Sequence[Mapping[str, object]], path: Path) -> bool:
        if ".codex" in str(path):
            return True
        return any(obj.get("type") == "session_meta" for obj in objects[:20])

    def parse(
        self, path: Path, objects: Sequence[Mapping[str, object]]
    ) -> list[AnalyticsEvent]:
        session_id = session_id_from_path(path)
        project_path = ""
        model = ""
        events: list[AnalyticsEvent] = []

        for position, obj in enumerate(objects):
            obj_type = string_value(obj, "type")
            payload = mapping_value(obj, "payload")
            timestamp = string_value(obj, "timestamp") or string_value(
                payload, "timestamp"
            )

            if obj_type == "session_meta":
                session_id = string_value(payload, "id", session_id)
                project_path = string_value(payload, "cwd", project_path)
                events.append(
                    make_event(
                        source=self.name,
                        source_path=path,
                        session_id=session_id,
                        event_type=EventType.SESSION_META,
                        position=position,
                        timestamp=timestamp,
                        project_path=project_path,
                        event_metadata=metadata(
                            originator=payload.get("originator", ""),
                            cli_version=payload.get("cli_version", ""),
                            model_provider=payload.get("model_provider", ""),
                        ),
                    )
                )
                continue

            if obj_type == "turn_context":
                model = string_value(payload, "model", model)
                project_path = string_value(payload, "cwd", project_path)
                events.append(
                    make_event(
                        source=self.name,
                        source_path=path,
                        session_id=session_id,
                        event_type=EventType.TURN_CONTEXT,
                        position=position,
                        timestamp=timestamp,
                        project_path=project_path,
                        model=model,
                        event_metadata=metadata(
                            collaboration_mode=payload.get("collaboration_mode", {})
                        ),
                    )
                )
                continue

            if obj_type == "response_item":
                response_type = string_value(payload, "type")
                if response_type in {"function_call", "custom_tool_call"}:
                    tool_name = string_value(payload, "name")
                    events.append(
                        make_event(
                            source=self.name,
                            source_path=path,
                            session_id=session_id,
                            event_type=EventType.TOOL_CALL,
                            position=position,
                            timestamp=timestamp,
                            project_path=project_path,
                            model=model,
                            tool_name=tool_name,
                            command=_codex_command_from_payload(tool_name, payload),
                            event_metadata=metadata(call_id=payload.get("call_id", "")),
                        )
                    )
                elif response_type == "message":
                    events.append(
                        make_event(
                            source=self.name,
                            source_path=path,
                            session_id=session_id,
                            event_type=EventType.MESSAGE,
                            position=position,
                            timestamp=timestamp,
                            project_path=project_path,
                            model=model,
                            event_metadata=metadata(role=payload.get("role", "")),
                        )
                    )
                continue

            if obj_type != "event_msg":
                continue

            event_type = string_value(payload, "type")
            if event_type == "token_count":
                info = mapping_value(payload, "info")
                usage_data = info.get("last_token_usage")
                usage = TokenUsage.from_mapping(
                    cast(Mapping[str, object], usage_data)
                    if isinstance(usage_data, Mapping)
                    else None
                )
                if usage.total_tokens:
                    events.append(
                        make_event(
                            source=self.name,
                            source_path=path,
                            session_id=session_id,
                            event_type=EventType.MODEL_CALL,
                            position=position,
                            timestamp=timestamp,
                            project_path=project_path,
                            model=model,
                            token_usage=usage,
                        )
                    )
            elif event_type == "exec_command_end":
                command = " ".join(str(part) for part in list_value(payload, "command"))
                events.append(
                    make_event(
                        source=self.name,
                        source_path=path,
                        session_id=session_id,
                        event_type=EventType.CLI_COMMAND,
                        position=position,
                        timestamp=timestamp,
                        project_path=project_path,
                        model=model,
                        tool_name="exec_command",
                        command=command,
                        event_metadata=metadata(
                            exit_code=payload.get("exit_code"),
                            process_id=payload.get("process_id", ""),
                        ),
                    )
                )
        return events


def _codex_command_from_payload(tool_name: str, payload: Mapping[str, object]) -> str:
    raw_arguments = payload.get("arguments") or payload.get("input") or ""
    if not raw_arguments or not (
        tool_name.endswith("exec_command") or tool_name == "exec_command"
    ):
        return ""
    parsed: object
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return ""
    else:
        parsed = raw_arguments
    if not isinstance(parsed, Mapping):
        return ""
    parsed_mapping = cast(Mapping[str, object], parsed)
    return str(parsed_mapping.get("cmd", ""))
