"""Tests for dashboard/views/export_view.py."""

from __future__ import annotations

import zipfile
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_output_dir(tmp_path: Path) -> Path:
    """Create a mock output directory with sample artifacts."""
    output = tmp_path / "output"
    tables = output / "tables"
    figures = output / "figures"
    tables.mkdir(parents=True)
    figures.mkdir(parents=True)

    (tables / "table_aggregate.tex").write_text(
        r"\begin{tabular}{lcc}" "\n" r"\toprule" "\n" r"\end{tabular}",
        encoding="utf-8",
    )
    (tables / "table_efficiency.tex").write_text(
        r"\begin{tabular}{lr}" "\n" r"\bottomrule" "\n" r"\end{tabular}",
        encoding="utf-8",
    )
    (figures / "fig_pass_rate.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>',
        encoding="utf-8",
    )
    (figures / "fig_pass_rate.pdf").write_bytes(b"%PDF-1.4 fake")

    return output


# ---------------------------------------------------------------------------
# Tests: _human_size
# ---------------------------------------------------------------------------


class TestHumanSize:
    def test_bytes(self) -> None:
        from dashboard.views.export_view import _human_size
        assert _human_size(512) == "512 B"

    def test_kilobytes(self) -> None:
        from dashboard.views.export_view import _human_size
        assert _human_size(2048) == "2.0 KB"

    def test_megabytes(self) -> None:
        from dashboard.views.export_view import _human_size
        assert _human_size(2 * 1024 * 1024) == "2.0 MB"

    def test_zero(self) -> None:
        from dashboard.views.export_view import _human_size
        assert _human_size(0) == "0 B"


# ---------------------------------------------------------------------------
# Tests: _modification_time
# ---------------------------------------------------------------------------


class TestModificationTime:
    def test_returns_formatted_string(self, tmp_path: Path) -> None:
        from dashboard.views.export_view import _modification_time
        f = tmp_path / "test.txt"
        f.write_text("hello")
        result = _modification_time(f)
        assert "UTC" in result

    def test_missing_file(self, tmp_path: Path) -> None:
        from dashboard.views.export_view import _modification_time
        result = _modification_time(tmp_path / "nonexistent.txt")
        assert result == "unknown"


# ---------------------------------------------------------------------------
# Tests: _collect_artifacts
# ---------------------------------------------------------------------------


class TestCollectArtifacts:
    def test_collects_tables_and_figures(self, tmp_path: Path) -> None:
        from dashboard.views.export_view import _collect_artifacts
        output = _make_output_dir(tmp_path)
        artifacts = _collect_artifacts(output)
        assert len(artifacts["tables"]) == 2
        assert len(artifacts["figures"]) == 2

    def test_empty_output_dir(self, tmp_path: Path) -> None:
        from dashboard.views.export_view import _collect_artifacts
        output = tmp_path / "output"
        output.mkdir()
        artifacts = _collect_artifacts(output)
        assert artifacts["tables"] == []
        assert artifacts["figures"] == []

    def test_missing_output_dir(self, tmp_path: Path) -> None:
        from dashboard.views.export_view import _collect_artifacts
        artifacts = _collect_artifacts(tmp_path / "nonexistent")
        assert artifacts["tables"] == []
        assert artifacts["figures"] == []

    def test_ignores_unsupported_extensions(self, tmp_path: Path) -> None:
        from dashboard.views.export_view import _collect_artifacts
        output = tmp_path / "output"
        tables = output / "tables"
        tables.mkdir(parents=True)
        (tables / "notes.md").write_text("markdown file")
        (tables / "data.tex").write_text("latex")
        artifacts = _collect_artifacts(output)
        assert len(artifacts["tables"]) == 1
        assert artifacts["tables"][0].name == "data.tex"

    def test_sorted_output(self, tmp_path: Path) -> None:
        from dashboard.views.export_view import _collect_artifacts
        output = tmp_path / "output"
        tables = output / "tables"
        tables.mkdir(parents=True)
        (tables / "z_table.tex").write_text("z")
        (tables / "a_table.tex").write_text("a")
        artifacts = _collect_artifacts(output)
        names = [p.name for p in artifacts["tables"]]
        assert names == ["a_table.tex", "z_table.tex"]


# ---------------------------------------------------------------------------
# Tests: _build_zip
# ---------------------------------------------------------------------------


class TestBuildZip:
    def test_creates_valid_zip(self, tmp_path: Path) -> None:
        from dashboard.views.export_view import _build_zip, _collect_artifacts
        output = _make_output_dir(tmp_path)
        artifacts = _collect_artifacts(output)
        zip_bytes = _build_zip(output, artifacts)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert "tables/table_aggregate.tex" in names
            assert "figures/fig_pass_rate.svg" in names
            assert len(names) == 4

    def test_empty_artifacts(self, tmp_path: Path) -> None:
        from dashboard.views.export_view import _build_zip
        output = tmp_path / "output"
        output.mkdir()
        zip_bytes = _build_zip(output, {"tables": [], "figures": []})

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            assert zf.namelist() == []


# ---------------------------------------------------------------------------
# Tests: _mime_for_suffix
# ---------------------------------------------------------------------------


class TestMimeForSuffix:
    def test_known_types(self) -> None:
        from dashboard.views.export_view import _mime_for_suffix
        assert _mime_for_suffix(".tex") == "application/x-latex"
        assert _mime_for_suffix(".pdf") == "application/pdf"
        assert _mime_for_suffix(".svg") == "image/svg+xml"
        assert _mime_for_suffix(".png") == "image/png"

    def test_unknown_type(self) -> None:
        from dashboard.views.export_view import _mime_for_suffix
        assert _mime_for_suffix(".xyz") == "application/octet-stream"


