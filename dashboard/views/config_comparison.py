"""
Config Comparison View

Side-by-side comparison of baseline vs sourcegraph_base vs sourcegraph_full
metrics for the same tasks. Uses filesystem-based comparison_loader for
always-current data.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st

from dashboard.utils.agent_labels import AGENT_DISPLAY_NAMES
from dashboard.utils.comparison_filters import (
    filter_comparison_tasks,
    _get_search_strategy_type,
)
from dashboard.utils.comparison_loader import load_comparison_data
from dashboard.utils.comparison_metrics import compute_mcp_benefit

# Column display names keyed by config directory name
_CONFIG_DISPLAY: dict[str, str] = {
    "baseline": AGENT_DISPLAY_NAMES.get("baseline", "Baseline"),
    "sourcegraph_base": AGENT_DISPLAY_NAMES.get(
        "sourcegraph_no_ds", "Sourcegraph (no Deep Search)"
    ),
    "sourcegraph_full": AGENT_DISPLAY_NAMES.get(
        "sourcegraph_full", "Sourcegraph (Full)"
    ),
}

_DASH = "\u2014"


def _safe_float(value: object) -> Optional[float]:
    """Coerce a value to float, returning None for non-numeric."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> Optional[int]:
    """Coerce a value to int, returning None for non-numeric."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _fmt_float(val: Optional[float], decimals: int = 2) -> str:
    """Format a float or return dash for None/NaN."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return _DASH
    return f"{val:.{decimals}f}"


def _fmt_int(val: Optional[int]) -> str:
    """Format an int with comma separator or return dash for None."""
    if val is None:
        return _DASH
    return f"{val:,}"


