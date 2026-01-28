"""
Parse trajectory.json files (ATIF format) to extract per-tool token usage.

Extracts:
- Total token usage (prompt, completion, cached)
- Per-tool token attribution
- Per-category token aggregation (MCP, DEEP_SEARCH, LOCAL, OTHER)
- Cost calculations using model pricing

Token Attribution Strategy:
- Steps with 1 tool call: Attribute all step tokens to that tool
- Steps with multiple tool calls: Divide tokens equally among tools
- Steps with 0 tool calls: Attribute to OTHER category
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .transcript_parser import ToolCategory

logger = logging.getLogger(__name__)


@dataclass
class TrajectoryStep:
    """A single step from the trajectory."""
    step_id: int
    source: str  # "user" or "agent"
    timestamp: str
    message: Optional[str] = None
    model_name: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    tool_calls: list[str] = field(default_factory=list)  # List of tool names
    is_sidechain: bool = False


@dataclass
class TrajectoryMetrics:
    """Metrics extracted from a trajectory.json file."""
    # Total token usage
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cached_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_cache_read_tokens: int = 0

    # Cost
    cost_usd: Optional[float] = None
    cost_breakdown: dict = field(default_factory=dict)

    # Per-category token attribution
    # Format: {ToolCategory.MCP: {"prompt": X, "completion": Y, "cached": Z}}
    tokens_by_category: dict[ToolCategory, dict[str, int]] = field(default_factory=dict)

    # Per-tool token attribution
    # Format: {"sg_keyword_search": {"prompt": X, "completion": Y, "cached": Z}}
    tokens_by_tool: dict[str, dict[str, int]] = field(default_factory=dict)

    # Tool call counts (for comparison with TranscriptMetrics)
    tool_call_counts: dict[str, int] = field(default_factory=dict)
    total_tool_calls: int = 0

    # Metadata
    schema_version: str = ""
    session_id: str = ""
    agent_name: str = ""
    agent_version: str = ""
    model_name: str = ""
    total_steps: int = 0
    agent_steps: int = 0


class TrajectoryParser:
    """Parse trajectory.json files to extract token usage per tool."""

    def __init__(self, calculate_cost: bool = True):
        """
        Initialize parser.

        Args:
            calculate_cost: Whether to calculate cost from token usage
        """
        self.calculate_cost = calculate_cost

    def parse_file(self, trajectory_path: Path) -> Optional[TrajectoryMetrics]:
        """
        Parse a trajectory.json file.

        Args:
            trajectory_path: Path to trajectory.json

        Returns:
            TrajectoryMetrics if successful, None if parsing fails
        """
        try:
            content = trajectory_path.read_text(encoding="utf-8")
            data = json.loads(content)
            return self.parse_data(data)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {trajectory_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing {trajectory_path}: {e}")
            return None

    def parse_data(self, data: dict) -> TrajectoryMetrics:
        """
        Parse trajectory data from a dictionary.

        Args:
            data: Loaded trajectory.json data

        Returns:
            TrajectoryMetrics with extracted data
        """
        metrics = TrajectoryMetrics()

        # Extract metadata
        metrics.schema_version = data.get("schema_version", "")
        metrics.session_id = data.get("session_id", "")

        agent_info = data.get("agent", {})
        metrics.agent_name = agent_info.get("name", "")
        metrics.agent_version = agent_info.get("version", "")
        metrics.model_name = agent_info.get("model_name", "")

        # Initialize category token dicts
        for category in ToolCategory:
            metrics.tokens_by_category[category] = {
                "prompt": 0,
                "completion": 0,
                "cached": 0,
            }

        # Extract steps and process them
        steps = self._extract_steps(data)
        metrics.total_steps = len(steps)

        for step in steps:
            if step.source != "agent":
                continue

            if step.is_sidechain:
                # Skip warmup/sidechain steps for attribution
                # but still count tokens
                pass

            metrics.agent_steps += 1

            # Accumulate totals
            metrics.total_prompt_tokens += step.prompt_tokens
            metrics.total_completion_tokens += step.completion_tokens
            metrics.total_cached_tokens += step.cached_tokens
            metrics.total_cache_creation_tokens += step.cache_creation_tokens
            metrics.total_cache_read_tokens += step.cache_read_tokens

            # Attribute tokens to tools/categories
            self._attribute_tokens(step, metrics)

        # Use final_metrics as fallback if step-level totals are too low
        # This handles trajectory formats where per-step metrics are incomplete
        final_metrics = data.get("final_metrics", {})
        if final_metrics:
            final_prompt = final_metrics.get("total_prompt_tokens", 0)
            final_completion = final_metrics.get("total_completion_tokens", 0)
            final_cached = final_metrics.get("total_cached_tokens", 0)

            # Use final_metrics if they're significantly higher than step totals
            # (indicating incomplete step-level data)
            if final_prompt > metrics.total_prompt_tokens * 1.1:  # 10% tolerance
                metrics.total_prompt_tokens = final_prompt
            if final_completion > metrics.total_completion_tokens * 1.1:
                metrics.total_completion_tokens = final_completion
            if final_cached > metrics.total_cached_tokens * 1.1:
                metrics.total_cached_tokens = final_cached

            # Extract extra cache metrics from final_metrics
            extra = final_metrics.get("extra", {})
            if extra:
                if extra.get("total_cache_creation_input_tokens", 0) > metrics.total_cache_creation_tokens:
                    metrics.total_cache_creation_tokens = extra.get("total_cache_creation_input_tokens", 0)
                if extra.get("total_cache_read_input_tokens", 0) > metrics.total_cache_read_tokens:
                    metrics.total_cache_read_tokens = extra.get("total_cache_read_input_tokens", 0)

        # Calculate cost if requested
        if self.calculate_cost and metrics.model_name:
            self._calculate_cost(metrics)

        return metrics

    def _extract_steps(self, data: dict) -> list[TrajectoryStep]:
        """Extract steps from trajectory data."""
        steps = []
        raw_steps = data.get("steps", [])

        for raw_step in raw_steps:
            step = TrajectoryStep(
                step_id=raw_step.get("step_id", 0),
                source=raw_step.get("source", ""),
                timestamp=raw_step.get("timestamp", ""),
                message=raw_step.get("message"),
                model_name=raw_step.get("model_name"),
            )

            # Extract metrics if present
            metrics_data = raw_step.get("metrics", {})
            if metrics_data:
                step.prompt_tokens = metrics_data.get("prompt_tokens", 0)
                step.completion_tokens = metrics_data.get("completion_tokens", 0)
                step.cached_tokens = metrics_data.get("cached_tokens", 0)

                # Extract detailed cache metrics from extra
                extra_metrics = metrics_data.get("extra", {})
                step.cache_creation_tokens = extra_metrics.get("cache_creation_input_tokens", 0)
                step.cache_read_tokens = extra_metrics.get("cache_read_input_tokens", 0)

            # Extract tool calls
            tool_calls = raw_step.get("tool_calls", [])
            for tc in tool_calls:
                tool_name = tc.get("function_name", "")
                if tool_name:
                    step.tool_calls.append(tool_name)

            # Check for sidechain (warmup)
            extra = raw_step.get("extra", {})
            step.is_sidechain = extra.get("is_sidechain", False)

            steps.append(step)

        return steps

    def _attribute_tokens(self, step: TrajectoryStep, metrics: TrajectoryMetrics) -> None:
        """
        Attribute step tokens to tools and categories.

        Token Attribution Strategy:
        - 1 tool call: All step tokens to that tool
        - Multiple tool calls: Divide tokens equally
        - 0 tool calls: Attribute to OTHER category
        """
        prompt = step.prompt_tokens
        completion = step.completion_tokens
        cached = step.cached_tokens

        if not step.tool_calls:
            # No tool calls - attribute to OTHER
            metrics.tokens_by_category[ToolCategory.OTHER]["prompt"] += prompt
            metrics.tokens_by_category[ToolCategory.OTHER]["completion"] += completion
            metrics.tokens_by_category[ToolCategory.OTHER]["cached"] += cached
            return

        # Calculate per-tool share
        num_tools = len(step.tool_calls)
        per_tool_prompt = prompt // num_tools
        per_tool_completion = completion // num_tools
        per_tool_cached = cached // num_tools

        # Handle remainder (give to first tool)
        remainder_prompt = prompt % num_tools
        remainder_completion = completion % num_tools
        remainder_cached = cached % num_tools

        for i, tool_name in enumerate(step.tool_calls):
            # Count tool calls
            metrics.tool_call_counts[tool_name] = metrics.tool_call_counts.get(tool_name, 0) + 1
            metrics.total_tool_calls += 1

            # Calculate this tool's share
            tool_prompt = per_tool_prompt + (remainder_prompt if i == 0 else 0)
            tool_completion = per_tool_completion + (remainder_completion if i == 0 else 0)
            tool_cached = per_tool_cached + (remainder_cached if i == 0 else 0)

            # Attribute to tool
            if tool_name not in metrics.tokens_by_tool:
                metrics.tokens_by_tool[tool_name] = {
                    "prompt": 0,
                    "completion": 0,
                    "cached": 0,
                }
            metrics.tokens_by_tool[tool_name]["prompt"] += tool_prompt
            metrics.tokens_by_tool[tool_name]["completion"] += tool_completion
            metrics.tokens_by_tool[tool_name]["cached"] += tool_cached

            # Attribute to category
            category = self._categorize_tool(tool_name)
            metrics.tokens_by_category[category]["prompt"] += tool_prompt
            metrics.tokens_by_category[category]["completion"] += tool_completion
            metrics.tokens_by_category[category]["cached"] += tool_cached

    def _categorize_tool(self, tool_name: str) -> ToolCategory:
        """
        Categorize a tool by name.

        Reuses logic from TranscriptParser for consistency.
        """
        tool_lower = tool_name.lower()

        # MCP tools (check prefix first - mcp__ tools are MCP servers)
        if tool_lower.startswith("mcp__") or tool_lower.startswith("mcp_"):
            return ToolCategory.MCP

        # Sourcegraph MCP tools
        if any(x in tool_lower for x in [
            "sourcegraph", "sg_", "keyword_search", "nls_search",
            "read_file", "list_files", "go_to_definition", "commit_search",
        ]):
            return ToolCategory.MCP

        # Deep Search tools (Sourcegraph Deep Search, not MCP prefix)
        if "deepsearch" in tool_lower or "deep_search" in tool_lower:
            return ToolCategory.DEEP_SEARCH

        # Local tools (Claude Code built-ins)
        if any(x in tool_lower for x in [
            "bash", "shell", "grep", "find", "ls", "cat", "sed",
            "awk", "cut", "head", "tail", "sort", "uniq",
            "read", "write", "edit", "glob", "todowrite", "task",
        ]):
            return ToolCategory.LOCAL

        return ToolCategory.OTHER

    def _calculate_cost(self, metrics: TrajectoryMetrics) -> None:
        """Calculate cost using the cost_calculator module."""
        try:
            from ..benchmark.cost_calculator import calculate_cost

            cost_result = calculate_cost(
                model_name=metrics.model_name,
                input_tokens=metrics.total_prompt_tokens,
                output_tokens=metrics.total_completion_tokens,
                cache_creation_tokens=metrics.total_cache_creation_tokens,
                cache_read_tokens=metrics.total_cache_read_tokens,
            )

            metrics.cost_usd = cost_result.get("total_cost", 0.0)
            metrics.cost_breakdown = cost_result
        except ImportError:
            logger.warning("cost_calculator not available, skipping cost calculation")
        except Exception as e:
            logger.warning(f"Error calculating cost: {e}")
