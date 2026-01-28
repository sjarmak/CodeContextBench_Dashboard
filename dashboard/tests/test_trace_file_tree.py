"""Tests for dashboard.utils.trace_file_tree module."""

from unittest.mock import MagicMock, patch

import pytest

from dashboard.utils.trace_diffs import FileOperation
from dashboard.utils.trace_file_tree import (
    ICON_CREATED,
    ICON_FOLDER,
    ICON_MODIFIED,
    ICON_READ_ONLY,
    FileAccessInfo,
    TreeNode,
    _count_files_in_subtree,
    _dict_to_tree_node,
    _normalize_path,
    build_file_access_map,
    build_tree,
    classify_file_access,
    get_file_icon,
    render_file_tree,
    render_file_tree_node,
)
from src.ingest.trace_viewer_parser import TraceMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_op(
    operation: str,
    file_path: str,
    seq: int,
    old_string: str = "",
    new_string: str = "",
    full_content: str = "",
) -> FileOperation:
    return FileOperation(
        operation=operation,
        file_path=file_path,
        old_string=old_string,
        new_string=new_string,
        full_content=full_content,
        sequence_number=seq,
    )


def _make_trace_msg(
    msg_type: str = "assistant",
    subtype: str = "tool_use",
    tool_name: str = "Read",
    tool_input: dict = None,
    parent_tool_use_id: str = "",
    sequence_number: int = 0,
) -> TraceMessage:
    return TraceMessage(
        type=msg_type,
        subtype=subtype,
        content="",
        tool_name=tool_name,
        tool_input=tool_input,
        tool_result="",
        token_usage=None,
        parent_tool_use_id=parent_tool_use_id,
        session_id="",
        uuid="",
        sequence_number=sequence_number,
    )


# ---------------------------------------------------------------------------
# classify_file_access tests
# ---------------------------------------------------------------------------


class TestClassifyFileAccess:
    def test_read_only(self):
        ops = [_make_op("Read", "/src/main.py", 1)]
        result = classify_file_access(ops)
        assert result.was_read is True
        assert result.was_edited is False
        assert result.was_created is False

    def test_multiple_reads_still_read_only(self):
        ops = [
            _make_op("Read", "/src/main.py", 1),
            _make_op("Read", "/src/main.py", 5),
        ]
        result = classify_file_access(ops)
        assert result.was_read is True
        assert result.was_edited is False
        assert result.was_created is False

    def test_edit_marks_modified(self):
        ops = [
            _make_op("Read", "/src/main.py", 1),
            _make_op("Edit", "/src/main.py", 2, "old", "new"),
        ]
        result = classify_file_access(ops)
        assert result.was_read is False
        assert result.was_edited is True
        assert result.was_created is False

    def test_write_after_read_marks_modified(self):
        ops = [
            _make_op("Read", "/src/main.py", 1),
            _make_op("Write", "/src/main.py", 2, full_content="content"),
        ]
        result = classify_file_access(ops)
        assert result.was_read is False
        assert result.was_edited is True
        assert result.was_created is False

    def test_write_without_read_marks_created(self):
        ops = [
            _make_op("Write", "/src/new_file.py", 1, full_content="content"),
        ]
        result = classify_file_access(ops)
        assert result.was_read is False
        assert result.was_edited is False
        assert result.was_created is True

    def test_write_before_read_marks_created(self):
        ops = [
            _make_op("Write", "/src/new_file.py", 1, full_content="content"),
            _make_op("Read", "/src/new_file.py", 5),
        ]
        result = classify_file_access(ops)
        assert result.was_created is True

    def test_edit_only_marks_modified(self):
        ops = [
            _make_op("Edit", "/src/main.py", 1, "old", "new"),
        ]
        result = classify_file_access(ops)
        assert result.was_edited is True
        assert result.was_created is False
        assert result.was_read is False

    def test_file_path_from_first_operation(self):
        ops = [_make_op("Read", "/src/main.py", 1)]
        result = classify_file_access(ops)
        assert result.file_path == "/src/main.py"

    def test_empty_ops_returns_empty_path(self):
        result = classify_file_access([])
        assert result.file_path == ""