# ---------------------------------------------------------------------------
# Tests: show_export_view (integration with mocked streamlit)
# ---------------------------------------------------------------------------


class TestShowExportView:
    @patch("dashboard.views.export_view.st")
    @patch("dashboard.views.export_view._DEFAULT_OUTPUT_DIR")
    def test_no_artifacts_shows_info(self, mock_output_dir: MagicMock, mock_st: MagicMock, tmp_path: Path) -> None:
        from dashboard.views.export_view import show_export_view

        empty_output = tmp_path / "output"
        empty_output.mkdir()
        mock_output_dir.__truediv__ = empty_output.__truediv__
        mock_output_dir.is_dir = empty_output.is_dir

        # Patch _collect_artifacts to return empty
        with patch("dashboard.views.export_view._collect_artifacts", return_value={"tables": [], "figures": []}):
            show_export_view()

        mock_st.info.assert_called_once()
        info_msg = mock_st.info.call_args[0][0]
        assert "No artifacts found" in info_msg

    @patch("dashboard.views.export_view.st")
    def test_with_artifacts_shows_sections(self, mock_st: MagicMock, tmp_path: Path) -> None:
        from dashboard.views.export_view import show_export_view, _collect_artifacts

        output = _make_output_dir(tmp_path)
        artifacts = _collect_artifacts(output)

        # Mock columns to return list of mocks
        mock_st.columns.side_effect = lambda *a, **kw: [
            MagicMock() for _ in range(a[0] if isinstance(a[0], int) else len(a[0]))
        ]

        with patch("dashboard.views.export_view._DEFAULT_OUTPUT_DIR", output):
            with patch("dashboard.views.export_view._collect_artifacts", return_value=artifacts):
                with patch("dashboard.views.export_view._render_artifact_row"):
                    show_export_view()

        # Should show summary and subheaders
        mock_st.markdown.assert_any_call("**4 artifacts** found: 2 tables, 2 figures")
        mock_st.subheader.assert_any_call("Tables (2)")
        mock_st.subheader.assert_any_call("Figures (2)")

    @patch("dashboard.views.export_view.st")
    def test_download_all_button(self, mock_st: MagicMock, tmp_path: Path) -> None:
        from dashboard.views.export_view import show_export_view, _collect_artifacts

        output = _make_output_dir(tmp_path)
        artifacts = _collect_artifacts(output)

        mock_st.columns.side_effect = lambda *a, **kw: [
            MagicMock() for _ in range(a[0] if isinstance(a[0], int) else len(a[0]))
        ]

        with patch("dashboard.views.export_view._DEFAULT_OUTPUT_DIR", output):
            with patch("dashboard.views.export_view._collect_artifacts", return_value=artifacts):
                with patch("dashboard.views.export_view._render_artifact_row"):
                    show_export_view()

        # Check download_button was called with ZIP
        download_calls = mock_st.download_button.call_args_list
        zip_call = [c for c in download_calls if c[0][0] == "Download All (ZIP)"]
        assert len(zip_call) == 1
        assert zip_call[0][1]["mime"] == "application/zip"


# ---------------------------------------------------------------------------
# Tests: _render_table_preview
# ---------------------------------------------------------------------------


class TestRenderTablePreview:
    @patch("dashboard.views.export_view.st")
    def test_renders_latex_code_block(self, mock_st: MagicMock, tmp_path: Path) -> None:
        from dashboard.views.export_view import _render_table_preview

        f = tmp_path / "table.tex"
        f.write_text(r"\begin{tabular}{lcc}\end{tabular}")
        _render_table_preview(f)
        mock_st.code.assert_called_once()
        call_args = mock_st.code.call_args
        assert call_args[1]["language"] == "latex" or call_args[0][1] == "latex"

    @patch("dashboard.views.export_view.st")
    def test_missing_file_shows_error(self, mock_st: MagicMock, tmp_path: Path) -> None:
        from dashboard.views.export_view import _render_table_preview

        _render_table_preview(tmp_path / "nonexistent.tex")
        mock_st.error.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: _render_figure_preview
# ---------------------------------------------------------------------------


class TestRenderFigurePreview:
    @patch("dashboard.views.export_view.st")
    def test_svg_preview(self, mock_st: MagicMock, tmp_path: Path) -> None:
        from dashboard.views.export_view import _render_figure_preview

        f = tmp_path / "fig.svg"
        f.write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')
        _render_figure_preview(f)
        mock_st.image.assert_called_once()

    @patch("dashboard.views.export_view.st")
    def test_png_preview(self, mock_st: MagicMock, tmp_path: Path) -> None:
        from dashboard.views.export_view import _render_figure_preview

        f = tmp_path / "fig.png"
        f.write_bytes(b"\x89PNG fake")
        _render_figure_preview(f)
        mock_st.image.assert_called_once_with(str(f))

    @patch("dashboard.views.export_view.st")
    def test_pdf_no_preview(self, mock_st: MagicMock, tmp_path: Path) -> None:
        from dashboard.views.export_view import _render_figure_preview

        f = tmp_path / "fig.pdf"
        f.write_bytes(b"%PDF-1.4 fake")
        _render_figure_preview(f)
        mock_st.caption.assert_called_once()
        assert "PDF" in mock_st.caption.call_args[0][0]
