"""Tests for dashboard.utils.trace_diff_viewer module."""

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from dashboard.utils.trace_diff_viewer import (
    DIFF_FORMAT_SIDE_BY_SIDE,
    DIFF_FORMAT_UNIFIED,
    DIFF_FORMATS,
    DiffEntry,
    _build_diff_entries,
    _build_github_url,
    _detect_language,
    _generate_unified_diff,
    _render_diff_header,
    _render_side_by_side_diff,
    _render_unified_diff,
    render_diff_viewer,
    render_file_diff_panel,
)
from dashboard.utils.trace_diffs import FileOperation


# === Test _generate_unified_diff ===


class TestGenerateUnifiedDiff:
    """Tests for unified diff generation."""

    def test_basic_edit(self):
        """Generates diff for a simple text change."""
        result = _generate_unified_diff(
            "hello world",
            "hello universe",
            "test.py",
        )
        assert "--- a/test.py" in result
        assert "+++ b/test.py" in result
        assert "-hello world" in result
        assert "+hello universe" in result

    def test_multiline_edit(self):
        """Generates diff for multiline text changes."""
        old = "line1\nline2\nline3"
        new = "line1\nmodified\nline3"
        result = _generate_unified_diff(old, new, "src/main.py")
        assert "-line2" in result
        assert "+modified" in result

    def test_identical_text(self):
        """Returns empty string for identical old and new text."""
        result = _generate_unified_diff("same", "same", "test.py")
        assert result == ""

    def test_empty_old_text(self):
        """Generates diff when old text is empty (addition)."""
        result = _generate_unified_diff("", "new content", "test.py")
        assert "+new content" in result

    def test_empty_new_text(self):
        """Generates diff when new text is empty (deletion)."""
        result = _generate_unified_diff("old content", "", "test.py")
        assert "-old content" in result

    def test_both_empty(self):
        """Returns empty string when both texts are empty."""
        result = _generate_unified_diff("", "", "test.py")
        assert result == ""


# === Test _build_diff_entries ===


class TestBuildDiffEntries:
    """Tests for building diff entries from file operations."""

    def test_edit_operation(self):
        """Creates DiffEntry for an Edit operation."""
        ops = [
            FileOperation(
                operation="Edit",
                file_path="/src/main.py",
                old_string="old",
                new_string="new",
                full_content="",
                sequence_number=5,
            )
        ]
        entries = _build_diff_entries(ops, "/src/main.py")
        assert len(entries) == 1
        assert entries[0].operation == "Edit"
        assert entries[0].sequence_number == 5
        assert entries[0].old_text == "old"
        assert entries[0].new_text == "new"
        assert entries[0].unified_diff != ""

    def test_write_operation(self):
        """Creates DiffEntry for a Write operation."""
        ops = [
            FileOperation(
                operation="Write",
                file_path="/src/new_file.py",
                old_string="",
                new_string="",
                full_content="print('hello')",
                sequence_number=10,
            )
        ]
        entries = _build_diff_entries(ops, "/src/new_file.py")
        assert len(entries) == 1
        assert entries[0].operation == "Write"
        assert entries[0].sequence_number == 10
        assert entries[0].new_text == "print('hello')"
        assert entries[0].unified_diff == ""

    def test_read_operation_skipped(self):
        """Read operations are not included in diff entries."""
        ops = [
            FileOperation(
                operation="Read",
                file_path="/src/main.py",
                old_string="",
                new_string="",
                full_content="contents",
                sequence_number=1,
            )
        ]
        entries = _build_diff_entries(ops, "/src/main.py")
        assert len(entries) == 0

    def test_multiple_operations(self):
        """Builds entries for multiple operations in sequence order."""
        ops = [
            FileOperation(
                operation="Read",
                file_path="/src/main.py",
                old_string="",
                new_string="",
                full_content="original",
                sequence_number=1,
            ),
            FileOperation(
                operation="Edit",
                file_path="/src/main.py",
                old_string="original",
                new_string="modified",
                full_content="",
                sequence_number=5,
            ),
            FileOperation(
                operation="Edit",
                file_path="/src/main.py",
                old_string="modified",
                new_string="final",
                full_content="",
                sequence_number=10,
            ),
        ]
        entries = _build_diff_entries(ops, "/src/main.py")
        assert len(entries) == 2
        assert entries[0].sequence_number == 5
        assert entries[1].sequence_number == 10

    def test_empty_operations(self):
        """Returns empty list for no operations."""
        entries = _build_diff_entries([], "/src/main.py")
        assert entries == []


# === Test _build_github_url ===