# ---------------------------------------------------------------------------
# get_file_icon tests
# ---------------------------------------------------------------------------


class TestGetFileIcon:
    def test_read_only_gets_eye(self):
        info = FileAccessInfo("/f", was_read=True, was_edited=False, was_created=False)
        assert get_file_icon(info) == ICON_READ_ONLY

    def test_modified_gets_pencil(self):
        info = FileAccessInfo("/f", was_read=False, was_edited=True, was_created=False)
        assert get_file_icon(info) == ICON_MODIFIED

    def test_created_gets_plus(self):
        info = FileAccessInfo("/f", was_read=False, was_edited=False, was_created=True)
        assert get_file_icon(info) == ICON_CREATED

    def test_created_takes_priority_over_modified(self):
        info = FileAccessInfo("/f", was_read=False, was_edited=True, was_created=True)
        assert get_file_icon(info) == ICON_CREATED

    def test_modified_takes_priority_over_read(self):
        info = FileAccessInfo("/f", was_read=True, was_edited=True, was_created=False)
        assert get_file_icon(info) == ICON_MODIFIED


# ---------------------------------------------------------------------------
# _normalize_path tests
# ---------------------------------------------------------------------------


class TestNormalizePath:
    def test_absolute_path(self):
        assert _normalize_path("/src/main.py") == ["src", "main.py"]

    def test_relative_path(self):
        assert _normalize_path("src/main.py") == ["src", "main.py"]

    def test_deeply_nested(self):
        assert _normalize_path("/a/b/c/d.py") == ["a", "b", "c", "d.py"]

    def test_single_file(self):
        assert _normalize_path("file.py") == ["file.py"]

    def test_leading_slashes_stripped(self):
        assert _normalize_path("///src/main.py") == ["src", "main.py"]

    def test_empty_segments_removed(self):
        assert _normalize_path("/src//main.py") == ["src", "main.py"]

    def test_empty_string(self):
        assert _normalize_path("") == []


# ---------------------------------------------------------------------------
# build_tree tests
# ---------------------------------------------------------------------------


class TestBuildTree:
    def test_single_file(self):
        access_map = {
            "/src/main.py": FileAccessInfo("/src/main.py", True, False, False),
        }
        tree = build_tree(access_map)
        assert tree.is_directory is True
        assert len(tree.children) == 1
        src_node = tree.children[0]
        assert src_node.name == "src"
        assert src_node.is_directory is True
        assert len(src_node.children) == 1
        file_node = src_node.children[0]
        assert file_node.name == "main.py"
        assert file_node.is_directory is False
        assert file_node.access_info is not None
        assert file_node.access_info.was_read is True

    def test_multiple_files_same_directory(self):
        access_map = {
            "/src/a.py": FileAccessInfo("/src/a.py", True, False, False),
            "/src/b.py": FileAccessInfo("/src/b.py", False, True, False),
        }
        tree = build_tree(access_map)
        src_node = tree.children[0]
        assert len(src_node.children) == 2
        assert src_node.children[0].name == "a.py"
        assert src_node.children[1].name == "b.py"

    def test_nested_directories(self):
        access_map = {
            "/src/utils/helper.py": FileAccessInfo(
                "/src/utils/helper.py", True, False, False
            ),
        }
        tree = build_tree(access_map)
        src = tree.children[0]
        assert src.name == "src"
        utils = src.children[0]
        assert utils.name == "utils"
        helper = utils.children[0]
        assert helper.name == "helper.py"

    def test_directories_sorted_before_files(self):
        access_map = {
            "/src/z_file.py": FileAccessInfo("/src/z_file.py", True, False, False),
            "/src/a_dir/x.py": FileAccessInfo(
                "/src/a_dir/x.py", True, False, False
            ),
        }
        tree = build_tree(access_map)
        src = tree.children[0]
        # a_dir (directory) should come before z_file.py (file)
        assert src.children[0].name == "a_dir"
        assert src.children[0].is_directory is True
        assert src.children[1].name == "z_file.py"
        assert src.children[1].is_directory is False

    def test_empty_access_map(self):
        tree = build_tree({})
        assert tree.is_directory is False  # root with no children
        assert len(tree.children) == 0

    def test_files_in_different_top_level_dirs(self):
        access_map = {
            "/src/main.py": FileAccessInfo("/src/main.py", True, False, False),
            "/tests/test_main.py": FileAccessInfo(
                "/tests/test_main.py", True, False, False
            ),
        }
        tree = build_tree(access_map)
        assert len(tree.children) == 2
        names = [c.name for c in tree.children]
        assert "src" in names
        assert "tests" in names

    def test_full_path_preserved_for_files(self):
        access_map = {
            "/src/main.py": FileAccessInfo("/src/main.py", True, False, False),
        }
        tree = build_tree(access_map)
        file_node = tree.children[0].children[0]
        assert file_node.full_path == "/src/main.py"


