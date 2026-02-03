"""Unified LLM Judge dashboard view.

Provides a Streamlit interface to configure, run, and analyze judge evaluations
across pairwise comparison, direct review, and reference-based modes. Supports
single-model and multi-model ensemble evaluation with results visualization.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_EXPERIMENTS_DIR = _PROJECT_ROOT / "eval_runs_v2" / "judge_experiments"
_TEMPLATES_DIR = _PROJECT_ROOT / "configs" / "judge_prompts"
_EXTERNAL_RUNS_DIR = Path(
    __import__("os").environ.get(
        "CCB_EXTERNAL_RUNS_DIR",
        str(Path.home() / "evals" / "custom_agents" / "agents" / "claudecode" / "runs"),
    )
)

# Available models for ensemble configuration
_AVAILABLE_MODELS = {
    "claude-sonnet-4-20250514": "Anthropic",
    "claude-haiku-4-5-20251001": "Anthropic",
    "gpt-4o": "OpenAI",
    "gpt-4o-mini": "OpenAI",
}

# Severity display colors
_SEVERITY_COLORS = {
    "critical": "#ff4b4b",
    "warning": "#ffa726",
    "suggestion": "#42a5f5",
    "praise": "#66bb6a",
}


def _load_experiment_results() -> list[dict[str, Any]]:
    """Load results from judge experiment directories."""
    results: list[dict[str, Any]] = []
    if not _EXPERIMENTS_DIR.is_dir():
        return results

    for exp_dir in sorted(_EXPERIMENTS_DIR.iterdir()):
        if not exp_dir.is_dir() or not exp_dir.name.startswith("exp_"):
            continue
        results_path = exp_dir / "results.json"
        config_path = exp_dir / "config.json"
        if not results_path.exists():
            continue
        try:
            with open(results_path) as f:
                data = json.load(f)
            config = {}
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
            results.append({
                "experiment_id": exp_dir.name,
                "config": config,
                "results": data.get("results", []),
                "path": str(exp_dir),
            })
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load experiment %s: %s", exp_dir.name, exc)

    return results


def _load_run_dirs() -> list[dict[str, Any]]:
    """Load available run directories with metadata."""
    runs: list[dict[str, Any]] = []
    if not _EXTERNAL_RUNS_DIR.is_dir():
        return runs

    for run_dir in sorted(_EXTERNAL_RUNS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        result_path = run_dir / "result.json"
        if not result_path.exists():
            continue
        try:
            with open(result_path) as f:
                data = json.load(f)
            task_name = data.get("task_name", "")
            if not task_name:
                task_id_raw = data.get("task_id")
                if isinstance(task_id_raw, dict):
                    task_name = task_id_raw.get("path", "")
                elif isinstance(task_id_raw, str):
                    task_name = task_id_raw
            if not task_name:
                continue

            runs.append({
                "name": run_dir.name,
                "task_name": task_name,
                "path": str(run_dir),
                "result": data,
            })
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load run %s: %s", run_dir.name, exc)

    return runs


def _extract_agent_output(run_dir_path: str) -> str:
    """Extract agent output from a run directory."""
    run_dir = Path(run_dir_path)
    solution_path = run_dir / "logs" / "agent" / "solution.md"
    if solution_path.exists():
        try:
            return solution_path.read_text(errors="replace")[:20000]
        except OSError:
            pass

    agent_dir = run_dir / "logs" / "agent"
    if agent_dir.is_dir():
        for md_file in sorted(agent_dir.glob("*.md")):
            try:
                return md_file.read_text(errors="replace")[:20000]
            except OSError:
                continue

    submission_path = run_dir / "submission.txt"
    if submission_path.exists():
        try:
            return submission_path.read_text(errors="replace")[:20000]
        except OSError:
            pass

    return ""


def _load_templates() -> list[str]:
    """Load available prompt template names from configs directory."""
    templates: list[str] = []
    if not _TEMPLATES_DIR.is_dir():
        return templates
    for yaml_file in sorted(_TEMPLATES_DIR.glob("*.yaml")):
        templates.append(yaml_file.stem)
    return templates


def _serialize_verdict(verdict: Any) -> dict[str, Any]:
    """Serialize a JudgeVerdict or EnsembleVerdict to a JSON-compatible dict."""
    try:
        from src.judge.models import EnsembleVerdict, JudgeVerdict

        if isinstance(verdict, EnsembleVerdict):
            return {
                "consensus_score": verdict.consensus_score,
                "agreement_score": verdict.agreement_score,
                "confidence": verdict.confidence,
                "vote_distribution": dict(verdict.vote_distribution),
                "per_model_verdicts": [
                    _serialize_verdict(v) for v in verdict.per_model_verdicts
                ],
            }
        if isinstance(verdict, JudgeVerdict):
            scores_dict = {}
            for dim_name, dim_score in verdict.scores.items():
                scores_dict[dim_name] = {
                    "score": dim_score.score,
                    "weight": dim_score.weight,
                    "evidence": dim_score.evidence,
                    "reasoning": dim_score.reasoning,
                }
            line_comments = []
            for lc in verdict.line_comments:
                line_comments.append({
                    "file_path": lc.file_path,
                    "line_range": list(lc.line_range),
                    "severity": lc.severity.value,
                    "comment": lc.comment,
                    "category": lc.category.value,
                })
            return {
                "mode": verdict.mode.value,
                "overall_score": verdict.overall_score,
                "reasoning": verdict.reasoning,
                "evidence": list(verdict.evidence),
                "confidence": verdict.confidence,
                "model_id": verdict.model_id,
                "scores": scores_dict,
                "line_comments": line_comments,
                "metadata": dict(verdict.metadata),
            }
    except ImportError:
        pass
    return {"error": "Unable to serialize verdict"}


def _verdict_to_csv_rows(verdict_data: dict[str, Any], task_id: str) -> list[dict[str, str]]:
    """Convert serialized verdict data to flat CSV rows."""
    rows: list[dict[str, str]] = []
    base = {
        "task_id": task_id,
        "overall_score": str(verdict_data.get("overall_score", "")),
        "confidence": str(verdict_data.get("confidence", "")),
        "model_id": str(verdict_data.get("model_id", "")),
        "reasoning": verdict_data.get("reasoning", ""),
    }
    scores = verdict_data.get("scores", {})
    for dim_name, dim_data in scores.items():
        row = {**base, "dimension": dim_name}
        if isinstance(dim_data, dict):
            row["dimension_score"] = str(dim_data.get("score", ""))
            row["dimension_weight"] = str(dim_data.get("weight", ""))
        rows.append(row)
    if not scores:
        rows.append({**base, "dimension": "", "dimension_score": "", "dimension_weight": ""})
    return rows


def _init_session_state() -> None:
    """Initialize session state for unified judge view."""
    if "judge_unified_results" not in st.session_state:
        st.session_state.judge_unified_results = None
    if "judge_unified_running" not in st.session_state:
        st.session_state.judge_unified_running = False


def _render_ensemble_config() -> dict[str, Any]:
    """Render ensemble configuration panel. Returns config dict."""
    st.markdown("**Ensemble Configuration**")

    col_ensemble, col_template = st.columns(2)

    with col_ensemble:
        use_ensemble = st.checkbox(
            "Enable Multi-Model Ensemble",
            key="judge_unified_ensemble_flag",
        )

        selected_models: list[str] = []
        model_weights: dict[str, float] = {}

        if use_ensemble:
            for model_id, provider in _AVAILABLE_MODELS.items():
                checked = st.checkbox(
                    f"{model_id} ({provider})",
                    value=(model_id == "claude-sonnet-4-20250514"),
                    key=f"judge_unified_model_{model_id}",
                )
                if checked:
                    selected_models.append(model_id)

            if selected_models:
                st.markdown("**Model Weights**")
                for model_id in selected_models:
                    weight = st.slider(
                        model_id,
                        min_value=0.1,
                        max_value=2.0,
                        value=1.0,
                        step=0.1,
                        key=f"judge_unified_weight_{model_id}",
                    )
                    model_weights[model_id] = weight

            if use_ensemble and len(selected_models) < 2:
                st.warning("Ensemble requires at least 2 models.")
        else:
            selected_models = ["claude-sonnet-4-20250514"]

    with col_template:
        templates = _load_templates()
        selected_template = ""
        if templates:
            template_options = ["(default)"] + templates
            selected_idx = st.selectbox(
                "Judge Template",
                options=range(len(template_options)),
                format_func=lambda i: template_options[i],
                key="judge_unified_template_select",
            )
            if selected_idx and selected_idx > 0:
                selected_template = templates[selected_idx - 1]

        # Agreement metrics display (from previous results)
        results = st.session_state.get("judge_unified_results")
        if results and isinstance(results, dict):
            agreement = results.get("agreement_score")
            if agreement is not None:
                st.metric("Agreement Score (Fleiss' kappa)", f"{agreement:.3f}")
            confidence = results.get("confidence")
            if confidence is not None:
                st.metric("Confidence", f"{confidence:.3f}")

    return {
        "use_ensemble": use_ensemble,
        "selected_models": selected_models,
        "model_weights": model_weights,
        "selected_template": selected_template,
    }


def _render_export_buttons(results_data: dict[str, Any]) -> None:
    """Render JSON and CSV download buttons for results."""
    col_json, col_csv = st.columns(2)

    with col_json:
        json_str = json.dumps(results_data, indent=2, default=str)
        st.download_button(
            "Download JSON",
            data=json_str,
            file_name="judge_results.json",
            mime="application/json",
            key="judge_unified_download_json",
        )

    with col_csv:
        csv_buffer = io.StringIO()
        writer = None
        verdicts = results_data.get("verdicts", [])
        for entry in verdicts:
            task_id = entry.get("task_id", "")
            verdict_data = entry.get("verdict", {})
            rows = _verdict_to_csv_rows(verdict_data, task_id)
            for row in rows:
                if writer is None:
                    writer = csv.DictWriter(csv_buffer, fieldnames=sorted(row.keys()))
                    writer.writeheader()
                writer.writerow(row)
        csv_content = csv_buffer.getvalue()
        st.download_button(
            "Download CSV",
            data=csv_content if csv_content else "No data",
            file_name="judge_results.csv",
            mime="text/csv",
            key="judge_unified_download_csv",
        )


def _render_pairwise_tab() -> None:
    """Render the Pairwise Comparison tab."""
    st.subheader("Pairwise Comparison")
    st.caption("Compare outputs from multiple runs side-by-side")

    runs = _load_run_dirs()
    if not runs:
        st.info("No runs found. Ensure run directories contain result.json files.")
        return

    run_names = [r["name"] for r in runs]
    selected_runs = st.multiselect(
        "Select runs to compare",
        options=run_names,
        default=run_names[:2] if len(run_names) >= 2 else run_names,
        key="judge_unified_pairwise_runs",
    )

    if len(selected_runs) < 2:
        st.warning("Select at least 2 runs for pairwise comparison.")
        return

    selected_run_data = [r for r in runs if r["name"] in selected_runs]

    # Group by task to find common tasks
    tasks_by_name: dict[str, dict[str, str]] = {}
    for run_data in selected_run_data:
        task_name = run_data["task_name"]
        output = _extract_agent_output(run_data["path"])
        if output:
            if task_name not in tasks_by_name:
                tasks_by_name[task_name] = {}
            tasks_by_name[task_name][run_data["name"]] = output

    common_tasks = {
        tid: outputs
        for tid, outputs in tasks_by_name.items()
        if len(outputs) >= 2
    }

    if not common_tasks:
        st.warning("No common tasks found across selected runs.")
        return

    st.markdown(f"**{len(common_tasks)} common tasks** across selected runs")

    # Display existing results
    results = st.session_state.get("judge_unified_results")
    if results and results.get("mode") == "pairwise":
        _render_pairwise_results(results)

    # Run Judge button
    if st.button("Run Pairwise Judge", key="judge_unified_pairwise_run"):
        st.session_state.judge_unified_running = True
        config = st.session_state.get("judge_unified_ensemble_config", {})
        _run_pairwise_evaluation(common_tasks, config)
        st.session_state.judge_unified_running = False


def _render_pairwise_results(results: dict[str, Any]) -> None:
    """Render pairwise comparison results with rankings and charts."""
    verdicts = results.get("verdicts", [])
    if not verdicts:
        return

    st.markdown("---")
    st.markdown("**Results**")

    # Aggregate win rates across all verdicts
    aggregate_wins: dict[str, float] = {}
    total_tasks = 0

    for entry in verdicts:
        verdict_data = entry.get("verdict", {})
        win_rates = verdict_data.get("win_rates", {})
        for condition, rate in win_rates.items():
            aggregate_wins[condition] = aggregate_wins.get(condition, 0.0) + rate
        total_tasks += 1

    if aggregate_wins and total_tasks > 0:
        avg_wins = {
            cond: total / total_tasks for cond, total in aggregate_wins.items()
        }

        # Rankings table
        rankings = sorted(avg_wins.items(), key=lambda x: x[1], reverse=True)
        st.markdown("**Rankings (by average win rate)**")
        ranking_rows = [
            {"Rank": i + 1, "Condition": cond, "Win Rate": f"{rate:.3f}"}
            for i, (cond, rate) in enumerate(rankings)
        ]
        st.dataframe(ranking_rows, use_container_width=True, hide_index=True)

        # Win rate bar chart
        try:
            import plotly.graph_objects as go

            conditions = [r[0] for r in rankings]
            rates = [r[1] for r in rankings]
            fig = go.Figure(data=[
                go.Bar(
                    x=conditions,
                    y=rates,
                    marker_color="#4a9eff",
                )
            ])
            fig.update_layout(
                title="Win Rates by Condition",
                xaxis_title="Condition",
                yaxis_title="Average Win Rate",
                yaxis_range=[0, 1],
                template="plotly_dark",
            )
            st.plotly_chart(fig, use_container_width=True, key="judge_unified_pairwise_bar")
        except ImportError:
            st.caption("Install plotly for interactive charts: pip install plotly")

    # Preference matrix heatmap
    all_matrices: dict[str, dict[str, float]] = {}
    for entry in verdicts:
        verdict_data = entry.get("verdict", {})
        pref_matrix = verdict_data.get("preference_matrix", {})
        for row_key, row_vals in pref_matrix.items():
            if row_key not in all_matrices:
                all_matrices[row_key] = {}
            for col_key, val in row_vals.items():
                all_matrices[row_key][col_key] = (
                    all_matrices[row_key].get(col_key, 0.0) + val
                )

    if all_matrices and total_tasks > 0:
        conditions = sorted(all_matrices.keys())
        try:
            import plotly.graph_objects as go

            z_data = []
            for row_cond in conditions:
                row = []
                for col_cond in conditions:
                    val = all_matrices.get(row_cond, {}).get(col_cond, 0.0)
                    row.append(val / total_tasks)
                z_data.append(row)

            fig = go.Figure(data=go.Heatmap(
                z=z_data,
                x=conditions,
                y=conditions,
                colorscale="Blues",
                text=[[f"{v:.2f}" for v in row] for row in z_data],
                texttemplate="%{text}",
            ))
            fig.update_layout(
                title="Preference Matrix (averaged)",
                template="plotly_dark",
            )
            st.plotly_chart(fig, use_container_width=True, key="judge_unified_pairwise_heatmap")
        except ImportError:
            pass


def _run_pairwise_evaluation(
    common_tasks: dict[str, dict[str, str]],
    config: dict[str, Any],
) -> None:
    """Run pairwise evaluation on common tasks."""
    try:
        from src.judge.engine import JudgeConfig, UnifiedJudge
        from src.judge.ensemble import EnsembleConfig, EnsembleJudge
        from src.judge.models import EvaluationMode, PairwiseInput
        from src.judge.backends.anthropic import AnthropicBackend

        use_ensemble = config.get("use_ensemble", False)
        selected_models = config.get("selected_models", ["claude-sonnet-4-20250514"])
        model_weights = config.get("model_weights", {})
        template_name = config.get("selected_template", "")

        judge_config = JudgeConfig(
            pairwise_method="simultaneous",
            templates_dir=str(_TEMPLATES_DIR) if not template_name else "",
        )

        verdicts: list[dict[str, Any]] = []
        errors: list[str] = []

        progress = st.progress(0.0)
        status = st.empty()
        total = len(common_tasks)

        async def _run() -> None:
            if use_ensemble and len(selected_models) >= 2:
                judges = []
                for model_id in selected_models:
                    backend = AnthropicBackend(model=model_id)
                    judge = UnifiedJudge(backend=backend, config=judge_config)
                    judges.append(judge)
                ensemble_config = EnsembleConfig(
                    model_weights=model_weights,
                )
                evaluator = EnsembleJudge(judges=judges, config=ensemble_config)
            else:
                model_id = selected_models[0] if selected_models else "claude-sonnet-4-20250514"
                backend = AnthropicBackend(model=model_id)
                evaluator = UnifiedJudge(backend=backend, config=judge_config)

            for idx, (task_id, outputs) in enumerate(common_tasks.items()):
                status.text(f"Evaluating task {idx + 1}/{total}: {task_id[:50]}...")
                judge_input = PairwiseInput(
                    task_id=task_id,
                    task_description=task_id,
                    evaluation_mode=EvaluationMode.PAIRWISE,
                    outputs=outputs,
                )
                try:
                    result = await evaluator.evaluate(judge_input)
                    verdicts.append({
                        "task_id": task_id,
                        "verdict": _serialize_verdict(result),
                    })
                except Exception as exc:
                    errors.append(f"{task_id}: {exc}")
                    logger.warning("Pairwise eval failed for %s: %s", task_id, exc)
                progress.progress((idx + 1) / total)

        asyncio.run(_run())
        progress.empty()
        status.empty()

        st.session_state.judge_unified_results = {
            "mode": "pairwise",
            "verdicts": verdicts,
            "errors": errors,
        }

        if errors:
            st.warning(f"{len(errors)} tasks failed evaluation.")
        st.success(f"Evaluated {len(verdicts)} tasks successfully.")
        st.rerun()

    except ImportError as exc:
        st.error(f"Missing dependency: {exc}")
    except Exception as exc:
        st.error(f"Evaluation failed: {exc}")
        logger.exception("Pairwise evaluation error")


def _render_direct_tab() -> None:
    """Render the Direct Review tab."""
    st.subheader("Direct Review (PR-Style)")
    st.caption("Evaluate individual run outputs with dimensional scoring and line comments")

    runs = _load_run_dirs()
    experiments = _load_experiment_results()

    sources: list[tuple[str, str]] = []
    for r in runs:
        sources.append((f"run: {r['name']}", r["path"]))
    for exp in experiments:
        sources.append((f"experiment: {exp['experiment_id']}", exp["path"]))

    if not sources:
        st.info("No runs or experiments found.")
        return

    source_labels = [s[0] for s in sources]
    selected_idx = st.selectbox(
        "Select run or experiment",
        options=range(len(source_labels)),
        format_func=lambda i: source_labels[i],
        key="judge_unified_direct_source",
    )

    selected_source = sources[selected_idx]
    source_label, source_path = selected_source

    if source_label.startswith("run:"):
        output = _extract_agent_output(source_path)
        if output:
            display = output[:5000] + "..." if len(output) > 5000 else output
            st.text_area(
                "Agent Output",
                value=display,
                height=300,
                disabled=True,
                key="judge_unified_direct_output_display",
            )
    elif source_label.startswith("experiment:"):
        exp_data = next((e for e in experiments if e["path"] == source_path), None)
        if exp_data and exp_data["results"]:
            task_ids = [r.get("task_id", "unknown") for r in exp_data["results"]]
            st.caption(f"{len(task_ids)} tasks in this experiment")

    # Display existing results
    results = st.session_state.get("judge_unified_results")
    if results and results.get("mode") == "direct":
        _render_direct_results(results)

    # Run Judge button
    if st.button("Run Direct Judge", key="judge_unified_direct_run"):
        st.session_state.judge_unified_running = True
        config = st.session_state.get("judge_unified_ensemble_config", {})
        _run_direct_evaluation(source_label, source_path, config)
        st.session_state.judge_unified_running = False


def _render_direct_results(results: dict[str, Any]) -> None:
    """Render direct review results with line comments and radar chart."""
    verdicts = results.get("verdicts", [])
    if not verdicts:
        return

    st.markdown("---")
    st.markdown("**Results**")

    for entry in verdicts:
        task_id = entry.get("task_id", "unknown")
        verdict_data = entry.get("verdict", {})

        with st.expander(f"Task: {task_id[:60]}", expanded=(len(verdicts) == 1)):
            overall = verdict_data.get("overall_score", 0)
            confidence = verdict_data.get("confidence", 0)

            col_score, col_conf, col_model = st.columns(3)
            with col_score:
                st.metric("Overall Score", f"{overall:.3f}")
            with col_conf:
                st.metric("Confidence", f"{confidence:.3f}")
            with col_model:
                st.metric("Model", verdict_data.get("model_id", "N/A"))

            # Dimension scores
            scores = verdict_data.get("scores", {})
            if scores:
                st.markdown("**Dimension Scores**")
                dim_rows = []
                dim_names = []
                dim_values = []
                for dim_name, dim_data in scores.items():
                    if isinstance(dim_data, dict):
                        score_val = dim_data.get("score", 0)
                        weight_val = dim_data.get("weight", 0)
                        dim_rows.append({
                            "Dimension": dim_name,
                            "Score": f"{score_val:.3f}",
                            "Weight": f"{weight_val:.2f}",
                            "Evidence": dim_data.get("evidence", "")[:100],
                        })
                        dim_names.append(dim_name)
                        dim_values.append(score_val)
                st.dataframe(dim_rows, use_container_width=True, hide_index=True)

                # Radar chart for dimensions
                if dim_names and len(dim_names) >= 3:
                    try:
                        import plotly.graph_objects as go

                        fig = go.Figure(data=go.Scatterpolar(
                            r=dim_values + [dim_values[0]],
                            theta=dim_names + [dim_names[0]],
                            fill="toself",
                            fillcolor="rgba(74, 158, 255, 0.2)",
                            line_color="#4a9eff",
                        ))
                        fig.update_layout(
                            polar=dict(radialaxis=dict(range=[0, 1])),
                            title="Dimension Radar",
                            template="plotly_dark",
                        )
                        st.plotly_chart(
                            fig,
                            use_container_width=True,
                            key=f"judge_unified_direct_radar_{task_id}",
                        )
                    except ImportError:
                        pass

            # Line comments
            line_comments = verdict_data.get("line_comments", [])
            if line_comments:
                st.markdown("**Line Comments**")
                for lc in line_comments:
                    severity = lc.get("severity", "suggestion")
                    color = _SEVERITY_COLORS.get(severity, "#888")
                    file_path = lc.get("file_path", "")
                    line_range = lc.get("line_range", [0, 0])
                    comment = lc.get("comment", "")
                    category = lc.get("category", "")

                    st.markdown(
                        f'<div style="border-left: 4px solid {color}; '
                        f'padding: 8px 12px; margin: 4px 0; '
                        f'background-color: rgba(0,0,0,0.2); border-radius: 4px;">'
                        f'<strong style="color: {color};">[{severity.upper()}]</strong> '
                        f'<code>{file_path}:{line_range[0]}-{line_range[1]}</code> '
                        f'<em>({category})</em><br/>{comment}</div>',
                        unsafe_allow_html=True,
                    )

            # Reasoning
            reasoning = verdict_data.get("reasoning", "")
            if reasoning:
                with st.expander("Full Reasoning"):
                    st.markdown(reasoning)


def _run_direct_evaluation(
    source_label: str,
    source_path: str,
    config: dict[str, Any],
) -> None:
    """Run direct evaluation on selected source."""
    try:
        from src.judge.engine import JudgeConfig, UnifiedJudge
        from src.judge.ensemble import EnsembleConfig, EnsembleJudge
        from src.judge.models import DirectInput, EvaluationMode
        from src.judge.backends.anthropic import AnthropicBackend

        use_ensemble = config.get("use_ensemble", False)
        selected_models = config.get("selected_models", ["claude-sonnet-4-20250514"])
        model_weights = config.get("model_weights", {})

        judge_config = JudgeConfig(templates_dir=str(_TEMPLATES_DIR))

        tasks: list[tuple[str, str]] = []
        if source_label.startswith("run:"):
            run_name = source_label.removeprefix("run: ")
            output = _extract_agent_output(source_path)
            if output:
                tasks.append((run_name, output))
        elif source_label.startswith("experiment:"):
            results_path = Path(source_path) / "results.json"
            if results_path.exists():
                with open(results_path) as f:
                    data = json.load(f)
                for result in data.get("results", []):
                    tid = result.get("task_id", "unknown")
                    agent_output = result.get("agent_output", "")
                    if agent_output:
                        tasks.append((tid, agent_output))

        if not tasks:
            st.warning("No evaluable outputs found.")
            return

        verdicts: list[dict[str, Any]] = []
        errors: list[str] = []

        progress = st.progress(0.0)
        status = st.empty()

        async def _run() -> None:
            if use_ensemble and len(selected_models) >= 2:
                judges = []
                for model_id in selected_models:
                    backend = AnthropicBackend(model=model_id)
                    judge = UnifiedJudge(backend=backend, config=judge_config)
                    judges.append(judge)
                evaluator = EnsembleJudge(
                    judges=judges,
                    config=EnsembleConfig(model_weights=model_weights),
                )
            else:
                model_id = selected_models[0] if selected_models else "claude-sonnet-4-20250514"
                backend = AnthropicBackend(model=model_id)
                evaluator = UnifiedJudge(backend=backend, config=judge_config)

            for idx, (task_id, agent_output) in enumerate(tasks):
                status.text(f"Evaluating task {idx + 1}/{len(tasks)}: {task_id[:50]}...")
                judge_input = DirectInput(
                    task_id=task_id,
                    task_description=task_id,
                    evaluation_mode=EvaluationMode.DIRECT,
                    agent_output=agent_output,
                )
                try:
                    result = await evaluator.evaluate(judge_input)
                    verdicts.append({
                        "task_id": task_id,
                        "verdict": _serialize_verdict(result),
                    })
                except Exception as exc:
                    errors.append(f"{task_id}: {exc}")
                    logger.warning("Direct eval failed for %s: %s", task_id, exc)
                progress.progress((idx + 1) / len(tasks))

        asyncio.run(_run())
        progress.empty()
        status.empty()

        st.session_state.judge_unified_results = {
            "mode": "direct",
            "verdicts": verdicts,
            "errors": errors,
        }

        if errors:
            st.warning(f"{len(errors)} tasks failed evaluation.")
        st.success(f"Evaluated {len(verdicts)} tasks successfully.")
        st.rerun()

    except ImportError as exc:
        st.error(f"Missing dependency: {exc}")
    except Exception as exc:
        st.error(f"Evaluation failed: {exc}")
        logger.exception("Direct evaluation error")


def _render_reference_tab() -> None:
    """Render the Reference-Based tab."""
    st.subheader("Reference-Based Evaluation")
    st.caption("Evaluate agent outputs against ground truth / oracle data")

    runs = _load_run_dirs()
    experiments = _load_experiment_results()

    sources: list[tuple[str, str]] = []
    for r in runs:
        sources.append((f"run: {r['name']}", r["path"]))
    for exp in experiments:
        sources.append((f"experiment: {exp['experiment_id']}", exp["path"]))

    if not sources:
        st.info("No runs or experiments found.")
        return

    source_labels = [s[0] for s in sources]
    selected_idx = st.selectbox(
        "Select run or experiment",
        options=range(len(source_labels)),
        format_func=lambda i: source_labels[i],
        key="judge_unified_ref_source",
    )

    selected_source = sources[selected_idx]
    source_label, source_path = selected_source

    # Oracle data directory
    oracle_dir = st.text_input(
        "Oracle data directory (LoCoBench scenario JSON files)",
        value=str(_PROJECT_ROOT / "benchmarks" / "locobench_agent" / "data" / "output" / "agent_scenarios"),
        key="judge_unified_ref_oracle_dir",
    )

    # Display existing results
    results = st.session_state.get("judge_unified_results")
    if results and results.get("mode") == "reference":
        _render_reference_results(results)

    # Run Judge button
    if st.button("Run Reference Judge", key="judge_unified_ref_run"):
        st.session_state.judge_unified_running = True
        config = st.session_state.get("judge_unified_ensemble_config", {})
        _run_reference_evaluation(source_label, source_path, oracle_dir, config)
        st.session_state.judge_unified_running = False


def _render_reference_results(results: dict[str, Any]) -> None:
    """Render reference-based results with correctness/completeness scores."""
    verdicts = results.get("verdicts", [])
    if not verdicts:
        return

    st.markdown("---")
    st.markdown("**Results**")

    # Summary metrics
    scores_list = [
        v.get("verdict", {}).get("overall_score", 0) for v in verdicts
    ]
    if scores_list:
        avg_score = sum(scores_list) / len(scores_list)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Mean Score", f"{avg_score:.3f}")
        with col2:
            st.metric("Tasks Evaluated", str(len(verdicts)))
        with col3:
            errors = results.get("errors", [])
            st.metric("Errors", str(len(errors)))

    # Context file coverage bar
    coverage_data: list[dict[str, Any]] = []
    for entry in verdicts:
        task_id = entry.get("task_id", "unknown")
        verdict_data = entry.get("verdict", {})
        metadata = verdict_data.get("metadata", {})
        coverage = metadata.get("context_file_coverage", 0)
        coverage_data.append({
            "Task": task_id[:40],
            "Coverage": coverage,
            "Score": verdict_data.get("overall_score", 0),
        })

    if coverage_data:
        try:
            import plotly.graph_objects as go

            tasks = [d["Task"] for d in coverage_data]
            coverages = [d["Coverage"] for d in coverage_data]
            task_scores = [d["Score"] for d in coverage_data]

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=tasks,
                y=coverages,
                name="Context Coverage",
                marker_color="#4a9eff",
            ))
            fig.add_trace(go.Bar(
                x=tasks,
                y=task_scores,
                name="Overall Score",
                marker_color="#66bb6a",
            ))
            fig.update_layout(
                title="Context File Coverage and Score by Task",
                barmode="group",
                yaxis_range=[0, 1],
                template="plotly_dark",
                xaxis_tickangle=-45,
            )
            st.plotly_chart(fig, use_container_width=True, key="judge_unified_ref_coverage")
        except ImportError:
            st.dataframe(coverage_data, use_container_width=True, hide_index=True)

    # Per-task details
    for entry in verdicts:
        task_id = entry.get("task_id", "unknown")
        verdict_data = entry.get("verdict", {})

        with st.expander(f"Task: {task_id[:60]}"):
            scores = verdict_data.get("scores", {})
            if scores:
                dim_rows = [
                    {
                        "Dimension": dim_name,
                        "Score": f"{dim_data.get('score', 0):.3f}" if isinstance(dim_data, dict) else str(dim_data),
                        "Evidence": (dim_data.get("evidence", "")[:100] if isinstance(dim_data, dict) else ""),
                    }
                    for dim_name, dim_data in scores.items()
                ]
                st.dataframe(dim_rows, use_container_width=True, hide_index=True)

            reasoning = verdict_data.get("reasoning", "")
            if reasoning:
                st.markdown(reasoning)


def _run_reference_evaluation(
    source_label: str,
    source_path: str,
    oracle_dir: str,
    config: dict[str, Any],
) -> None:
    """Run reference-based evaluation on selected source."""
    try:
        from src.judge.engine import JudgeConfig, UnifiedJudge
        from src.judge.ensemble import EnsembleConfig, EnsembleJudge
        from src.judge.models import EvaluationMode, ReferenceInput
        from src.judge.backends.anthropic import AnthropicBackend

        use_ensemble = config.get("use_ensemble", False)
        selected_models = config.get("selected_models", ["claude-sonnet-4-20250514"])
        model_weights = config.get("model_weights", {})

        judge_config = JudgeConfig(
            templates_dir=str(_TEMPLATES_DIR),
            scoring_scale="0.0-1.0",
        )

        oracle_path = Path(oracle_dir)

        tasks: list[tuple[str, str, dict[str, Any]]] = []
        if source_label.startswith("run:"):
            output = _extract_agent_output(source_path)
            if output:
                run_result_path = Path(source_path) / "result.json"
                task_name = ""
                if run_result_path.exists():
                    with open(run_result_path) as f:
                        result_data = json.load(f)
                    task_name = result_data.get("task_name", "")
                oracle_data = _load_oracle_data(oracle_path, task_name)
                tasks.append((task_name or source_label, output, oracle_data))
        elif source_label.startswith("experiment:"):
            results_file = Path(source_path) / "results.json"
            if results_file.exists():
                with open(results_file) as f:
                    data = json.load(f)
                for result in data.get("results", []):
                    tid = result.get("task_id", "unknown")
                    agent_output = result.get("agent_output", "")
                    if agent_output:
                        oracle_data = _load_oracle_data(oracle_path, tid)
                        tasks.append((tid, agent_output, oracle_data))

        if not tasks:
            st.warning("No evaluable outputs found.")
            return

        verdicts: list[dict[str, Any]] = []
        errors: list[str] = []

        progress = st.progress(0.0)
        status = st.empty()

        async def _run() -> None:
            if use_ensemble and len(selected_models) >= 2:
                judges = []
                for model_id in selected_models:
                    backend = AnthropicBackend(model=model_id)
                    judge = UnifiedJudge(backend=backend, config=judge_config)
                    judges.append(judge)
                evaluator = EnsembleJudge(
                    judges=judges,
                    config=EnsembleConfig(model_weights=model_weights),
                )
            else:
                model_id = selected_models[0] if selected_models else "claude-sonnet-4-20250514"
                backend = AnthropicBackend(model=model_id)
                evaluator = UnifiedJudge(backend=backend, config=judge_config)

            for idx, (task_id, agent_output, oracle_data) in enumerate(tasks):
                status.text(f"Evaluating task {idx + 1}/{len(tasks)}: {task_id[:50]}...")
                ground_truth = oracle_data.get("ground_truth", "")
                if isinstance(ground_truth, dict):
                    ground_truth = json.dumps(ground_truth)
                context_files = oracle_data.get("context_files", [])
                reference_answer = ground_truth or oracle_data.get("expected_approach", "")

                judge_input = ReferenceInput(
                    task_id=task_id,
                    task_description=oracle_data.get("task_description", task_id),
                    evaluation_mode=EvaluationMode.REFERENCE_BASED,
                    ground_truth=ground_truth if ground_truth else None,
                    evaluation_criteria=oracle_data.get("evaluation_criteria"),
                    agent_output=agent_output,
                    reference_answer=reference_answer,
                    context_files=context_files,
                )
                try:
                    result = await evaluator.evaluate(judge_input)
                    verdicts.append({
                        "task_id": task_id,
                        "verdict": _serialize_verdict(result),
                    })
                except Exception as exc:
                    errors.append(f"{task_id}: {exc}")
                    logger.warning("Reference eval failed for %s: %s", task_id, exc)
                progress.progress((idx + 1) / len(tasks))

        asyncio.run(_run())
        progress.empty()
        status.empty()

        st.session_state.judge_unified_results = {
            "mode": "reference",
            "verdicts": verdicts,
            "errors": errors,
        }

        if errors:
            st.warning(f"{len(errors)} tasks failed evaluation.")
        st.success(f"Evaluated {len(verdicts)} tasks successfully.")
        st.rerun()

    except ImportError as exc:
        st.error(f"Missing dependency: {exc}")
    except Exception as exc:
        st.error(f"Evaluation failed: {exc}")
        logger.exception("Reference evaluation error")


def _load_oracle_data(oracle_dir: Path, task_name: str) -> dict[str, Any]:
    """Load oracle data from LoCoBench scenario JSON files."""
    if not oracle_dir.is_dir():
        return {}

    # Try direct match
    scenario_file = oracle_dir / f"{task_name}.json"
    if scenario_file.exists():
        try:
            with open(scenario_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # Try fuzzy match on task name prefix
    for json_file in oracle_dir.glob("*.json"):
        if task_name and json_file.stem.startswith(task_name[:20]):
            try:
                with open(json_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

    return {}


def show_judge_unified() -> None:
    """Main entry point for the unified judge dashboard view."""
    _init_session_state()

    st.title("Unified LLM Judge")
    st.caption(
        "Configure, run, and analyze judge evaluations across pairwise, "
        "direct review, and reference-based modes"
    )

    # Ensemble config panel in main content area (not sidebar)
    with st.expander("Judge Configuration", expanded=False):
        ensemble_config = _render_ensemble_config()
        st.session_state.judge_unified_ensemble_config = ensemble_config

    # Mode tabs
    tab_pairwise, tab_direct, tab_reference = st.tabs([
        "Pairwise Comparison",
        "Direct Review",
        "Reference-Based",
    ])

    with tab_pairwise:
        _render_pairwise_tab()

    with tab_direct:
        _render_direct_tab()

    with tab_reference:
        _render_reference_tab()

    # Export section
    results = st.session_state.get("judge_unified_results")
    if results and results.get("verdicts"):
        st.markdown("---")
        st.subheader("Export Results")
        _render_export_buttons(results)
