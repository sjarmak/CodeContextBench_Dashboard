"""
LLM judge test prompt utility.

Allows testing the current judge configuration on a single task
and displaying the result inline. Uses the Prompt & Rubric Editor
config from session state to build evaluation prompts.
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import streamlit as st

from dashboard.utils.judge_config import (
    JudgeConfig,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DimensionResult:
    """Score result for a single dimension."""

    name: str
    score: str  # "pass", "partial", "fail" or numeric
    reasoning: str


@dataclass(frozen=True)
class TestPromptResult:
    """Result from testing a judge prompt on a single task."""

    task_id: str
    dimension_results: tuple[DimensionResult, ...]
    overall_score: str
    overall_reasoning: str
    error: Optional[str] = None


def _load_task_data(task_dir: Path) -> dict:
    """Load task data from a task directory.

    Extracts task description, code changes, and trace content
    from the task directory files.

    Args:
        task_dir: Path to the task instance directory

    Returns:
        Dict with task_description, code_changes, trace_content,
        reward, and config fields
    """
    data: dict = {
        "task_description": "",
        "code_changes": "",
        "trace_content": "",
        "reward": 0.0,
        "config": {},
    }

    # Load config.json
    config_file = task_dir / "config.json"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                task_config = json.load(f)
            data["config"] = task_config

            # Extract task description from config
            task_info = task_config.get("task", {})
            description = (
                task_info.get("problem_statement")
                or task_info.get("instruction")
                or task_info.get("prompt")
                or task_config.get("problem_statement")
                or task_config.get("instruction")
                or task_config.get("prompt")
                or ""
            )
            data["task_description"] = description
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load config.json: %s", e)

    # Fallback: try tests/config.json (SWE-Bench format)
    if not data["task_description"]:
        tests_config = task_dir / "tests" / "config.json"
        if tests_config.exists():
            try:
                with open(tests_config, "r", encoding="utf-8") as f:
                    tc = json.load(f)
                data["task_description"] = tc.get("problem_statement", "")
            except (json.JSONDecodeError, OSError):
                pass

    # Load result.json for reward
    result_file = task_dir / "result.json"
    if result_file.exists():
        try:
            with open(result_file, "r", encoding="utf-8") as f:
                result_data = json.load(f)
            if "reward" in result_data:
                data["reward"] = float(result_data.get("reward", 0.0))
            elif "verifier_result" in result_data:
                data["reward"] = float(
                    result_data.get("verifier_result", {})
                    .get("rewards", {})
                    .get("reward", 0.0)
                )
        except (json.JSONDecodeError, OSError, ValueError) as e:
            logger.warning("Failed to load result.json: %s", e)

    # Load trace content from claude-code.txt
    agent_dir = task_dir / "agent"
    claude_file = agent_dir / "claude-code.txt"
    if claude_file.exists():
        try:
            with open(claude_file, "r", encoding="utf-8", errors="ignore") as f:
                data["trace_content"] = f.read()[:20000]
        except OSError as e:
            logger.warning("Failed to load claude-code.txt: %s", e)

    # Extract code changes from trace
    data["code_changes"] = _extract_code_changes(data["trace_content"])

    # Load solution.md if available
    solution_file = agent_dir / "solution.md" if agent_dir.exists() else None
    if solution_file and solution_file.exists():
        try:
            with open(solution_file, "r", encoding="utf-8", errors="ignore") as f:
                data["solution"] = f.read()[:15000]
        except OSError:
            pass

    # Fallback task description from trace system message
    if not data["task_description"] and data["trace_content"]:
        data["task_description"] = _extract_description_from_trace(
            data["trace_content"]
        )

    return data


def _extract_code_changes(trace_content: str, max_chars: int = 15000) -> str:
    """Extract code changes from JSONL trace content.

    Parses Edit tool calls to find old_string/new_string pairs.

    Args:
        trace_content: Raw JSONL trace content
        max_chars: Maximum characters to return

    Returns:
        Formatted string of code changes
    """
    if not trace_content:
        return ""

    changes: list[str] = []

    for line in trace_content.split("\n"):
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        if msg.get("type") != "assistant":
            continue

        content = msg.get("content", [])
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue

            tool_name = block.get("name", "")
            tool_input = block.get("input", {})

            if tool_name == "Edit":
                file_path = tool_input.get("file_path", "unknown")
                old_str = tool_input.get("old_string", "")[:500]
                new_str = tool_input.get("new_string", "")[:500]
                if old_str or new_str:
                    changes.append(
                        f"File: {file_path}\n--- Old:\n{old_str}\n+++ New:\n{new_str}"
                    )
            elif tool_name == "Write":
                file_path = tool_input.get("file_path", "unknown")
                content_str = tool_input.get("content", "")[:1000]
                if content_str:
                    changes.append(f"File: {file_path}\n+++ Written:\n{content_str}")

    if not changes:
        return ""

    result = "\n---\n".join(changes[:10])
    return result[:max_chars]


def _extract_description_from_trace(trace_content: str) -> str:
    """Extract task description from the first system message in trace.

    Args:
        trace_content: Raw JSONL trace content

    Returns:
        Extracted description or empty string
    """
    for line in trace_content.split("\n"):
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        if msg.get("type") != "system":
            continue

        content = msg.get("content", "")
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            content = "\n".join(parts)

        if content:
            return content[:3000]

    return ""


def _build_evaluation_prompt(
    config: JudgeConfig,
    task_description: str,
    code_changes: str,
    reward: float,
) -> str:
    """Build an evaluation prompt from the judge config and task data.

    Uses the config system prompt, dimensions, and criteria to construct
    a structured evaluation prompt.

    Args:
        config: JudgeConfig with system prompt and dimensions
        task_description: Description of the task
        code_changes: Agent's code changes
        reward: Task reward score

    Returns:
        Formatted evaluation prompt string
    """
    parts: list[str] = [config.system_prompt, ""]

    parts.append("## Task Description")
    parts.append(task_description[:3000] if task_description else "No description available")
    parts.append("")

    parts.append("## Agent's Solution")
    parts.append(code_changes[:10000] if code_changes else "No code changes extracted")
    parts.append("")

    parts.append("## Test Result")
    parts.append(f"Reward: {reward} (1.0 = tests passed, 0.0 = tests failed)")
    parts.append("")

    parts.append("## Scoring Dimensions")
    for dim in config.dimensions:
        parts.append(f"### {dim.name} (weight: {dim.weight})")
        for criterion in dim.criteria:
            parts.append(f"  Score {criterion.level}: {criterion.description}")
        parts.append("")

    parts.append("## Instructions")
    parts.append(
        "For each scoring dimension, provide a score (1-5) and brief reasoning."
    )
    parts.append("Then provide an overall score (1-5) as a weighted average.")
    parts.append("")
    parts.append("Respond with valid JSON only:")
    parts.append("{")
    parts.append('  "dimensions": [')
    for i, dim in enumerate(config.dimensions):
        comma = "," if i < len(config.dimensions) - 1 else ""
        parts.append(
            f'    {{"name": "{dim.name}", "score": <1-5>, "reasoning": "<brief>"}}{comma}'
        )
    parts.append("  ],")
    parts.append('  "overall_score": <1-5>,')
    parts.append('  "overall_reasoning": "<2-3 sentences>"')
    parts.append("}")

    return "\n".join(parts)


def _parse_judge_response(response_text: str, config: JudgeConfig) -> TestPromptResult:
    """Parse the LLM judge response into a TestPromptResult.

    Args:
        response_text: Raw text response from the LLM
        config: JudgeConfig used for the evaluation

    Returns:
        TestPromptResult with parsed scores and reasoning
    """
    # Strip markdown code blocks
    text = response_text
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        # Try to extract partial JSON
        import re

        json_match = re.search(
            r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL
        )
        if json_match:
            try:
                data = json.loads(json_match.group(0))
            except json.JSONDecodeError:
                return TestPromptResult(
                    task_id="",
                    dimension_results=(),
                    overall_score="N/A",
                    overall_reasoning="Failed to parse judge response as JSON.",
                    error=f"JSON parse error. Raw response: {response_text[:500]}",
                )
        else:
            return TestPromptResult(
                task_id="",
                dimension_results=(),
                overall_score="N/A",
                overall_reasoning="Failed to parse judge response as JSON.",
                error=f"No JSON found in response. Raw response: {response_text[:500]}",
            )

    # Parse dimension results
    dim_results: list[DimensionResult] = []
    for dim_data in data.get("dimensions", []):
        dim_results.append(
            DimensionResult(
                name=str(dim_data.get("name", "Unknown")),
                score=str(dim_data.get("score", "N/A")),
                reasoning=str(dim_data.get("reasoning", "")),
            )
        )

    overall_score = str(data.get("overall_score", "N/A"))
    overall_reasoning = str(data.get("overall_reasoning", ""))

    return TestPromptResult(
        task_id="",
        dimension_results=tuple(dim_results),
        overall_score=overall_score,
        overall_reasoning=overall_reasoning,
    )


def run_test_prompt(
    config: JudgeConfig,
    task_dir: Path,
    task_id: str,
) -> TestPromptResult:
    """Run the judge with the given config on a single task.

    Loads task data, builds evaluation prompt, calls the LLM,
    and parses the response.

    Args:
        config: JudgeConfig with system prompt, dimensions, model settings
        task_dir: Path to the task instance directory
        task_id: Task identifier for display

    Returns:
        TestPromptResult with scores and reasoning
    """
    try:
        import anthropic
    except ImportError:
        return TestPromptResult(
            task_id=task_id,
            dimension_results=(),
            overall_score="N/A",
            overall_reasoning="",
            error="anthropic package not installed. Run: pip install anthropic",
        )

    # Load task data
    task_data = _load_task_data(task_dir)

    # Use solution.md for analysis tasks, code_changes otherwise
    effective_solution = task_data.get("solution", "") or task_data.get(
        "code_changes", ""
    )
    if not effective_solution:
        effective_solution = "No solution extracted from agent output"

    # Build prompt
    prompt = _build_evaluation_prompt(
        config=config,
        task_description=task_data["task_description"],
        code_changes=effective_solution,
        reward=task_data["reward"],
    )

    # Call the LLM
    try:
        import os

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return TestPromptResult(
                task_id=task_id,
                dimension_results=(),
                overall_score="N/A",
                overall_reasoning="",
                error="ANTHROPIC_API_KEY not set in environment",
            )

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text
        result = _parse_judge_response(response_text, config)

        return TestPromptResult(
            task_id=task_id,
            dimension_results=result.dimension_results,
            overall_score=result.overall_score,
            overall_reasoning=result.overall_reasoning,
            error=result.error,
        )

    except Exception as e:
        return TestPromptResult(
            task_id=task_id,
            dimension_results=(),
            overall_score="N/A",
            overall_reasoning="",
            error=f"API call failed: {e}",
        )


def _find_experiment_tasks(
    runs_dir: Path,
    experiment_name: str,
) -> list[tuple[str, Path]]:
    """Find all task directories in an experiment.

    Args:
        runs_dir: Base runs directory
        experiment_name: Name of the experiment

    Returns:
        List of (task_id, task_dir) tuples
    """
    exp_dir = runs_dir / experiment_name
    if not exp_dir.exists():
        return []

    tasks: list[tuple[str, Path]] = []

    # Check for paired experiment structure
    baseline_dir = exp_dir / "baseline"
    deepsearch_dir = exp_dir / "deepsearch"

    if baseline_dir.exists() or deepsearch_dir.exists():
        # Paired experiment - scan subdirectories
        for mode_dir in [baseline_dir, deepsearch_dir]:
            if not mode_dir.exists():
                continue
            for subdir in sorted(mode_dir.iterdir()):
                if not subdir.is_dir():
                    continue
                # Check nested timestamp dirs
                for item in sorted(subdir.iterdir()):
                    if item.is_dir() and (item / "result.json").exists():
                        task_id = f"{subdir.name}/{item.name}"
                        tasks.append((task_id, item))
                # Or direct task dir
                if (subdir / "result.json").exists():
                    tasks.append((subdir.name, subdir))
    else:
        # Standard Harbor format
        for d in sorted(exp_dir.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            if (d / "agent").exists() or (d / "result.json").exists():
                tasks.append((d.name, d))

    return tasks


def render_test_prompt_section(project_root: Path) -> None:
    """Render the test prompt UI section.

    Displays a task selector and test button. When clicked,
    runs the judge on the selected task using the current editor
    config and displays results inline.

    Args:
        project_root: Path to the project root directory
    """
    st.markdown("---")
    st.markdown("### Test Prompt on Single Task")

    # Get available experiments
    runs_dir = Path(
        os.environ.get(
            "CCB_EXTERNAL_RUNS_DIR",
            os.path.expanduser("~/evals/custom_agents/agents/claudecode/runs"),
        )
    )

    if not runs_dir.exists():
        st.info("No experiments directory found. Set CCB_EXTERNAL_RUNS_DIR.")
        return

    experiments: list[str] = []
    for d in sorted(runs_dir.iterdir(), key=lambda x: x.name):
        if d.is_dir() and not d.name.startswith("."):
            experiments.append(d.name)

    if not experiments:
        st.info("No experiments found.")
        return

    # Experiment selector
    selected_exp = st.selectbox(
        "Experiment",
        experiments,
        key="test_prompt_experiment",
    )

    if not selected_exp:
        return

    # Task selector
    tasks = _find_experiment_tasks(runs_dir, selected_exp)
    if not tasks:
        st.info("No tasks found in this experiment.")
        return

    task_ids = [t[0] for t in tasks]
    selected_task_idx = st.selectbox(
        "Task",
        range(len(task_ids)),
        format_func=lambda i: task_ids[i],
        key="test_prompt_task",
    )

    if selected_task_idx is None:
        return

    selected_task_id = tasks[selected_task_idx][0]
    selected_task_dir = tasks[selected_task_idx][1]

    # Test button
    if st.button(
        "Test Prompt",
        key="test_prompt_run_btn",
        type="primary",
    ):
        _run_and_display_result(
            project_root=project_root,
            task_id=selected_task_id,
            task_dir=selected_task_dir,
        )

    # Display previous result if stored in session state
    prev_result = st.session_state.get("test_prompt_result")
    if prev_result and not st.session_state.get("test_prompt_running", False):
        _display_result(prev_result)


def _run_and_display_result(
    project_root: Path,
    task_id: str,
    task_dir: Path,
) -> None:
    """Run the test prompt and display the result.

    Args:
        project_root: Project root path
        task_id: Task identifier
        task_dir: Path to task directory
    """
    from dashboard.utils.judge_editor import _session_state_to_config

    config = _session_state_to_config()

    st.session_state["test_prompt_running"] = True

    with st.spinner("Running judge evaluation..."):
        result = run_test_prompt(
            config=config,
            task_dir=task_dir,
            task_id=task_id,
        )

    st.session_state["test_prompt_result"] = result
    st.session_state["test_prompt_running"] = False

    _display_result(result)


def _display_result(result: TestPromptResult) -> None:
    """Display the test prompt result inline.

    Args:
        result: TestPromptResult to display
    """
    if result.error:
        st.error(f"Evaluation error: {result.error}")
        return

    st.markdown("#### Results")

    # Per-dimension scores
    if result.dimension_results:
        for dim_result in result.dimension_results:
            with st.expander(
                f"**{dim_result.name}**: Score {dim_result.score}/5",
                expanded=True,
            ):
                st.markdown(dim_result.reasoning)

    # Overall score
    st.markdown("---")
    col_score, col_reasoning = st.columns([1, 3])
    with col_score:
        st.metric("Overall Score", f"{result.overall_score}/5")
    with col_reasoning:
        st.markdown(f"**Reasoning:** {result.overall_reasoning}")
