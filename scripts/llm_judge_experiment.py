#!/usr/bin/env python3
"""
LLM-as-Judge Evaluation for MCP Experiment

Evaluates agent outputs on two dimensions:
1. Retrieval Quality - How well did the agent use search/context tools?
2. Code Quality - How correct and idiomatic is the solution?

Usage:
    python scripts/llm_judge_experiment.py <experiment_dir> [--model MODEL]
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Try to import anthropic
try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed")
    print("Run: pip install anthropic")
    sys.exit(1)


RETRIEVAL_QUALITY_PROMPT = """You are evaluating an AI coding agent's use of code search and retrieval tools.

## Task Description
{task_description}

## Agent's Tool Usage (Search/Retrieval Calls)
{tool_calls}

## Evaluation Criteria

Rate the agent's retrieval strategy on a scale of 1-5:

1. **Terrible**: No relevant searches, missed obvious queries, or searched for wrong things
2. **Poor**: Some relevant searches but missed key areas, inefficient queries
3. **Adequate**: Found main relevant code but could have been more thorough
4. **Good**: Comprehensive search strategy, found all key files and context
5. **Excellent**: Optimal search strategy, efficient queries, perfect context gathering

Consider:
- Did the agent search for the right concepts?
- Did it find the relevant files/functions?
- Was the search strategy efficient (not too many redundant calls)?
- Did it gather enough context before making changes?

Respond with JSON:
{{
    "score": <1-5>,
    "reasoning": "<2-3 sentence explanation>",
    "strengths": ["<strength 1>", "<strength 2>"],
    "weaknesses": ["<weakness 1>", "<weakness 2>"]
}}
"""

CODE_QUALITY_PROMPT = """You are evaluating an AI coding agent's solution to a coding task.

## Task Description
{task_description}

## Agent's Solution (Code Changes)
{code_changes}

## Task Result
Reward: {reward} (1.0 = success, 0.0 = failure)

## Evaluation Criteria

Rate the solution quality on a scale of 1-5:

1. **Terrible**: Completely wrong approach, broken code, or no meaningful changes
2. **Poor**: Partially correct but significant issues, hacky workarounds
3. **Adequate**: Works but not ideal, some code quality issues
4. **Good**: Correct solution, follows conventions, minor improvements possible
5. **Excellent**: Optimal solution, clean code, follows best practices

Consider:
- Does the solution correctly address the task?
- Is the code idiomatic for the language/framework?
- Are there any bugs or edge cases missed?
- Is the solution maintainable?

