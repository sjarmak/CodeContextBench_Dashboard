"""
Tests for the trace summary overview panel.

Tests the rendering helper functions and data transformation logic
in dashboard/utils/trace_summary.py, plus the _build_file_access_from_trace
helper in run_results.py.
"""

from unittest.mock import MagicMock, patch

from src.ingest.trace_viewer_parser import TraceSummary


# --- Tests for _build_file_access_from_trace ---


class TestBuildFileAccessFromTrace:
    """Tests for the file access dict builder used in run_results.py."""

    def _build(
        self,
        files_read: list[str] | None = None,
        edits_made: list[dict] | None = None,
    ) -> dict[str, dict[str, int]]:
        # Import at call time to avoid Streamlit import issues
        from dashboard.views.run_results import _build_file_access_from_trace

        return _build_file_access_from_trace(
            files_read=files_read or [],
            edits_made=edits_made or [],
        )

    def test_empty_inputs(self) -> None:
        result = self._build()
        assert result == {}

    def test_reads_only(self) -> None:
        result = self._build(files_read=["/a.py", "/b.py", "/a.py"])
        assert result["/a.py"]["read_count"] == 2
        assert result["/a.py"]["write_count"] == 0
        assert result["/a.py"]["edit_count"] == 0
        assert result["/b.py"]["read_count"] == 1

    def test_edits_only(self) -> None:
        result = self._build(
            edits_made=[
                {"file": "/a.py", "old": "x", "new": "y"},
                {"file": "/a.py", "old": "a", "new": "b"},
            ]
        )
        assert result["/a.py"]["edit_count"] == 2
        assert result["/a.py"]["read_count"] == 0

    def test_mixed_reads_and_edits(self) -> None:
        result = self._build(
            files_read=["/a.py", "/a.py", "/b.py"],
            edits_made=[{"file": "/a.py", "old": "x", "new": "y"}],
        )
        assert result["/a.py"]["read_count"] == 2
        assert result["/a.py"]["edit_count"] == 1
        assert result["/b.py"]["read_count"] == 1

    def test_sorted_by_total_access_descending(self) -> None:
        result = self._build(
            files_read=["/b.py", "/a.py", "/a.py", "/a.py"],
        )
        keys = list(result.keys())
        assert keys[0] == "/a.py"
        assert keys[1] == "/b.py"

    def test_empty_file_path_in_edit_skipped(self) -> None:
        result = self._build(
            edits_made=[{"file": "", "old": "x", "new": "y"}],
        )
        assert result == {}

    def test_missing_file_key_in_edit_skipped(self) -> None:
        result = self._build(
            edits_made=[{"old": "x", "new": "y"}],
        )
        assert result == {}


# --- Tests for trace_summary module functions ---


class TestRenderMetricCards:
    """Tests for _render_metric_cards via mocked Streamlit."""

    @patch("dashboard.utils.trace_summary.st")
    def test_renders_five_columns(self, mock_st: MagicMock) -> None:
        from dashboard.utils.trace_summary import _render_metric_cards

        mock_cols = [MagicMock() for _ in range(5)]
        mock_st.columns.return_value = mock_cols

        summary = TraceSummary(
            total_messages=100,
            total_tool_calls=50,
            unique_tools=8,
            total_tokens=25000,
            tools_by_name={"Read": 20, "Bash": 15},
            files_accessed={},
        )

        _render_metric_cards(summary, session_duration=None)

        mock_st.columns.assert_called_once_with(5)
        # Each column's __enter__ is called
        for col in mock_cols:
            col.__enter__.assert_called_once()

    @patch("dashboard.utils.trace_summary.st")
    def test_duration_formatting(self, mock_st: MagicMock) -> None:
        from dashboard.utils.trace_summary import _render_metric_cards

        mock_cols = [MagicMock() for _ in range(5)]
        mock_st.columns.return_value = mock_cols

        summary = TraceSummary(
            total_messages=10,
            total_tool_calls=5,
            unique_tools=3,
            total_tokens=1000,
            tools_by_name={},
            files_accessed={},
        )

        _render_metric_cards(summary, session_duration=125.0)

        # st.metric is called on global st inside column context managers
        metric_calls = mock_st.metric.call_args_list
        assert len(metric_calls) == 5
        # Last metric call should be session duration with "2m 5s"
        duration_call = metric_calls[4]
        assert duration_call[0][0] == "Session Duration"
        assert "2m 5s" in str(duration_call)

    @patch("dashboard.utils.trace_summary.st")
    def test_duration_none_shows_na(self, mock_st: MagicMock) -> None:
        from dashboard.utils.trace_summary import _render_metric_cards

        mock_cols = [MagicMock() for _ in range(5)]
        mock_st.columns.return_value = mock_cols

        summary = TraceSummary(
            total_messages=10,
            total_tool_calls=5,
            unique_tools=3,
            total_tokens=1000,
            tools_by_name={},
            files_accessed={},
        )

        _render_metric_cards(summary, session_duration=None)

        metric_calls = mock_st.metric.call_args_list
        duration_call = metric_calls[4]
        assert "N/A" in str(duration_call)


