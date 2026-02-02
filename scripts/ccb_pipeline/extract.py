"""
Unified metrics extraction pipeline.

Walks a runs directory and produces experiment_metrics.json with all
metrics per trial, including reward, timing, tokens, config detection,
and tool utilization.

Usage:
    python -m scripts.ccb_pipeline.extract --runs-dir <path> --output <path>
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from src.ingest.config_detector import AgentConfig, detect_agent_config
from src.ingest.transcript_tool_extractor import (
    ToolUtilizationMetrics,
    extract_tool_utilization,
)

logger = logging.getLogger(__name__)

# Run categories to scan under the runs directory
RUN_CATEGORIES = ("official", "experiment", "troubleshooting")


@dataclass(frozen=True)
class TrialMetrics:
    """Immutable metrics extracted for a single trial."""

    trial_id: str
    task_name: str
    benchmark: str
    agent_config: str  # AgentConfig enum value
    reward: float | None
    pass_fail: str  # "pass", "fail", "partial", "unknown"
    duration_seconds: float | None
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    tool_utilization: dict


@dataclass(frozen=True)
class ExperimentData:
    """Immutable data for a single experiment (a batch run)."""

    experiment_id: str
    trials: tuple[TrialMetrics, ...]


@dataclass(frozen=True)
class ExtractionResult:
    """Immutable top-level extraction output."""

    run_category: str
    experiments: tuple[ExperimentData, ...]


def _extract_reward(trial_dir: Path) -> float | None:
    """Extract reward from reward.txt or result.json.

    Checks reward.txt first (in verifier/ subdir), then result.json.
    """
    # Check reward.txt in verifier/
    reward_txt = trial_dir / "verifier" / "reward.txt"
    if reward_txt.is_file():
        try:
            text = reward_txt.read_text(encoding="utf-8").strip()
            return float(text)
        except (ValueError, OSError) as exc:
            logger.debug("Cannot parse reward.txt at %s: %s", reward_txt, exc)

    # Check result.json
    result_json = trial_dir / "result.json"
    if result_json.is_file():
        try:
            data = json.loads(result_json.read_text(encoding="utf-8"))
            verifier = data.get("verifier_result") or {}
            rewards = verifier.get("rewards") or {}
            reward_val = rewards.get("reward")
            if reward_val is not None:
                return float(reward_val)
        except (json.JSONDecodeError, OSError, TypeError) as exc:
            logger.debug("Cannot extract reward from result.json at %s: %s", result_json, exc)

    return None


def _classify_pass_fail(reward: float | None) -> str:
    """Classify a reward value into pass/fail/partial/unknown."""
    if reward is None:
        return "unknown"
    if reward >= 1.0:
        return "pass"
    if reward > 0.0:
        return "partial"
    return "fail"


def _extract_timing(trial_dir: Path) -> float | None:
    """Extract duration in seconds from result.json timing fields."""
    result_json = trial_dir / "result.json"
    if not result_json.is_file():
        return None

    try:
        data = json.loads(result_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    # Try agent_execution timing first (actual agent run time)
    agent_exec = data.get("agent_execution") or {}
    started = agent_exec.get("started_at")
    finished = agent_exec.get("finished_at")

    # Fall back to top-level timing
    if not started or not finished:
        started = data.get("started_at")
        finished = data.get("finished_at")

    if not started or not finished:
        return None

    try:
        from datetime import datetime, timezone

        # Parse ISO format timestamps
        start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
        return (end_dt - start_dt).total_seconds()
    except (ValueError, TypeError):
        return None


def _extract_tokens_from_result(trial_dir: Path) -> tuple[int, int, int]:
    """Extract token counts from task_metrics.json or result.json.

    Returns (input_tokens, output_tokens, cached_tokens).
    """
    # Try task_metrics.json first
    task_metrics = trial_dir / "task_metrics.json"
    if task_metrics.is_file():
        try:
            data = json.loads(task_metrics.read_text(encoding="utf-8"))
            return (
                data.get("input_tokens", 0) or 0,
                data.get("output_tokens", 0) or 0,
                data.get("cache_tokens", 0) or data.get("cached_tokens", 0) or 0,
            )
        except (json.JSONDecodeError, OSError):
            pass

    # Fall back to result.json agent_result
    result_json = trial_dir / "result.json"
    if result_json.is_file():
        try:
            data = json.loads(result_json.read_text(encoding="utf-8"))
            agent_result = data.get("agent_result") or {}
            return (
                agent_result.get("n_input_tokens", 0) or 0,
                agent_result.get("n_output_tokens", 0) or 0,
                agent_result.get("n_cache_tokens", 0) or 0,
            )
        except (json.JSONDecodeError, OSError):
            pass

    return (0, 0, 0)


def _extract_benchmark_name(trial_dir: Path) -> str:
    """Extract benchmark name from task_metrics.json or config.json or task name."""
    # Try task_metrics.json
    task_metrics = trial_dir / "task_metrics.json"
    if task_metrics.is_file():
        try:
            data = json.loads(task_metrics.read_text(encoding="utf-8"))
            benchmark = data.get("benchmark", "")
            if benchmark:
                return benchmark
        except (json.JSONDecodeError, OSError):
            pass

    # Try config.json task.path
    config_json = trial_dir / "config.json"
    if config_json.is_file():
        try:
            data = json.loads(config_json.read_text(encoding="utf-8"))
            task_path = ""
            task_conf = data.get("task") or {}
            task_path = task_conf.get("path", "")
            if task_path:
                # Extract benchmark from path like .../benchmarks/big_code_mcp/big-code-k8s-001
                parts = Path(task_path).parts
                if "benchmarks" in parts:
                    idx = parts.index("benchmarks")
                    if idx + 1 < len(parts):
                        return parts[idx + 1]
        except (json.JSONDecodeError, OSError):
            pass

    return "unknown"


def _extract_task_name(trial_dir: Path) -> str:
    """Extract task name from result.json or config.json."""
    result_json = trial_dir / "result.json"
    if result_json.is_file():
        try:
            data = json.loads(result_json.read_text(encoding="utf-8"))
            name = data.get("task_name", "")
            if name:
                return name
        except (json.JSONDecodeError, OSError):
            pass

    # Fall back to config.json
    config_json = trial_dir / "config.json"
    if config_json.is_file():
        try:
            data = json.loads(config_json.read_text(encoding="utf-8"))
            task_conf = data.get("task") or {}
            task_path = task_conf.get("path", "")
            if task_path:
                return Path(task_path).name
        except (json.JSONDecodeError, OSError):
            pass

    return trial_dir.name


def _tool_utilization_to_dict(metrics: ToolUtilizationMetrics) -> dict:
    """Convert ToolUtilizationMetrics to a JSON-serializable dict."""
    raw = asdict(metrics)
    # Convert search_queries from tuple of dicts to list
    raw["search_queries"] = [
        {"tool_name": sq["tool_name"], "query_text": sq["query_text"], "category": sq["category"]}
        for sq in raw.get("search_queries", ())
    ]
    # Convert tool_calls_by_name from tuple of tuples to dict
    raw["tool_calls_by_name"] = dict(raw.get("tool_calls_by_name", ()))
    return raw


def _is_trial_dir(directory: Path) -> bool:
    """Check if a directory is a trial directory (has result.json)."""
    return (directory / "result.json").is_file()


def _find_trials(search_root: Path) -> list[Path]:
    """Recursively find all trial directories under a search root.

    A trial directory is one that contains result.json and has
    an agent/ subdirectory (or at minimum result.json).
    """
    trials: list[Path] = []
    if not search_root.is_dir():
        return trials

    for item in sorted(search_root.iterdir()):
        if not item.is_dir():
            continue
        if _is_trial_dir(item):
            trials.append(item)
        else:
            # Recurse into subdirectories
            trials.extend(_find_trials(item))

    return trials


def _extract_trial(trial_dir: Path) -> TrialMetrics:
    """Extract all metrics for a single trial directory."""
    task_name = _extract_task_name(trial_dir)
    benchmark = _extract_benchmark_name(trial_dir)
    agent_config = detect_agent_config(trial_dir)
    reward = _extract_reward(trial_dir)
    pass_fail = _classify_pass_fail(reward)
    duration = _extract_timing(trial_dir)
    input_tokens, output_tokens, cached_tokens = _extract_tokens_from_result(trial_dir)

    # Extract tool utilization from transcript
    transcript_path = trial_dir / "agent" / "claude-code.txt"
    tool_metrics = extract_tool_utilization(transcript_path)
    tool_util_dict = _tool_utilization_to_dict(tool_metrics)

    return TrialMetrics(
        trial_id=trial_dir.name,
        task_name=task_name,
        benchmark=benchmark,
        agent_config=agent_config.value,
        reward=reward,
        pass_fail=pass_fail,
        duration_seconds=duration,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
        tool_utilization=tool_util_dict,
    )


def _group_trials_by_experiment(
    trials: list[tuple[str, Path]],
) -> dict[str, list[Path]]:
    """Group trial paths by experiment ID.

    The experiment ID is derived from the directory structure.
    Trials are grouped by the first directory under the category.
    """
    groups: dict[str, list[Path]] = {}
    for experiment_id, trial_path in trials:
        if experiment_id not in groups:
            groups[experiment_id] = []
        groups[experiment_id].append(trial_path)
    return groups


def extract_metrics(runs_dir: Path) -> list[dict]:
    """Extract metrics from all trials in a runs directory.

    Args:
        runs_dir: Path to the root runs directory containing
            official/, experiment/, troubleshooting/ subdirectories.

    Returns:
        List of category dicts suitable for JSON serialization.
    """
    categories: list[dict] = []

    for category_name in RUN_CATEGORIES:
        category_dir = runs_dir / category_name
        if not category_dir.is_dir():
            logger.info("Category directory not found, skipping: %s", category_dir)
            continue

        experiments: list[dict] = []

        # Each subdirectory of the category is an experiment
        for experiment_dir in sorted(category_dir.iterdir()):
            if not experiment_dir.is_dir():
                continue

            experiment_id = experiment_dir.name
            trial_dirs = _find_trials(experiment_dir)

            if not trial_dirs:
                logger.info("No trials found in experiment: %s", experiment_id)
                continue

            trial_metrics_list: list[dict] = []
            for trial_dir in trial_dirs:
                try:
                    metrics = _extract_trial(trial_dir)
                    trial_metrics_list.append(asdict(metrics))
                except Exception as exc:
                    logger.warning(
                        "Failed to extract metrics for trial %s: %s",
                        trial_dir,
                        exc,
                    )
                    continue

            if trial_metrics_list:
                experiments.append({
                    "experiment_id": experiment_id,
                    "trials": trial_metrics_list,
                })

        if experiments:
            categories.append({
                "run_category": category_name,
                "experiments": experiments,
            })

    return categories


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the extraction pipeline."""
    parser = argparse.ArgumentParser(
        description="Extract experiment metrics from Harbor runs directory.",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        required=True,
        help="Path to runs directory (contains official/, experiment/, troubleshooting/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/experiment_metrics.json"),
        help="Output path for experiment_metrics.json (default: output/experiment_metrics.json)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    runs_dir: Path = args.runs_dir
    output_path: Path = args.output

    if not runs_dir.is_dir():
        logger.error("Runs directory does not exist: %s", runs_dir)
        return 1

    logger.info("Extracting metrics from: %s", runs_dir)
    categories = extract_metrics(runs_dir)

    # Count totals for summary
    total_experiments = sum(len(cat["experiments"]) for cat in categories)
    total_trials = sum(
        len(exp["trials"])
        for cat in categories
        for exp in cat["experiments"]
    )

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(categories, indent=2, default=str),
        encoding="utf-8",
    )

    logger.info(
        "Extraction complete: %d categories, %d experiments, %d trials -> %s",
        len(categories),
        total_experiments,
        total_trials,
        output_path,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