# ---------------------------------------------------------------------------
# _count_files_in_subtree tests
# ---------------------------------------------------------------------------


class TestCountFilesInSubtree:
    def test_single_file(self):
        node = TreeNode("f.py", "/f.py", False, None, ())
        assert _count_files_in_subtree(node) == 1

    def test_directory_with_files(self):
        file1 = TreeNode("a.py", "/src/a.py", False, None, ())
        file2 = TreeNode("b.py", "/src/b.py", False, None, ())
        dir_node = TreeNode("src", "src", True, None, (file1, file2))
        assert _count_files_in_subtree(dir_node) == 2

    def test_nested_directories(self):
        f1 = TreeNode("x.py", "/a/b/x.py", False, None, ())
        b = TreeNode("b", "a/b", True, None, (f1,))
        f2 = TreeNode("y.py", "/a/y.py", False, None, ())
        a = TreeNode("a", "a", True, None, (b, f2))
        assert _count_files_in_subtree(a) == 2

    def test_empty_directory(self):
        dir_node = TreeNode("empty", "empty", True, None, ())
        assert _count_files_in_subtree(dir_node) == 0


# ---------------------------------------------------------------------------
# _dict_to_tree_node tests
# ---------------------------------------------------------------------------


class TestDictToTreeNode:
    def test_leaf_node(self):
        d = {
            "name": "file.py",
            "children": {},
            "access_info": None,
            "full_path": "/file.py",
        }
        node = _dict_to_tree_node(d)
        assert node.name == "file.py"
        assert node.is_directory is False
        assert len(node.children) == 0

    def test_directory_node(self):
        d = {
            "name": "src",
            "children": {
                "main.py": {
                    "name": "main.py",
                    "children": {},
                    "access_info": None,
                    "full_path": "/src/main.py",
                }
            },
            "access_info": None,
            "full_path": "src",
        }
        node = _dict_to_tree_node(d)
        assert node.is_directory is True
        assert len(node.children) == 1
        assert node.children[0].name == "main.py"

    def test_children_sorted_dirs_first(self):
        d = {
            "name": "root",
            "children": {
                "z.py": {
                    "name": "z.py",
                    "children": {},
                    "access_info": None,
                    "full_path": "/z.py",
                },
                "a_dir": {
                    "name": "a_dir",
                    "children": {
                        "x.py": {
                            "name": "x.py",
                            "children": {},
                            "access_info": None,
                            "full_path": "/a_dir/x.py",
                        }
                    },
                    "access_info": None,
                    "full_path": "a_dir",
                },
            },
            "access_info": None,
            "full_path": "",
        }
        node = _dict_to_tree_node(d)
        assert node.children[0].name == "a_dir"
        assert node.children[1].name == "z.py"


# ---------------------------------------------------------------------------
# build_file_access_map tests
# ---------------------------------------------------------------------------


