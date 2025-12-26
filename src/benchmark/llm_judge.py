"""
LLM Judge Module

Reusable LLM-based evaluation for agent runs.
Evaluates on multiple dimensions:
- Retrieval quality (search/tool usage)
- Code quality (solution correctness and idiomaticity)

Supports multi-LLM voting for consensus.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import os

try:
    import anthropic
except ImportError:
    anthropic = None

from .evaluation_schema import JudgeAssessment


# Evaluation prompts
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


class LLMJudge:
    """LLM-based judge for agent evaluation."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001", api_key: Optional[str] = None):
        """
        Initialize LLM judge.

        Args:
            model: Model name for judging (default: haiku for cost efficiency)
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        if anthropic is None:
            raise ImportError("anthropic package required. Run: pip install anthropic")

        self.model = model
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = anthropic.Anthropic(api_key=api_key)

    def evaluate_retrieval(
        self, task_description: str, tool_calls: str
    ) -> JudgeAssessment:
        """
        Evaluate retrieval quality.

        Args:
            task_description: The task description/instruction
            tool_calls: Formatted string of tool usage

        Returns:
            JudgeAssessment for retrieval quality
        """
        prompt = RETRIEVAL_QUALITY_PROMPT.format(
            task_description=task_description[:2000], tool_calls=tool_calls[:5000]
        )

        result = self._call_llm(prompt)

        return JudgeAssessment(
            dimension="retrieval_quality",
            score=result.get("score", 0),
            reasoning=result.get("reasoning", "Evaluation failed"),
            strengths=result.get("strengths", []),
            weaknesses=result.get("weaknesses", []),
            judge_model=self.model,
        )

    def evaluate_code(
        self, task_description: str, code_changes: str, reward: float
    ) -> JudgeAssessment:
        """
        Evaluate code quality.

        Args:
            task_description: The task description/instruction
            code_changes: Formatted string of code changes
            reward: Task reward (0.0 or 1.0)

        Returns:
            JudgeAssessment for code quality
        """
        prompt = CODE_QUALITY_PROMPT.format(
            task_description=task_description[:2000],
            code_changes=code_changes[:5000],
            reward=reward,
        )

        result = self._call_llm(prompt)

        return JudgeAssessment(
            dimension="code_quality",
            score=result.get("score", 0),
            reasoning=result.get("reasoning", "Evaluation failed"),
            strengths=result.get("strengths", []),
            weaknesses=result.get("weaknesses", []),
            judge_model=self.model,
        )

    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """Call LLM and parse JSON response."""
        try:
            response = self.client.messages.create(
                model=self.model, max_tokens=1000, messages=[{"role": "user", "content": prompt}]
            )

            # Extract text content
            text = response.content[0].text

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


def extract_tool_calls_from_trajectory(trajectory: Dict) -> str:
    """Extract search/retrieval tool calls from trajectory for judge evaluation."""
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

    # Also check old format
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
    for i, call in enumerate(tool_calls[:30], 1):
        lines.append(f"{i}. {call['tool']}")
        if isinstance(call["input"], dict):
            for k, v in list(call["input"].items())[:3]:
                v_str = str(v)[:200]
                lines.append(f"   {k}: {v_str}")

    if len(tool_calls) > 30:
        lines.append(f"... and {len(tool_calls) - 30} more calls")

    return "\n".join(lines)


def extract_code_changes_from_trajectory(trajectory: Dict) -> str:
    """Extract code edit operations from trajectory for judge evaluation."""
    changes = []

    for step in trajectory.get("steps", []):
        extra = step.get("extra", {})
        tool_name = extra.get("tool_use_name", "")

        if tool_name and any(
            x in tool_name.lower() for x in ["edit", "write", "create", "replace"]
        ):
            raw_args = extra.get("raw_arguments", {})
            file_path = raw_args.get("file_path", raw_args.get("path", "unknown"))

            # Extract actual diff content
            if "edit" in tool_name.lower():
                old_str = raw_args.get("old_string", "")
                new_str = raw_args.get("new_string", "")
                changes.append({
                    "type": "edit",
                    "file": file_path,
                    "old": old_str,
                    "new": new_str,
                })
            elif "write" in tool_name.lower():
                content = raw_args.get("content", "")
                changes.append({
                    "type": "write",
                    "file": file_path,
                    "content": content,
                })

    # Also check old format
    for step in trajectory.get("steps", []):
        if step.get("source") != "agent":
            continue

        content = step.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    name = item.get("name", "")
                    input_data = item.get("input", {})

                    if "edit" in name.lower():
                        old_str = input_data.get("old_string", "")
                        new_str = input_data.get("new_string", "")
                        file_path = input_data.get("file_path", input_data.get("path", "unknown"))
                        changes.append({
                            "type": "edit",
                            "file": file_path,
                            "old": old_str,
                            "new": new_str,
                        })
                    elif "write" in name.lower() or "create" in name.lower():
                        content_str = input_data.get("content", "")
                        file_path = input_data.get("file_path", input_data.get("path", "unknown"))
                        changes.append({
                            "type": "write",
                            "file": file_path,
                            "content": content_str,
                        })

    if not changes:
        return "No code changes found"

    lines = []
    for i, change in enumerate(changes[:20], 1):
        if change["type"] == "edit":
            lines.append(f"\n{i}. EDIT: {change['file']}")
            lines.append("=" * 60)
            lines.append("OLD:")
            lines.append(change['old'][:2000] if len(change['old']) > 2000 else change['old'])
            lines.append("\nNEW:")
            lines.append(change['new'][:2000] if len(change['new']) > 2000 else change['new'])
            lines.append("=" * 60)
        elif change["type"] == "write":
            lines.append(f"\n{i}. WRITE: {change['file']}")
            lines.append("=" * 60)
            content = change['content'][:2000] if len(change['content']) > 2000 else change['content']
            lines.append(content)
            lines.append("=" * 60)

    if len(changes) > 20:
        lines.append(f"\n... and {len(changes) - 20} more changes")

    return "\n".join(lines)


def load_task_description(task_path: Path) -> str:
    """Load task description from common instruction files."""
    for filename in ["instruction.md", "TASK.md", "prompt.md", "task.md", "README.md"]:
        task_file = task_path / filename
        if task_file.exists():
            return task_file.read_text()

    # Try task.toml
    toml_file = task_path / "task.toml"
    if toml_file.exists():
        return toml_file.read_text()

    return "Task description not found"
