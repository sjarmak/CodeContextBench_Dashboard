"""
Comparison Analysis View

Interactive comparison view with tabs matching paper sections 4.1-4.5.
Loads analysis_results.json from the pipeline output directory.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# Default pipeline output directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "output"

# Config display names
_CONFIG_DISPLAY = {
    "BASELINE": "Baseline",
    "MCP_BASE": "MCP-Base",
    "MCP_FULL": "MCP-Full",
}

# Canonical config order
_CONFIG_ORDER = ["BASELINE", "MCP_BASE", "MCP_FULL"]


def _display_config(config: str) -> str:
    """Map internal config name to paper-friendly display name."""
    return _CONFIG_DISPLAY.get(config, config)


def _load_analysis_results(output_dir: Path) -> dict:
    """Load analysis_results.json from the output directory.

    Returns a dict with analysis sections, or an empty dict on error.
    """
    results_path = output_dir / "analysis_results.json"
    if not results_path.is_file():
        return {}
    try:
        data = json.loads(results_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return {}
    except (json.JSONDecodeError, OSError):
        return {}


def _sort_configs(configs: list[str]) -> list[str]:
    """Sort configs in canonical order (BASELINE, MCP_BASE, MCP_FULL)."""
    order = {c: i for i, c in enumerate(_CONFIG_ORDER)}
    return sorted(configs, key=lambda c: order.get(c, 99))


def _significance_marker(p_value: float) -> str:
    """Return significance marker for p-value."""
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return ""


def _fmt_pvalue(p: float) -> str:
    """Format p-value for display."""
    if p < 0.001:
        return "< 0.001"
    return f"{p:.4f}"


def _df_to_csv(df: pd.DataFrame) -> str:
    """Convert DataFrame to CSV string."""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tab 1: Aggregate (Section 4.1)
# ---------------------------------------------------------------------------


def _render_aggregate_tab(data: dict) -> None:
    """Render the Aggregate metrics tab (paper section 4.1)."""
    aggregate = data.get("aggregate_metrics", [])
    if not aggregate:
        st.info("No aggregate metrics available. Run the pipeline first.")
        return

    # Build table
    rows = []
    for entry in aggregate:
        config = entry.get("config", "")
        rows.append({
            "Config": _display_config(config),
            "N": entry.get("n_trials", 0),
            "Pass Rate": f"{entry.get('pass_rate', 0):.1%} ({entry.get('se_pass_rate', 0):.3f})",
            "Mean Reward": f"{entry.get('mean_reward', 0):.4f} ({entry.get('se_reward', 0):.4f})",
            "Median Duration (s)": f"{entry.get('median_duration_seconds', 0) or 0:.0f}",
            "Mean Input Tokens": f"{entry.get('mean_input_tokens', 0):,.0f}",
            "Mean Output Tokens": f"{entry.get('mean_output_tokens', 0):,.0f}",
            "_config_raw": config,
        })

    # Sort by canonical order
    order = {c: i for i, c in enumerate(_CONFIG_ORDER)}
    rows.sort(key=lambda r: order.get(r["_config_raw"], 99))

    df = pd.DataFrame(rows)
    display_df = df.drop(columns=["_config_raw"])

    st.markdown("### Aggregate Metrics by Configuration")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Plotly bar chart of pass rates with error bars
    chart_data = []
    for entry in aggregate:
        chart_data.append({
            "Config": _display_config(entry.get("config", "")),
            "Pass Rate": entry.get("pass_rate", 0),
            "SE": entry.get("se_pass_rate", 0),
            "_order": order.get(entry.get("config", ""), 99),
        })

    chart_df = pd.DataFrame(chart_data).sort_values("_order")

    fig = px.bar(
        chart_df,
        x="Config",
        y="Pass Rate",
        error_y="SE",
        title="Pass Rate by Configuration",
        color="Config",
        color_discrete_sequence=px.colors.qualitative.T10,
    )
    fig.update_layout(
        yaxis_tickformat=".0%",
        showlegend=False,
        yaxis_title="Pass Rate",
        xaxis_title="",
    )
    st.plotly_chart(fig, use_container_width=True, key="ca_agg_pass_rate")

    # Export
    col_csv, col_png = st.columns(2)
    with col_csv:
        st.download_button(
            "Export Table (CSV)",
            _df_to_csv(display_df),
            file_name="aggregate_metrics.csv",
            mime="text/csv",
            key="ca_agg_csv",
        )
    with col_png:
        st.download_button(
            "Export Chart (PNG)",
            fig.to_image(format="png"),
            file_name="pass_rate_chart.png",
            mime="image/png",
            key="ca_agg_png",
        )


# ---------------------------------------------------------------------------
# Tab 2: Per-Benchmark (Section 4.2)
# ---------------------------------------------------------------------------


def _render_per_benchmark_tab(data: dict) -> None:
    """Render the Per-Benchmark breakdown tab (paper section 4.2)."""
    per_benchmark = data.get("per_benchmark", [])
    per_benchmark_sig = data.get("per_benchmark_significance", [])

    if not per_benchmark:
        st.info("No per-benchmark metrics available. Run the pipeline first.")
        return

    # Build significance lookup: (benchmark, config) -> min p-value across pairs
    sig_lookup: dict[tuple[str, str], float] = {}
    for sig in per_benchmark_sig:
        benchmark = sig.get("benchmark", "")
        for cfg_key in ("config_a", "config_b"):
            cfg = sig.get(cfg_key, "")
            key = (benchmark, cfg)
            p = sig.get("p_value", 1.0)
            if key not in sig_lookup or p < sig_lookup[key]:
                sig_lookup[key] = p

    # Table
    rows = []
    for entry in per_benchmark:
        benchmark = entry.get("benchmark", "")
        config = entry.get("config", "")
        p_min = sig_lookup.get((benchmark, config), 1.0)
        marker = _significance_marker(p_min)

        rows.append({
            "Benchmark": benchmark,
            "Config": _display_config(config),
            "N": entry.get("n_trials", 0),
            "Pass Rate": f"{entry.get('pass_rate', 0):.1%}",
            "Mean Reward": f"{entry.get('mean_reward', 0):.4f} ({entry.get('se_reward', 0):.4f})",
            "Sig": marker,
            "_benchmark": benchmark,
            "_config": config,
        })

    df = pd.DataFrame(rows)
    display_df = df.drop(columns=["_benchmark", "_config"])

    st.markdown("### Per-Benchmark Metrics")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Heatmap: reward delta (MCP-Full minus Baseline) per benchmark
    st.markdown("### Reward Delta Heatmap (MCP-Full minus Baseline)")

    # Build delta matrix
    bench_config_reward: dict[str, dict[str, float]] = {}
    for entry in per_benchmark:
        benchmark = entry.get("benchmark", "")
        config = entry.get("config", "")
        reward = entry.get("mean_reward", 0.0)
        if benchmark not in bench_config_reward:
            bench_config_reward[benchmark] = {}
        bench_config_reward[benchmark][config] = reward

    heatmap_rows = []
    for benchmark in sorted(bench_config_reward.keys()):
        rewards = bench_config_reward[benchmark]
        baseline_reward = rewards.get("BASELINE", 0.0)
        mcp_full_reward = rewards.get("MCP_FULL")
        if mcp_full_reward is not None:
            delta = mcp_full_reward - baseline_reward
            heatmap_rows.append({
                "Benchmark": benchmark,
                "Reward Delta": delta,
            })

    if heatmap_rows:
        heatmap_df = pd.DataFrame(heatmap_rows)

        fig = px.imshow(
            heatmap_df.set_index("Benchmark").T,
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0,
            aspect="auto",
            title="Reward Delta: MCP-Full minus Baseline",
            labels={"color": "Delta"},
        )
        fig.update_layout(yaxis_title="", xaxis_title="")
        st.plotly_chart(fig, use_container_width=True, key="ca_bench_heatmap")

        col_csv, col_png = st.columns(2)
        with col_csv:
            st.download_button(
                "Export Table (CSV)",
                _df_to_csv(display_df),
                file_name="per_benchmark_metrics.csv",
                mime="text/csv",
                key="ca_bench_csv",
            )
        with col_png:
            st.download_button(
                "Export Chart (PNG)",
                fig.to_image(format="png"),
                file_name="benchmark_heatmap.png",
                mime="image/png",
                key="ca_bench_png",
            )
    else:
        st.caption("Heatmap requires both BASELINE and MCP_FULL configs.")
        st.download_button(
            "Export Table (CSV)",
            _df_to_csv(display_df),
            file_name="per_benchmark_metrics.csv",
            mime="text/csv",
            key="ca_bench_csv_only",
        )


# ---------------------------------------------------------------------------
# Tab 3: Config Sensitivity (Section 4.3)
# ---------------------------------------------------------------------------


def _render_config_sensitivity_tab(data: dict) -> None:
    """Render the Config Sensitivity tab (paper section 4.3)."""
    pairwise = data.get("pairwise_tests", [])
    effect_sizes = data.get("effect_sizes", [])

    if not pairwise:
        st.info("No pairwise test results available. Run the pipeline first.")
        return

    # Pairwise tests table
    st.markdown("### Pairwise Statistical Tests")

    rows = []
    for test in pairwise:
        p = test.get("p_value", 1.0)
        rows.append({
            "Config A": _display_config(test.get("config_a", "")),
            "Config B": _display_config(test.get("config_b", "")),
            "Metric": test.get("metric", ""),
            "Test": test.get("test_name", ""),
            "Statistic": f"{test.get('statistic', 0):.4f}",
            "p-value": _fmt_pvalue(p),
            "Sig": _significance_marker(p),
        })

    df_tests = pd.DataFrame(rows)
    st.dataframe(df_tests, use_container_width=True, hide_index=True)

    # Effect sizes table and visualization
    if effect_sizes:
        st.markdown("### Effect Sizes (Cohen's d)")

        es_rows = []
        for es in effect_sizes:
            es_rows.append({
                "Config A": _display_config(es.get("config_a", "")),
                "Config B": _display_config(es.get("config_b", "")),
                "Metric": es.get("metric", ""),
                "Cohen's d": f"{es.get('cohens_d', 0):.4f}",
                "Interpretation": es.get("interpretation", ""),
                "_cohens_d": es.get("cohens_d", 0),
                "_label": f"{_display_config(es.get('config_a', ''))} vs {_display_config(es.get('config_b', ''))} ({es.get('metric', '')})",
            })

        df_es = pd.DataFrame(es_rows)
        display_es = df_es.drop(columns=["_cohens_d", "_label"])
        st.dataframe(display_es, use_container_width=True, hide_index=True)

        # Effect size bar chart
        fig = px.bar(
            df_es,
            x="_label",
            y="_cohens_d",
            color="Interpretation",
            title="Effect Sizes by Comparison",
            labels={"_cohens_d": "Cohen's d", "_label": ""},
            color_discrete_map={
                "negligible": "#999999",
                "small": "#4a9eff",
                "medium": "#ff9f43",
                "large": "#ff4757",
            },
        )
        fig.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True, key="ca_es_chart")

    # Export
    col_csv1, col_csv2 = st.columns(2)
    with col_csv1:
        st.download_button(
            "Export Tests (CSV)",
            _df_to_csv(df_tests),
            file_name="pairwise_tests.csv",
            mime="text/csv",
            key="ca_pw_csv",
        )
    if effect_sizes:
        with col_csv2:
            st.download_button(
                "Export Effect Sizes (CSV)",
                _df_to_csv(display_es),
                file_name="effect_sizes.csv",
                mime="text/csv",
                key="ca_es_csv",
            )


# ---------------------------------------------------------------------------
# Tab 4: Efficiency (Section 4.4)
# ---------------------------------------------------------------------------


def _render_efficiency_tab(data: dict) -> None:
    """Render the Efficiency tab (paper section 4.4)."""
    efficiency = data.get("efficiency", [])

    if not efficiency:
        st.info("No efficiency metrics available. Run the pipeline first.")
        return

    # Metrics table
    st.markdown("### Token Consumption and Timing")

    rows = []
    for entry in efficiency:
        config = entry.get("config", "")
        tps = entry.get("tokens_per_success")
        overhead = entry.get("mcp_token_overhead")

        rows.append({
            "Config": _display_config(config),
            "N": entry.get("n_trials", 0),
            "Mean Input Tokens": f"{entry.get('mean_input_tokens', 0):,.0f} ({entry.get('se_input_tokens', 0):,.0f})",
            "Mean Output Tokens": f"{entry.get('mean_output_tokens', 0):,.0f} ({entry.get('se_output_tokens', 0):,.0f})",
            "Tokens/Success": f"{tps:,.0f}" if tps is not None else "--",
            "I/O Ratio": f"{entry.get('input_to_output_ratio', 0) or 0:.2f}",
            "MCP Overhead": f"{overhead:+,.0f}" if overhead is not None else "--",
            "_config": config,
        })

    order = {c: i for i, c in enumerate(_CONFIG_ORDER)}
    rows.sort(key=lambda r: order.get(r["_config"], 99))

    df = pd.DataFrame(rows)
    display_df = df.drop(columns=["_config"])

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Token distribution bar chart
    st.markdown("### Token Distribution by Configuration")

    chart_data = []
    for entry in efficiency:
        config = _display_config(entry.get("config", ""))
        chart_data.append({"Config": config, "Token Type": "Input", "Tokens": entry.get("mean_input_tokens", 0), "_order": order.get(entry.get("config", ""), 99)})
        chart_data.append({"Config": config, "Token Type": "Output", "Tokens": entry.get("mean_output_tokens", 0), "_order": order.get(entry.get("config", ""), 99)})

    chart_df = pd.DataFrame(chart_data).sort_values("_order")

    fig = px.bar(
        chart_df,
        x="Config",
        y="Tokens",
        color="Token Type",
        barmode="group",
        title="Mean Token Usage by Configuration",
        color_discrete_sequence=px.colors.qualitative.T10,
    )
    fig.update_layout(yaxis_title="Tokens", xaxis_title="")
    st.plotly_chart(fig, use_container_width=True, key="ca_eff_tokens")

    # Tokens per success comparison
    tps_data = []
    for entry in efficiency:
        tps = entry.get("tokens_per_success")
        if tps is not None:
            tps_data.append({
                "Config": _display_config(entry.get("config", "")),
                "Tokens per Success": tps,
                "_order": order.get(entry.get("config", ""), 99),
            })

    if tps_data:
        st.markdown("### Tokens per Success")
        tps_df = pd.DataFrame(tps_data).sort_values("_order")

        fig_tps = px.bar(
            tps_df,
            x="Config",
            y="Tokens per Success",
            title="Tokens Required per Successful Task",
            color="Config",
            color_discrete_sequence=px.colors.qualitative.T10,
        )
        fig_tps.update_layout(showlegend=False, yaxis_title="Tokens", xaxis_title="")
        st.plotly_chart(fig_tps, use_container_width=True, key="ca_eff_tps")

    # Export
    col_csv, col_png = st.columns(2)
    with col_csv:
        st.download_button(
            "Export Table (CSV)",
            _df_to_csv(display_df),
            file_name="efficiency_metrics.csv",
            mime="text/csv",
            key="ca_eff_csv",
        )
    with col_png:
        st.download_button(
            "Export Chart (PNG)",
            fig.to_image(format="png"),
            file_name="token_distribution.png",
            mime="image/png",
            key="ca_eff_png",
        )


# ---------------------------------------------------------------------------
# Tab 5: Tool Utilization (Section 4.5)
# ---------------------------------------------------------------------------


def _render_tool_utilization_tab(data: dict) -> None:
    """Render the Tool Utilization tab (paper section 4.5)."""
    tool_util = data.get("tool_utilization", [])
    tool_corr = data.get("tool_reward_correlation", [])
    bench_tool = data.get("benchmark_tool_usage", [])

    if not tool_util:
        st.info("No tool utilization metrics available. Run the pipeline first.")
        return

    # Tool call distribution chart (stacked bar)
    st.markdown("### Tool Call Distribution by Configuration")

    order = {c: i for i, c in enumerate(_CONFIG_ORDER)}
    chart_data = []
    for entry in tool_util:
        config = _display_config(entry.get("config", ""))
        mcp = entry.get("mean_mcp_calls", 0)
        ds = entry.get("mean_deep_search_calls", 0)
        # Approximate local/other as: we don't have exact breakdown, so show MCP and Deep Search
        chart_data.append({"Config": config, "Tool Category": "MCP Calls", "Mean Calls": mcp, "_order": order.get(entry.get("config", ""), 99)})
        chart_data.append({"Config": config, "Tool Category": "Deep Search Calls", "Mean Calls": ds, "_order": order.get(entry.get("config", ""), 99)})

    chart_df = pd.DataFrame(chart_data).sort_values("_order")

    fig = px.bar(
        chart_df,
        x="Config",
        y="Mean Calls",
        color="Tool Category",
        barmode="stack",
        title="Tool Call Distribution per Configuration",
        color_discrete_sequence=px.colors.qualitative.T10,
    )
    fig.update_layout(yaxis_title="Mean Tool Calls", xaxis_title="")
    st.plotly_chart(fig, use_container_width=True, key="ca_tu_dist")

    # Metrics table
    st.markdown("### Tool Utilization Metrics")

    rows = []
    for entry in tool_util:
        config = entry.get("config", "")
        rows.append({
            "Config": _display_config(config),
            "N": entry.get("n_trials", 0),
            "Mean MCP Calls": f"{entry.get('mean_mcp_calls', 0):.1f} ({entry.get('se_mcp_calls', 0):.1f})",
            "Mean Deep Search": f"{entry.get('mean_deep_search_calls', 0):.1f} ({entry.get('se_deep_search_calls', 0):.1f})",
            "DS/Keyword Ratio": f"{entry.get('mean_deep_search_vs_keyword_ratio', 0):.3f}",
            "Context Fill Rate": f"{entry.get('mean_context_fill_rate', 0):.1%} ({entry.get('se_context_fill_rate', 0):.3f})",
            "_config": config,
        })

    rows.sort(key=lambda r: order.get(r["_config"], 99))
    df = pd.DataFrame(rows)
    display_df = df.drop(columns=["_config"])
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Correlation scatter plot
    if tool_corr:
        st.markdown("### MCP Tool Calls vs Reward Correlation")

        for corr in tool_corr:
            r_val = corr.get("pearson_r", 0)
            p_val = corr.get("p_value", 1.0)
            n_obs = corr.get("n_observations", 0)
            sig = "significant" if corr.get("significant", False) else "not significant"
            st.markdown(
                f"Pearson r = **{r_val:.4f}**, p = **{_fmt_pvalue(p_val)}** "
                f"(n = {n_obs}, {sig})"
            )

    # Per-benchmark tool usage
    if bench_tool:
        st.markdown("### Tool Usage by Benchmark")

        bt_rows = []
        for entry in bench_tool:
            bt_rows.append({
                "Benchmark": entry.get("benchmark", ""),
                "Config": _display_config(entry.get("config", "")),
                "N": entry.get("n_trials", 0),
                "Mean MCP Calls": f"{entry.get('mean_mcp_calls', 0):.1f}",
                "Mean Deep Search": f"{entry.get('mean_deep_search_calls', 0):.1f}",
                "Mean Total Tool Calls": f"{entry.get('mean_total_tool_calls', 0):.1f}",
            })

        bt_df = pd.DataFrame(bt_rows)
        st.dataframe(bt_df, use_container_width=True, hide_index=True)

    # Export
    col_csv, col_png = st.columns(2)
    with col_csv:
        st.download_button(
            "Export Table (CSV)",
            _df_to_csv(display_df),
            file_name="tool_utilization.csv",
            mime="text/csv",
            key="ca_tu_csv",
        )
    with col_png:
        st.download_button(
            "Export Chart (PNG)",
            fig.to_image(format="png"),
            file_name="tool_distribution.png",
            mime="image/png",
            key="ca_tu_png",
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def show_comparison_analysis() -> None:
    """Main entry point for the Comparison Analysis view."""
    st.title("Comparison Analysis")
    st.caption("Interactive analysis matching paper sections 4.1-4.5.")
    st.markdown("---")

    # Load data
    data = _load_analysis_results(_DEFAULT_OUTPUT_DIR)

    if not data:
        st.info(
            "No analysis_results.json found in output/ directory. "
            "Run the analysis pipeline from the Home page first."
        )
        return

    # 5 tabs matching paper sections
    tab_agg, tab_bench, tab_sens, tab_eff, tab_tool = st.tabs([
        "Aggregate (4.1)",
        "Per-Benchmark (4.2)",
        "Config Sensitivity (4.3)",
        "Efficiency (4.4)",
        "Tool Utilization (4.5)",
    ])

    with tab_agg:
        _render_aggregate_tab(data)

    with tab_bench:
        _render_per_benchmark_tab(data)

    with tab_sens:
        _render_config_sensitivity_tab(data)

    with tab_eff:
        _render_efficiency_tab(data)

    with tab_tool:
        _render_tool_utilization_tab(data)