Respond with JSON:
{{
    "score": <1-5>,
    "reasoning": "<2-3 sentence explanation>",
    "strengths": ["<strength 1>", "<strength 2>"],
    "weaknesses": ["<weakness 1>", "<weakness 2>"]
}}
"""


def load_task_description(task_path: Path) -> str:
    """Load task description from instruction.md or other common files."""
    for filename in ["instruction.md", "TASK.md", "prompt.md", "task.md", "README.md"]:
        task_file = task_path / filename
        if task_file.exists():
            return task_file.read_text()

    # Also try task.toml
    toml_file = task_path / "task.toml"
    if toml_file.exists():
        return toml_file.read_text()

    return "Task description not found"


def extract_tool_calls(trajectory: dict) -> str:
    """Extract search/retrieval tool calls from trajectory."""
    tool_calls = []

    for step in trajectory.get("steps", []):
        extra = step.get("extra", {})
        tool_name = extra.get("tool_use_name", "")

        if tool_name:
            # Include MCP search tools and local search tools
            if any(
                x in tool_name.lower()
                for x in ["search", "grep", "find", "read", "mcp__", "sg_", "glob"]
            ):
                raw_args = extra.get("raw_arguments", {})
                tool_calls.append({"tool": tool_name, "input": raw_args})

    # Also check old format (content list)
    for step in trajectory.get("steps", []):
        if step.get("source") != "agent":
            continue

        content = step.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    name = item.get("name", "")
                    if any(
                        x in name.lower()
                        for x in ["search", "grep", "find", "read", "mcp__", "sg_"]
                    ):
                        input_data = item.get("input", {})
                        tool_calls.append({"tool": name, "input": input_data})

    if not tool_calls:
        return "No search/retrieval tool calls found"

    # Format for display
    lines = []
    for i, call in enumerate(tool_calls[:30], 1):  # Limit to 30 calls
        lines.append(f"{i}. {call['tool']}")
        if isinstance(call["input"], dict):
            for k, v in list(call["input"].items())[:3]:  # Limit fields
                v_str = str(v)[:200]  # Limit value length
                lines.append(f"   {k}: {v_str}")

    if len(tool_calls) > 30:
        lines.append(f"... and {len(tool_calls) - 30} more calls")

    return "\n".join(lines)


def extract_code_changes(trajectory: dict) -> str:
    """Extract code edit operations from trajectory."""
    changes = []

    for step in trajectory.get("steps", []):
        extra = step.get("extra", {})
        tool_name = extra.get("tool_use_name", "")

        if tool_name and any(
            x in tool_name.lower() for x in ["edit", "write", "create", "replace"]
        ):
            raw_args = extra.get("raw_arguments", {})
            changes.append(
                {
                    "tool": tool_name,
                    "file": raw_args.get("file_path", raw_args.get("path", "unknown")),
                    "content_preview": str(raw_args)[:500],
                }
            )

    # Also check old format (content list)
    for step in trajectory.get("steps", []):
        if step.get("source") != "agent":
            continue

        content = step.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    name = item.get("name", "")
                    if any(
                        x in name.lower()
                        for x in ["edit", "write", "create", "replace"]
                    ):
                        input_data = item.get("input", {})
                        changes.append(
                            {
                                "tool": name,
                                "file": input_data.get(
                                    "file_path", input_data.get("path", "unknown")
                                ),
                                "content_preview": str(input_data)[:500],
                            }
                        )

    if not changes:
        return "No code changes found"

    lines = []
    for i, change in enumerate(changes[:20], 1):
        lines.append(f"{i}. {change['tool']} on {change['file']}")
        lines.append(f"   Preview: {change['content_preview'][:200]}...")

    if len(changes) > 20:
        lines.append(f"... and {len(changes) - 20} more changes")

    return "\n".join(lines)


def evaluate_with_llm(client: anthropic.Anthropic, prompt: str, model: str) -> dict:
    """Call LLM to evaluate and parse response."""
    try:
        response = client.messages.create(
            model=model, max_tokens=1000, messages=[{"role": "user", "content": prompt}]
        )

        # Extract text content
        text = response.content[0].text

        # Try to parse JSON
        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        return json.loads(text.strip())
    except Exception as e:
        return {
            "score": 0,
            "reasoning": f"Evaluation failed: {str(e)}",
            "strengths": [],
            "weaknesses": ["Evaluation error"],
        }


def evaluate_run(
    client: anthropic.Anthropic, run_dir: Path, task_description: str, model: str
) -> dict:
    """Evaluate a single agent run."""
    # Find trajectory file
    trajectory_files = list(run_dir.rglob("trajectory.json"))
    if not trajectory_files:
        return {"error": "No trajectory.json found"}

    trajectory_path = trajectory_files[0]
    with open(trajectory_path) as f:
        trajectory = json.load(f)

    # Find result file
    result_files = list(run_dir.rglob("result.json"))
    reward = 0.0
    if result_files:
        with open(result_files[0]) as f:
            result = json.load(f)
            # Extract reward from nested structure
            stats = result.get("stats", {}).get("evals", {})
            for eval_data in stats.values():
                metrics = eval_data.get("metrics", [])
                if metrics:
                    reward = metrics[0].get("mean", 0.0)
                    break

    # Extract tool calls and code changes
    tool_calls = extract_tool_calls(trajectory)
    code_changes = extract_code_changes(trajectory)

    # Evaluate retrieval quality
    retrieval_prompt = RETRIEVAL_QUALITY_PROMPT.format(
        task_description=task_description[:2000], tool_calls=tool_calls[:5000]
    )
    retrieval_eval = evaluate_with_llm(client, retrieval_prompt, model)

    # Evaluate code quality
    code_prompt = CODE_QUALITY_PROMPT.format(
        task_description=task_description[:2000],
        code_changes=code_changes[:5000],
        reward=reward,
    )
    code_eval = evaluate_with_llm(client, code_prompt, model)

    return {
        "reward": reward,
        "retrieval": retrieval_eval,
        "code": code_eval,
        "tool_call_count": len(trajectory.get("steps", [])),
        "trajectory_path": str(trajectory_path),
    }


def detect_experiment_format(experiment_dir: Path) -> str:
    """Detect if this is single-task or multi-task format."""
    # Check for agent directories directly under experiment_dir
    agent_names = {"strategic", "aggressive", "baseline"}
    subdirs = {d.name for d in experiment_dir.iterdir() if d.is_dir()}

    if subdirs & agent_names:
        return "single-task"

    # Check for task directories
    for subdir in experiment_dir.iterdir():
        if subdir.is_dir() and subdir.name.startswith("big-code-"):
            return "multi-task"

    return "unknown"


def find_task_from_trajectory(trajectory_path: Path) -> str:
    """Extract task name from trajectory path."""
    # Look for big-code-* in path
    for part in trajectory_path.parts:
        if "big-code-" in part:
            # Extract just the task name
            if "__" in part:
                return part.split("__")[0]
            return part
    return "unknown-task"


def main():
    parser = argparse.ArgumentParser(description="LLM-as-Judge Evaluation")
    parser.add_argument("experiment_dir", help="Path to experiment directory")
    parser.add_argument(
        "--model",
        default="claude-haiku-4-5-20251001",
        help="Model for judge evaluation",
    )
    args = parser.parse_args()

    experiment_dir = Path(args.experiment_dir)
    if not experiment_dir.exists():
        print(f"ERROR: Experiment directory not found: {experiment_dir}")
        sys.exit(1)

    # Initialize Anthropic client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Detect experiment format
    exp_format = detect_experiment_format(experiment_dir)
    print(f"Detected format: {exp_format}")

    results = {}

    if exp_format == "single-task":
        # Agent directories at top level, find task from trajectory
        for agent_dir in sorted(experiment_dir.iterdir()):
            if not agent_dir.is_dir() or agent_dir.name.startswith("."):
                continue

            agent_name = agent_dir.name
            if agent_name not in {"strategic", "aggressive", "baseline"}:
                continue

            # Find trajectory to get task name
            trajectory_files = list(agent_dir.rglob("trajectory.json"))
            if not trajectory_files:
                continue

            task_name = find_task_from_trajectory(trajectory_files[0])

            if task_name not in results:
                results[task_name] = {}

            # Load task description
            task_path = Path("benchmarks/big_code_mcp") / task_name
            task_description = load_task_description(task_path)

            print(f"\nEvaluating {agent_name} on {task_name}")

            eval_result = evaluate_run(client, agent_dir, task_description, args.model)
            results[task_name][agent_name] = eval_result

            if "error" not in eval_result:
                r_score = eval_result["retrieval"].get("score", 0)
                c_score = eval_result["code"].get("score", 0)
                reward = eval_result["reward"]
                print(f"  Reward: {reward}, Retrieval: {r_score}/5, Code: {c_score}/5")
    else:
        # Multi-task format: task directories with agent subdirectories
        for task_dir in sorted(experiment_dir.iterdir()):
            if not task_dir.is_dir() or task_dir.name.startswith("."):
                continue

            task_name = task_dir.name
            if not task_name.startswith("big-code-"):
                continue

            print(f"\nEvaluating task: {task_name}")

            # Load task description
            task_path = Path("benchmarks/big_code_mcp") / task_name
            task_description = load_task_description(task_path)

            results[task_name] = {}

            # Evaluate each agent
            for agent_dir in sorted(task_dir.iterdir()):
                if not agent_dir.is_dir():
                    continue

                agent_name = agent_dir.name
                print(f"  Evaluating agent: {agent_name}")

                eval_result = evaluate_run(
                    client, agent_dir, task_description, args.model
                )
                results[task_name][agent_name] = eval_result

                # Print quick summary
                if "error" not in eval_result:
                    r_score = eval_result["retrieval"].get("score", 0)
                    c_score = eval_result["code"].get("score", 0)
                    reward = eval_result["reward"]
                    print(
                        f"    Reward: {reward}, Retrieval: {r_score}/5, Code: {c_score}/5"
                    )

    # Save results
    output_path = experiment_dir / "llm_judge_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n✓ Results saved to {output_path}")

    # Print summary table
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Task':<20} {'Agent':<12} {'Reward':<8} {'Retrieval':<10} {'Code':<8}")
    print("-" * 60)

    for task_name, agents in results.items():
        for agent_name, eval_result in agents.items():
            if "error" in eval_result:
                print(f"{task_name:<20} {agent_name:<12} ERROR")
                continue

            reward = eval_result["reward"]
            r_score = eval_result["retrieval"].get("score", 0)
            c_score = eval_result["code"].get("score", 0)
            print(
                f"{task_name:<20} {agent_name:<12} {reward:<8.1f} {r_score:<10}/5 {c_score:<8}/5"
            )


if __name__ == "__main__":
    main()
