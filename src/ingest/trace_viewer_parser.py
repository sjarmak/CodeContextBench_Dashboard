"""
JSONL trace parser for claude-code.txt files.

Reads each line as JSON, extracts structured trace messages,
computes token usage, and produces summary metrics.

The claude-code.txt format is JSONL with these message types:
- system (subtype: init): session metadata (model, tools, session_id)
- assistant: agent messages with text and/or tool_use content blocks
- user: user messages and tool_result content
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenUsage:
    """Token usage from an assistant message."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass(frozen=True)
class TraceMessage:
    """A single message from the JSONL trace."""

    type: str
    subtype: str
    content: str
    tool_name: str
    tool_input: Optional[dict]
    tool_result: str
    token_usage: Optional[TokenUsage]
    parent_tool_use_id: str
    session_id: str
    uuid: str
    sequence_number: int


@dataclass(frozen=True)
class TraceSummary:
    """Summary metrics computed from a parsed trace."""

    total_messages: int
    total_tool_calls: int
    unique_tools: int
    total_tokens: int
    tools_by_name: dict[str, int]
    files_accessed: dict[str, dict[str, int]]


def _extract_token_usage(message_data: dict) -> Optional[TokenUsage]:
    """Extract token usage from an assistant message's usage field."""
    msg = message_data.get("message", {})
    usage = msg.get("usage")
    if not usage:
        return None

    return TokenUsage(
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
        cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
    )


