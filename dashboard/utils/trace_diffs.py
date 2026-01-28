"""
Utility for extracting file diffs from trace Edit/Write operations.

Processes TraceMessage lists to extract file modifications, building a
per-file history of Read (baseline), Edit, and Write operations that
can be used for diff visualization.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from src.ingest.trace_viewer_parser import TraceMessage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileOperation:
    """A single file operation extracted from a trace message."""

    operation: str  # "Read", "Edit", or "Write"
    file_path: str
    old_string: str
    new_string: str
    full_content: str
    sequence_number: int


def _extract_read_operation(msg: TraceMessage) -> Optional[FileOperation]:
    """Extract a Read operation from a tool_use TraceMessage.

    Captures the file path from the tool input. The actual file content
    comes from the corresponding tool_result message, which is handled
    separately via link_read_results().

    Args:
        msg: A tool_use TraceMessage with tool_name "Read"

    Returns:
        FileOperation or None if tool_input is missing
    """
    if msg.tool_input is None:
        return None

    file_path = msg.tool_input.get("file_path", "")
    if not file_path:
        return None

    return FileOperation(
        operation="Read",
        file_path=file_path,
        old_string="",
        new_string="",
        full_content="",
        sequence_number=msg.sequence_number,
    )


def _extract_edit_operation(msg: TraceMessage) -> Optional[FileOperation]:
    """Extract an Edit operation from a tool_use TraceMessage.

    Args:
        msg: A tool_use TraceMessage with tool_name "Edit"

    Returns:
        FileOperation with old_string and new_string, or None
    """
    if msg.tool_input is None:
        return None

    file_path = msg.tool_input.get("file_path", "")
    if not file_path:
        return None

    old_string = msg.tool_input.get("old_string", "")
    new_string = msg.tool_input.get("new_string", "")

    return FileOperation(
        operation="Edit",
        file_path=file_path,
        old_string=old_string,
        new_string=new_string,
        full_content="",
        sequence_number=msg.sequence_number,
    )


def _extract_write_operation(msg: TraceMessage) -> Optional[FileOperation]:
    """Extract a Write operation from a tool_use TraceMessage.

    Args:
        msg: A tool_use TraceMessage with tool_name "Write"

    Returns:
        FileOperation with full_content, or None
    """
    if msg.tool_input is None:
        return None

    file_path = msg.tool_input.get("file_path", "")
    if not file_path:
        return None

    content = msg.tool_input.get("content", "")

    return FileOperation(
        operation="Write",
        file_path=file_path,
        old_string="",
        new_string="",
        full_content=content,
        sequence_number=msg.sequence_number,
    )


def _build_read_result_map(
    messages: list[TraceMessage],
) -> dict[str, str]:
    """Build a mapping from parent_tool_use_id to tool result content.

    This maps Read tool_use IDs to their corresponding tool_result content,
    allowing us to capture file baselines.

    Args:
        messages: Full list of TraceMessages

    Returns:
        Dict mapping parent_tool_use_id -> tool_result text
    """
    result_map: dict[str, str] = {}
    for msg in messages:
        if msg.type == "user" and msg.subtype == "tool_result":
            parent_id = msg.parent_tool_use_id
            if parent_id:
                result_text = msg.tool_result if msg.tool_result else msg.content
                result_map = {**result_map, parent_id: result_text}
    return result_map


def _link_read_results(
    operations: list[FileOperation],
    messages: list[TraceMessage],
) -> list[FileOperation]:
    """Link Read operations with their tool_result content.

    Finds the tool_result message corresponding to each Read operation
    and creates a new FileOperation with the full_content populated.

    Args:
        operations: List of FileOperations (may include Read ops without content)
        messages: Full list of TraceMessages for looking up tool results

    Returns:
        New list of FileOperations with Read content populated
    """
    # Build a map of tool_use_id -> tool_result content
    result_map = _build_read_result_map(messages)

    # Build a map of sequence_number -> parent_tool_use_id for Read tool_use messages
    read_id_map: dict[int, str] = {}
    for msg in messages:
        if (
            msg.type == "assistant"
            and msg.subtype == "tool_use"
            and msg.tool_name == "Read"
        ):
            read_id_map = {**read_id_map, msg.sequence_number: msg.parent_tool_use_id}

    linked: list[FileOperation] = []
    for op in operations:
        if op.operation == "Read":
            tool_use_id = read_id_map.get(op.sequence_number, "")
            content = result_map.get(tool_use_id, "")
            linked = [
                *linked,
                FileOperation(
                    operation=op.operation,
                    file_path=op.file_path,
                    old_string=op.old_string,
                    new_string=op.new_string,
                    full_content=content,
                    sequence_number=op.sequence_number,
                ),
            ]
        else:
            linked = [*linked, op]

    return linked


def extract_file_operations(
    messages: list[TraceMessage],
) -> dict[str, list[FileOperation]]:
    """Extract file modifications from Read/Edit/Write tool calls in a trace.

    Processes all tool_use messages to build a per-file history of operations.
    Read operations capture the baseline file state (from tool_result content).
    Edit operations capture old_string -> new_string replacements.
    Write operations capture the full file content written.

    Args:
        messages: List of TraceMessages from parse_trace()

    Returns:
        Dict mapping file_path to a list of FileOperations sorted by
        sequence_number. Each FileOperation contains:
        - operation: "Read", "Edit", or "Write"
        - file_path: path to the file
        - old_string: text replaced (Edit only)
        - new_string: replacement text (Edit only)
        - full_content: complete file content (Write) or read content (Read)
        - sequence_number: position in the trace sequence
    """
    operations: list[FileOperation] = []

    for msg in messages:
        if msg.type != "assistant" or msg.subtype != "tool_use":
            continue

        op: Optional[FileOperation] = None

        if msg.tool_name == "Read":
            op = _extract_read_operation(msg)
        elif msg.tool_name == "Edit":
            op = _extract_edit_operation(msg)
        elif msg.tool_name == "Write":
            op = _extract_write_operation(msg)

        if op is not None:
            operations = [*operations, op]

    # Link Read operations with their result content
    operations = _link_read_results(operations, messages)

    # Group by file path and sort by sequence number
    grouped: dict[str, list[FileOperation]] = {}
    for op in operations:
        existing = grouped.get(op.file_path, [])
        grouped = {**grouped, op.file_path: [*existing, op]}

    # Sort each file's operations by sequence number
    sorted_grouped: dict[str, list[FileOperation]] = {}
    for path, ops in grouped.items():
        sorted_grouped = {
            **sorted_grouped,
            path: sorted(ops, key=lambda o: o.sequence_number),
        }

    return sorted_grouped