class TestBuildGithubUrl:
    """Tests for GitHub URL construction."""

    def test_https_url(self):
        """Constructs URL from HTTPS git URL."""
        url = _build_github_url(
            "https://github.com/org/repo.git",
            "src/main.py",
        )
        assert url == "https://github.com/org/repo/blob/main/src/main.py"

    def test_ssh_url(self):
        """Constructs URL from SSH git URL."""
        url = _build_github_url(
            "git@github.com:org/repo.git",
            "src/main.py",
        )
        assert url == "https://github.com/org/repo/blob/main/src/main.py"

    def test_url_without_git_suffix(self):
        """Handles URL without .git suffix."""
        url = _build_github_url(
            "https://github.com/org/repo",
            "src/main.py",
        )
        assert url == "https://github.com/org/repo/blob/main/src/main.py"

    def test_leading_slash_stripped(self):
        """Strips leading slash from file path."""
        url = _build_github_url(
            "https://github.com/org/repo.git",
            "/src/main.py",
        )
        assert url == "https://github.com/org/repo/blob/main/src/main.py"

    def test_empty_git_url(self):
        """Returns empty string for empty git URL."""
        url = _build_github_url("", "src/main.py")
        assert url == ""

    def test_empty_file_path(self):
        """Handles empty file path."""
        url = _build_github_url(
            "https://github.com/org/repo.git",
            "",
        )
        assert url == "https://github.com/org/repo/blob/main/"

    def test_deep_nested_path(self):
        """Handles deeply nested file paths."""
        url = _build_github_url(
            "https://github.com/org/repo.git",
            "src/components/ui/Button.tsx",
        )
        assert url == "https://github.com/org/repo/blob/main/src/components/ui/Button.tsx"


# === Test _detect_language ===


class TestDetectLanguage:
    """Tests for file language detection."""

    def test_python(self):
        assert _detect_language("main.py") == "python"

    def test_javascript(self):
        assert _detect_language("app.js") == "javascript"

    def test_typescript(self):
        assert _detect_language("index.ts") == "typescript"

    def test_tsx(self):
        assert _detect_language("Component.tsx") == "typescript"

    def test_json(self):
        assert _detect_language("config.json") == "json"

    def test_yaml(self):
        assert _detect_language("config.yaml") == "yaml"

    def test_yml(self):
        assert _detect_language("config.yml") == "yaml"

    def test_rust(self):
        assert _detect_language("main.rs") == "rust"

    def test_go(self):
        assert _detect_language("main.go") == "go"

    def test_bash(self):
        assert _detect_language("script.sh") == "bash"

    def test_unknown_extension(self):
        assert _detect_language("file.xyz") == ""

    def test_no_extension(self):
        assert _detect_language("Makefile") == ""

    def test_case_insensitive(self):
        assert _detect_language("Main.PY") == "python"

    def test_full_path(self):
        assert _detect_language("/src/components/App.tsx") == "typescript"

    def test_html(self):
        assert _detect_language("index.html") == "html"

    def test_css(self):
        assert _detect_language("styles.css") == "css"


# === Test DiffEntry dataclass ===


class TestDiffEntry:
    """Tests for DiffEntry frozen dataclass."""

    def test_creation(self):
        entry = DiffEntry(
            sequence_number=1,
            operation="Edit",
            file_path="test.py",
            unified_diff="diff content",
            old_text="old",
            new_text="new",
        )
        assert entry.sequence_number == 1
        assert entry.operation == "Edit"
        assert entry.file_path == "test.py"

    def test_frozen(self):
        entry = DiffEntry(
            sequence_number=1,
            operation="Edit",
            file_path="test.py",
            unified_diff="",
            old_text="",
            new_text="",
        )
        with pytest.raises(AttributeError):
            entry.operation = "Write"  # type: ignore[misc]


# === Test render functions (mocked Streamlit) ===


class TestRenderDiffHeader:
    """Tests for diff header rendering."""

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_edit_header_without_github(self, mock_st):
        entry = DiffEntry(
            sequence_number=5,
            operation="Edit",
            file_path="test.py",
            unified_diff="",
            old_text="",
            new_text="",
        )
        _render_diff_header(entry, "")
        mock_st.markdown.assert_called_once()
        call_html = mock_st.markdown.call_args[0][0]
        assert "Edit" in call_html
        assert "#5" in call_html
        assert "GitHub" not in call_html

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_header_with_github_link(self, mock_st):
        entry = DiffEntry(
            sequence_number=3,
            operation="Write",
            file_path="test.py",
            unified_diff="",
            old_text="",
            new_text="",
        )
        _render_diff_header(entry, "https://github.com/org/repo/blob/main/test.py")
        call_html = mock_st.markdown.call_args[0][0]
        assert "GitHub" in call_html
        assert "https://github.com/org/repo/blob/main/test.py" in call_html

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_edit_badge_color(self, mock_st):
        entry = DiffEntry(
            sequence_number=1,
            operation="Edit",
            file_path="test.py",
            unified_diff="",
            old_text="",
            new_text="",
        )
        _render_diff_header(entry, "")
        call_html = mock_st.markdown.call_args[0][0]
        assert "#3b82f6" in call_html  # blue for Edit

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_write_badge_color(self, mock_st):
        entry = DiffEntry(
            sequence_number=1,
            operation="Write",
            file_path="test.py",
            unified_diff="",
            old_text="",
            new_text="",
        )
        _render_diff_header(entry, "")
        call_html = mock_st.markdown.call_args[0][0]
        assert "#22c55e" in call_html  # green for Write