def _extract_content_text(content) -> str:
    """Extract displayable text content from a message content field."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)
        return "\n".join(text_parts)

    return ""


def _extract_tool_result_text(data: dict) -> str:
    """Extract tool result text from a user message."""
    tool_result = data.get("toolUseResult", {})
    if not tool_result:
        msg = data.get("message", {})
        content = msg.get("content", "")
        return _extract_content_text(content)

    result_content = tool_result.get("content", "")
    if isinstance(result_content, str):
        return result_content

    if isinstance(result_content, list):
        parts = []
        for block in result_content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "tool_result":
                    parts.append(block.get("content", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)

    return str(result_content) if result_content else ""


def _parse_line(line_data: dict, sequence_number: int) -> list[TraceMessage]:
    """
    Parse a single JSONL line into one or more TraceMessages.

    Assistant messages with multiple content blocks (text + tool_use)
    produce multiple TraceMessage entries.
    """
    msg_type = line_data.get("type", "")
    session_id = line_data.get("sessionId", line_data.get("session_id", ""))
    uuid_val = line_data.get("uuid", "")

    # Skip non-conversation types (queue-operation, etc.)
    if msg_type not in ("system", "assistant", "user"):
        return []

    messages: list[TraceMessage] = []

    if msg_type == "system":
        subtype = line_data.get("subtype", "")
        content_parts = []
        if subtype == "init":
            model = line_data.get("model", "")
            tools = line_data.get("tools", [])
            content_parts.append(f"Model: {model}")
            content_parts.append(f"Tools: {', '.join(tools)}")

        messages.append(
            TraceMessage(
                type="system",
                subtype=subtype,
                content="\n".join(content_parts),
                tool_name="",
                tool_input=None,
                tool_result="",
                token_usage=None,
                parent_tool_use_id="",
                session_id=session_id,
                uuid=uuid_val,
                sequence_number=sequence_number,
            )
        )
        return messages

    if msg_type == "assistant":
        token_usage = _extract_token_usage(line_data)
        parent_uuid = line_data.get("parentUuid", "")

        msg = line_data.get("message", {})
        content = msg.get("content", "")

        if isinstance(content, str):
            messages.append(
                TraceMessage(
                    type="assistant",
                    subtype="text",
                    content=content,
                    tool_name="",
                    tool_input=None,
                    tool_result="",
                    token_usage=token_usage,
                    parent_tool_use_id=parent_uuid or "",
                    session_id=session_id,
                    uuid=uuid_val,
                    sequence_number=sequence_number,
                )
            )
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type", "")

                if block_type == "text":
                    messages.append(
                        TraceMessage(
                            type="assistant",
                            subtype="text",
                            content=block.get("text", ""),
                            tool_name="",
                            tool_input=None,
                            tool_result="",
                            token_usage=token_usage,
                            parent_tool_use_id=parent_uuid or "",
                            session_id=session_id,
                            uuid=uuid_val,
                            sequence_number=sequence_number,
                        )
                    )
                elif block_type == "tool_use":
                    messages.append(
                        TraceMessage(
                            type="assistant",
                            subtype="tool_use",
                            content="",
                            tool_name=block.get("name", ""),
                            tool_input=block.get("input"),
                            tool_result="",
                            token_usage=token_usage,
                            parent_tool_use_id=block.get("id", parent_uuid or ""),
                            session_id=session_id,
                            uuid=uuid_val,
                            sequence_number=sequence_number,
                        )
                    )

        return messages

    if msg_type == "user":
        parent_uuid = line_data.get("parentUuid", "")
        tool_use_result = line_data.get("toolUseResult")

        if tool_use_result:
            subtype = "tool_result"
            result_text = _extract_tool_result_text(line_data)
        else:
            subtype = "text"
            result_text = ""

        content_text = _extract_content_text(
            line_data.get("message", {}).get("content", "")
        )

        messages.append(
            TraceMessage(
                type="user",
                subtype=subtype,
                content=content_text,
                tool_name="",
                tool_input=None,
                tool_result=result_text,
                token_usage=None,
                parent_tool_use_id=parent_uuid or "",
                session_id=session_id,
                uuid=uuid_val,
                sequence_number=sequence_number,
            )
        )
        return messages

    return []


def parse_trace(file_path: str | Path) -> list[TraceMessage]:
    """
    Parse a claude-code.txt JSONL file into structured trace messages.

    Reads each line as JSON, skipping malformed lines with a warning.

    Args:
        file_path: Path to the claude-code.txt file (str or Path)

    Returns:
        List of TraceMessage dataclasses in sequence order
    """
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"Trace file not found: {path}")
        return []

    messages: list[TraceMessage] = []
    sequence = 0

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line_num, raw_line in enumerate(f, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue

                try:
                    line_data = json.loads(stripped)
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Malformed JSON at line {line_num} in {path}: {e}"
                    )
                    continue

                parsed = _parse_line(line_data, sequence)
                for msg in parsed:
                    messages.append(msg)
                    sequence += 1
    except OSError as e:
        logger.warning(f"Failed to read trace file {path}: {e}")

    return messages


def _track_file_access(
    files: dict[str, dict[str, int]], tool_name: str, tool_input: Optional[dict]
) -> None:
    """Track file access counts from tool calls (mutates files dict for efficiency)."""
    if tool_input is None:
        return

    file_path = tool_input.get("file_path", "")
    if not file_path:
        return

    if file_path not in files:
        files[file_path] = {"read_count": 0, "write_count": 0, "edit_count": 0}

    if tool_name == "Read":
        files[file_path] = {
            **files[file_path],
            "read_count": files[file_path]["read_count"] + 1,
        }
    elif tool_name == "Write":
        files[file_path] = {
            **files[file_path],
            "write_count": files[file_path]["write_count"] + 1,
        }
    elif tool_name == "Edit":
        files[file_path] = {
            **files[file_path],
            "edit_count": files[file_path]["edit_count"] + 1,
        }


def compute_summary(messages: list[TraceMessage]) -> TraceSummary:
    """
    Compute summary metrics from parsed trace messages.

    Args:
        messages: List of TraceMessage from parse_trace

    Returns:
        TraceSummary with aggregated metrics
    """
    tool_calls: dict[str, int] = {}
    files_accessed: dict[str, dict[str, int]] = {}
    total_input = 0
    total_output = 0
    seen_usage_uuids: set[str] = set()

    for msg in messages:
        if msg.subtype == "tool_use" and msg.tool_name:
            tool_calls = {
                **tool_calls,
                msg.tool_name: tool_calls.get(msg.tool_name, 0) + 1,
            }
            _track_file_access(files_accessed, msg.tool_name, msg.tool_input)

        if msg.token_usage is not None and msg.uuid not in seen_usage_uuids:
            seen_usage_uuids.add(msg.uuid)
            total_input += msg.token_usage.input_tokens
            total_output += msg.token_usage.output_tokens

    return TraceSummary(
        total_messages=len(messages),
        total_tool_calls=sum(tool_calls.values()),
        unique_tools=len(tool_calls),
        total_tokens=total_input + total_output,
        tools_by_name=dict(sorted(tool_calls.items(), key=lambda x: -x[1])),
        files_accessed=dict(
            sorted(
                files_accessed.items(),
                key=lambda x: -(
                    x[1]["read_count"] + x[1]["write_count"] + x[1]["edit_count"]
                ),
            )
        ),
    )
