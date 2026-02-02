"""
Publication artifact generator for the CCB pipeline.

Consumes analysis_results.json and produces LaTeX tables and figures
for the CodeContextBench paper.

Usage:
    python -m scripts.ccb_pipeline.publish --input analysis_results.json --output-dir output/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")  # Non-interactive backend for headless environments

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Figure style constants
# ---------------------------------------------------------------------------

_STYLE = "seaborn-v0_8-paper"
_PALETTE = "tab10"
_FIG_DPI = 300
_CONFIG_ORDER = ("BASELINE", "MCP_BASE", "MCP_FULL")
_CONFIG_LABELS = {"BASELINE": "Baseline", "MCP_BASE": "MCP-Base", "MCP_FULL": "MCP-Full"}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt_float(value: float | None, decimals: int = 3) -> str:
    """Format a float for LaTeX output, returning '--' for None."""
    if value is None:
        return "--"
    return f"{value:.{decimals}f}"


def _fmt_int(value: int | float | None) -> str:
    """Format an integer with comma separators, returning '--' for None."""
    if value is None:
        return "--"
    return f"{int(value):,}"


def _fmt_pvalue(p: float) -> str:
    """Format a p-value for LaTeX, using < 0.001 for very small values."""
    if p < 0.001:
        return "$< 0.001$"
    return f"{p:.3f}"


def _significance_marker(p: float) -> str:
    """Return a significance marker string for a p-value."""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def _config_display(config: str) -> str:
    """Convert config enum to display name for tables."""
    mapping = {
        "BASELINE": "Baseline",
        "MCP_BASE": "MCP-Base",
        "MCP_FULL": "MCP-Full",
    }
    return mapping.get(config, config)


# ---------------------------------------------------------------------------
# Table generators
# ---------------------------------------------------------------------------


def generate_table_aggregate(aggregate_metrics: list[dict]) -> str:
    """Generate table_aggregate.tex: config | pass rate | mean reward | median duration | mean tokens with SE.

    Args:
        aggregate_metrics: List of ConfigAggregateMetrics dicts from analysis_results.json.

    Returns:
        LaTeX table string.
    """
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{Aggregate performance metrics by agent configuration.}",
        r"  \label{tab:aggregate}",
        r"  \begin{tabular}{lcccc}",
        r"    \toprule",
        r"    Configuration & Pass Rate & Mean Reward & Median Duration (s) & Mean Tokens (In / Out) \\",
        r"    \midrule",
    ]

    for m in sorted(aggregate_metrics, key=lambda x: x.get("config", "")):
        config = _config_display(m.get("config", ""))
        pass_rate = m.get("pass_rate", 0.0)
        se_pass = m.get("se_pass_rate", 0.0)
        mean_reward = m.get("mean_reward", 0.0)
        se_reward = m.get("se_reward", 0.0)
        median_dur = m.get("median_duration_seconds")
        mean_in = m.get("mean_input_tokens", 0.0)
        mean_out = m.get("mean_output_tokens", 0.0)

        dur_str = _fmt_float(median_dur, 1)
        tokens_str = f"{_fmt_int(mean_in)} / {_fmt_int(mean_out)}"

        lines.append(
            f"    {config} & "
            f"{_fmt_float(pass_rate)} $\\pm$ {_fmt_float(se_pass)} & "
            f"{_fmt_float(mean_reward)} $\\pm$ {_fmt_float(se_reward)} & "
            f"{dur_str} & "
            f"{tokens_str} \\\\"
        )

    lines.extend([
        r"    \bottomrule",
        r"  \end{tabular}",
        r"\end{table}",
    ])

    return "\n".join(lines) + "\n"


def generate_table_per_benchmark(
    per_benchmark: list[dict],
    per_benchmark_significance: list[dict],
) -> str:
    """Generate table_per_benchmark.tex: benchmark | config | pass rate | reward | significance marker.

    Args:
        per_benchmark: List of BenchmarkConfigMetrics dicts.
        per_benchmark_significance: List of BenchmarkSignificanceResult dicts.

    Returns:
        LaTeX table string.
    """
    # Build significance lookup: (benchmark, config_a, config_b, metric) -> p_value
    sig_lookup: dict[tuple[str, str], float] = {}
    for sig in per_benchmark_significance:
        if sig.get("metric") == "reward":
            benchmark = sig.get("benchmark", "")
            # Store the minimum p-value across all pairs for this benchmark
            key = (benchmark, sig.get("config_a", ""))
            existing = sig_lookup.get(key, 1.0)
            sig_lookup[key] = min(existing, sig.get("p_value", 1.0))
            key_b = (benchmark, sig.get("config_b", ""))
            existing_b = sig_lookup.get(key_b, 1.0)
            sig_lookup[key_b] = min(existing_b, sig.get("p_value", 1.0))

    # Group by benchmark
    benchmarks: dict[str, list[dict]] = {}
    for entry in per_benchmark:
        bm = entry.get("benchmark", "unknown")
        if bm not in benchmarks:
            benchmarks[bm] = []
        benchmarks[bm].append(entry)

    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{Per-benchmark performance by configuration. Significance markers: * $p < 0.05$, ** $p < 0.01$, *** $p < 0.001$.}",
        r"  \label{tab:per_benchmark}",
        r"  \begin{tabular}{llcccc}",
        r"    \toprule",
        r"    Benchmark & Configuration & $n$ & Pass Rate & Mean Reward & Sig. \\",
        r"    \midrule",
    ]

    for bm_name in sorted(benchmarks.keys()):
        entries = sorted(benchmarks[bm_name], key=lambda x: x.get("config", ""))
        first_row = True
        for entry in entries:
            config = _config_display(entry.get("config", ""))
            n = entry.get("n_trials", 0)
            pass_rate = _fmt_float(entry.get("pass_rate", 0.0))
            mean_reward = _fmt_float(entry.get("mean_reward", 0.0))
            se_reward = _fmt_float(entry.get("se_reward", 0.0))

            p_val = sig_lookup.get((bm_name, entry.get("config", "")), 1.0)
            sig_mark = _significance_marker(p_val)

            bm_display = bm_name if first_row else ""
            first_row = False

            lines.append(
                f"    {bm_display} & {config} & {n} & "
                f"{pass_rate} & {mean_reward} $\\pm$ {se_reward} & "
                f"{sig_mark} \\\\"
            )
        lines.append(r"    \midrule")

    # Remove trailing midrule and replace with bottomrule
    if lines and lines[-1] == r"    \midrule":
        lines[-1] = r"    \bottomrule"

    lines.extend([
        r"  \end{tabular}",
        r"\end{table}",
    ])

    return "\n".join(lines) + "\n"


def generate_table_significance(
    pairwise_tests: list[dict],
    effect_sizes: list[dict],
) -> str:
    """Generate table_significance.tex: pair | metric | p-value | effect size | interpretation.

    Args:
        pairwise_tests: List of PairwiseTestResult dicts.
        effect_sizes: List of EffectSizeResult dicts.

    Returns:
        LaTeX table string.
    """
    # Build effect size lookup: (config_a, config_b, metric) -> EffectSizeResult dict
    es_lookup: dict[tuple[str, str, str], dict] = {}
    for es in effect_sizes:
        key = (es.get("config_a", ""), es.get("config_b", ""), es.get("metric", ""))
        es_lookup[key] = es

    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{Pairwise statistical tests with effect sizes.}",
        r"  \label{tab:significance}",
        r"  \begin{tabular}{llcccl}",
        r"    \toprule",
        r"    Pair & Metric & $p$-value & Cohen's $d$ & Sig. & Interpretation \\",
        r"    \midrule",
    ]

    for test in sorted(
        pairwise_tests,
        key=lambda x: (x.get("config_a", ""), x.get("config_b", ""), x.get("metric", "")),
    ):
        config_a = test.get("config_a", "")
        config_b = test.get("config_b", "")
        metric = test.get("metric", "")
        p_val = test.get("p_value", 1.0)

        pair_str = f"{_config_display(config_a)} vs {_config_display(config_b)}"
        sig_mark = _significance_marker(p_val)

        es_key = (config_a, config_b, metric)
        es_entry = es_lookup.get(es_key, {})
        cohens_d = es_entry.get("cohens_d")
        interpretation = es_entry.get("interpretation", "--")

        d_str = _fmt_float(cohens_d) if cohens_d is not None else "--"

        lines.append(
            f"    {pair_str} & {metric} & "
            f"{_fmt_pvalue(p_val)} & {d_str} & "
            f"{sig_mark} & {interpretation} \\\\"
        )

    lines.extend([
        r"    \bottomrule",
        r"  \end{tabular}",
        r"\end{table}",
    ])

    return "\n".join(lines) + "\n"


def generate_table_efficiency(efficiency: list[dict]) -> str:
    """Generate table_efficiency.tex: config | input tokens | output tokens | tokens per success | fill rate.

    Args:
        efficiency: List of EfficiencyMetrics dicts from analysis_results.json.

    Returns:
        LaTeX table string.
    """
    # Get fill rate from tool_utilization if available; efficiency doesn't have it directly
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{Token efficiency metrics by configuration.}",
        r"  \label{tab:efficiency}",
        r"  \begin{tabular}{lccccc}",
        r"    \toprule",
        r"    Configuration & Mean Input Tokens & Mean Output Tokens & Tokens / Success & I/O Ratio & MCP Overhead \\",
        r"    \midrule",
    ]

    for m in sorted(efficiency, key=lambda x: x.get("config", "")):
        config = _config_display(m.get("config", ""))
        mean_in = m.get("mean_input_tokens", 0.0)
        se_in = m.get("se_input_tokens", 0.0)
        mean_out = m.get("mean_output_tokens", 0.0)
        se_out = m.get("se_output_tokens", 0.0)
        tps = m.get("tokens_per_success")
        io_ratio = m.get("input_to_output_ratio")
        overhead = m.get("mcp_token_overhead")

        lines.append(
            f"    {config} & "
            f"{_fmt_int(mean_in)} $\\pm$ {_fmt_int(se_in)} & "
            f"{_fmt_int(mean_out)} $\\pm$ {_fmt_int(se_out)} & "
            f"{_fmt_int(tps)} & "
            f"{_fmt_float(io_ratio, 1)} & "
            f"{_fmt_int(overhead)} \\\\"
        )

    lines.extend([
        r"    \bottomrule",
        r"  \end{tabular}",
        r"\end{table}",
    ])

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Figure generators
# ---------------------------------------------------------------------------


def _get_colorblind_colors(n: int) -> list[tuple[float, ...]]:
    """Get n colors from the tableau-colorblind10 palette."""
    cmap = plt.get_cmap(_PALETTE)
    return [cmap(i / max(n - 1, 1)) for i in range(n)]


def _ordered_configs(configs: list[str]) -> list[str]:
    """Sort configs in canonical order, with unknowns at the end."""
    order = {c: i for i, c in enumerate(_CONFIG_ORDER)}
    return sorted(configs, key=lambda c: order.get(c, 999))


def generate_fig_pass_rate(aggregate_metrics: list[dict], output_dir: Path) -> list[str]:
    """Generate grouped bar chart of pass rate by config with SE error bars.

    Returns list of written file paths.
    """
    if not aggregate_metrics:
        return []

    configs = _ordered_configs([m["config"] for m in aggregate_metrics])
    config_lookup = {m["config"]: m for m in aggregate_metrics}
    colors = _get_colorblind_colors(len(configs))

    with plt.style.context(_STYLE):
        fig, ax = plt.subplots(figsize=(6, 4))

        x = np.arange(len(configs))
        pass_rates = [config_lookup[c].get("pass_rate", 0.0) for c in configs]
        se_values = [config_lookup[c].get("se_pass_rate", 0.0) for c in configs]
        labels = [_CONFIG_LABELS.get(c, c) for c in configs]

        bars = ax.bar(x, pass_rates, yerr=se_values, capsize=4,
                      color=colors[:len(configs)], edgecolor="black", linewidth=0.5)

        ax.set_xlabel("Configuration")
        ax.set_ylabel("Pass Rate")
        ax.set_title("Pass Rate by Agent Configuration")
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylim(0, min(max(pass_rates) * 1.3 + 0.05, 1.05))

        fig.tight_layout()

        written: list[str] = []
        for ext in ("pdf", "svg"):
            path = output_dir / f"fig_pass_rate.{ext}"
            fig.savefig(path, dpi=_FIG_DPI, bbox_inches="tight")
            written.append(str(path))

        plt.close(fig)
    return written


def generate_fig_benchmark_heatmap(per_benchmark: list[dict], output_dir: Path) -> list[str]:
    """Generate heatmap of reward delta (MCP-Full minus Baseline) per benchmark.

    Returns list of written file paths.
    """
    if not per_benchmark:
        return []

    # Group by benchmark -> config -> mean_reward
    bm_config_reward: dict[str, dict[str, float]] = {}
    for entry in per_benchmark:
        bm = entry.get("benchmark", "unknown")
        config = entry.get("config", "UNKNOWN")
        reward = entry.get("mean_reward", 0.0)
        if bm not in bm_config_reward:
            bm_config_reward[bm] = {}
        bm_config_reward[bm][config] = reward

    # Compute deltas: MCP_FULL - BASELINE for each benchmark
    benchmarks = sorted(bm_config_reward.keys())
    deltas: list[float] = []
    valid_benchmarks: list[str] = []
    for bm in benchmarks:
        baseline_r = bm_config_reward[bm].get("BASELINE")
        mcp_full_r = bm_config_reward[bm].get("MCP_FULL")
        if baseline_r is not None and mcp_full_r is not None:
            deltas.append(mcp_full_r - baseline_r)
            valid_benchmarks.append(bm)

    if not valid_benchmarks:
        return []

    with plt.style.context(_STYLE):
        fig, ax = plt.subplots(figsize=(8, max(2, len(valid_benchmarks) * 0.5 + 1)))

        data = np.array(deltas).reshape(-1, 1)
        max_abs = max(abs(d) for d in deltas) if deltas else 0.1
        im = ax.imshow(data, cmap="RdYlGn", aspect="auto",
                       vmin=-max_abs, vmax=max_abs)

        ax.set_yticks(range(len(valid_benchmarks)))
        ax.set_yticklabels(valid_benchmarks)
        ax.set_xticks([0])
        ax.set_xticklabels(["Reward Delta\n(MCP-Full - Baseline)"])
        ax.set_title("Reward Delta per Benchmark")

        # Annotate cells
        for i, val in enumerate(deltas):
            color = "black" if abs(val) < max_abs * 0.6 else "white"
            ax.text(0, i, f"{val:+.3f}", ha="center", va="center",
                    color=color, fontsize=9)

        cbar = fig.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label("Reward Delta")

        fig.tight_layout()

        written: list[str] = []
        for ext in ("pdf", "svg"):
            path = output_dir / f"fig_benchmark_heatmap.{ext}"
            fig.savefig(path, dpi=_FIG_DPI, bbox_inches="tight")
            written.append(str(path))

        plt.close(fig)
    return written


def generate_fig_token_overhead(
    efficiency: list[dict],
    aggregate_metrics: list[dict],
) -> list[str]:
    """Generate scatter plot of token overhead vs reward improvement per config.

    Note: This operates at the config level (not per-task) since we don't have
    per-task paired data in analysis_results.json. Each point is a config.

    Returns list of written file paths (empty since no output_dir yet -- called
    from publish_figures which passes the dir).
    """
    # This is a stub -- the actual implementation is in _generate_fig_token_overhead
    return []


def _generate_fig_token_overhead(
    efficiency: list[dict],
    aggregate_metrics: list[dict],
    output_dir: Path,
) -> list[str]:
    """Generate scatter plot of token overhead vs reward improvement per config.

    Each point represents a non-BASELINE config. X-axis: MCP token overhead,
    Y-axis: reward improvement over BASELINE.
    """
    if not efficiency or not aggregate_metrics:
        return []

    # Get baseline reward
    agg_lookup = {m["config"]: m for m in aggregate_metrics}
    baseline_reward = agg_lookup.get("BASELINE", {}).get("mean_reward")
    if baseline_reward is None:
        return []

    points: list[tuple[float, float, str]] = []
    for eff in efficiency:
        config = eff.get("config", "")
        overhead = eff.get("mcp_token_overhead")
        if config == "BASELINE" or overhead is None:
            continue
        config_reward = agg_lookup.get(config, {}).get("mean_reward", 0.0)
        reward_delta = config_reward - baseline_reward
        points.append((overhead, reward_delta, config))

    if not points:
        return []

    colors = _get_colorblind_colors(len(points) + 1)

    with plt.style.context(_STYLE):
        fig, ax = plt.subplots(figsize=(6, 4))

        for i, (overhead, reward_delta, config) in enumerate(points):
            label = _CONFIG_LABELS.get(config, config)
            ax.scatter(overhead, reward_delta, s=100, c=[colors[i + 1]],
                       edgecolors="black", linewidth=0.5, label=label, zorder=5)

        ax.axhline(y=0, color="grey", linestyle="--", linewidth=0.8, alpha=0.7)
        ax.axvline(x=0, color="grey", linestyle="--", linewidth=0.8, alpha=0.7)

        ax.set_xlabel("Token Overhead (mean tokens vs Baseline)")
        ax.set_ylabel("Reward Improvement vs Baseline")
        ax.set_title("Token Overhead vs Reward Improvement")
        ax.legend()

        fig.tight_layout()

        written: list[str] = []
        for ext in ("pdf", "svg"):
            path = output_dir / f"fig_token_overhead.{ext}"
            fig.savefig(path, dpi=_FIG_DPI, bbox_inches="tight")
            written.append(str(path))

        plt.close(fig)
    return written


def generate_fig_tool_utilization(
    tool_utilization: list[dict],
    benchmark_tool_usage: list[dict],
    output_dir: Path,
) -> list[str]:
    """Generate stacked bar chart of tool call distribution by category per config.

    Categories: MCP calls, Deep Search calls, Other (total - MCP - deep_search).

    Returns list of written file paths.
    """
    if not tool_utilization:
        return []

    configs = _ordered_configs([m["config"] for m in tool_utilization])
    util_lookup = {m["config"]: m for m in tool_utilization}

    # Compute per-config: mcp calls (non-deep-search), deep search calls, and
    # we need total calls from benchmark_tool_usage aggregation
    # Since tool_utilization has mean_mcp_calls and mean_deep_search_calls,
    # compute other = total - mcp - deep_search from benchmark_tool_usage
    total_by_config: dict[str, float] = {}
    if benchmark_tool_usage:
        for config in configs:
            totals = [
                e.get("mean_total_tool_calls", 0.0)
                for e in benchmark_tool_usage
                if e.get("config") == config
            ]
            total_by_config[config] = sum(totals) / len(totals) if totals else 0.0

    colors = _get_colorblind_colors(3)

    with plt.style.context(_STYLE):
        fig, ax = plt.subplots(figsize=(6, 4))

        x = np.arange(len(configs))
        labels = [_CONFIG_LABELS.get(c, c) for c in configs]

        mcp_non_ds = []
        ds_calls = []
        other_calls = []

        for config in configs:
            m = util_lookup.get(config, {})
            mcp = m.get("mean_mcp_calls", 0.0)
            ds = m.get("mean_deep_search_calls", 0.0)
            total = total_by_config.get(config, mcp)
            # MCP calls that are NOT deep search
            mcp_non_deep = max(mcp - ds, 0.0)
            other = max(total - mcp, 0.0)

            mcp_non_ds.append(mcp_non_deep)
            ds_calls.append(ds)
            other_calls.append(other)

        bar_width = 0.5
        ax.bar(x, other_calls, bar_width, label="Local/Other", color=colors[0],
               edgecolor="black", linewidth=0.5)
        ax.bar(x, mcp_non_ds, bar_width, bottom=other_calls,
               label="MCP (keyword/NLS)", color=colors[1],
               edgecolor="black", linewidth=0.5)
        bottom_ds = [o + m for o, m in zip(other_calls, mcp_non_ds)]
        ax.bar(x, ds_calls, bar_width, bottom=bottom_ds,
               label="Deep Search", color=colors[2],
               edgecolor="black", linewidth=0.5)

        ax.set_xlabel("Configuration")
        ax.set_ylabel("Mean Tool Calls")
        ax.set_title("Tool Call Distribution by Configuration")
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.legend(loc="upper left")

        fig.tight_layout()

        written: list[str] = []
        for ext in ("pdf", "svg"):
            path = output_dir / f"fig_tool_utilization.{ext}"
            fig.savefig(path, dpi=_FIG_DPI, bbox_inches="tight")
            written.append(str(path))

        plt.close(fig)
    return written


# ---------------------------------------------------------------------------
# Figure publish orchestrator
# ---------------------------------------------------------------------------


def publish_figures(analysis_results: dict, output_dir: Path) -> list[str]:
    """Generate all publication figures and write to output_dir/figures/.

    Args:
        analysis_results: Parsed analysis_results.json dict.
        output_dir: Root output directory (figures go in output_dir/figures/).

    Returns:
        List of file paths written.
    """
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []

    aggregate = analysis_results.get("aggregate_metrics") or []
    per_benchmark = analysis_results.get("per_benchmark") or []
    efficiency = analysis_results.get("efficiency") or []
    tool_util = analysis_results.get("tool_utilization") or []
    bench_tool = analysis_results.get("benchmark_tool_usage") or []

    # Fig 1: Pass rate bar chart
    written.extend(generate_fig_pass_rate(aggregate, figures_dir))

    # Fig 2: Benchmark heatmap
    written.extend(generate_fig_benchmark_heatmap(per_benchmark, figures_dir))

    # Fig 3: Token overhead scatter
    written.extend(_generate_fig_token_overhead(efficiency, aggregate, figures_dir))

    # Fig 4: Tool utilization stacked bar
    written.extend(generate_fig_tool_utilization(tool_util, bench_tool, figures_dir))

    return written


# ---------------------------------------------------------------------------
# Main publish pipeline
# ---------------------------------------------------------------------------


def publish_tables(analysis_results: dict, output_dir: Path) -> list[str]:
    """Generate all LaTeX tables and write to output_dir/tables/.

    Args:
        analysis_results: Parsed analysis_results.json dict.
        output_dir: Root output directory (tables go in output_dir/tables/).

    Returns:
        List of file paths written.
    """
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []

    # Table 1: Aggregate metrics
    aggregate = analysis_results.get("aggregate_metrics") or []
    if aggregate:
        content = generate_table_aggregate(aggregate)
        path = tables_dir / "table_aggregate.tex"
        path.write_text(content, encoding="utf-8")
        written.append(str(path))

    # Table 2: Per-benchmark
    per_benchmark = analysis_results.get("per_benchmark") or []
    per_benchmark_sig = analysis_results.get("per_benchmark_significance") or []
    if per_benchmark:
        content = generate_table_per_benchmark(per_benchmark, per_benchmark_sig)
        path = tables_dir / "table_per_benchmark.tex"
        path.write_text(content, encoding="utf-8")
        written.append(str(path))

    # Table 3: Significance tests
    pairwise = analysis_results.get("pairwise_tests") or []
    effect_sizes = analysis_results.get("effect_sizes") or []
    if pairwise:
        content = generate_table_significance(pairwise, effect_sizes)
        path = tables_dir / "table_significance.tex"
        path.write_text(content, encoding="utf-8")
        written.append(str(path))

    # Table 4: Efficiency
    efficiency = analysis_results.get("efficiency") or []
    if efficiency:
        content = generate_table_efficiency(efficiency)
        path = tables_dir / "table_efficiency.tex"
        path.write_text(content, encoding="utf-8")
        written.append(str(path))

    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the publish step."""
    parser = argparse.ArgumentParser(
        description="Generate publication artifacts (LaTeX tables and figures) from analysis results.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("output/analysis_results.json"),
        help="Path to analysis_results.json (default: output/analysis_results.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Root output directory (default: output/)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    input_path: Path = args.input
    output_dir: Path = args.output_dir

    if not input_path.is_file():
        logger.error("Input file does not exist: %s", input_path)
        return 1

    try:
        analysis_results = json.loads(input_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read input file: %s", exc)
        return 1

    if not isinstance(analysis_results, dict):
        logger.error("Input must be a JSON object")
        return 1

    logger.info("Generating publication artifacts from: %s", input_path)

    # Generate tables
    table_files = publish_tables(analysis_results, output_dir)
    logger.info("Generated %d table files", len(table_files))
    for tf in table_files:
        logger.info("  -> %s", tf)

    # Generate figures
    figure_files = publish_figures(analysis_results, output_dir)
    logger.info("Generated %d figure files", len(figure_files))
    for ff in figure_files:
        logger.info("  -> %s", ff)

    logger.info("Publication artifacts written to: %s", output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
