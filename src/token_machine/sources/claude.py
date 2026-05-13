"""Claude Code session source adapter."""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Mapping, cast

from token_machine.config import DEFAULT_WATCH_PATHS
from token_machine.models import AgentSource, AnalyticsEvent, EventType, TokenUsage
from token_machine.sources.base import (
    discover_jsonl_files,
    make_event,
    mapping_value,
    metadata,
    session_id_from_path,
    string_value,
)


class ClaudeSource:
    name = AgentSource.CLAUDE_CODE

    def default_paths(self) -> tuple[Path, ...]:
        return (DEFAULT_WATCH_PATHS[1],)

    def discover_files(self, root: Path) -> list[Path]:
        return discover_jsonl_files(root)

    def detect(self, objects: Sequence[Mapping[str, object]], path: Path) -> bool:
        path_text = str(path)
        if ".claude" in path_text:
            return True
        if ".gemini" in path_text:
            return False
        return any(
            "message" in obj or "version" in obj or obj.get("userType") == "external"
            for obj in objects[:20]
        )

    def parse(
        self, path: Path, objects: Sequence[Mapping[str, object]]
    ) -> list[AnalyticsEvent]:
        session_id = session_id_from_path(path)
        project_path = ""
        model = ""
        events: list[AnalyticsEvent] = []
        session_meta_emitted = False

        for position, obj in enumerate(objects):
            session_id = string_value(obj, "sessionId", session_id)
            project_path = string_value(obj, "cwd", project_path)
            timestamp = string_value(obj, "timestamp")
            message = mapping_value(obj, "message")
            role = string_value(message, "role") or string_value(obj, "type")

            if not session_meta_emitted and "version" in obj:
                session_meta_emitted = True
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
                            version=obj.get("version", ""),
                            entrypoint=obj.get("entrypoint", ""),
                        ),
                    )
                )

            if role in {"user", "assistant"}:
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
                        event_metadata=metadata(role=role),
                    )
                )

            if role == "assistant":
                model = string_value(message, "model") or string_value(
                    obj, "model", model
                )
                usage_data = message.get("usage")
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
                for tool in _claude_tool_uses(message.get("content")):
                    tool_input = mapping_value(tool, "input")
                    tool_name = string_value(tool, "name")
                    if tool_name == "Skill":
                        events.append(
                            make_event(
                                source=self.name,
                                source_path=path,
                                session_id=session_id,
                                event_type=EventType.SKILL_CALL,
                                position=position,
                                timestamp=timestamp,
                                project_path=project_path,
                                model=model,
                                skill_name=string_value(tool_input, "skill"),
                                skill_description=string_value(tool_input, "args"),
                                event_metadata=metadata(tool_id=tool.get("id", "")),
                            )
                        )
                        continue
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
                            tool_description=string_value(tool_input, "description"),
                            command=string_value(tool_input, "cmd")
                            or string_value(tool_input, "command"),
                            event_metadata=metadata(tool_id=tool.get("id", "")),
                        )
                    )

            command = _claude_command_from_message(message)
            if command:
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
                        command=command,
                        event_metadata=metadata(role=role),
                    )
                )

            attachment = mapping_value(obj, "attachment")
            hook_command = string_value(attachment, "command")
            if hook_command:
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
                        tool_name=string_value(attachment, "hookName"),
                        command=hook_command,
                        event_metadata=metadata(exit_code=attachment.get("exitCode")),
                    )
                )
        return events


def _claude_tool_uses(content: object) -> list[Mapping[str, object]]:
    if not isinstance(content, list):
        return []
    tools: list[Mapping[str, object]] = []
    for item in content:
        if not isinstance(item, Mapping):
            continue
        tool = cast(Mapping[str, object], item)
        if tool.get("type") == "tool_use":
            tools.append(tool)
    return tools


def _claude_command_from_message(message: Mapping[str, object]) -> str:
    content = message.get("content")
    if not isinstance(content, str):
        return ""
    command_match = re.search(r"<command-name>(.*?)</command-name>", content, re.S)
    if command_match:
        command_name = command_match.group(1).strip()
        return command_name if command_name.startswith("/") else "/" + command_name
    bash_match = re.search(r"<bash-input>(.*?)</bash-input>", content, re.S)
    if bash_match:
        return html.unescape(bash_match.group(1).strip())
    return ""
