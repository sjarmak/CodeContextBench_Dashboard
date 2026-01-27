"""
Task detail metadata panel component.

Renders task metadata, build environment, execution metrics,
agent result, verifier output, CLAUDE.md content, and task
instruction prompt in collapsible expander sections.

Supports both paired-mode tasks (from _scan_paired_mode_tasks)
and single-experiment tasks (from load_external_tasks).
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st

from dashboard.utils.benchmark_detection import detect_benchmark_set
from dashboard.utils.task_list import parse_task_metadata

logger = logging.getLogger(__name__)


def _load_json_file(path: Path) -> dict:
    """Load a JSON file, returning empty dict on failure."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load JSON from {path}: {e}")
        return {}


def _compute_timing(result_data: dict) -> dict[str, float]:
    """Extract timing durations from result.json timing phases."""
    timing: dict[str, float] = {}

    for phase in [
        "environment_setup",
        "agent_setup",
        "agent_execution",
        "verifier",
    ]:
        phase_data = result_data.get(phase, {})
        if not isinstance(phase_data, dict):
            continue
        started = phase_data.get("started_at", "")
        finished = phase_data.get("finished_at", "")
        if started and finished:
            try:
                start_dt = datetime.fromisoformat(
                    started.replace("Z", "+00:00")
                )
                end_dt = datetime.fromisoformat(
                    finished.replace("Z", "+00:00")
                )
                timing[phase] = (end_dt - start_dt).total_seconds()
            except (ValueError, TypeError):
                pass

    # Overall timing from top-level fields or timing object
    timing_obj = result_data.get("timing", {})
    if isinstance(timing_obj, dict):
        top_started = timing_obj.get("started_at", "")
        top_finished = timing_obj.get("finished_at", "")
    else:
        top_started = ""
        top_finished = ""

    if not top_started:
        top_started = result_data.get("started_at", "")
    if not top_finished:
        top_finished = result_data.get("finished_at", "")

    if top_started and top_finished:
        try:
            start_dt = datetime.fromisoformat(
                top_started.replace("Z", "+00:00")
            )
            end_dt = datetime.fromisoformat(
                top_finished.replace("Z", "+00:00")
            )
            timing["total"] = (end_dt - start_dt).total_seconds()
        except (ValueError, TypeError):
            pass

    return timing


def _format_seconds(seconds: Optional[float]) -> str:
    """Format seconds into human-readable duration."""
    if seconds is None or seconds == 0:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


def _extract_token_usage(
    task: dict, result_data: dict
) -> dict[str, int]:
    """Extract token usage from task and result data."""
    tokens: dict[str, int] = {}

    # From task-level data (paired mode)
    input_t = task.get("input_tokens")
    output_t = task.get("output_tokens")

    # From agent_result in result.json
    agent_result = result_data.get("agent_result", {})
    if isinstance(agent_result, dict):
        if input_t is None or input_t == 0:
            input_t = agent_result.get("n_input_tokens", 0)
        if output_t is None or output_t == 0:
            output_t = agent_result.get("n_output_tokens", 0)
        tokens["cached"] = agent_result.get("n_cached_tokens", 0)
        tokens["tool_calls"] = agent_result.get("n_tool_calls", 0)
        tokens["cost"] = agent_result.get("cost", 0)

    # From metrics in result.json (single experiment format)
    metrics = result_data.get("metrics", {})
    if isinstance(metrics, dict):
        if input_t is None or input_t == 0:
            input_t = metrics.get("input_tokens", 0)
        if output_t is None or output_t == 0:
            output_t = metrics.get("output_tokens", 0)
        if not tokens.get("cached"):
            tokens["cached"] = metrics.get("cached_tokens", 0)
        if not tokens.get("tool_calls"):
            tokens["tool_calls"] = metrics.get("tool_calls", 0)

    # From total_tokens (single experiment format)
    total_t = task.get("total_tokens")
    if total_t is not None and total_t != "N/A":
        try:
            tokens["total"] = int(total_t)
        except (ValueError, TypeError):
            pass

    tokens["input"] = int(input_t or 0)
    tokens["output"] = int(output_t or 0)

    if "total" not in tokens:
        tokens["total"] = tokens["input"] + tokens["output"]

    return tokens