class TestBuildFileAccessMap:
    @patch("dashboard.utils.trace_file_tree.extract_file_operations")
    def test_builds_map_from_operations(self, mock_extract):
        mock_extract.return_value = {
            "/src/main.py": [_make_op("Read", "/src/main.py", 1)],
            "/src/new.py": [
                _make_op("Write", "/src/new.py", 2, full_content="content")
            ],
        }
        result = build_file_access_map([])
        assert "/src/main.py" in result
        assert "/src/new.py" in result
        assert result["/src/main.py"].was_read is True
        assert result["/src/new.py"].was_created is True

    @patch("dashboard.utils.trace_file_tree.extract_file_operations")
    def test_empty_operations(self, mock_extract):
        mock_extract.return_value = {}
        result = build_file_access_map([])
        assert result == {}


# ---------------------------------------------------------------------------
# render_file_tree_node tests (UI rendering)
# ---------------------------------------------------------------------------


class TestRenderFileTreeNode:
    @patch("dashboard.utils.trace_file_tree.st")
    def test_renders_directory_with_expander(self, mock_st):
        child = TreeNode(
            "main.py",
            "/src/main.py",
            False,
            FileAccessInfo("/src/main.py", True, False, False),
            (),
        )
        node = TreeNode("src", "src", True, None, (child,))

        mock_expander = MagicMock()
        mock_st.expander.return_value.__enter__ = MagicMock(
            return_value=mock_expander
        )
        mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)
        mock_st.session_state = {}

        render_file_tree_node(node, "selected_file", 0)
        mock_st.expander.assert_called_once()
        call_args = mock_st.expander.call_args
        label = call_args[0][0]
        assert "src" in label
        assert "(1)" in label

    @patch("dashboard.utils.trace_file_tree.st")
    def test_renders_file_as_button(self, mock_st):
        access = FileAccessInfo("/src/main.py", True, False, False)
        node = TreeNode("main.py", "/src/main.py", False, access, ())

        mock_st.session_state = {}
        mock_st.button.return_value = False

        render_file_tree_node(node, "selected_file", 0)
        mock_st.button.assert_called_once()
        button_label = mock_st.button.call_args[0][0]
        assert "main.py" in button_label
        assert ICON_READ_ONLY in button_label

    @patch("dashboard.utils.trace_file_tree.st")
    def test_selected_file_highlighted(self, mock_st):
        access = FileAccessInfo("/src/main.py", True, False, False)
        node = TreeNode("main.py", "/src/main.py", False, access, ())

        mock_st.session_state = {"selected_file": "/src/main.py"}

        render_file_tree_node(node, "selected_file", 0)
        mock_st.markdown.assert_called_once()
        html_arg = mock_st.markdown.call_args[0][0]
        assert "e0e7ff" in html_arg
        assert "main.py" in html_arg

    @patch("dashboard.utils.trace_file_tree.st")
    def test_root_node_renders_children_directly(self, mock_st):
        child = TreeNode(
            "main.py",
            "/main.py",
            False,
            FileAccessInfo("/main.py", True, False, False),
            (),
        )
        root = TreeNode("", "", True, None, (child,))

        mock_st.session_state = {}
        mock_st.button.return_value = False

        render_file_tree_node(root, "selected_file", 0)
        # Should NOT create expander for root
        mock_st.expander.assert_not_called()
        # Should render the child file button
        mock_st.button.assert_called_once()

    @patch("dashboard.utils.trace_file_tree.st")
    def test_clicking_file_sets_session_state(self, mock_st):
        access = FileAccessInfo("/src/main.py", True, False, False)
        node = TreeNode("main.py", "/src/main.py", False, access, ())

        mock_st.session_state = {}
        mock_st.button.return_value = True

        render_file_tree_node(node, "selected_file", 0)
        assert mock_st.session_state["selected_file"] == "/src/main.py"
        mock_st.rerun.assert_called_once()


# ---------------------------------------------------------------------------
# render_file_tree tests (full component)
# ---------------------------------------------------------------------------


