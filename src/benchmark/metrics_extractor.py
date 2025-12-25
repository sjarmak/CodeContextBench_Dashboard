"""
Metrics Extraction from Harbor Results

Extracts comprehensive metrics from Harbor trajectory and result files:
- Tool usage statistics
- Token consumption and caching
- Timing information
- Success/failure status
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
from datetime import datetime
from collections import defaultdict

from .evaluation_schema import (
    AgentRunEvaluation,
    TokenMetrics,
    TimingMetrics,
    ToolUsageSummary,
)


class MetricsExtractor:
    """Extract metrics from Harbor result and trajectory files."""

    def __init__(self, trial_dir: Path):
        """
        Initialize extractor for a trial directory.

        Args:
            trial_dir: Path to trial directory (e.g., jobs/.../task__trial_id/)
        """
        self.trial_dir = trial_dir
        self.result_path = trial_dir / "result.json"
        self.trajectory_path = trial_dir / "agent" / "trajectory.json"

    def extract_all(self) -> Optional[AgentRunEvaluation]:
        """
        Extract all metrics from trial directory.

        Returns:
            AgentRunEvaluation object with all metrics, or None if files missing
        """
        if not self.result_path.exists() or not self.trajectory_path.exists():
            return None

        # Load files
        with open(self.result_path) as f:
            result_data = json.load(f)

        with open(self.trajectory_path) as f:
            trajectory_data = json.load(f)

        # Extract components
        token_metrics = self._extract_token_metrics(result_data, trajectory_data)
        timing_metrics = self._extract_timing_metrics(result_data)
        tool_usage = self._extract_tool_usage(trajectory_data)

        # Extract identity and results
        task_name = result_data.get("task_name", "unknown")
        trial_name = result_data.get("trial_name", "unknown")

        agent_config = result_data.get("config", {}).get("agent", {})
        agent_import_path = agent_config.get("import_path", "unknown")
        model_name = agent_config.get("model_name", "unknown")

        # Derive agent name from import path (e.g., "agents.foo:BarAgent" -> "BarAgent")
        agent_name = agent_import_path.split(":")[-1] if ":" in agent_import_path else "unknown"

        # Extract reward
        verifier_result = result_data.get("verifier_result", {})
        rewards = verifier_result.get("rewards", {})
        reward = rewards.get("reward", 0.0)
        success = reward > 0.0

        # Exception info
        exception_info = result_data.get("exception_info")
        if exception_info:
            exception_info = str(exception_info)

        return AgentRunEvaluation(
            trial_name=trial_name,
            task_name=task_name,
            agent_name=agent_name,
            agent_import_path=agent_import_path,
            model_name=model_name,
            reward=float(reward),
            success=success,
            token_metrics=token_metrics,
            timing_metrics=timing_metrics,
            tool_usage=tool_usage,
            judge_assessments=[],  # Populated later by LLM judge
            trajectory_path=str(self.trajectory_path),
            result_path=str(self.result_path),
            exception_info=exception_info,
        )

    def _extract_token_metrics(self, result_data: Dict, trajectory_data: Dict) -> TokenMetrics:
        """Extract token usage metrics."""
        agent_result = result_data.get("agent_result", {})

        total_input = agent_result.get("n_input_tokens", 0)
        total_output = agent_result.get("n_output_tokens", 0)
        total_cache = agent_result.get("n_cache_tokens", 0)
        cost_usd = agent_result.get("cost_usd")

        # Extract cache breakdown from trajectory steps
        cache_creation = 0
        cache_read = 0

        for step in trajectory_data.get("steps", []):
            metrics = step.get("metrics", {})
            extra = metrics.get("extra", {})

            cache_creation += extra.get("cache_creation_input_tokens", 0)
            cache_read += extra.get("cache_read_input_tokens", 0)

        return TokenMetrics(
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cache_tokens=total_cache,
            total_cost_usd=cost_usd,
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read,
        )

    def _extract_timing_metrics(self, result_data: Dict) -> TimingMetrics:
        """Extract timing information."""
        env_setup = result_data.get("environment_setup", {})
        agent_setup = result_data.get("agent_setup", {})
        agent_exec = result_data.get("agent_execution", {})
        verifier = result_data.get("verifier", {})

        def parse_duration(start: str, end: str) -> float:
            """Parse duration in seconds from ISO timestamps."""
            try:
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                return (end_dt - start_dt).total_seconds()
            except:
                return 0.0

        env_sec = parse_duration(
            env_setup.get("started_at", ""), env_setup.get("finished_at", "")
        )
        agent_setup_sec = parse_duration(
            agent_setup.get("started_at", ""), agent_setup.get("finished_at", "")
        )
        exec_sec = parse_duration(
            agent_exec.get("started_at", ""), agent_exec.get("finished_at", "")
        )
        verifier_sec = parse_duration(
            verifier.get("started_at", ""), verifier.get("finished_at", "")
        )

        total_sec = parse_duration(
            result_data.get("started_at", ""), result_data.get("finished_at", "")
        )

        return TimingMetrics(
            environment_setup_sec=env_sec,
            agent_setup_sec=agent_setup_sec,
            agent_execution_sec=exec_sec,
            verifier_sec=verifier_sec,
            total_sec=total_sec,
            started_at=result_data.get("started_at", ""),
            finished_at=result_data.get("finished_at", ""),
        )

    def _extract_tool_usage(self, trajectory_data: Dict) -> List[ToolUsageSummary]:
        """Extract tool usage statistics from trajectory."""
        tool_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"calls": 0, "successes": 0, "failures": 0, "tokens": []}
        )

        for step in trajectory_data.get("steps", []):
            # Check for tool usage in step.extra
            extra = step.get("extra", {})
            tool_name = extra.get("tool_use_name")

            if tool_name:
                stats = tool_stats[tool_name]
                stats["calls"] += 1

                # Check for tool result (success/failure)
                # This is heuristic - Harbor doesn't always mark tool success explicitly
                # We assume success unless there's an explicit error
                if "error" in extra or "exception" in extra:
                    stats["failures"] += 1
                else:
                    stats["successes"] += 1

                # Track tokens for this step
                metrics = step.get("metrics", {})
                prompt_tokens = metrics.get("prompt_tokens", 0)
                completion_tokens = metrics.get("completion_tokens", 0)
                stats["tokens"].append(prompt_tokens + completion_tokens)

            # Also check old format (content list with tool_use type)
            content = step.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        name = item.get("name", "unknown")
                        stats = tool_stats[name]
                        stats["calls"] += 1
                        stats["successes"] += 1  # Assume success in old format

        # Convert to ToolUsageSummary objects
        summaries = []
        for tool_name, stats in tool_stats.items():
            total_tokens = sum(stats["tokens"])
            avg_tokens = total_tokens / stats["calls"] if stats["calls"] > 0 else 0.0

            summaries.append(
                ToolUsageSummary(
                    tool_name=tool_name,
                    call_count=stats["calls"],
                    success_count=stats["successes"],
                    failure_count=stats["failures"],
                    total_tokens=total_tokens,
                    avg_tokens_per_call=avg_tokens,
                )
            )

        return sorted(summaries, key=lambda x: x.call_count, reverse=True)


def extract_experiment_metrics(experiment_dir: Path) -> List[AgentRunEvaluation]:
    """
    Extract metrics from all trials in an experiment directory.

    Args:
        experiment_dir: Path to experiment directory (e.g., jobs/2025-12-23__11-13-40/)

    Returns:
        List of AgentRunEvaluation objects
    """
    evaluations = []

    # Find all trial directories (contain result.json)
    for trial_dir in experiment_dir.rglob("*"):
        if not trial_dir.is_dir():
            continue

        result_file = trial_dir / "result.json"
        if result_file.exists():
            extractor = MetricsExtractor(trial_dir)
            evaluation = extractor.extract_all()
            if evaluation:
                evaluations.append(evaluation)

    return evaluations
