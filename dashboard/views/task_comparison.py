"""
Task Comparison View

Baseline vs MCP side-by-side comparison, powered by experiment_metrics.json
(same data source as Results Explorer).  Pick a task and see metrics,
status, token counts, and the full judge context for each variant.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.utils.agent_labels import display_name

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "output"

# Config values treated as baseline
_BASELINE_CONFIGS = {"BASELINE"}

# Human-readable labels for agent_config values
_CONFIG_DISPLAY: dict[str, str] = {
    "BASELINE": "Baseline",
    "MCP_BASE": "Sourcegraph Base",
    "MCP_FULL": "Sourcegraph Full",
}

# Canonical display names for programming languages
_LANGUAGE_DISPLAY: dict[str, str] = {
    "c": "C",
    "cpp": "C++",
    "csharp": "C#",
    "go": "Go",
    "java": "Java",
    "javascript": "JavaScript",
    "python": "Python",
    "rust": "Rust",
    "typescript": "TypeScript",
}


def _display_language(raw: str) -> str:
    """Map a raw language identifier to its display name."""
    return _LANGUAGE_DISPLAY.get(raw, raw.title() if raw != "unknown" else "unknown")


def _config_tab_label(config: str) -> str:
    """Map an agent_config value to a human-readable label."""
    return _CONFIG_DISPLAY.get(config, config.replace("_", " ").title() if config else "Variant")


# ---------------------------------------------------------------------------
# Data loading  (shared format with Results Explorer)
# ---------------------------------------------------------------------------


def _load_experiment_metrics(output_dir: Path) -> list[dict]:
    metrics_path = output_dir / "experiment_metrics.json"
    if not metrics_path.is_file():
        return []
    try:
        data = json.loads(metrics_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _flatten_trials(categories: list[dict]) -> list[dict]:
    trials: list[dict] = []
    for category in categories:
        run_cat = category.get("run_category", "unknown")
        for experiment in category.get("experiments", []):
            exp_id = experiment.get("experiment_id", "unknown")
            for trial in experiment.get("trials", []):
                trials.append({**trial, "run_category": run_cat, "experiment_id": exp_id})
    return trials


# ---------------------------------------------------------------------------
# Pair matching
# ---------------------------------------------------------------------------


def _build_task_pairs(
    trials: list[dict],
) -> dict[str, dict[str, list[dict]]]:
    """Group trials by task_name, then by config role (baseline / variant).

    Returns ``{task_name: {"baseline": [...], "variant": [...]}}``
    where each list contains the trial dicts for that role.
    """
    by_task: dict[str, dict[str, list[dict]]] = defaultdict(
        lambda: {"baseline": [], "variant": []}
    )
    for trial in trials:
        config = trial.get("agent_config", "")
        role = "baseline" if config in _BASELINE_CONFIGS else "variant"
        by_task[trial.get("task_name", "unknown")][role].append(trial)
    return dict(by_task)


def _pick_best_pair(
    sides: dict[str, list[dict]],
) -> tuple[dict, dict] | None:
    """Select one baseline and one variant trial for comparison.

    Prefers trials from the same experiment.  If multiple experiments,
    picks the pair with the most recent experiment_id (alphabetical last).
    """
    baselines = sides.get("baseline", [])
    variants = sides.get("variant", [])
    if not baselines or not variants:
        return None

    # Try same-experiment first
    bl_by_exp = {t["experiment_id"]: t for t in baselines}
    for v in sorted(variants, key=lambda t: t["experiment_id"], reverse=True):
        if v["experiment_id"] in bl_by_exp:
            return (bl_by_exp[v["experiment_id"]], v)

    # Fall back to most recent of each
    bl = sorted(baselines, key=lambda t: t["experiment_id"], reverse=True)[0]
    vr = sorted(variants, key=lambda t: t["experiment_id"], reverse=True)[0]
    return (bl, vr)


# ---------------------------------------------------------------------------
# Comparison table dataframe
# ---------------------------------------------------------------------------


def _build_comparison_df(
    paired: dict[str, tuple[dict, dict]],
) -> pd.DataFrame:
    rows = []
    for task_name, (bl, vr) in paired.items():
        bl_reward = bl.get("reward")
        vr_reward = vr.get("reward")
        delta = None
        if bl_reward is not None and vr_reward is not None:
            delta = vr_reward - bl_reward

        raw_lang = bl.get("language") or "unknown"
        rows.append({
            "task_name": task_name,
            "benchmark": bl.get("benchmark", "unknown"),
            "language": _display_language(raw_lang),
            "difficulty": bl.get("difficulty") or "unknown",
            "bl_status": bl.get("pass_fail", "unknown"),
            "vr_status": vr.get("pass_fail", "unknown"),
            "bl_reward": bl_reward,
            "vr_reward": vr_reward,
            "reward_delta": delta,
            "bl_input_tokens": bl.get("input_tokens", 0),
            "vr_input_tokens": vr.get("input_tokens", 0),
            "bl_output_tokens": bl.get("output_tokens", 0),
            "vr_output_tokens": vr.get("output_tokens", 0),
            "bl_duration": bl.get("duration_seconds"),
            "vr_duration": vr.get("duration_seconds"),
            "bl_instance_dir": bl.get("instance_dir", ""),
            "vr_instance_dir": vr.get("instance_dir", ""),
            "bl_config": bl.get("agent_config", "BASELINE"),
            "vr_config": vr.get("agent_config", ""),
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def _checkbox_group(
    label: str, options: list[str], key_prefix: str,
) -> list[str]:
    """Render a labeled group of checkboxes and return selected values."""
    st.markdown(f"**{label}**")
    selected: list[str] = []
    for option in options:
        if st.checkbox(option, key=f"{key_prefix}_{option}"):
            selected.append(option)
    return selected


def _render_filters(df: pd.DataFrame) -> pd.DataFrame:
    search = st.text_input(
        "Search tasks", placeholder="Filter by task name...", key="tc_search"
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        benchmarks = sorted(df["benchmark"].unique().tolist())
        sel_bench = _checkbox_group("Benchmark", benchmarks, "tc_f_bench")
    with c2:
        outcomes = sorted(
            set(df["bl_status"].unique().tolist() + df["vr_status"].unique().tolist())
            - {"unknown"}
        )
        sel_outcome = _checkbox_group(
            "Outcome (either side)", outcomes, "tc_f_outcome",
        )
    with c3:
        languages = sorted(
            v for v in df["language"].unique().tolist() if v != "unknown"
        )
        sel_lang = _checkbox_group("Language", languages, "tc_f_lang")
    with c4:
        difficulties = sorted(
            v for v in df["difficulty"].unique().tolist() if v != "unknown"
        )
        sel_diff = _checkbox_group("Difficulty", difficulties, "tc_f_diff")

    mask = pd.Series(True, index=df.index)
    if sel_bench:
        mask = mask & df["benchmark"].isin(sel_bench)
    if sel_outcome:
        mask = mask & (df["bl_status"].isin(sel_outcome) | df["vr_status"].isin(sel_outcome))
    if sel_lang:
        mask = mask & df["language"].isin(sel_lang)
    if sel_diff:
        mask = mask & df["difficulty"].isin(sel_diff)
    if search.strip():
        mask = mask & df["task_name"].str.contains(search.strip(), case=False, na=False)

    return df[mask]


# ---------------------------------------------------------------------------
# Overview table
# ---------------------------------------------------------------------------

_TABLE_COLS = [
    "task_name", "benchmark", "language", "difficulty",
    "bl_status", "vr_status", "bl_reward", "vr_reward", "reward_delta",
    "bl_input_tokens", "vr_input_tokens",
]

def _table_rename(variant_label: str) -> dict[str, str]:
    """Build column rename map with dynamic variant label."""
    return {
        "task_name": "Task",
        "benchmark": "Benchmark",
        "language": "Language",
        "difficulty": "Difficulty",
        "bl_status": "Baseline Status",
        "vr_status": f"{variant_label} Status",
        "bl_reward": "Baseline Reward",
        "vr_reward": f"{variant_label} Reward",
        "reward_delta": "Reward Delta",
        "bl_input_tokens": "Baseline Tokens",
        "vr_input_tokens": f"{variant_label} Tokens",
    }


def _render_overview_table(filtered: pd.DataFrame, variant_label: str) -> int | None:
    """Render the paired-task overview table. Returns selected row index."""
    if filtered.empty:
        st.warning("No paired tasks match the filters.")
        return None

    st.caption("Click a row to view task details below.")

    event = st.dataframe(
        filtered[_TABLE_COLS].rename(columns=_table_rename(variant_label)),
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="tc_table_select",
    )

    selected_rows = event.selection.rows
    if selected_rows:
        return selected_rows[0]
    return None


# ---------------------------------------------------------------------------
# Detail panel  (side-by-side comparison + judge context)
# ---------------------------------------------------------------------------


def _render_detail_panel(filtered: pd.DataFrame, selected_idx: int | None) -> None:
    if filtered.empty or selected_idx is None:
        return

    st.markdown("### Task Detail")

    row = filtered.iloc[selected_idx]

    # Derive dynamic labels from config columns
    bl_label = _config_tab_label(row.get("bl_config", "BASELINE"))
    vr_label = _config_tab_label(row.get("vr_config", ""))

    # Show which task is selected
    delta_str = ""
    if row["reward_delta"] is not None:
        delta_str = f"  |  Reward delta: {row['reward_delta']:+.2f}"
    st.caption(f"Viewing: {row['task_name']}{delta_str}")

    # --- Side-by-side metrics ---
    st.markdown("#### Metrics Comparison")
    col_bl, col_vr = st.columns(2)

    with col_bl:
        st.markdown(f"**{bl_label}**")
        _render_side_metrics(row, "bl")

    with col_vr:
        st.markdown(f"**{vr_label}**")
        _render_side_metrics(row, "vr")

    st.markdown("---")

    # --- Judge context tabs ---
    st.markdown("#### Judge Context")
    st.caption("This is the context that would be passed to the LLM judge for evaluation.")

    tab_names = [
        "Task Description",
        f"{bl_label} Output",
        f"{vr_label} Output",
        "Token Metrics",
        "Judge Evaluation",
    ]
    tab_instruction, tab_bl_out, tab_vr_out, tab_metrics_detail, tab_judge = st.tabs(
        tab_names
    )

    # Load task instances on demand
    bl_data = _load_side_data(row["bl_instance_dir"])
    vr_data = _load_side_data(row["vr_instance_dir"])

    with tab_instruction:
        _render_instruction_tab(bl_data, vr_data, row)

    with tab_bl_out:
        _render_output_tab(bl_data, bl_label)

    with tab_vr_out:
        _render_output_tab(vr_data, vr_label)

    with tab_metrics_detail:
        _render_full_metrics_tab(bl_data, vr_data, row)

    with tab_judge:
        _render_judge_tab(bl_data, vr_data, row, bl_label, vr_label)


def _render_side_metrics(row: pd.Series, prefix: str) -> None:
    reward = row[f"{prefix}_reward"]
    reward_str = f"{reward:.2f}" if reward is not None else "N/A"
    dur = row[f"{prefix}_duration"]
    dur_str = f"{dur:.0f}s" if dur is not None else "N/A"

    m1, m2 = st.columns(2)
    m1.metric("Reward", reward_str)
    m2.metric("Status", row[f"{prefix}_status"])

    m3, m4 = st.columns(2)
    m3.metric("Input Tokens", f"{row[f'{prefix}_input_tokens']:,}")
    m4.metric("Duration", dur_str)


def _load_instruction_text(instance_dir: str) -> str:
    """Read instruction.txt from a trial instance directory."""
    if not instance_dir:
        return ""
    path = Path(instance_dir) / "instruction.txt"
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:5000]
    except OSError:
        return ""


def _load_mcp_config(instance_dir: str) -> dict | None:
    """Read .mcp.json from a trial instance directory."""
    if not instance_dir:
        return None
    # Check agent/sessions/.mcp.json (Harbor convention) then agent/.mcp.json
    for sub in ("agent/sessions/.mcp.json", "agent/.mcp.json"):
        path = Path(instance_dir) / sub
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
    return None


def _load_side_data(instance_dir: str) -> object | None:
    if not instance_dir or not Path(instance_dir).is_dir():
        return None
    try:
        from dashboard.utils.judge_task_loader import load_task_instance
        return load_task_instance(Path(instance_dir))
    except Exception as exc:
        logger.warning("Failed to load instance from %s: %s", instance_dir, exc)
        return None


def _render_instruction_tab(bl_data: object | None, vr_data: object | None, row: pd.Series) -> None:
    source = bl_data or vr_data
    if source is None:
        st.info("Run directories not found. Cannot load task instruction.")
        return

    # Side-by-side instructions from instruction.txt
    bl_instruction = _load_instruction_text(row.get("bl_instance_dir", ""))
    vr_instruction = _load_instruction_text(row.get("vr_instance_dir", ""))

    if bl_instruction or vr_instruction:
        st.markdown("**Per-Side Instructions**")
        col_bl, col_vr = st.columns(2)
        bl_label = _config_tab_label(row.get("bl_config", "BASELINE"))
        vr_label = _config_tab_label(row.get("vr_config", ""))

        with col_bl:
            st.markdown(f"*{bl_label} Instruction*")
            if bl_instruction:
                st.code(bl_instruction, language="markdown")
            else:
                st.caption("No instruction.txt found")

        with col_vr:
            st.markdown(f"*{vr_label} Instruction*")
            if vr_instruction:
                st.code(vr_instruction, language="markdown")
            else:
                st.caption("No instruction.txt found")

        # MCP configuration (if variant has one)
        vr_mcp = _load_mcp_config(row.get("vr_instance_dir", ""))
        if vr_mcp:
            with st.expander("MCP Configuration"):
                st.json(vr_mcp)
    else:
        # Fall back to decoded task description
        st.markdown("**Task Description**")
        desc = getattr(source, "task_description", "N/A")
        st.text(desc[:4000])

    # Metadata
    st.markdown("**Task Metadata**")
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Language", row.get("language", "N/A"))
    mc2.metric("Difficulty", row.get("difficulty", "N/A"))
    mc3.metric("Benchmark", row.get("benchmark", "N/A"))
    task_cat = getattr(source, "task_category", "") or "N/A"
    mc4.metric("Category", task_cat)

    # Oracle / ground truth
    oracle = getattr(source, "oracle_data", None) or {}
    ground_truth = oracle.get("ground_truth", "")
    expected_approach = oracle.get("expected_approach", "")
    eval_criteria = oracle.get("evaluation_criteria", "")

    if ground_truth or expected_approach or eval_criteria:
        st.markdown("**Oracle Reference Data**")
        if expected_approach:
            st.markdown("*Expected Approach:*")
            st.text(str(expected_approach)[:2000])
        if eval_criteria:
            st.markdown("*Evaluation Criteria:*")
            st.text(str(eval_criteria)[:2000])
        if ground_truth:
            st.markdown("*Ground Truth:*")
            st.text(str(ground_truth)[:2000])


def _render_output_tab(data: object | None, label: str) -> None:
    if data is None:
        st.info(f"{label} run directory not found.")
        return

    # Solution content
    solution_type = getattr(data, "solution_type", "none")
    st.caption(f"Solution source: {solution_type}")

    solution = getattr(data, "effective_solution", "")
    if solution and solution != "No solution extracted from agent output":
        st.code(solution[:10000], language="diff")
    else:
        st.info(f"No solution content for {label}.")

    # Tool usage
    tool_counts = getattr(data, "tool_counts", {})
    if tool_counts:
        mcp_tools = {k: v for k, v in tool_counts.items()
                     if "mcp" in k.lower() or "sourcegraph" in k.lower()}
        local_tools = {k: v for k, v in tool_counts.items()
                       if k not in mcp_tools}

        tc1, tc2 = st.columns(2)
        with tc1:
            st.markdown("**Local Tools**")
            if local_tools:
                local_df = pd.DataFrame(
                    sorted(local_tools.items(), key=lambda x: x[1], reverse=True),
                    columns=["Tool", "Count"],
                )
                st.dataframe(local_df, use_container_width=True, hide_index=True)
        with tc2:
            st.markdown("**MCP Tools**")
            if mcp_tools:
                mcp_df = pd.DataFrame(
                    sorted(mcp_tools.items(), key=lambda x: x[1], reverse=True),
                    columns=["Tool", "Count"],
                )
                st.dataframe(mcp_df, use_container_width=True, hide_index=True)
            else:
                st.caption("None")


def _render_full_metrics_tab(
    bl_data: object | None, vr_data: object | None, row: pd.Series
) -> None:
    vr_label = _config_tab_label(row.get("vr_config", ""))
    st.markdown("**Side-by-Side Token Breakdown**")

    cols = ["Metric", "Baseline", vr_label, "Delta"]
    metrics_rows = []

    def _tok(data: object | None, attr: str) -> int:
        return getattr(data, attr, 0) if data else 0

    bl_in = _tok(bl_data, "input_tokens")
    vr_in = _tok(vr_data, "input_tokens")
    metrics_rows.append(["Input Tokens", f"{bl_in:,}", f"{vr_in:,}", f"{vr_in - bl_in:+,}"])

    bl_out = _tok(bl_data, "output_tokens")
    vr_out = _tok(vr_data, "output_tokens")
    metrics_rows.append(["Output Tokens", f"{bl_out:,}", f"{vr_out:,}", f"{vr_out - bl_out:+,}"])

    bl_cc = _tok(bl_data, "cache_creation_tokens")
    vr_cc = _tok(vr_data, "cache_creation_tokens")
    metrics_rows.append(["Cache Creation", f"{bl_cc:,}", f"{vr_cc:,}", f"{vr_cc - bl_cc:+,}"])

    bl_cr = _tok(bl_data, "cache_read_tokens")
    vr_cr = _tok(vr_data, "cache_read_tokens")
    metrics_rows.append(["Cache Read", f"{bl_cr:,}", f"{vr_cr:,}", f"{vr_cr - bl_cr:+,}"])

    df_tok = pd.DataFrame(metrics_rows, columns=cols)
    st.dataframe(df_tok, use_container_width=True, hide_index=True)

    # Duration comparison
    st.markdown("**Timing**")
    bl_dur = row.get("bl_duration")
    vr_dur = row.get("vr_duration")
    dc1, dc2, dc3 = st.columns(3)
    dc1.metric("Baseline Duration", f"{bl_dur:.0f}s" if bl_dur is not None else "N/A")
    dc2.metric(f"{vr_label} Duration", f"{vr_dur:.0f}s" if vr_dur is not None else "N/A")
    if bl_dur is not None and vr_dur is not None:
        dc3.metric("Duration Delta", f"{vr_dur - bl_dur:+.0f}s")

    # Reward comparison
    st.markdown("**Reward**")
    rc1, rc2, rc3 = st.columns(3)
    bl_r = row.get("bl_reward")
    vr_r = row.get("vr_reward")
    rc1.metric("Baseline", f"{bl_r:.2f}" if bl_r is not None else "N/A")
    rc2.metric(vr_label, f"{vr_r:.2f}" if vr_r is not None else "N/A")
    delta = row.get("reward_delta")
    rc3.metric("Delta", f"{delta:+.2f}" if delta is not None else "N/A")


def _render_judge_tab(
    bl_data: object | None,
    vr_data: object | None,
    row: pd.Series,
    bl_label: str,
    vr_label: str,
) -> None:
    """Render the Judge Evaluation tab with dimension selection and results."""
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.info(
            "ANTHROPIC_API_KEY not set. "
            "Add it to .env.local and restart the dashboard to enable judge evaluation."
        )
        return

    if bl_data is None or vr_data is None:
        st.info("Both baseline and variant run data are required for judge evaluation.")
        return

    task_name = row.get("task_name", "unknown")
    cache_key = f"tc_judge_{task_name}"

    # Dimension selection
    all_dims = ["correctness", "completeness", "retrieval_quality", "mcp_effectiveness", "code_quality"]
    default_dims = ["correctness", "completeness"]

    selected_dims = []
    dim_cols = st.columns(len(all_dims))
    for i, dim in enumerate(all_dims):
        with dim_cols[i]:
            checked = st.checkbox(
                dim.replace("_", " ").title(),
                value=dim in default_dims,
                key=f"tc_judge_dim_{task_name}_{dim}",
            )
            if checked:
                selected_dims.append(dim)

    if not selected_dims:
        st.warning("Select at least one dimension.")
        return

    # Run button
    if st.button("Run Judge Evaluation", key=f"tc_judge_run_{task_name}"):
        with st.spinner("Running LLM judge evaluation..."):
            try:
                from src.benchmark.llm_judge import EnhancedLLMJudge
                from dashboard.utils.judge_comparison import evaluate_pair

                judge = EnhancedLLMJudge(model="claude-haiku-4-5-20251001")
                result = evaluate_pair(
                    task_name=task_name,
                    baseline_run={"instance_dir": row["bl_instance_dir"]},
                    variant_run={"instance_dir": row["vr_instance_dir"]},
                    judge=judge,
                    dimensions=selected_dims,
                )
                st.session_state[cache_key] = result
            except Exception as exc:
                st.error(f"Judge evaluation failed: {exc}")
                return

    # Display cached results
    result = st.session_state.get(cache_key)
    if result is None:
        st.caption("Click 'Run Judge Evaluation' to score this task pair.")
        return

    if result.error:
        st.error(f"Judge error: {result.error}")

    # Score comparison table
    score_rows = []
    for dim in result.dimensions:
        bl_score = result.baseline_scores.get(dim, 0.0)
        vr_score = result.variant_scores.get(dim, 0.0)
        delta = result.score_deltas.get(dim, 0.0)
        score_rows.append({
            "Dimension": dim.replace("_", " ").title(),
            bl_label: f"{bl_score:.2f}",
            vr_label: f"{vr_score:.2f}",
            "Delta": f"{delta:+.2f}",
        })

    if score_rows:
        st.markdown("**Score Comparison**")
        st.dataframe(
            pd.DataFrame(score_rows),
            use_container_width=True,
            hide_index=True,
        )

    # Per-dimension reasoning expanders
    for dim in result.dimensions:
        dim_display = dim.replace("_", " ").title()
        with st.expander(f"{dim_display} Reasoning"):
            r_bl = result.baseline_reasoning.get(dim, "N/A")
            r_vr = result.variant_reasoning.get(dim, "N/A")
            rc1, rc2 = st.columns(2)
            with rc1:
                st.markdown(f"*{bl_label}*")
                st.text(str(r_bl)[:2000])
            with rc2:
                st.markdown(f"*{vr_label}*")
                st.text(str(r_vr)[:2000])

    st.caption(f"Judge model: {result.judge_model}")


# ---------------------------------------------------------------------------
# Summary bar
# ---------------------------------------------------------------------------


def _render_summary(df: pd.DataFrame, variant_label: str) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Paired Tasks", len(df))

    wins = (df["reward_delta"].dropna() > 0).sum()
    losses = (df["reward_delta"].dropna() < 0).sum()
    ties = (df["reward_delta"].dropna() == 0).sum()

    c2.metric(f"{variant_label} Wins", int(wins))
    c3.metric("Ties", int(ties))
    c4.metric(f"{variant_label} Losses", int(losses))

    deltas = df["reward_delta"].dropna()
    if len(deltas) > 0:
        mean_delta = deltas.mean()
        st.caption(f"Mean reward delta: {mean_delta:+.4f}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def show_task_comparison() -> None:
    st.title("Task Comparison")
    st.caption("Baseline vs MCP side-by-side. Filter tasks, then click a row to compare.")
    st.markdown("---")

    categories = _load_experiment_metrics(_DEFAULT_OUTPUT_DIR)
    if not categories:
        st.info(
            "No experiment_metrics.json found in output/ directory. "
            "Run the analysis pipeline from the Home page first."
        )
        return

    flat_trials = _flatten_trials(categories)
    if not flat_trials:
        st.warning("No trial data found.")
        return

    # Build pairs
    task_sides = _build_task_pairs(flat_trials)
    paired: dict[str, tuple[dict, dict]] = {}
    for task_name, sides in task_sides.items():
        pair = _pick_best_pair(sides)
        if pair is not None:
            paired[task_name] = pair

    if not paired:
        st.warning("No tasks have both a baseline and MCP variant run.")
        return

    comp_df = _build_comparison_df(paired)

    # Derive dominant variant label for summary/table headers
    if not comp_df.empty and "vr_config" in comp_df.columns:
        dominant_config = comp_df["vr_config"].mode()
        variant_label = _config_tab_label(dominant_config.iloc[0] if len(dominant_config) > 0 else "")
    else:
        variant_label = "Variant"

    # Summary
    _render_summary(comp_df, variant_label)

    st.markdown("---")

    # Filters + table
    filtered = _render_filters(comp_df)
    st.caption(f"Showing {len(filtered)} of {len(comp_df)} paired tasks")

    selected_idx = _render_overview_table(filtered, variant_label)

    st.markdown("---")

    # Detail panel (click a row above to populate)
    _render_detail_panel(filtered, selected_idx)