def _extract_build_environment(
    result_data: dict, instance_dir: Optional[Path]
) -> dict[str, str]:
    """Extract build environment info from config.json and result data."""
    env_info: dict[str, str] = {}

    # Try config.json in instance directory
    config_data: dict = {}
    if instance_dir:
        config_path = instance_dir / "config.json"
        config_data = _load_json_file(config_path)

    # Agent info from config
    agent_config = config_data.get("agent", {})
    if isinstance(agent_config, dict):
        if agent_config.get("model_name"):
            env_info["Model"] = agent_config["model_name"]
        if agent_config.get("import_path"):
            env_info["Agent"] = agent_config["import_path"]
        if agent_config.get("name"):
            env_info["Agent Name"] = agent_config["name"]

    # Agent info from result.json
    agent_info = result_data.get("agent_info", {})
    if isinstance(agent_info, dict):
        if agent_info.get("name") and "Agent Name" not in env_info:
            env_info["Agent Name"] = agent_info["name"]
        model_info = agent_info.get("model_info", {})
        if isinstance(model_info, dict) and model_info.get("name"):
            if "Model" not in env_info:
                env_info["Model"] = model_info["name"]

    # Config from result.json
    result_config = result_data.get("config", {})
    if isinstance(result_config, dict):
        result_agent = result_config.get("agent", {})
        if isinstance(result_agent, dict):
            if result_agent.get("model_name") and "Model" not in env_info:
                env_info["Model"] = result_agent["model_name"]

    # Docker image from config
    docker_config = config_data.get("docker", {})
    if isinstance(docker_config, dict) and docker_config.get("image"):
        env_info["Docker Image"] = docker_config["image"]

    # Environment type
    env_config = config_data.get("environment", {})
    if isinstance(env_config, dict) and env_config.get("type"):
        env_info["Environment"] = env_config["type"]

    # Task source info
    task_info = config_data.get("task", {})
    if isinstance(task_info, dict):
        if task_info.get("path"):
            env_info["Task Path"] = task_info["path"]
        if task_info.get("git_url"):
            env_info["Git URL"] = task_info["git_url"]
        if task_info.get("source"):
            env_info["Source"] = task_info["source"]

    return env_info


def _extract_verifier_output(
    result_data: dict, instance_dir: Optional[Path]
) -> dict:
    """Extract verifier output from result.json and verifier/output.json."""
    verifier: dict = {}

    # From result.json verifier_result
    verifier_result = result_data.get("verifier_result", {})
    if isinstance(verifier_result, dict):
        rewards = verifier_result.get("rewards", {})
        if isinstance(rewards, dict):
            verifier["reward"] = rewards.get("reward")
            # Include all reward breakdown fields
            for key, val in rewards.items():
                if key != "reward":
                    verifier[f"reward_{key}"] = val

        # Test results
        test_result = verifier_result.get("test_result", {})
        if isinstance(test_result, dict):
            verifier["tests_passed"] = test_result.get("passed", 0)
            verifier["tests_failed"] = test_result.get("failed", 0)
            verifier["tests_total"] = test_result.get("total", 0)
            verifier["test_output"] = test_result.get("output", "")

    # Try verifier/output.json in instance directory
    if instance_dir:
        verifier_output_path = instance_dir / "verifier" / "output.json"
        verifier_output = _load_json_file(verifier_output_path)
        if verifier_output:
            # Merge verifier output data (don't overwrite existing)
            for key, val in verifier_output.items():
                if key not in verifier:
                    verifier[key] = val

    return verifier