class TestRenderFileTree:
    @patch("dashboard.utils.trace_file_tree.render_file_tree_node")
    @patch("dashboard.utils.trace_file_tree.build_tree")
    @patch("dashboard.utils.trace_file_tree.build_file_access_map")
    @patch("dashboard.utils.trace_file_tree.st")
    def test_renders_tree_with_summary(
        self, mock_st, mock_build_map, mock_build_tree, mock_render_node
    ):
        mock_build_map.return_value = {
            "/src/main.py": FileAccessInfo("/src/main.py", True, False, False),
            "/src/new.py": FileAccessInfo("/src/new.py", False, False, True),
            "/src/edited.py": FileAccessInfo(
                "/src/edited.py", False, True, False
            ),
        }
        mock_tree = MagicMock()
        mock_build_tree.return_value = mock_tree

        render_file_tree([], "selected_file")

        mock_st.markdown.assert_called_once_with("### Files Accessed")
        mock_st.caption.assert_called_once()
        caption_text = mock_st.caption.call_args[0][0]
        assert "Read: 1" in caption_text
        assert "Modified: 1" in caption_text
        assert "Created: 1" in caption_text
        mock_render_node.assert_called_once_with(mock_tree, "selected_file")

    @patch("dashboard.utils.trace_file_tree.build_file_access_map")
    @patch("dashboard.utils.trace_file_tree.st")
    def test_empty_trace_shows_info(self, mock_st, mock_build_map):
        mock_build_map.return_value = {}
        render_file_tree([], "selected_file")
        mock_st.info.assert_called_once_with(
            "No file operations found in this trace."
        )

    @patch("dashboard.utils.trace_file_tree.render_file_tree_node")
    @patch("dashboard.utils.trace_file_tree.build_tree")
    @patch("dashboard.utils.trace_file_tree.build_file_access_map")
    @patch("dashboard.utils.trace_file_tree.st")
    def test_only_read_shows_read_legend(
        self, mock_st, mock_build_map, mock_build_tree, mock_render_node
    ):
        mock_build_map.return_value = {
            "/src/main.py": FileAccessInfo("/src/main.py", True, False, False),
        }
        mock_build_tree.return_value = MagicMock()

        render_file_tree([], "selected_file")

        caption_text = mock_st.caption.call_args[0][0]
        assert "Read: 1" in caption_text
        assert "Modified" not in caption_text
        assert "Created" not in caption_text


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestIntegration:
    @patch("dashboard.utils.trace_file_tree.extract_file_operations")
    def test_full_pipeline_from_operations(self, mock_extract):
        """Test building access map -> tree from realistic operations."""
        mock_extract.return_value = {
            "/workspace/src/main.py": [
                _make_op("Read", "/workspace/src/main.py", 1),
                _make_op("Edit", "/workspace/src/main.py", 5, "old", "new"),
            ],
            "/workspace/src/utils/helper.py": [
                _make_op("Read", "/workspace/src/utils/helper.py", 2),
            ],
            "/workspace/tests/test_main.py": [
                _make_op(
                    "Write",
                    "/workspace/tests/test_main.py",
                    3,
                    full_content="test content",
                ),
            ],
            "/workspace/README.md": [
                _make_op("Read", "/workspace/README.md", 4),
                _make_op(
                    "Write",
                    "/workspace/README.md",
                    6,
                    full_content="updated readme",
                ),
            ],
        }

        access_map = build_file_access_map([])

        # Check classifications
        assert access_map["/workspace/src/main.py"].was_edited is True
        assert access_map["/workspace/src/utils/helper.py"].was_read is True
        assert access_map["/workspace/tests/test_main.py"].was_created is True
        assert access_map["/workspace/README.md"].was_edited is True

        # Build tree
        tree = build_tree(access_map)

        # Root should have one child: workspace
        assert len(tree.children) == 1
        workspace = tree.children[0]
        assert workspace.name == "workspace"
        assert workspace.is_directory is True

        # workspace should have: src (dir), tests (dir), README.md (file)
        child_names = [c.name for c in workspace.children]
        assert "src" in child_names
        assert "tests" in child_names
        assert "README.md" in child_names

    def test_classify_complex_scenario(self):
        """Test classification with Read -> Write -> Read sequence."""
        ops = [
            _make_op("Read", "/f.py", 1),
            _make_op("Write", "/f.py", 2, full_content="v2"),
            _make_op("Read", "/f.py", 3),
        ]
        result = classify_file_access(ops)
        # Read first, then Write = modified (not created)
        assert result.was_edited is True
        assert result.was_created is False
