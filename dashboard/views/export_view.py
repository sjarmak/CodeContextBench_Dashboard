"""
Export Artifacts View

Browse and download publication artifacts (LaTeX tables, PDF/SVG figures)
from the pipeline output directory.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st


# Default pipeline output directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "output"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _human_size(size_bytes: int) -> str:
    """Format byte count as human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _modification_time(path: Path) -> str:
    """Return the file modification time as a formatted string."""
    try:
        mtime = path.stat().st_mtime
        dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except OSError:
        return "unknown"


def _collect_artifacts(output_dir: Path) -> dict[str, list[Path]]:
    """Collect artifact files grouped by category.

    Returns a dict with keys 'tables' and 'figures', each containing
    a sorted list of file paths.
    """
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"

    tables: list[Path] = []
    if tables_dir.is_dir():
        tables = sorted(
            p for p in tables_dir.iterdir()
            if p.is_file() and p.suffix in {".tex", ".csv", ".txt"}
        )

    figures: list[Path] = []
    if figures_dir.is_dir():
        figures = sorted(
            p for p in figures_dir.iterdir()
            if p.is_file() and p.suffix in {".pdf", ".svg", ".png", ".jpg"}
        )

    return {"tables": tables, "figures": figures}


def _build_zip(output_dir: Path, artifacts: dict[str, list[Path]]) -> bytes:
    """Create an in-memory zip archive of all artifacts.

    Preserves the relative directory structure (tables/, figures/).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for _category, paths in artifacts.items():
            for path in paths:
                arcname = str(path.relative_to(output_dir))
                zf.write(path, arcname)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _render_table_preview(path: Path) -> None:
    """Render inline preview for a LaTeX/text table file."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        st.error(f"Could not read {path.name}")
        return

    syntax = "latex" if path.suffix == ".tex" else "text"
    st.code(content, language=syntax)


def _render_figure_preview(path: Path) -> None:
    """Render inline preview for a figure file."""
    if path.suffix == ".svg":
        try:
            svg_content = path.read_text(encoding="utf-8")
            st.image(svg_content)
        except OSError:
            st.error(f"Could not read {path.name}")
    elif path.suffix in {".png", ".jpg"}:
        st.image(str(path))
    elif path.suffix == ".pdf":
        st.caption("PDF preview not supported in Streamlit. Use the download button.")
    else:
        st.caption(f"No preview available for {path.suffix} files.")


def _render_artifact_row(path: Path, category: str, idx: int) -> None:
    """Render a single artifact row with metadata, preview, and download."""
    size = _human_size(path.stat().st_size) if path.exists() else "N/A"
    mtime = _modification_time(path)

    col_info, col_download = st.columns([3, 1])

    with col_info:
        st.markdown(f"**{path.name}**")
        st.caption(f"{size} | Modified: {mtime}")

    with col_download:
        try:
            file_bytes = path.read_bytes()
        except OSError:
            st.error("Read error")
            return

        mime = _mime_for_suffix(path.suffix)
        st.download_button(
            "Download",
            data=file_bytes,
            file_name=path.name,
            mime=mime,
            key=f"export_dl_{category}_{idx}",
        )

    # Inline preview in expander
    with st.expander(f"Preview {path.name}", expanded=False):
        if category == "tables":
            _render_table_preview(path)
        else:
            _render_figure_preview(path)


def _mime_for_suffix(suffix: str) -> str:
    """Return MIME type for a file suffix."""
    mime_map = {
        ".tex": "application/x-latex",
        ".csv": "text/csv",
        ".txt": "text/plain",
        ".pdf": "application/pdf",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
    }
    return mime_map.get(suffix, "application/octet-stream")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def show_export_view() -> None:
    """Main entry point for the Export Artifacts view."""
    st.title("Export Artifacts")
    st.caption("Browse and download publication-ready tables and figures.")
    st.markdown("---")

    output_dir = _DEFAULT_OUTPUT_DIR
    artifacts = _collect_artifacts(output_dir)

    total_files = sum(len(v) for v in artifacts.values())

    if total_files == 0:
        st.info(
            "No artifacts found -- run the pipeline first. "
            "Use the Home page to run the analysis pipeline, which generates "
            "LaTeX tables and figures in the output/ directory."
        )
        return

    # Summary
    n_tables = len(artifacts["tables"])
    n_figures = len(artifacts["figures"])
    st.markdown(f"**{total_files} artifacts** found: {n_tables} tables, {n_figures} figures")

    # Download All button
    zip_bytes = _build_zip(output_dir, artifacts)
    st.download_button(
        "Download All (ZIP)",
        data=zip_bytes,
        file_name="ccb_publication_artifacts.zip",
        mime="application/zip",
        key="export_download_all",
    )

    st.markdown("---")

    # Tables section
    if artifacts["tables"]:
        st.subheader(f"Tables ({n_tables})")
        for idx, path in enumerate(artifacts["tables"]):
            _render_artifact_row(path, "tables", idx)
            if idx < n_tables - 1:
                st.markdown("---")

    # Figures section
    if artifacts["figures"]:
        st.subheader(f"Figures ({n_figures})")
        for idx, path in enumerate(artifacts["figures"]):
            _render_artifact_row(path, "figures", idx)
            if idx < n_figures - 1:
                st.markdown("---")
