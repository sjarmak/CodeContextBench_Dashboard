"""
Trace Parser

Parse Harbor trajectory.json files to extract and format agent execution traces.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ToolCall:
    """Represents a tool invocation."""
    tool_name: str
    parameters: Dict[str, str]
    raw_xml: str


@dataclass
class TraceStep:
    """Represents a step in the execution trace."""
    step_id: int
    timestamp: str
    source: str  # "user" or "agent"
    message: str
    tool_calls: List[ToolCall]
    metrics: Optional[Dict[str, Any]] = None
    is_sidechain: bool = False


class TraceParser:
    """Parse Harbor trajectory files."""

    FUNCTION_CALL_PATTERN = re.compile(
        r'<function_calls>\s*<invoke name="([^"]+)">(.*?)</invoke>\s*</function_calls>',
        re.DOTALL
    )

    PARAMETER_PATTERN = re.compile(
        r'<parameter name="([^"]+)">(.*?)</parameter>',
        re.DOTALL
    )

    @classmethod
    def parse_trajectory_file(cls, trajectory_path: Path) -> List[TraceStep]:
        """
        Parse a trajectory.json file.

        Args:
            trajectory_path: Path to trajectory.json

        Returns:
            List of TraceStep objects
        """
        with open(trajectory_path) as f:
            data = json.load(f)

        steps = []
        for step_data in data.get("steps", []):
            steps.append(cls._parse_step(step_data))

        return steps

    @classmethod
    def _parse_step(cls, step_data: Dict) -> TraceStep:
        """Parse a single step from trajectory data."""
        message = step_data.get("message", "")
        tool_calls = cls._extract_tool_calls(message)

        return TraceStep(
            step_id=step_data.get("step_id", 0),
            timestamp=step_data.get("timestamp", ""),
            source=step_data.get("source", ""),
            message=message,
            tool_calls=tool_calls,
            metrics=step_data.get("metrics"),
            is_sidechain=step_data.get("extra", {}).get("is_sidechain", False)
        )

    @classmethod
    def _extract_tool_calls(cls, message: str) -> List[ToolCall]:
        """Extract tool calls from message text."""
        tool_calls = []

        for match in cls.FUNCTION_CALL_PATTERN.finditer(message):
            tool_name = match.group(1)
            invoke_content = match.group(2)

            # Extract parameters
            parameters = {}
            for param_match in cls.PARAMETER_PATTERN.finditer(invoke_content):
                param_name = param_match.group(1)
                param_value = param_match.group(2).strip()
                parameters[param_name] = param_value

            tool_calls.append(ToolCall(
                tool_name=tool_name,
                parameters=parameters,
                raw_xml=match.group(0)
            ))

        return tool_calls

    @classmethod
    def get_clean_message(cls, step: TraceStep) -> str:
        """
        Get message text without tool call XML.

        Args:
            step: TraceStep object

        Returns:
            Clean message text
        """
        message = step.message

        # Remove all function_calls blocks
        message = cls.FUNCTION_CALL_PATTERN.sub("", message)

        # Clean up extra whitespace
        message = re.sub(r'\n\n\n+', '\n\n', message)
        message = message.strip()

        return message

    @classmethod
    def extract_diffs(cls, tool_calls: List[ToolCall]) -> List[Dict[str, str]]:
        """
        Extract code diffs from Edit/Write tool calls.

        Args:
            tool_calls: List of ToolCall objects

        Returns:
            List of diffs with file_path, old_string, new_string
        """
        diffs = []

        for tool_call in tool_calls:
            if tool_call.tool_name == "Edit":
                diffs.append({
                    "type": "edit",
                    "file_path": tool_call.parameters.get("file_path", ""),
                    "old_string": tool_call.parameters.get("old_string", ""),
                    "new_string": tool_call.parameters.get("new_string", ""),
                })
            elif tool_call.tool_name == "Write":
                diffs.append({
                    "type": "write",
                    "file_path": tool_call.parameters.get("file_path", ""),
                    "content": tool_call.parameters.get("content", ""),
                })

        return diffs

    @classmethod
    def filter_sidechain(cls, steps: List[TraceStep], include_sidechain: bool = False) -> List[TraceStep]:
        """
        Filter out sidechain steps.

        Args:
            steps: List of TraceStep objects
            include_sidechain: Whether to include sidechain steps

        Returns:
            Filtered list of steps
        """
        if include_sidechain:
            return steps

        return [step for step in steps if not step.is_sidechain]

    @classmethod
    def get_tool_usage_summary(cls, steps: List[TraceStep]) -> Dict[str, int]:
        """
        Get summary of tool usage.

        Args:
            steps: List of TraceStep objects

        Returns:
            Dict of tool_name -> count
        """
        tool_counts = {}

        for step in steps:
            for tool_call in step.tool_calls:
                tool_counts[tool_call.tool_name] = tool_counts.get(tool_call.tool_name, 0) + 1

        return tool_counts

    @classmethod
    def get_token_summary(cls, steps: List[TraceStep]) -> Dict[str, int]:
        """
        Get summary of token usage.

        Args:
            steps: List of TraceStep objects

        Returns:
            Dict with total_prompt, total_completion, total_cached
        """
        total_prompt = 0
        total_completion = 0
        total_cached = 0

        for step in steps:
            if step.metrics:
                total_prompt += step.metrics.get("prompt_tokens", 0)
                total_completion += step.metrics.get("completion_tokens", 0)
                total_cached += step.metrics.get("cached_tokens", 0)

        return {
            "total_prompt": total_prompt,
            "total_completion": total_completion,
            "total_cached": total_cached,
            "total": total_prompt + total_completion,
        }