def _fmt_pct(val: Optional[float], decimals: int = 1) -> str:
    """Format a float as a signed percentage or return dash for None/NaN."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return _DASH
    return f"{val:+.{decimals}f}%"


def _build_comparison_df(
    comparison_data: dict[str, dict[str, Optional[dict]]],
) -> pd.DataFrame:
    """Build a flat DataFrame for the comparison table.

    Each row is one task_id with columns for each config's reward and tokens.
    """
    rows: list[dict] = []
    for task_id, configs in comparison_data.items():
        # Pick any available config for shared metadata
        representative: Optional[dict] = None
        for cfg in configs.values():
            if cfg is not None:
                representative = cfg
                break

        benchmark = (
            (representative.get("benchmark") or _DASH) if representative else _DASH
        )

        row: dict = {
            "task_id": task_id,
            "benchmark": benchmark,
        }

        for config_name in ("baseline", "sourcegraph_base", "sourcegraph_full"):
            metrics = configs.get(config_name)
            prefix = {
                "baseline": "bl",
                "sourcegraph_base": "sg_base",
                "sourcegraph_full": "sg_full",
            }[config_name]

            if metrics is not None:
                row[f"{prefix}_reward"] = _safe_float(metrics.get("reward"))
                input_tok = _safe_int(metrics.get("input_tokens"))
                output_tok = _safe_int(metrics.get("output_tokens"))
                total = None
                if input_tok is not None and output_tok is not None:
                    total = input_tok + output_tok
                row[f"{prefix}_tokens"] = total
            else:
                row[f"{prefix}_reward"] = None
                row[f"{prefix}_tokens"] = None

        # Compute MCP benefit metrics for sg_base and sg_full vs baseline
        baseline_metrics = configs.get("baseline")
        sg_base_benefit = compute_mcp_benefit(
            baseline_metrics, configs.get("sourcegraph_base")
        )
        sg_full_benefit = compute_mcp_benefit(
            baseline_metrics, configs.get("sourcegraph_full")
        )

        row["sg_base_benefit_pct"] = (
            sg_base_benefit["benefit_pct"] if sg_base_benefit else None
        )
        row["sg_full_benefit_pct"] = (
            sg_full_benefit["benefit_pct"] if sg_full_benefit else None
        )
        row["sg_full_token_cost_pct"] = (
            sg_full_benefit["token_cost_pct"] if sg_full_benefit else None
        )
        row["sg_full_efficiency"] = (
            sg_full_benefit["efficiency"] if sg_full_benefit else None
        )

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def _format_display_df(df: pd.DataFrame) -> pd.DataFrame:
    """Create a display-friendly copy with formatted strings."""
    display = pd.DataFrame()
    display["Task ID"] = df["task_id"]
    display["Benchmark"] = df["benchmark"]

    bl_display = _CONFIG_DISPLAY.get("baseline", "Baseline")
    sg_base_display = _CONFIG_DISPLAY.get("sourcegraph_base", "SG Base")
    sg_full_display = _CONFIG_DISPLAY.get("sourcegraph_full", "SG Full")

    display[f"{bl_display} Reward"] = df["bl_reward"].apply(
        lambda v: _fmt_float(v)
    )
    display[f"{sg_base_display} Reward"] = df["sg_base_reward"].apply(
        lambda v: _fmt_float(v)
    )
    display[f"{sg_full_display} Reward"] = df["sg_full_reward"].apply(
        lambda v: _fmt_float(v)
    )
    display[f"{bl_display} Tokens"] = df["bl_tokens"].apply(
        lambda v: _fmt_int(_safe_int(v))
    )
    display[f"{sg_base_display} Tokens"] = df["sg_base_tokens"].apply(
        lambda v: _fmt_int(_safe_int(v))
    )
    display[f"{sg_full_display} Tokens"] = df["sg_full_tokens"].apply(
        lambda v: _fmt_int(_safe_int(v))
    )

    # Computed effectiveness columns
    display["SG Base Benefit %"] = df["sg_base_benefit_pct"].apply(_fmt_pct)
    display["SG Full Benefit %"] = df["sg_full_benefit_pct"].apply(_fmt_pct)
    display["SG Full Token Cost %"] = df["sg_full_token_cost_pct"].apply(_fmt_pct)
    display["SG Full Efficiency"] = df["sg_full_efficiency"].apply(_fmt_float)

    return display


# Anomaly highlighting thresholds
_WIN_THRESHOLD = 50.0  # sg_full_benefit_pct > +50%
_REGRESSION_THRESHOLD = -20.0  # sg_full_benefit_pct < -20%
_TOKEN_SPIKE_THRESHOLD = 200.0  # sg_full_token_cost_pct > +200%

# Background colors (light, legible on white/dark Streamlit themes)
_WIN_BG = "background-color: rgba(0, 180, 0, 0.15)"
_REGRESSION_BG = "background-color: rgba(220, 0, 0, 0.15)"
_TOKEN_SPIKE_BG = "background-color: rgba(220, 180, 0, 0.15)"
_NO_HIGHLIGHT = ""


def _is_valid_number(val: Optional[float]) -> bool:
    """Check if a value is a usable numeric (not None, not NaN)."""
    if val is None:
        return False
    if isinstance(val, float) and math.isnan(val):
        return False
    return True


def _classify_anomaly(
    benefit_pct: Optional[float], token_cost_pct: Optional[float]
) -> str:
    """Return the anomaly label for a row based on thresholds.

    Priority: Regression > Token spike > Win (regression is most important
    to surface even if there's also a token spike or win).
    """
    if _is_valid_number(benefit_pct) and benefit_pct is not None:
        if benefit_pct < _REGRESSION_THRESHOLD:
            return "Regression"

    if _is_valid_number(token_cost_pct) and token_cost_pct is not None:
        if token_cost_pct > _TOKEN_SPIKE_THRESHOLD:
            return "Token spike"

    if _is_valid_number(benefit_pct) and benefit_pct is not None:
        if benefit_pct > _WIN_THRESHOLD:
            return "Win"

    return ""


def _build_anomaly_labels(raw_df: pd.DataFrame) -> pd.Series:
    """Compute per-row anomaly labels from the raw DataFrame."""
    return pd.Series(
        [
            _classify_anomaly(
                raw_df.at[idx, "sg_full_benefit_pct"],
                raw_df.at[idx, "sg_full_token_cost_pct"],
            )
            for idx in raw_df.index
        ],
        index=raw_df.index,
    )


def _apply_anomaly_styles(
    display_df: pd.DataFrame, anomaly_labels: pd.Series
) -> pd.io.formats.style.Styler:
    """Apply row-level background highlighting based on anomaly labels.

    Returns a Pandas Styler object compatible with st.dataframe().
    """
    color_map = {
        "Win": _WIN_BG,
        "Regression": _REGRESSION_BG,
        "Token spike": _TOKEN_SPIKE_BG,
    }

    def _row_style(row: pd.Series) -> list[str]:
        label = anomaly_labels.get(row.name, "")
        bg = color_map.get(label, _NO_HIGHLIGHT)
        return [bg] * len(row)

    return display_df.style.apply(_row_style, axis=1)


def _extract_unique_values(
    comparison_data: dict[str, dict[str, Optional[dict]]],
) -> dict[str, list[str]]:
    """Extract sorted unique values for each filter dimension.

    Scans the representative config for every task to build the set of
    distinct values present in the data.  Returns a dict keyed by
    dimension name.
    """
    benchmarks: set[str] = set()
    categories: set[str] = set()
    difficulties: set[str] = set()
    sdlc_phases: set[str] = set()
    strategies: set[str] = set()

    for configs in comparison_data.values():
        for cfg_metrics in configs.values():
            if cfg_metrics is None:
                continue

            bm = cfg_metrics.get("benchmark")
            if bm:
                benchmarks.add(bm)
            cat = cfg_metrics.get("category")
            if cat:
                categories.add(cat)
            diff = cfg_metrics.get("difficulty")
            if diff:
                difficulties.add(diff)
            phase = cfg_metrics.get("sdlc_phase")
            if phase:
                sdlc_phases.add(phase)
            strat = _get_search_strategy_type(cfg_metrics)
            if strat:
                strategies.add(strat)

    return {
        "benchmark": sorted(benchmarks),
        "category": sorted(categories),
        "difficulty": sorted(difficulties),
        "sdlc_phase": sorted(sdlc_phases),
        "search_strategy_type": sorted(strategies),
    }


_SIZE_OPTIONS = ("All", "Small (<300K)", "Medium (300K-1M)", "Large (>1M)")
_SIZE_MAP: dict[str, Optional[str]] = {
    "All": None,
    "Small (<300K)": "small",
    "Medium (300K-1M)": "medium",
    "Large (>1M)": "large",
}


def _render_filter_panel(
    unique_vals: dict[str, list[str]],
) -> dict[str, object]:
    """Render filter controls above the comparison table.

    Uses st.columns() layout (not sidebar) per CLAUDE.md guidance.
    All widget keys use the ``ccmp_filter_`` prefix.

    Returns a dict of kwargs suitable for ``filter_comparison_tasks()``.
    """
    st.subheader("Filters")

    # Row 1: Benchmark, Category, Difficulty
    col1, col2, col3 = st.columns(3)
    with col1:
        sel_benchmark = st.multiselect(
            "Benchmark",
            options=unique_vals["benchmark"],
            default=None,
            key="ccmp_filter_benchmark",
        )
    with col2:
        sel_category = st.multiselect(
            "Category",
            options=unique_vals["category"],
            default=None,
            key="ccmp_filter_category",
        )
    with col3:
        sel_difficulty = st.multiselect(
            "Difficulty",
            options=unique_vals["difficulty"],
            default=None,
            key="ccmp_filter_difficulty",
        )

    # Row 2: SDLC Phase, Search Strategy, Task Size
    col4, col5, col6 = st.columns(3)
    with col4:
        sel_sdlc = st.multiselect(
            "SDLC Phase",
            options=unique_vals["sdlc_phase"],
            default=None,
            key="ccmp_filter_sdlc_phase",
        )
    with col5:
        sel_strategy = st.multiselect(
            "Search Strategy Type",
            options=unique_vals["search_strategy_type"],
            default=None,
            key="ccmp_filter_strategy",
        )
    with col6:
        sel_size_label = st.radio(
            "Task Size",
            options=_SIZE_OPTIONS,
            index=0,
            key="ccmp_filter_size",
            horizontal=True,
        )

    return {
        "benchmark": sel_benchmark or None,
        "category": sel_category or None,
        "difficulty": sel_difficulty or None,
        "sdlc_phase": sel_sdlc or None,
        "size_bucket": _SIZE_MAP[sel_size_label],
        "search_strategy_type": sel_strategy or None,
    }


def show_config_comparison() -> None:
    """Main entry point for the Config Comparison view."""
    st.title("Config Comparison")
    st.caption(
        "Side-by-side metrics for baseline, Sourcegraph Base, and "
        "Sourcegraph Full configs across shared tasks."
    )

    # Load data
    comparison_data = load_comparison_data()

    if not comparison_data:
        st.info(
            "No comparison data found. Ensure runs are available at "
            "the configured runs directory with baseline/sourcegraph_base/"
            "sourcegraph_full config directories."
        )
        return

    total_tasks = len(comparison_data)

    # --- Filter panel ---
    unique_vals = _extract_unique_values(comparison_data)
    filter_kwargs = _render_filter_panel(unique_vals)
    filtered_data = filter_comparison_tasks(comparison_data, **filter_kwargs)

    st.markdown("---")

    # Show task count summary
    filtered_count = len(filtered_data)
    if filtered_count == 0:
        st.warning(
            "No tasks match the current filters. "
            "Try broadening your selection or resetting filters."
        )
        return

    st.caption(f"Showing **{filtered_count}** of **{total_tasks}** tasks")

    # Build raw dataframe from filtered data
    raw_df = _build_comparison_df(filtered_data)
    if raw_df.empty:
        st.warning("Loaded comparison data but no rows could be built.")
        return

    # Summary metrics
    tasks_with_all = sum(
        1
        for _, row in raw_df.iterrows()
        if row["bl_reward"] is not None
        and row["sg_base_reward"] is not None
        and row["sg_full_reward"] is not None
    )

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Total Tasks", filtered_count)
    col_m2.metric("Tasks with All 3 Configs", tasks_with_all)

    # Mean rewards
    bl_mean = raw_df["bl_reward"].dropna().mean()
    sg_full_mean = raw_df["sg_full_reward"].dropna().mean()
    if pd.notna(bl_mean) and pd.notna(sg_full_mean):
        delta = sg_full_mean - bl_mean
        col_m3.metric(
            "Mean Reward Delta (Full vs Baseline)",
            f"{delta:+.4f}",
        )
    else:
        col_m3.metric("Mean Reward Delta", _DASH)

    st.markdown("---")

    # Highlighting toggle
    show_highlights = st.checkbox(
        "Show highlights", value=True, key="ccmp_highlights"
    )

    # Build display table
    display_df = _format_display_df(raw_df)

    # Compute anomaly labels from raw data
    anomaly_labels = _build_anomaly_labels(raw_df)

    # Add label column to display DataFrame
    display_df.insert(2, "Anomaly", anomaly_labels.values)

    st.subheader(f"Comparison Table ({len(display_df)} tasks)")

    if show_highlights:
        styled = _apply_anomaly_styles(display_df, anomaly_labels)
        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            key="ccmp_comparison_table",
        )
    else:
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            key="ccmp_comparison_table",
        )

    # --- CSV Export ---
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    csv_data = display_df.to_csv(index=False)
    st.download_button(
        label="Export CSV",
        data=csv_data,
        file_name=f"ccb-comparison-{timestamp}.csv",
        mime="text/csv",
        key="ccmp_export_csv",
    )
