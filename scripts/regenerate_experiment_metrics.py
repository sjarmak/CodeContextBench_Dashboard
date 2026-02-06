#!/usr/bin/env python3
"""
Regenerate experiment_metrics.json from all official run directories.

Scans runs/official/ for paired experiments (baseline/sourcegraph_base/sourcegraph_full
mode subdirectories), extracts trial data from result.json and task_metrics.json,
and produces a single experiment_metrics.json compatible with the Task Comparison view.

Usage:
    python scripts/regenerate_experiment_metrics.py [--runs-dir PATH] [--output PATH]
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Mode directory -> agent_config label
_MODE_TO_CONFIG = {
    "baseline": "BASELINE",
    "sourcegraph_base": "MCP_BASE",
    "sourcegraph_full": "MCP_FULL",
    # Legacy names
    "sourcegraph_hybrid": "MCP_FULL",
    "deepsearch": "MCP_FULL",
    "mcp": "MCP_FULL",
    "sourcegraph": "MCP_BASE",
}

# Experiment directory prefix -> benchmark ID
_BENCHMARK_FROM_PREFIX = {
    "locobench": "ccb_locobench",
    "swebenchpro": "swebenchpro",
    "dibench": "ccb_dibench",
    "crossrepo": "ccb_crossrepo",
    "k8s_docs": "ccb_k8s_docs",
    "pytorch": "ccb_pytorch",
    "sweperf": "ccb_sweperf",
    "tac": "ccb_tac",
    "repoqa": "ccb_repoqa",
    "bigcode": "ccb_bigcode",
}


def _infer_benchmark(experiment_name: str) -> str:
    """Infer benchmark ID from experiment directory name."""
    lower = experiment_name.lower()
    for prefix, benchmark_id in _BENCHMARK_FROM_PREFIX.items():
        if lower.startswith(prefix):
            return benchmark_id
    return "unknown"


def _infer_language(task_name: str) -> str:
    """Infer programming language from task name patterns."""
    lower = task_name.lower()
    lang_markers = {
        "python": "python", "py-": "python", "py_": "python",
        "-python": "python",
        "javascript": "javascript", "js-": "javascript", "js_": "javascript",
        "-js-": "javascript",
        "typescript": "typescript", "ts-": "typescript", "ts_": "typescript",
        "-ts-": "typescript",
        "rust": "rust", "rust-": "rust",
        "-rust-": "rust",
        "go-": "go", "go_": "go", "-go-": "go",
        "java-": "java", "java_": "java", "-java-": "java",
        "cpp": "cpp", "c++": "cpp",
        "csharp": "csharp", "c#": "csharp",
    }
    for marker, lang in lang_markers.items():
        if marker in lower:
            return lang
    return "unknown"


def _compute_duration(result: dict) -> float | None:
    """Compute total duration from started_at/finished_at."""
    started = result.get("started_at", "")
    finished = result.get("finished_at", "")
    if not started or not finished:
        return None
    try:
        start = datetime.fromisoformat(started.replace("Z", "+00:00"))
        end = datetime.fromisoformat(finished.replace("Z", "+00:00"))
        return (end - start).total_seconds()
    except (ValueError, TypeError):
        return None


def _extract_tool_utilization(task_metrics: dict, result: dict) -> dict:
    """Build the tool_utilization sub-dict from available data."""
    by_name = task_metrics.get("tool_calls_by_name") or {}
    mcp_calls = task_metrics.get("tool_calls_mcp") or 0
    local_calls = task_metrics.get("tool_calls_local") or 0
    total = task_metrics.get("tool_calls_total") or (mcp_calls + local_calls)

    # Token fields
    agent_result = result.get("agent_result") or {}
    input_tok = (
        task_metrics.get("input_tokens")
        or agent_result.get("n_input_tokens")
        or 0
    )
    output_tok = (
        task_metrics.get("output_tokens")
        or agent_result.get("n_output_tokens")
        or 0
    )
    cached_tok = (
        task_metrics.get("cache_creation_tokens")
        or agent_result.get("n_cache_tokens")
        or 0
    )
    cost = task_metrics.get("cost_usd") or agent_result.get("cost_usd") or 0
    duration_ms = int((task_metrics.get("wall_clock_seconds") or 0) * 1000)

    # Search query extraction from by_name
    ds_calls = sum(
        v for k, v in by_name.items()
        if "deepsearch" in k.lower() or "deep_search" in k.lower()
    )
    kw_calls = sum(
        v for k, v in by_name.items()
        if "keyword_search" in k.lower() or "sg_keyword" in k.lower()
    )
    nls_calls = sum(
        v for k, v in by_name.items()
        if "nls_search" in k.lower() or "sg_nls" in k.lower()
    )

    return {
        "tool_calls_by_name": by_name,
        "mcp_calls": mcp_calls,
        "deep_search_calls": ds_calls,
        "local_calls": local_calls,
        "other_calls": 0,
        "total_tool_calls": total,
        "search_queries": task_metrics.get("search_queries") or [],
        "keyword_search_count": kw_calls,
        "nls_search_count": nls_calls,
        "deep_search_query_count": ds_calls,
        "deep_search_vs_keyword_ratio": (
            ds_calls / kw_calls if kw_calls > 0 else 0.0
        ),
        "cumulative_input_tokens": input_tok,
        "cumulative_output_tokens": output_tok,
        "cumulative_cached_tokens": cached_tok,
        "context_fill_rate": 0.0,
        "total_cost_usd": cost,
        "duration_ms": duration_ms,
        "num_turns": 0,
        "skipped_lines": 0,
    }


def _extract_trial(
    task_dir: Path,
    mode_name: str,
    experiment_name: str,
) -> dict | None:
    """Extract a single trial dict from a task instance directory."""
    result_file = task_dir / "result.json"
    if not result_file.is_file():
        return None

    try:
        result = json.loads(result_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    # Load task_metrics.json if available
    tm_file = task_dir / "task_metrics.json"
    task_metrics = {}
    if tm_file.is_file():
        try:
            task_metrics = json.loads(tm_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # Extract core fields
    task_name = result.get("task_name") or task_dir.name
    trial_name = result.get("trial_name") or task_dir.name
    agent_config = _MODE_TO_CONFIG.get(mode_name, mode_name.upper())
    raw_benchmark = task_metrics.get("benchmark") or _infer_benchmark(experiment_name)
    # Normalize: ensure consistent ccb_ prefix for swebenchpro
    benchmark = raw_benchmark if raw_benchmark != "swebenchpro" else "ccb_swebenchpro"

    # Strip status suffixes from task_name (Harbor bakes these in)
    crashed = "[CRASHED]" in task_name
    task_name = task_name.replace(" [CRASHED]", "").strip()

    # Reward
    verifier_result = result.get("verifier_result") or {}
    rewards = verifier_result.get("rewards") or {}
    reward = task_metrics.get("reward")
    if reward is None:
        reward = rewards.get("reward")
    reward = reward if reward is not None else 0.0

    pass_fail = "pass" if reward >= 1.0 else ("partial" if reward > 0 else "fail")
    if crashed or result.get("exception_info"):
        pass_fail = "error"

    # Tokens
    agent_result = result.get("agent_result") or {}
    input_tokens = (
        task_metrics.get("input_tokens")
        or agent_result.get("n_input_tokens")
        or 0
    )
    output_tokens = (
        task_metrics.get("output_tokens")
        or agent_result.get("n_output_tokens")
        or 0
    )
    cached_tokens = (
        task_metrics.get("cache_creation_tokens")
        or agent_result.get("n_cache_tokens")
        or 0
    )

    duration = _compute_duration(result)
    if duration is None:
        duration = task_metrics.get("wall_clock_seconds") or 0.0

    language = (
        task_metrics.get("language")
        or _infer_language(task_name)
    )

    started_at = result.get("started_at") or ""

    return {
        "trial_id": trial_name,
        "task_name": task_name,
        "benchmark": benchmark,
        "agent_config": agent_config,
        "reward": reward,
        "pass_fail": pass_fail,
        "started_at": started_at,
        "duration_seconds": duration,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "tool_utilization": _extract_tool_utilization(task_metrics, result),
        "language": language,
        "sdlc_phase": task_metrics.get("sdlc_phase"),
        "category": task_metrics.get("category"),
        "difficulty": task_metrics.get("difficulty"),
        "mcp_benefit_score": task_metrics.get("mcp_benefit_score"),
        "repo": task_metrics.get("repo"),
        "instance_dir": str(task_dir),
    }


def scan_experiment(exp_dir: Path) -> dict | None:
    """Scan a paired experiment directory and return an experiment dict."""
    known_modes = {
        "baseline", "sourcegraph_base", "sourcegraph_full",
        "sourcegraph_hybrid", "deepsearch", "mcp", "sourcegraph",
    }

    mode_dirs = [
        exp_dir / m for m in known_modes
        if (exp_dir / m).is_dir()
    ]
    if not mode_dirs:
        return None

    trials = []
    for mode_dir in mode_dirs:
        mode_name = mode_dir.name
        # Scan for timestamp subdirs -> task dirs with result.json
        for subdir in mode_dir.iterdir():
            if not subdir.is_dir():
                continue
            # Could be a timestamp dir containing task dirs
            found_nested = False
            for item in subdir.iterdir():
                if item.is_dir() and (item / "result.json").is_file():
                    trial = _extract_trial(item, mode_name, exp_dir.name)
                    if trial:
                        trials.append(trial)
                        found_nested = True
            # Only treat subdir as a task dir if no nested task dirs were found
            # and its result.json looks like a task result (has task_name),
            # not a batch/timestamp result (has n_total_trials).
            if not found_nested and (subdir / "result.json").is_file():
                try:
                    result = json.loads((subdir / "result.json").read_text(encoding="utf-8"))
                    if "task_name" in result and "n_total_trials" not in result:
                        trial = _extract_trial(subdir, mode_name, exp_dir.name)
                        if trial:
                            trials.append(trial)
                except (json.JSONDecodeError, OSError):
                    pass

    if not trials:
        return None

    return {
        "experiment_id": exp_dir.name,
        "trials": trials,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate experiment_metrics.json from official runs"
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path(os.path.expanduser(
            "~/evals/custom_agents/agents/claudecode/runs/official"
        )),
        help="Path to official runs directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "output" / "experiment_metrics.json",
        help="Output path for experiment_metrics.json",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge with existing experiment_metrics.json (add new experiments only)",
    )
    args = parser.parse_args()

    runs_dir = args.runs_dir
    if not runs_dir.is_dir():
        print(f"Runs directory not found: {runs_dir}", file=sys.stderr)
        sys.exit(1)

    # Load existing data if merging
    existing_experiments: set[str] = set()
    existing_data: list[dict] = []
    if args.merge and args.output.is_file():
        try:
            existing_data = json.loads(args.output.read_text(encoding="utf-8"))
            for cat in existing_data:
                for exp in cat.get("experiments", []):
                    existing_experiments.add(exp.get("experiment_id", ""))
            print(f"Loaded {len(existing_experiments)} existing experiments")
        except (json.JSONDecodeError, OSError):
            pass

    # Scan experiment directories
    experiments = []
    skip_names = {"archive", "errored_reruns_20260203_221710"}

    for exp_dir in sorted(runs_dir.iterdir()):
        if not exp_dir.is_dir():
            continue
        if exp_dir.name.startswith(".") or exp_dir.name.endswith(".log"):
            continue
        if exp_dir.name in skip_names:
            continue
        if exp_dir.name in existing_experiments:
            print(f"  Skipping (already exists): {exp_dir.name}")
            continue

        exp = scan_experiment(exp_dir)
        if exp:
            configs = {t["agent_config"] for t in exp["trials"]}
            print(
                f"  {exp_dir.name}: "
                f"{len(exp['trials'])} trials, configs={configs}"
            )
            experiments.append(exp)
        else:
            print(f"  {exp_dir.name}: no trials found (skipped)")

    if not experiments:
        print("No new experiments found.")
        return

    total_trials = sum(len(e["trials"]) for e in experiments)
    print(f"\nTotal: {len(experiments)} experiments, {total_trials} trials")

    # Build output structure
    if args.merge and existing_data:
        # Append new experiments to the first category
        if existing_data:
            existing_data[0]["experiments"].extend(experiments)
        output = existing_data
    else:
        output = [{
            "run_category": "official",
            "experiments": experiments,
        }]

    # Also include archive experiments from existing data if not merging
    if not args.merge and args.output.is_file():
        try:
            old = json.loads(args.output.read_text(encoding="utf-8"))
            for cat in old:
                for exp in cat.get("experiments", []):
                    if exp.get("experiment_id") == "archive":
                        # Clean up status suffixes in archived trial names
                        for trial in exp.get("trials", []):
                            tn = trial.get("task_name", "")
                            if "[CRASHED]" in tn:
                                trial["task_name"] = tn.replace(" [CRASHED]", "").strip()
                                trial["pass_fail"] = "error"
                        output[0]["experiments"].insert(0, exp)
                        print(f"Preserved archive experiment ({len(exp.get('trials', []))} trials)")
                        break
        except (json.JSONDecodeError, OSError):
            pass

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
