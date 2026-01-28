"""
File diff viewer panel for trace data.

Renders diffs for files modified by the agent with syntax highlighting.
Supports unified and side-by-side diff formats, with links to source
repository when available.
"""

import difflib
import logging
from dataclasses import dataclass

import streamlit as st

from dashboard.utils.trace_diffs import FileOperation

logger = logging.getLogger(__name__)

DIFF_FORMAT_UNIFIED = "Unified"
DIFF_FORMAT_SIDE_BY_SIDE = "Side-by-Side"

DIFF_FORMATS = (DIFF_FORMAT_UNIFIED, DIFF_FORMAT_SIDE_BY_SIDE)


@dataclass(frozen=True)
class DiffEntry:
    """A single diff entry for display."""

    sequence_number: int
    operation: str
    file_path: str
    unified_diff: str
    old_text: str
    new_text: str


def _generate_unified_diff(
    old_text: str,
    new_text: str,
    file_path: str,
) -> str:
    """Generate a unified diff string from old and new text.

    Args:
        old_text: Original text content
        new_text: Replacement text content
        file_path: File path for diff header

    Returns:
        Unified diff string, or empty string if texts are identical
    """
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
    )

    if not diff_lines:
        return ""

    return "\n".join(diff_lines)


def _build_diff_entries(
    operations: list[FileOperation],
    file_path: str,
) -> list[DiffEntry]:
    """Build DiffEntry list from file operations.

    For Edit operations, generates a unified diff from old_string -> new_string.
    For Write operations, shows the full content written.
    Read operations are skipped (they are baseline captures, not modifications).

    Args:
        operations: List of FileOperations for a single file
        file_path: File path for diff headers

    Returns:
        List of DiffEntry objects sorted by sequence number
    """
    entries: list[DiffEntry] = []

    for op in operations:
        if op.operation == "Edit":
            unified = _generate_unified_diff(
                op.old_string,
                op.new_string,
                file_path,
            )
            entries = [
                *entries,
                DiffEntry(
                    sequence_number=op.sequence_number,
                    operation="Edit",
                    file_path=file_path,
                    unified_diff=unified,
                    old_text=op.old_string,
                    new_text=op.new_string,
                ),
            ]
        elif op.operation == "Write":
            entries = [
                *entries,
                DiffEntry(
                    sequence_number=op.sequence_number,
                    operation="Write",
                    file_path=file_path,
                    unified_diff="",
                    old_text="",
                    new_text=op.full_content,
                ),
            ]

    return entries


def _build_github_url(
    git_url: str,
    file_path: str,
) -> str:
    """Build a GitHub URL for a file path given a repository git URL.

    Converts git URLs like:
    - https://github.com/org/repo.git -> https://github.com/org/repo/blob/main/{path}
    - git@github.com:org/repo.git -> https://github.com/org/repo/blob/main/{path}

    Args:
        git_url: Repository git URL from task config
        file_path: File path relative to repo root

    Returns:
        GitHub URL string, or empty string if URL cannot be constructed
    """
    if not git_url:
        return ""

    # Normalize git URL to HTTPS base
    base_url = git_url
    if base_url.startswith("git@github.com:"):
        base_url = base_url.replace("git@github.com:", "https://github.com/")
    if base_url.endswith(".git"):
        base_url = base_url[:-4]

    # Strip leading slash from file path
    clean_path = file_path.lstrip("/")

    return f"{base_url}/blob/main/{clean_path}"


def _render_diff_header(
    entry: DiffEntry,
    github_url: str,
) -> None:
    """Render the header for a single diff entry.

    Shows operation type badge, sequence number, and optional GitHub link.

    Args:
        entry: DiffEntry to render header for
        github_url: GitHub URL for the file, or empty string
    """
    badge_color = "#3b82f6" if entry.operation == "Edit" else "#22c55e"
    badge_label = entry.operation

    header_parts = [
        f"<span style='background-color: {badge_color}; color: white; "
        f"padding: 2px 8px; border-radius: 4px; font-size: 0.85em; "
        f"font-weight: bold;'>{badge_label}</span>",
        f"<span style='color: #6b7280; font-size: 0.85em;'>"
        f"Sequence #{entry.sequence_number}</span>",
    ]

    if github_url:
        header_parts = [
            *header_parts,
            f"<a href='{github_url}' target='_blank' "
            f"style='font-size: 0.85em; text-decoration: none;'>"
            f"View on GitHub ↗</a>",
        ]

    st.markdown(
        " &nbsp; ".join(header_parts),
        unsafe_allow_html=True,
    )


