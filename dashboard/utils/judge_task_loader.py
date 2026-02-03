"""
Reusable task-loading utilities for LLM judge evaluation.

Extracts task instance data from Harbor run directories, including:
- Task description and real task name from config
- Agent solution (solution.md or code changes from trace)
- Oracle data for reference-based evaluation
- MCP tool usage analysis
- Token counts and duration
"""

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TaskInstanceData:
    """All data needed to evaluate a single task instance."""

    task_dir: str
    real_task_name: str
    task_description: str
    effective_solution: str
    solution_type: str  # "solution.md" | "code changes (trace)" | "none"
    trace_content: str  # first 20K of claude-code.txt
    reward: float
    oracle_data: dict
    mcp_analysis: dict
    task_category: str
    difficulty: str
    missing_files: tuple[str, ...]
    tool_counts: dict[str, int]
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    duration: float | None


def _extract_task_description(cmd_content: str, fallback_name: str) -> str:
    """Extract a human-readable task description from command.txt content.

    Harbor command.txt files may contain:
      1. A ``# Task`` markdown section (older format).
      2. A base64-encoded instruction blob embedded in a shell one-liner
         (``echo '<base64>' | base64 -d > ...``).
      3. Plain shell bootstrap with no useful description.

    Returns the best description found, truncated to 3000 chars.
    """
    # Try explicit # Task section first
    task_match = re.search(r"# Task.*?(?=---|'''|$)", cmd_content, re.DOTALL)
    if task_match:
        return task_match.group(0).strip()[:3000]

    # Try decoding a base64 blob (pattern: echo '<base64-data>')
    b64_match = re.search(r"echo '([A-Za-z0-9+/=]{50,})'", cmd_content)
    if b64_match:
        try:
            decoded = base64.b64decode(b64_match.group(1)).decode("utf-8", errors="ignore")
            if decoded.strip():
                return decoded.strip()[:3000]
        except Exception:
            pass

    # Fallback: task ID
    return f"Task ID: {fallback_name}"


