"""
Embedded file tree from trace data.

Builds a hierarchical file tree from Read/Edit/Write tool calls in the trace,
displaying accessed files with operation-type icon badges and click-to-select.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import streamlit as st

from dashboard.utils.trace_diffs import FileOperation, extract_file_operations
from src.ingest.trace_viewer_parser import TraceMessage

logger = logging.getLogger(__name__)

# Icon badges for file operation types
ICON_READ_ONLY = "\U0001F441\uFE0F"  # eye
ICON_MODIFIED = "\u270F\uFE0F"  # pencil
ICON_CREATED = "\u2795"  # plus
ICON_FOLDER = "\U0001F4C1"  # folder


@dataclass(frozen=True)
class FileAccessInfo:
    """Summarized access info for a single file."""

    file_path: str
    was_read: bool
    was_edited: bool
    was_created: bool


@dataclass(frozen=True)
class TreeNode:
    """A node in the file tree (directory or file)."""

    name: str
    full_path: str
    is_directory: bool
    access_info: Optional[FileAccessInfo]
    children: tuple  # tuple of TreeNode (frozen dataclass can't have mutable default)


def classify_file_access(
    operations: list[FileOperation],
) -> FileAccessInfo:
    """Classify a file's access type from its operations list.

    A file is classified as:
    - created: if it has a Write operation but no preceding Read
    - modified: if it has Edit operations, or Write after a Read
    - read-only: if it only has Read operations

    Args:
        operations: List of FileOperations for a single file, sorted by sequence_number

    Returns:
        FileAccessInfo with boolean flags for access types
    """
    has_read = False
    has_edit = False
    has_write = False
    first_read_seq = float("inf")
    first_write_seq = float("inf")

    for op in operations:
        if op.operation == "Read":
            has_read = True
            first_read_seq = min(first_read_seq, op.sequence_number)
        elif op.operation == "Edit":
            has_edit = True
        elif op.operation == "Write":
            has_write = True
            first_write_seq = min(first_write_seq, op.sequence_number)

    # Created: Write without a prior Read
    was_created = has_write and (not has_read or first_write_seq < first_read_seq)
    # Modified: has Edit, or has Write after a Read
    was_edited = has_edit or (
        has_write and has_read and first_read_seq < first_write_seq
    )
    # Read-only: only Read operations (no edits, no writes)
    was_read = has_read and not has_edit and not was_created and not was_edited

    return FileAccessInfo(
        file_path=operations[0].file_path if operations else "",
        was_read=was_read,
        was_edited=was_edited,
        was_created=was_created,
    )


def get_file_icon(access_info: FileAccessInfo) -> str:
    """Get the icon badge for a file based on its access type.

    Priority: created > modified > read-only.

    Args:
        access_info: FileAccessInfo for the file

    Returns:
        Icon string
    """
    if access_info.was_created:
        return ICON_CREATED
    if access_info.was_edited:
        return ICON_MODIFIED
    return ICON_READ_ONLY


def build_file_access_map(
    messages: list[TraceMessage],
) -> dict[str, FileAccessInfo]:
    """Build a map of file paths to their access info from trace messages.

    Uses extract_file_operations() to get per-file operation lists, then
    classifies each file's access type.

    Args:
        messages: List of TraceMessages from parse_trace()

    Returns:
        Dict mapping file_path -> FileAccessInfo
    """
    file_ops = extract_file_operations(messages)
    access_map: dict[str, FileAccessInfo] = {}

    for path, ops in file_ops.items():
        access_map = {**access_map, path: classify_file_access(ops)}

    return access_map


def _normalize_path(file_path: str) -> list[str]:
    """Split a file path into its component parts, removing empty segments.

    Args:
        file_path: Absolute or relative file path

    Returns:
        List of path segments (e.g., ["src", "main.py"])
    """
    # Remove leading slash for consistent tree building
    cleaned = file_path.lstrip("/")
    parts = cleaned.split("/")
    return [p for p in parts if p]


def build_tree(
    access_map: dict[str, FileAccessInfo],
) -> TreeNode:
    """Build a hierarchical tree structure from the file access map.

    Creates a root node with nested directory/file nodes based on
    the file paths in the access map.

    Args:
        access_map: Dict mapping file_path -> FileAccessInfo

    Returns:
        Root TreeNode containing the full tree hierarchy
    """
    # Build an intermediate mutable dict structure, then convert to TreeNode
    # Structure: { "name", "children": { name: dict }, "access_info" }
    root: dict = {"name": "", "children": {}, "access_info": None, "full_path": ""}

    for file_path, access_info in sorted(access_map.items()):
        parts = _normalize_path(file_path)
        if not parts:
            continue

        current = root
        for i, part in enumerate(parts):
            is_last = i == len(parts) - 1
            if part not in current["children"]:
                current_path = "/".join(parts[: i + 1])
                current["children"] = {
                    **current["children"],
                    part: {
                        "name": part,
                        "children": {},
                        "access_info": access_info if is_last else None,
                        "full_path": file_path if is_last else current_path,
                    },
                }
            if is_last:
                # Update access_info for existing node (in case path was seen before)
                existing = current["children"][part]
                current["children"] = {
                    **current["children"],
                    part: {
                        **existing,
                        "access_info": access_info,
                        "full_path": file_path,
                    },
                }
            current = current["children"][part]

    return _dict_to_tree_node(root)


def _dict_to_tree_node(node_dict: dict) -> TreeNode:
    """Convert a mutable dict tree to an immutable TreeNode tree.

    Args:
        node_dict: Dict with keys: name, children, access_info, full_path

    Returns:
        Immutable TreeNode
    """
    children = tuple(
        _dict_to_tree_node(child)
        for child in sorted(
            node_dict["children"].values(),
            key=lambda c: (0 if c["children"] else 1, c["name"]),
        )
    )

    return TreeNode(
        name=node_dict["name"],
        full_path=node_dict.get("full_path", ""),
        is_directory=len(node_dict["children"]) > 0,
        access_info=node_dict.get("access_info"),
        children=children,
    )


def _count_files_in_subtree(node: TreeNode) -> int:
    """Count total files (non-directory nodes) in a subtree.

    Args:
        node: TreeNode to count files in

    Returns:
        Number of file nodes
    """
    if not node.is_directory:
        return 1
    total = 0
    for child in node.children:
        total = total + _count_files_in_subtree(child)
    return total


def render_file_tree_node(
    node: TreeNode,
    session_key: str = "selected_file",
    depth: int = 0,
) -> None:
    """Render a single tree node and its children recursively.

    Directories use st.expander. Files are rendered as buttons with icon badges.
    Clicking a file sets it as the selected file in session state.

    Args:
        node: TreeNode to render
        session_key: Session state key for selected file path
        depth: Current nesting depth (for indentation)
    """
    if node.is_directory and node.name:
        file_count = _count_files_in_subtree(node)
        label = f"{ICON_FOLDER} {node.name} ({file_count})"
        with st.expander(label, expanded=depth < 2):
            for child in node.children:
                render_file_tree_node(child, session_key, depth + 1)
    elif node.is_directory:
        # Root node: render children directly
        for child in node.children:
            render_file_tree_node(child, session_key, depth)
    else:
        # File node
        icon = get_file_icon(node.access_info) if node.access_info else ICON_READ_ONLY
        label = f"{icon} {node.name}"
        selected = st.session_state.get(session_key, "")
        is_selected = selected == node.full_path

        button_key = f"file_tree_{node.full_path}_{depth}"

        if is_selected:
            st.markdown(
                f"<div style='background-color: #e0e7ff; padding: 4px 8px; "
                f"border-radius: 4px; font-weight: bold;'>{label}</div>",
                unsafe_allow_html=True,
            )
        else:
            if st.button(label, key=button_key, use_container_width=True):
                st.session_state[session_key] = node.full_path
                st.rerun()


def render_file_tree(
    messages: list[TraceMessage],
    session_key: str = "selected_file",
) -> None:
    """Render the full embedded file tree from trace data.

    Builds the file access map, constructs the tree, and renders it
    as a nested Streamlit widget hierarchy.

    Args:
        messages: List of TraceMessages from parse_trace()
        session_key: Session state key for selected file path
    """
    access_map = build_file_access_map(messages)

    if not access_map:
        st.info("No file operations found in this trace.")
        return

    st.markdown("### Files Accessed")

    # Summary counts
    read_only = sum(
        1 for a in access_map.values()
        if a.was_read and not a.was_edited and not a.was_created
    )
    modified = sum(1 for a in access_map.values() if a.was_edited)
    created = sum(1 for a in access_map.values() if a.was_created)

    legend_parts = []
    if read_only > 0:
        legend_parts = [*legend_parts, f"{ICON_READ_ONLY} Read: {read_only}"]
    if modified > 0:
        legend_parts = [*legend_parts, f"{ICON_MODIFIED} Modified: {modified}"]
    if created > 0:
        legend_parts = [*legend_parts, f"{ICON_CREATED} Created: {created}"]

    st.caption(" | ".join(legend_parts))

    tree = build_tree(access_map)
    render_file_tree_node(tree, session_key)