class TestRenderUnifiedDiff:
    """Tests for unified diff rendering."""

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_edit_with_diff(self, mock_st):
        entry = DiffEntry(
            sequence_number=1,
            operation="Edit",
            file_path="test.py",
            unified_diff="--- a/test.py\n+++ b/test.py\n-old\n+new",
            old_text="old",
            new_text="new",
        )
        _render_unified_diff(entry)
        mock_st.code.assert_called_once()
        code_args = mock_st.code.call_args
        assert "--- a/test.py" in code_args[0][0]
        assert code_args[1]["language"] == "diff"

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_edit_no_changes(self, mock_st):
        entry = DiffEntry(
            sequence_number=1,
            operation="Edit",
            file_path="test.py",
            unified_diff="",
            old_text="same",
            new_text="same",
        )
        _render_unified_diff(entry)
        mock_st.info.assert_called_once()

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_write_full_content(self, mock_st):
        entry = DiffEntry(
            sequence_number=1,
            operation="Write",
            file_path="test.py",
            unified_diff="",
            old_text="",
            new_text="print('hello')",
        )
        _render_unified_diff(entry)
        mock_st.markdown.assert_called_once_with("**Full file content written:**")
        mock_st.code.assert_called_once()

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_write_empty_file(self, mock_st):
        entry = DiffEntry(
            sequence_number=1,
            operation="Write",
            file_path="test.py",
            unified_diff="",
            old_text="",
            new_text="",
        )
        _render_unified_diff(entry)
        mock_st.code.assert_called_once()
        assert "(empty file)" in mock_st.code.call_args[0][0]

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_write_large_content_truncated(self, mock_st):
        entry = DiffEntry(
            sequence_number=1,
            operation="Write",
            file_path="test.py",
            unified_diff="",
            old_text="",
            new_text="x" * 6000,
        )
        _render_unified_diff(entry)
        mock_st.code.assert_called_once()
        # Content should be truncated to 5000
        assert len(mock_st.code.call_args[0][0]) == 5000
        mock_st.caption.assert_called_once()


class TestRenderSideBySideDiff:
    """Tests for side-by-side diff rendering."""

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_edit_two_columns(self, mock_st):
        entry = DiffEntry(
            sequence_number=1,
            operation="Edit",
            file_path="test.py",
            unified_diff="",
            old_text="old code",
            new_text="new code",
        )
        # Mock st.columns to return context managers
        mock_col1 = mock.MagicMock()
        mock_col2 = mock.MagicMock()
        mock_st.columns.return_value = (mock_col1, mock_col2)

        _render_side_by_side_diff(entry)
        mock_st.columns.assert_called_once_with(2)

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_write_single_display(self, mock_st):
        entry = DiffEntry(
            sequence_number=1,
            operation="Write",
            file_path="test.py",
            unified_diff="",
            old_text="",
            new_text="new content",
        )
        _render_side_by_side_diff(entry)
        mock_st.markdown.assert_called_with("**Full file content written:**")


# === Test render_diff_viewer ===


class TestRenderDiffViewer:
    """Tests for the main diff viewer component."""

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_no_modifications(self, mock_st):
        """Shows info message for read-only files."""
        ops = [
            FileOperation(
                operation="Read",
                file_path="/src/main.py",
                old_string="",
                new_string="",
                full_content="contents",
                sequence_number=1,
            )
        ]
        render_diff_viewer("/src/main.py", ops)
        mock_st.info.assert_called_once()
        assert "read-only" in mock_st.info.call_args[0][0]

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_renders_header_and_format_toggle(self, mock_st):
        """Renders file header, count, and format toggle."""
        mock_st.radio.return_value = DIFF_FORMAT_UNIFIED
        mock_st.expander.return_value.__enter__ = mock.Mock(return_value=None)
        mock_st.expander.return_value.__exit__ = mock.Mock(return_value=None)

        ops = [
            FileOperation(
                operation="Edit",
                file_path="/src/main.py",
                old_string="old",
                new_string="new",
                full_content="",
                sequence_number=5,
            )
        ]
        render_diff_viewer("/src/main.py", ops, session_key="test_diff")

        # Check header
        mock_st.markdown.assert_any_call("### Diffs for `/src/main.py`")
        mock_st.caption.assert_any_call("1 modification(s)")

        # Check format radio
        mock_st.radio.assert_called_once_with(
            "Diff format",
            DIFF_FORMATS,
            horizontal=True,
            key="test_diff_format",
        )