def _render_unified_diff(entry: DiffEntry) -> None:
    """Render a diff entry in unified diff format.

    For Edit operations: shows unified diff with syntax highlighting.
    For Write operations: shows the full file content.

    Args:
        entry: DiffEntry to render
    """
    if entry.operation == "Edit":
        if entry.unified_diff:
            st.code(entry.unified_diff, language="diff")
        else:
            st.info("No text changes detected (old and new strings are identical).")
    elif entry.operation == "Write":
        st.markdown("**Full file content written:**")
        # Detect language from file extension
        lang = _detect_language(entry.file_path)
        content = entry.new_text if entry.new_text else "(empty file)"
        if len(content) > 5000:
            st.code(content[:5000], language=lang)
            st.caption(f"Content truncated (showing 5000 of {len(content)} characters)")
        else:
            st.code(content, language=lang)


def _render_side_by_side_diff(entry: DiffEntry) -> None:
    """Render a diff entry in side-by-side format.

    For Edit operations: shows old and new text in two columns.
    For Write operations: shows the full file content in a single column.

    Args:
        entry: DiffEntry to render
    """
    if entry.operation == "Edit":
        lang = _detect_language(entry.file_path)
        left_col, right_col = st.columns(2)
        with left_col:
            st.markdown("**Before:**")
            old_display = entry.old_text if entry.old_text else "(empty)"
            st.code(old_display, language=lang)
        with right_col:
            st.markdown("**After:**")
            new_display = entry.new_text if entry.new_text else "(empty)"
            st.code(new_display, language=lang)
    elif entry.operation == "Write":
        st.markdown("**Full file content written:**")
        lang = _detect_language(entry.file_path)
        content = entry.new_text if entry.new_text else "(empty file)"
        if len(content) > 5000:
            st.code(content[:5000], language=lang)
            st.caption(f"Content truncated (showing 5000 of {len(content)} characters)")
        else:
            st.code(content, language=lang)


def _detect_language(file_path: str) -> str:
    """Detect programming language from file extension for syntax highlighting.

    Args:
        file_path: File path to detect language from

    Returns:
        Language string for st.code(), or empty string for unknown
    """
    extension_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".html": "html",
        ".css": "css",
        ".sh": "bash",
        ".bash": "bash",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".rb": "ruby",
        ".toml": "toml",
        ".xml": "xml",
        ".sql": "sql",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
    }

    # Extract extension
    dot_idx = file_path.rfind(".")
    if dot_idx < 0:
        return ""
    ext = file_path[dot_idx:].lower()
    return extension_map.get(ext, "")


def render_diff_viewer(
    file_path: str,
    operations: list[FileOperation],
    git_url: str = "",
    session_key: str = "diff_format",
) -> None:
    """Render the diff viewer panel for a selected file.

    Shows all Edit and Write operations for the file with diff display.
    Includes a toggle between unified and side-by-side formats.

    Args:
        file_path: Path of the selected file
        operations: List of FileOperations for this file
        git_url: Optional git URL for constructing GitHub links
        session_key: Session state key for diff format preference
    """
    entries = _build_diff_entries(operations, file_path)

    if not entries:
        st.info(f"No modifications found for `{file_path}` (read-only file).")
        return

    # File header
    st.markdown(f"### Diffs for `{file_path}`")
    st.caption(f"{len(entries)} modification(s)")

    # Diff format toggle
    diff_format = st.radio(
        "Diff format",
        DIFF_FORMATS,
        horizontal=True,
        key=f"{session_key}_format",
    )

    # GitHub link for the file
    github_url = _build_github_url(git_url, file_path) if git_url else ""

    # Render each diff entry
    for i, entry in enumerate(entries):
        with st.expander(
            f"{entry.operation} #{entry.sequence_number}",
            expanded=i == 0,
        ):
            _render_diff_header(entry, github_url)
            st.markdown("---")
            if diff_format == DIFF_FORMAT_SIDE_BY_SIDE:
                _render_side_by_side_diff(entry)
            else:
                _render_unified_diff(entry)


def render_file_diff_panel(
    selected_file: str,
    file_operations: dict[str, list[FileOperation]],
    git_url: str = "",
    session_key: str = "diff_viewer",
) -> None:
    """Render the file diff panel for the currently selected file.

    This is the main entry point, called from the trace view when a file
    is selected from the file tree.

    Args:
        selected_file: Currently selected file path from session state
        file_operations: Dict mapping file_path -> list of FileOperations
        git_url: Optional git URL for constructing GitHub links
        session_key: Session state key prefix
    """
    if not selected_file:
        st.info("Select a file from the file tree to view its diffs.")
        return

    operations = file_operations.get(selected_file, [])
    render_diff_viewer(
        file_path=selected_file,
        operations=operations,
        git_url=git_url,
        session_key=session_key,
    )