class TestRenderToolCallChart:
    """Tests for _render_tool_call_chart via mocked Streamlit."""

    @patch("dashboard.utils.trace_summary.st")
    @patch("dashboard.utils.trace_summary.px")
    def test_empty_tools_shows_info(
        self, mock_px: MagicMock, mock_st: MagicMock
    ) -> None:
        from dashboard.utils.trace_summary import _render_tool_call_chart

        _render_tool_call_chart({})
        mock_st.info.assert_called_once()
        mock_px.bar.assert_not_called()

    @patch("dashboard.utils.trace_summary.st")
    @patch("dashboard.utils.trace_summary.px")
    def test_renders_bar_chart(
        self, mock_px: MagicMock, mock_st: MagicMock
    ) -> None:
        from dashboard.utils.trace_summary import _render_tool_call_chart

        mock_fig = MagicMock()
        mock_px.bar.return_value = mock_fig

        _render_tool_call_chart({"Bash": 10, "Read": 5})

        mock_px.bar.assert_called_once()
        mock_st.plotly_chart.assert_called_once()
        call_kwargs = mock_st.plotly_chart.call_args
        assert call_kwargs[1]["use_container_width"] is True


class TestRenderFileAccessTable:
    """Tests for _render_file_access_table via mocked Streamlit."""

    @patch("dashboard.utils.trace_summary.st")
    def test_empty_files_shows_info(self, mock_st: MagicMock) -> None:
        from dashboard.utils.trace_summary import _render_file_access_table

        _render_file_access_table({})
        mock_st.info.assert_called_once()

    @patch("dashboard.utils.trace_summary.st")
    def test_renders_dataframe(self, mock_st: MagicMock) -> None:
        from dashboard.utils.trace_summary import _render_file_access_table

        files = {
            "/a.py": {"read_count": 3, "write_count": 0, "edit_count": 1},
            "/b.py": {"read_count": 1, "write_count": 1, "edit_count": 0},
        }

        _render_file_access_table(files)

        mock_st.dataframe.assert_called_once()
        call_kwargs = mock_st.dataframe.call_args
        assert call_kwargs[1]["hide_index"] is True
        assert call_kwargs[1]["use_container_width"] is True

        # Verify the dataframe has correct structure
        df = call_kwargs[0][0]
        assert list(df.columns) == [
            "File Path",
            "Reads",
            "Writes",
            "Edits",
            "Total",
        ]
        assert len(df) == 2
        # Sorted by total descending: /a.py (4) before /b.py (2)
        assert df.iloc[0]["File Path"] == "/a.py"
        assert df.iloc[0]["Total"] == 4
        assert df.iloc[1]["File Path"] == "/b.py"
        assert df.iloc[1]["Total"] == 2