def load_task_instance(task_dir: Path) -> TaskInstanceData:
    """Load all evaluation-relevant data from a single task directory.

    Consolidates config.json, result.json, command.txt, solution.md,
    and claude-code.txt into a single TaskInstanceData object.

    Args:
        task_dir: Path to the task instance directory (containing agent/, config.json, etc.)

    Returns:
        TaskInstanceData with all fields populated (missing data uses sensible defaults).
    """
    agent_dir = task_dir / "agent"
    missing_files: list[str] = []

    # --- Real task name from config.json ---
    real_task_name = task_dir.name
    config_file = task_dir / "config.json"
    if config_file.exists():
        try:
            with open(config_file) as f:
                cfg = json.load(f)
            task_path = cfg.get("task", {}).get("path", "")
            if task_path:
                real_task_name = Path(task_path).name
        except (json.JSONDecodeError, KeyError):
            pass
    else:
        missing_files.append("config.json")

    # --- Task description from command.txt ---
    task_description = f"Task ID: {task_dir.name}"
    command_file = agent_dir / "command-1" / "command.txt"
    if command_file.exists():
        try:
            with open(command_file, "r", encoding="utf-8", errors="ignore") as f:
                cmd_content = f.read()
            task_description = _extract_task_description(cmd_content, task_dir.name)
        except Exception:
            pass
    else:
        missing_files.append("command.txt")

    # --- Oracle data ---
    oracle_data: dict[str, Any] = {}
    try:
        from dashboard.views.run_results import load_locobench_oracle
        if load_locobench_oracle:
            oracle_data = load_locobench_oracle(real_task_name) or {}
    except ImportError:
        pass

    task_category = oracle_data.get("task_category", "")
    difficulty = oracle_data.get("difficulty", "")
    is_analysis_task = task_category in {
        "architectural_understanding",
        "code_comprehension",
        "bug_investigation",
        "security_analysis",
    }

    # --- Agent solution ---
    solution_file = agent_dir / "solution.md"
    claude_file = agent_dir / "claude-code.txt"

    agent_solution = ""
    solution_type = "none"
    code_changes = ""

    if solution_file.exists():
        try:
            with open(solution_file, "r", encoding="utf-8", errors="ignore") as f:
                agent_solution = f.read()[:15000]
            solution_type = "solution.md"
        except Exception:
            pass
    else:
        missing_files.append("solution.md")

    if not claude_file.exists():
        missing_files.append("claude-code.txt")
    elif not is_analysis_task:
        code_changes = extract_code_changes_from_trace(claude_file)

    if is_analysis_task and agent_solution:
        effective_solution = agent_solution
        solution_type = "solution.md"
    elif code_changes:
        effective_solution = code_changes
        solution_type = "code changes (trace)"
    elif agent_solution:
        effective_solution = agent_solution
    else:
        effective_solution = "No solution extracted from agent output"

    # --- Trace content and tool counts ---
    trace_content = ""
    tool_counts: dict[str, int] = {}
    mcp_analysis: dict[str, Any] = {}

    if claude_file.exists():
        try:
            with open(claude_file, "r", encoding="utf-8", errors="ignore") as f:
                trace_content = f.read()[:20000]
            tool_counts = extract_tool_counts_from_trace(trace_content)

            try:
                from dashboard.views.run_results import analyze_mcp_tool_usage
                if analyze_mcp_tool_usage:
                    mcp_analysis = analyze_mcp_tool_usage(tool_counts, trace_content) or {}
            except ImportError:
                pass
        except Exception:
            pass

    # --- Result data (reward, tokens, duration) ---
    reward = 0.0
    input_tokens = 0
    output_tokens = 0
    cache_creation_tokens = 0
    cache_read_tokens = 0
    duration: float | None = None

    result_file = task_dir / "result.json"
    if result_file.exists():
        try:
            with open(result_file) as f:
                result_data = json.load(f)
            if "reward" in result_data:
                reward = result_data.get("reward") or 0.0
            elif "verifier_result" in result_data:
                vr = result_data.get("verifier_result") or {}
                reward = (vr.get("rewards") or {}).get("reward") or 0.0

            agent_result = result_data.get("agent_result") or {}
            input_tokens = agent_result.get("n_input_tokens") or 0
            output_tokens = agent_result.get("n_output_tokens") or 0
            cache_creation_tokens = agent_result.get("n_cache_tokens") or 0

            # Check task_metrics.json for more accurate token data
            metrics_file = task_dir / "task_metrics.json"
            if metrics_file.exists():
                try:
                    with open(metrics_file) as f:
                        tm = json.load(f)
                    input_tokens = tm.get("input_tokens") or input_tokens
                    output_tokens = tm.get("output_tokens") or output_tokens
                    cache_creation_tokens = tm.get("cache_creation_tokens") or cache_creation_tokens
                    cache_read_tokens = tm.get("cache_read_tokens") or 0
                except Exception:
                    pass

            started_at = result_data.get("started_at", "")
            finished_at = result_data.get("finished_at", "")
            if started_at and finished_at:
                try:
                    from datetime import datetime
                    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    end = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
                    duration = (end - start).total_seconds()
                except (ValueError, TypeError):
                    pass
        except (json.JSONDecodeError, KeyError):
            pass
    else:
        missing_files.append("result.json")

    return TaskInstanceData(
        task_dir=str(task_dir),
        real_task_name=real_task_name,
        task_description=task_description,
        effective_solution=effective_solution,
        solution_type=solution_type,
        trace_content=trace_content,
        reward=reward,
        oracle_data=oracle_data,
        mcp_analysis=mcp_analysis,
        task_category=task_category,
        difficulty=difficulty,
        missing_files=tuple(missing_files),
        tool_counts=tool_counts,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
        duration=duration,
    )


