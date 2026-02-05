"""
Config Comparison View

Side-by-side comparison of baseline vs sourcegraph_base vs sourcegraph_full
metrics for the same tasks. Uses filesystem-based comparison_loader for
always-current data.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from dashboard.utils.agent_labels import AGENT_DISPLAY_NAMES
from dashboard.utils.comparison_loader import load_comparison_data

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
    """Format a float or return dash for None."""
    if val is None:
        return _DASH
    return f"{val:.{decimals}f}"


def _fmt_int(val: Optional[int]) -> str:
    """Format an int with comma separator or return dash for None."""
    if val is None:
        return _DASH
    return f"{val:,}"


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

    return display


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

    # Build raw dataframe
    raw_df = _build_comparison_df(comparison_data)
    if raw_df.empty:
        st.warning("Loaded comparison data but no rows could be built.")
        return

    # Summary metrics
    total_tasks = len(raw_df)
    tasks_with_all = sum(
        1
        for _, row in raw_df.iterrows()
        if row["bl_reward"] is not None
        and row["sg_base_reward"] is not None
        and row["sg_full_reward"] is not None
    )

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Total Tasks", total_tasks)
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

    # Display table
    display_df = _format_display_df(raw_df)

    st.subheader(f"Comparison Table ({len(display_df)} tasks)")
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        key="ccmp_comparison_table",
    )