def _extract_claude_md_content(instance_dir: Optional[Path]) -> Optional[str]:
    """Extract CLAUDE.md content from the agent session directory.

    Searches for CLAUDE.md in these locations (in order):
    1. instance_dir/agent/.claude.json (sessions config with CLAUDE.md content)
    2. instance_dir/CLAUDE.md
    3. instance_dir/agent/CLAUDE.md
    4. instance_dir parent directories (up to 3 levels) for project CLAUDE.md

    Returns the CLAUDE.md content as a string, or None if not found.
    """
    if not instance_dir or not instance_dir.exists():
        return None

    # 1. Check .claude.json for embedded CLAUDE.md content
    claude_json_path = instance_dir / "agent" / ".claude.json"
    if claude_json_path.exists():
        try:
            with open(claude_json_path) as f:
                claude_config = json.load(f)
            # .claude.json may contain a claudeMd field
            claude_md = claude_config.get("claudeMd", "")
            if claude_md:
                return claude_md
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read .claude.json: {e}")

    # Also check sessions/.claude.json
    sessions_claude_json = instance_dir / "sessions" / ".claude.json"
    if sessions_claude_json.exists():
        try:
            with open(sessions_claude_json) as f:
                claude_config = json.load(f)
            claude_md = claude_config.get("claudeMd", "")
            if claude_md:
                return claude_md
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read sessions/.claude.json: {e}")

    # 2. Check instance_dir/CLAUDE.md
    claude_md_path = instance_dir / "CLAUDE.md"
    if claude_md_path.exists():
        try:
            return claude_md_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning(f"Failed to read {claude_md_path}: {e}")

    # 3. Check instance_dir/agent/CLAUDE.md
    agent_claude_md = instance_dir / "agent" / "CLAUDE.md"
    if agent_claude_md.exists():
        try:
            return agent_claude_md.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning(f"Failed to read {agent_claude_md}: {e}")

    # 4. Search parent directories (up to 3 levels)
    parent = instance_dir.parent
    for _ in range(3):
        if parent == parent.parent:
            break
        candidate = parent / "CLAUDE.md"
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8")
            except OSError as e:
                logger.warning(f"Failed to read {candidate}: {e}")
        parent = parent.parent

    return None


def _extract_task_prompt(
    instance_dir: Optional[Path],
    result_data: dict,
) -> Optional[str]:
    """Extract the task instruction prompt from trace data or task config.

    Searches for the prompt in these locations (in order):
    1. First system message in agent/claude-code.txt JSONL
    2. Task config problem_statement field (SWE-Bench format)
    3. Task config instruction or prompt field

    Returns the prompt content as a string, or None if not found.
    """
    if not instance_dir or not instance_dir.exists():
        # Try result_data as fallback
        return _extract_prompt_from_config(result_data)

    # 1. Extract from claude-code.txt first system message
    claude_file = instance_dir / "agent" / "claude-code.txt"
    if claude_file.exists():
        prompt = _parse_system_prompt_from_jsonl(claude_file)
        if prompt:
            return prompt

    # 2. Extract from task config
    config_data = _load_json_file(instance_dir / "config.json")
    if config_data:
        prompt = _extract_prompt_from_config(config_data)
        if prompt:
            return prompt

    # 3. Try tests/config.json (SWE-Bench format)
    tests_config = instance_dir / "tests" / "config.json"
    if tests_config.exists():
        config_data = _load_json_file(tests_config)
        prompt = _extract_prompt_from_config(config_data)
        if prompt:
            return prompt

    # 4. Fallback to result_data
    return _extract_prompt_from_config(result_data)