def build_judge_input(task_data: TaskInstanceData) -> Any:
    """Map TaskInstanceData fields to EnhancedJudgeInput for LLM evaluation.

    Args:
        task_data: Loaded task instance data.

    Returns:
        EnhancedJudgeInput instance ready for judge.evaluate().

    Raises:
        ImportError: If the llm_judge module is not available.
    """
    from src.benchmark.llm_judge import EnhancedJudgeInput

    oracle = task_data.oracle_data
    mcp = task_data.mcp_analysis

    return EnhancedJudgeInput(
        task_id=task_data.real_task_name,
        task_description=task_data.task_description,
        code_changes=task_data.effective_solution,
        tool_calls=task_data.trace_content[:10000],
        reward=task_data.reward,
        trajectory=task_data.trace_content[:8000],
        oracle_ground_truth=oracle.get("ground_truth"),
        oracle_expected_approach=oracle.get("expected_approach"),
        oracle_evaluation_criteria=oracle.get("evaluation_criteria"),
        oracle_context_files=oracle.get("context_files"),
        mcp_tools_used=mcp.get("sourcegraph_tools_used"),
        mcp_effectiveness_score=mcp.get("effectiveness_score"),
        mcp_recommendations=mcp.get("recommendations"),
        task_category=task_data.task_category,
        difficulty=task_data.difficulty,
    )


def extract_code_changes_from_trace(trace_file: Path, max_chars: int = 15000) -> str:
    """Extract actual code changes (diffs/patches) from a claude-code.txt trace file.

    The trace contains JSON messages with Edit tool calls that include:
    - oldString/newString: the before/after content
    - structuredPatch: unified diff format

    Returns a summary of actual code changes for LLM judge evaluation.
    """
    if not trace_file.exists():
        return ""

    try:
        with open(trace_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        code_changes: list[str] = []

        edit_pattern = r'"name"\s*:\s*"Edit"[^}]*"input"\s*:\s*\{[^}]*"file_path"\s*:\s*"([^"]+)"[^}]*"old_string"\s*:\s*"([^"]*)"[^}]*"new_string"\s*:\s*"([^"]*)"'

        for match in re.finditer(edit_pattern, content, re.DOTALL):
            file_path = match.group(1)
            old_str = match.group(2).replace("\\n", "\n").replace("\\t", "\t")[:500]
            new_str = match.group(3).replace("\\n", "\n").replace("\\t", "\t")[:500]

            if old_str or new_str:
                code_changes.append(
                    f"File: {file_path}\n--- Old:\n{old_str}\n+++ New:\n{new_str}\n"
                )

        patch_pattern = r'"structuredPatch"\s*:\s*\[(.*?)\]'
        for match in re.finditer(patch_pattern, content, re.DOTALL):
            patch_content = match.group(1)
            if '"lines"' in patch_content:
                lines_match = re.search(
                    r'"lines"\s*:\s*\[(.*?)\]', patch_content, re.DOTALL
                )
                if lines_match:
                    lines = lines_match.group(1)
                    code_changes.append(f"Patch:\n{lines[:1000]}\n")

        if code_changes:
            result = "\n---\n".join(code_changes[:10])
            return result[:max_chars]

        update_pattern = (
            r"The file ([^\s]+) has been updated[^}]*cat -n[^}]*(\d+→[^\}]+)"
        )
        for match in re.finditer(update_pattern, content, re.DOTALL):
            file_path = match.group(1)
            snippet = match.group(2)[:500]
            code_changes.append(f"Updated: {file_path}\n{snippet}\n")

        if code_changes:
            result = "\n---\n".join(code_changes[:10])
            return result[:max_chars]

        return content[-max_chars:] if len(content) > max_chars else content

    except Exception as e:
        return f"Error extracting code changes: {e}"


def extract_tool_counts_from_trace(trace_content: str) -> dict[str, int]:
    """Extract tool usage counts from trace content."""
    tool_counts: dict[str, int] = {}

    tool_pattern = r'"name"\s*:\s*"([^"]+)"[^}]*"type"\s*:\s*"tool_use"'
    for match in re.finditer(tool_pattern, trace_content):
        tool_name = match.group(1)
        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

    tool_pattern2 = r'"type"\s*:\s*"tool_use"[^}]*"name"\s*:\s*"([^"]+)"'
    for match in re.finditer(tool_pattern2, trace_content):
        tool_name = match.group(1)
        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

    return tool_counts
