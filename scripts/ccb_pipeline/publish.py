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

logger = logging.getLogger(__name__)


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

    logger.info("Publication artifacts written to: %s", output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
