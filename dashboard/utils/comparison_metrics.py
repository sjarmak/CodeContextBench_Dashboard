"""
Comparison metrics computation for cross-config analysis.

Derives benefit_pct, efficiency, error rates, and execution phase
breakdowns from paired task_metrics data without modifying source data.
"""

from typing import Optional


def compute_mcp_benefit(
    baseline: Optional[dict],
    variant: Optional[dict],
) -> Optional[dict]:
    """Compute MCP benefit metrics from paired baseline and variant data.

    Args:
        baseline: task_metrics dict for baseline config (can be None).
        variant: task_metrics dict for variant config (can be None).

    Returns:
        Dict with benefit_pct, token_cost_pct, efficiency, or None
        if either input is None or required fields are missing.
    """
    if baseline is None or variant is None:
        return None

    baseline_reward = baseline.get("reward")
    variant_reward = variant.get("reward")
    if baseline_reward is None or variant_reward is None:
        return None

    baseline_input = baseline.get("input_tokens")
    baseline_output = baseline.get("output_tokens")
    variant_input = variant.get("input_tokens")
    variant_output = variant.get("output_tokens")

    # Compute benefit percentage
    benefit_pct = (
        (variant_reward - baseline_reward)
        / max(baseline_reward, 0.001)
        * 100
    )

    # Compute token cost percentage (None if token data missing)
    token_cost_pct: Optional[float] = None
    efficiency: Optional[float] = None

    if (
        baseline_input is not None
        and baseline_output is not None
        and variant_input is not None
        and variant_output is not None
    ):
        baseline_tokens = baseline_input + baseline_output
        variant_tokens = variant_input + variant_output
        token_cost_pct = (
            (variant_tokens - baseline_tokens)
            / max(baseline_tokens, 1)
            * 100
        )
        efficiency = benefit_pct / max(token_cost_pct, 1)

    return {
        "benefit_pct": benefit_pct,
        "token_cost_pct": token_cost_pct,
        "efficiency": efficiency,
    }


def compute_task_ratios(task: Optional[dict]) -> Optional[dict]:
    """Compute task-level ratios from a single task_metrics dict.

    Args:
        task: task_metrics dict (can be None).

    Returns:
        Dict with tool_error_rate_pct, backtrack_ratio,
        execution_phase_breakdown, or None if task is None.
    """
    if task is None:
        return None

    # Tool error rate
    tool_errors = task.get("tool_errors_by_name") or {}
    tool_calls = task.get("tool_calls_by_name") or {}
    total_errors = sum(tool_errors.values()) if tool_errors else 0
    total_calls = sum(tool_calls.values()) if tool_calls else 0
    tool_error_rate_pct = (
        (total_errors / max(total_calls, 1)) * 100
        if total_calls > 0
        else None
    )

    # Backtrack ratio (lines removed vs lines added)
    lines_added = task.get("lines_added")
    lines_removed = task.get("lines_removed")
    backtrack_ratio: Optional[float] = None
    if lines_added is not None and lines_removed is not None:
        backtrack_ratio = lines_removed / max(lines_added, 1)

    # Execution phase breakdown
    wall_clock = task.get("wall_clock_seconds")
    agent_exec = task.get("agent_execution_seconds")
    env_setup = task.get("environment_setup_seconds")
    verifier = task.get("verifier_seconds")

    execution_phase_breakdown: Optional[dict] = None
    if wall_clock is not None and wall_clock > 0:
        execution_phase_breakdown = {
            "agent_pct": ((agent_exec or 0) / wall_clock) * 100,
            "setup_pct": ((env_setup or 0) / wall_clock) * 100,
            "verifier_pct": ((verifier or 0) / wall_clock) * 100,
        }

    return {
        "tool_error_rate_pct": tool_error_rate_pct,
        "backtrack_ratio": backtrack_ratio,
        "execution_phase_breakdown": execution_phase_breakdown,
    }