# === Test render_file_diff_panel ===


class TestRenderFileDiffPanel:
    """Tests for the main entry point."""

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_no_file_selected(self, mock_st):
        """Shows info message when no file is selected."""
        render_file_diff_panel("", {})
        mock_st.info.assert_called_once()
        assert "Select a file" in mock_st.info.call_args[0][0]

    @mock.patch("dashboard.utils.trace_diff_viewer.st")
    def test_file_not_in_operations(self, mock_st):
        """Shows info message when selected file has no operations."""
        render_file_diff_panel("/missing.py", {})
        mock_st.info.assert_called_once()

    @mock.patch("dashboard.utils.trace_diff_viewer.render_diff_viewer")
    def test_delegates_to_render_diff_viewer(self, mock_render):
        """Delegates to render_diff_viewer with correct args."""
        ops = {
            "/src/main.py": [
                FileOperation(
                    operation="Edit",
                    file_path="/src/main.py",
                    old_string="old",
                    new_string="new",
                    full_content="",
                    sequence_number=5,
                )
            ]
        }
        render_file_diff_panel(
            "/src/main.py",
            ops,
            git_url="https://github.com/org/repo.git",
            session_key="test",
        )
        mock_render.assert_called_once_with(
            file_path="/src/main.py",
            operations=ops["/src/main.py"],
            git_url="https://github.com/org/repo.git",
            session_key="test",
        )


# === Test _extract_git_url_from_trace_context ===


class TestExtractGitUrlFromTraceContext:
    """Tests for git URL extraction from task config."""

    def test_extracts_git_url(self):
        """Extracts git_url from config.json."""
        from dashboard.views.run_results import _extract_git_url_from_trace_context

        with tempfile.TemporaryDirectory() as tmpdir:
            instance_dir = Path(tmpdir)
            agent_dir = instance_dir / "agent"
            agent_dir.mkdir()
            claude_file = agent_dir / "claude-code.txt"
            claude_file.touch()

            config = {"task": {"git_url": "https://github.com/org/repo.git"}}
            config_path = instance_dir / "config.json"
            config_path.write_text(json.dumps(config))

            result = _extract_git_url_from_trace_context(claude_file)
            assert result == "https://github.com/org/repo.git"

    def test_no_config_file(self):
        """Returns empty string when config.json doesn't exist."""
        from dashboard.views.run_results import _extract_git_url_from_trace_context

        with tempfile.TemporaryDirectory() as tmpdir:
            instance_dir = Path(tmpdir)
            agent_dir = instance_dir / "agent"
            agent_dir.mkdir()
            claude_file = agent_dir / "claude-code.txt"
            claude_file.touch()

            result = _extract_git_url_from_trace_context(claude_file)
            assert result == ""

    def test_no_git_url_in_config(self):
        """Returns empty string when config has no git_url."""
        from dashboard.views.run_results import _extract_git_url_from_trace_context

        with tempfile.TemporaryDirectory() as tmpdir:
            instance_dir = Path(tmpdir)
            agent_dir = instance_dir / "agent"
            agent_dir.mkdir()
            claude_file = agent_dir / "claude-code.txt"
            claude_file.touch()

            config = {"task": {"path": "/some/path"}}
            config_path = instance_dir / "config.json"
            config_path.write_text(json.dumps(config))

            result = _extract_git_url_from_trace_context(claude_file)
            assert result == ""

    def test_malformed_json(self):
        """Returns empty string for malformed config.json."""
        from dashboard.views.run_results import _extract_git_url_from_trace_context

        with tempfile.TemporaryDirectory() as tmpdir:
            instance_dir = Path(tmpdir)
            agent_dir = instance_dir / "agent"
            agent_dir.mkdir()
            claude_file = agent_dir / "claude-code.txt"
            claude_file.touch()

            config_path = instance_dir / "config.json"
            config_path.write_text("not valid json")

            result = _extract_git_url_from_trace_context(claude_file)
            assert result == ""


# === Test constants ===


class TestConstants:
    """Tests for module constants."""

    def test_diff_formats(self):
        assert DIFF_FORMAT_UNIFIED in DIFF_FORMATS
        assert DIFF_FORMAT_SIDE_BY_SIDE in DIFF_FORMATS
        assert len(DIFF_FORMATS) == 2