class TestRenderTraceSummaryPanel:
    """Tests for the main render_trace_summary_panel function."""

    @patch("dashboard.utils.trace_summary.st")
    @patch("dashboard.utils.trace_summary._render_file_access_table")
    @patch("dashboard.utils.trace_summary._render_tool_call_chart")
    @patch("dashboard.utils.trace_summary._render_metric_cards")
    def test_calls_all_sub_renderers(
        self,
        mock_cards: MagicMock,
        mock_chart: MagicMock,
        mock_table: MagicMock,
        mock_st: MagicMock,
    ) -> None:
        from dashboard.utils.trace_summary import render_trace_summary_panel

        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        mock_st.columns.return_value = [mock_col1, mock_col2]

        summary = TraceSummary(
            total_messages=50,
            total_tool_calls=20,
            unique_tools=5,
            total_tokens=10000,
            tools_by_name={"Bash": 10, "Read": 5},
            files_accessed={"/a.py": {"read_count": 3, "write_count": 0, "edit_count": 1}},
        )

        render_trace_summary_panel(summary, session_duration=60.0)

        mock_st.markdown.assert_any_call("### Trace Summary")
        mock_cards.assert_called_once_with(summary, 60.0)
        mock_chart.assert_called_once_with(summary.tools_by_name)
        mock_table.assert_called_once_with(summary.files_accessed)


class TestLoadAndRenderTraceSummary:
    """Tests for the convenience load_and_render_trace_summary function."""

    @patch("dashboard.utils.trace_summary.render_trace_summary_panel")
    @patch("dashboard.utils.trace_summary.compute_summary")
    @patch("dashboard.utils.trace_summary.parse_trace")
    def test_nonexistent_file_returns_none(
        self,
        mock_parse: MagicMock,
        mock_compute: MagicMock,
        mock_render: MagicMock,
        tmp_path,
    ) -> None:
        from dashboard.utils.trace_summary import load_and_render_trace_summary

        result = load_and_render_trace_summary(tmp_path / "missing.txt")
        assert result is None
        mock_parse.assert_not_called()

    @patch("dashboard.utils.trace_summary.render_trace_summary_panel")
    @patch("dashboard.utils.trace_summary.compute_summary")
    @patch("dashboard.utils.trace_summary.parse_trace")
    def test_empty_trace_returns_none(
        self,
        mock_parse: MagicMock,
        mock_compute: MagicMock,
        mock_render: MagicMock,
        tmp_path,
    ) -> None:
        from dashboard.utils.trace_summary import load_and_render_trace_summary

        trace_file = tmp_path / "claude-code.txt"
        trace_file.write_text("")
        mock_parse.return_value = []

        result = load_and_render_trace_summary(trace_file)
        assert result is None
        mock_render.assert_not_called()

    @patch("dashboard.utils.trace_summary.render_trace_summary_panel")
    @patch("dashboard.utils.trace_summary.compute_summary")
    @patch("dashboard.utils.trace_summary.parse_trace")
    def test_valid_trace_renders_and_returns_summary(
        self,
        mock_parse: MagicMock,
        mock_compute: MagicMock,
        mock_render: MagicMock,
        tmp_path,
    ) -> None:
        from dashboard.utils.trace_summary import load_and_render_trace_summary

        trace_file = tmp_path / "claude-code.txt"
        trace_file.write_text("{}")

        mock_messages = [MagicMock()]
        mock_parse.return_value = mock_messages

        expected_summary = TraceSummary(
            total_messages=1,
            total_tool_calls=0,
            unique_tools=0,
            total_tokens=0,
            tools_by_name={},
            files_accessed={},
        )
        mock_compute.return_value = expected_summary

        result = load_and_render_trace_summary(trace_file, session_duration=30.0)

        assert result is expected_summary
        mock_parse.assert_called_once_with(trace_file)
        mock_compute.assert_called_once_with(mock_messages)
        mock_render.assert_called_once_with(expected_summary, 30.0)