def _parse_system_prompt_from_jsonl(claude_file: Path) -> Optional[str]:
    """Parse the first system message from a claude-code.txt JSONL file."""
    try:
        with open(claude_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if record.get("type") == "system":
                    message = record.get("message", {})
                    # System message content can be a string or list
                    content = message.get("content", "")
                    if isinstance(content, list):
                        # Join text blocks from content array
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                            elif isinstance(item, str):
                                text_parts.append(item)
                        return "\n".join(text_parts) if text_parts else None
                    if isinstance(content, str) and content.strip():
                        return content
    except OSError as e:
        logger.warning(f"Failed to read {claude_file}: {e}")
    return None


def _extract_prompt_from_config(config_data: dict) -> Optional[str]:
    """Extract task prompt from config data dict."""
    if not isinstance(config_data, dict):
        return None

    # SWE-Bench format: problem_statement
    problem = config_data.get("problem_statement")
    if problem and isinstance(problem, str):
        return problem

    # Task config: instruction or prompt field
    task_config = config_data.get("task", {})
    if isinstance(task_config, dict):
        instruction = task_config.get("instruction") or task_config.get("prompt")
        if instruction and isinstance(instruction, str):
            return instruction

    # Direct instruction/prompt field
    instruction = config_data.get("instruction") or config_data.get("prompt")
    if instruction and isinstance(instruction, str):
        return instruction

    return None


def render_task_detail_panel(
    task: dict,
    instance_dir: Optional[Path] = None,
    experiment_path: Optional[Path] = None,
) -> None:
    """
    Render the full task detail metadata panel with collapsible sections.

    Args:
        task: Task dict with at minimum task_name/task_id and status fields
        instance_dir: Path to the task instance directory (contains result.json, config.json)
        experiment_path: Path to the parent experiment directory (for benchmark detection)
    """
    task_name = task.get("task_name", task.get("task_id", "unknown"))

    # Resolve instance_dir from task if not provided
    if instance_dir is None:
        task_instance_dir = task.get("instance_dir")
        if task_instance_dir is not None:
            instance_dir = Path(task_instance_dir) if not isinstance(
                task_instance_dir, Path
            ) else task_instance_dir

    # Load result.json from instance directory
    result_data: dict = {}
    if instance_dir:
        result_data = _load_json_file(instance_dir / "result.json")

    # --- Section 1: Task Metadata ---
    metadata = parse_task_metadata(task_name)

    benchmark_source = "Unknown"
    if experiment_path:
        benchmark_source = detect_benchmark_set(experiment_path)

    # Gather tags from task metadata and result data
    tags: list[str] = []
    task_id_info = result_data.get("task_id", {})
    if isinstance(task_id_info, dict):
        task_tags = task_id_info.get("tags", [])
        if isinstance(task_tags, list):
            tags = [str(t) for t in task_tags]

    with st.expander("Task Metadata", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Task ID:** `{task_name}`")
            st.markdown(f"**Benchmark Source:** {benchmark_source}")
            st.markdown(f"**Language:** {metadata.language}")
        with col2:
            st.markdown(f"**Difficulty:** {metadata.difficulty}")
            st.markdown(f"**Task Type:** {metadata.task_type}")
            if tags:
                st.markdown(f"**Tags:** {', '.join(tags)}")

    # --- Section 2: Build Environment ---
    env_info = _extract_build_environment(result_data, instance_dir)

    with st.expander("Build Environment", expanded=True):
        if env_info:
            col1, col2 = st.columns(2)
            items = list(env_info.items())
            mid = (len(items) + 1) // 2
            with col1:
                for key, val in items[:mid]:
                    st.markdown(f"**{key}:** `{val}`")
            with col2:
                for key, val in items[mid:]:
                    st.markdown(f"**{key}:** `{val}`")
        else:
            st.info("No build environment information available.")

    # --- Section 3: Execution Metrics ---
    timing = _compute_timing(result_data)
    tokens = _extract_token_usage(task, result_data)

    with st.expander("Execution Metrics", expanded=True):
        # Duration metrics row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Duration", _format_seconds(timing.get("total")))
        with col2:
            st.metric(
                "Agent Execution", _format_seconds(timing.get("agent_execution"))
            )
        with col3:
            st.metric(
                "Env Setup", _format_seconds(timing.get("environment_setup"))
            )
        with col4:
            st.metric("Verifier", _format_seconds(timing.get("verifier")))

        # Token metrics row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Input Tokens", f"{tokens['input']:,}")
        with col2:
            st.metric("Output Tokens", f"{tokens['output']:,}")
        with col3:
            cached = tokens.get("cached", 0)
            st.metric("Cached Tokens", f"{cached:,}")
        with col4:
            tool_calls = tokens.get("tool_calls", 0)
            st.metric("Tool Calls", f"{tool_calls:,}")

        # Summary row
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Tokens", f"{tokens['total']:,}")
        with col2:
            reward = task.get("reward")
            if reward is not None and reward != "N/A":
                try:
                    st.metric("Reward Score", f"{float(reward):.4f}")
                except (ValueError, TypeError):
                    st.metric("Reward Score", str(reward))
            else:
                st.metric("Reward Score", "N/A")

    # --- Section 4: Agent Result ---
    agent_result = result_data.get("agent_result", {})
    status = task.get("status", "unknown")

    with st.expander("Agent Result", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            # Pass/Fail badge
            reward_val = task.get("reward")
            if reward_val is not None and reward_val != "N/A":
                try:
                    passed = float(reward_val) > 0
                except (ValueError, TypeError):
                    passed = False
            else:
                passed = status == "completed"

            if status == "error":
                st.error("Status: Error")
            elif passed:
                st.success("Status: Pass")
            else:
                st.warning("Status: Fail")

        with col2:
            if isinstance(agent_result, dict):
                exit_code = agent_result.get("exit_code")
                if exit_code is not None:
                    st.markdown(f"**Exit Code:** `{exit_code}`")
                else:
                    st.markdown("**Exit Code:** N/A")
            else:
                st.markdown("**Exit Code:** N/A")

        # Error info
        error_info = result_data.get("exception_info")
        if not error_info:
            error_info = task.get("error")
        if error_info:
            st.markdown("**Error:**")
            st.code(str(error_info), language="text")

    # --- Section 5: Verifier Output ---
    verifier = _extract_verifier_output(result_data, instance_dir)

    with st.expander("Verifier Output", expanded=False):
        if verifier:
            # Test counts
            tests_passed = verifier.get("tests_passed")
            tests_failed = verifier.get("tests_failed")
            tests_total = verifier.get("tests_total")

            if tests_total is not None:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Tests Passed", tests_passed or 0)
                with col2:
                    st.metric("Tests Failed", tests_failed or 0)
                with col3:
                    st.metric("Tests Total", tests_total)

            # Reward breakdown
            reward_keys = [
                k for k in verifier if k.startswith("reward_")
            ]
            if reward_keys:
                st.markdown("**Reward Breakdown:**")
                breakdown_data = {
                    k.replace("reward_", ""): verifier[k]
                    for k in reward_keys
                }
                for name, value in breakdown_data.items():
                    st.markdown(f"- **{name}:** {value}")

            # Overall reward
            if verifier.get("reward") is not None:
                st.markdown(f"**Overall Reward:** {verifier['reward']}")

            # Test output
            test_output = verifier.get("test_output", "")
            if test_output:
                st.markdown("**Test Output:**")
                # Truncate long output
                output_str = str(test_output)
                if len(output_str) > 5000:
                    st.code(output_str[:5000], language="text")
                    st.caption("(output truncated)")
                else:
                    st.code(output_str, language="text")
        else:
            st.info("No verifier output available.")

    # --- Section 6: CLAUDE.md Content ---
    claude_md_content = _extract_claude_md_content(instance_dir)

    with st.expander("CLAUDE.md", expanded=False):
        if claude_md_content:
            st.markdown(claude_md_content)
        else:
            st.info("Not available")

    # --- Section 7: Task Instruction Prompt ---
    task_prompt = _extract_task_prompt(instance_dir, result_data)

    with st.expander("Task Instruction Prompt", expanded=False):
        if task_prompt:
            st.markdown(task_prompt)
        else:
            st.info("Not available")
