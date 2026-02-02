"""
Extract tool utilization metrics from claude-code.txt JSONL files.

Parses JSONL events to compute:
- Tool call counts by name and category (MCP/DEEP_SEARCH/LOCAL/OTHER)
- Search query text from MCP tool calls
- Deep Search vs keyword search ratio
- Context window fill rate (cumulative input tokens / model context limit)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.ingest.transcript_parser import ToolCategory

logger = logging.getLogger(__name__)

# Claude Haiku 4.5 context window size
MODEL_CONTEXT_LIMIT = 200_000


@dataclass(frozen=True)
class SearchQuery:
    """A single search query extracted from a tool call."""

    tool_name: str
    query_text: str
    category: str  # "keyword", "nls", "deep_search"


@dataclass(frozen=True)
class ToolUtilizationMetrics:
    """Immutable metrics extracted from claude-code.txt JSONL."""

    # Counts by tool name
    tool_calls_by_name: tuple[tuple[str, int], ...] = ()

    # Counts by category
    mcp_calls: int = 0
    deep_search_calls: int = 0
    local_calls: int = 0
    other_calls: int = 0
    total_tool_calls: int = 0

    # Search queries
    search_queries: tuple[SearchQuery, ...] = ()
    keyword_search_count: int = 0
    nls_search_count: int = 0
    deep_search_query_count: int = 0

    # Ratios
    deep_search_vs_keyword_ratio: float = 0.0

    # Context window utilization
    cumulative_input_tokens: int = 0
    cumulative_output_tokens: int = 0
    cumulative_cached_tokens: int = 0
    context_fill_rate: float = 0.0

    # From result summary (if present)
    total_cost_usd: float = 0.0
    duration_ms: int = 0
    num_turns: int = 0

    # Malformed line count for diagnostics
    skipped_lines: int = 0


def _categorize_tool(tool_name: str) -> ToolCategory:
    """Categorize a tool by its name.

    MCP tools use the mcp__sourcegraph__ prefix.
    Deep search tools contain 'deepsearch' or 'deep_search' in name.
    Local tools are standard Claude Code tools (Bash, Read, Write, etc.).
    """
    name_lower = tool_name.lower()

    # Deep Search tools
    if "deepsearch" in name_lower or "deep_search" in name_lower:
        return ToolCategory.DEEP_SEARCH

    # MCP/Sourcegraph tools (but not deep search)
    if name_lower.startswith("mcp__"):
        return ToolCategory.MCP

    # Local tools (standard Claude Code tools)
    local_tools = {
        "bash", "read", "write", "edit", "glob", "grep",
        "notebookedit", "webfetch", "websearch", "todowrite",
        "task", "taskoutput", "taskstop", "skill",
        "enterplanmode", "exitplanmode", "askuserquestion",
        "toolsearch",
    }
    if name_lower in local_tools:
        return ToolCategory.LOCAL

    return ToolCategory.OTHER


def _classify_search_tool(tool_name: str) -> str | None:
    """Classify a tool as a search type, or None if not a search tool."""
    name_lower = tool_name.lower()

    if "deepsearch" in name_lower or "deep_search" in name_lower:
        return "deep_search"
    if "nls_search" in name_lower or "nls" in name_lower:
        return "nls"
    if "keyword_search" in name_lower or "keyword" in name_lower:
        return "keyword"
    return None


def _extract_query_text(tool_input: dict) -> str:
    """Extract the query text from a tool call input dict."""
    # Most search tools use "query" key
    query = tool_input.get("query", "")
    if isinstance(query, str):
        return query
    return ""


def extract_tool_utilization(transcript_path: Path) -> ToolUtilizationMetrics:
    """Extract tool utilization metrics from a claude-code.txt JSONL file.

    Args:
        transcript_path: Path to claude-code.txt file.

    Returns:
        Frozen ToolUtilizationMetrics dataclass with all computed fields.
    """
    if not transcript_path.is_file():
        logger.warning("Transcript file not found: %s", transcript_path)
        return ToolUtilizationMetrics()

    tool_counts: dict[str, int] = {}
    category_counts = {
        ToolCategory.MCP: 0,
        ToolCategory.DEEP_SEARCH: 0,
        ToolCategory.LOCAL: 0,
        ToolCategory.OTHER: 0,
    }
    search_queries: list[SearchQuery] = []
    keyword_count = 0
    nls_count = 0
    deep_search_count = 0

    cumulative_input = 0
    cumulative_output = 0
    cumulative_cached = 0

    total_cost = 0.0
    duration_ms = 0
    num_turns = 0
    skipped = 0

    try:
        content = transcript_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Cannot read transcript %s: %s", transcript_path, exc)
        return ToolUtilizationMetrics()

    for line_num, line in enumerate(content.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            logger.debug("Skipping malformed JSONL line %d in %s", line_num, transcript_path)
            continue

        entry_type = entry.get("type", "")

        # Extract tool calls from assistant messages
        if entry_type == "assistant":
            message = entry.get("message") or {}
            usage = message.get("usage") or {}

            # Accumulate token usage
            input_tokens = usage.get("input_tokens", 0) or 0
            output_tokens = usage.get("output_tokens", 0) or 0
            cache_creation = usage.get("cache_creation_input_tokens", 0) or 0
            cache_read = usage.get("cache_read_input_tokens", 0) or 0

            cumulative_input += input_tokens + cache_creation
            cumulative_output += output_tokens
            cumulative_cached += cache_read

            # Extract tool use blocks from content
            content_blocks = message.get("content", [])
            if isinstance(content_blocks, list):
                for block in content_blocks:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use":
                        continue

                    tool_name = block.get("name", "")
                    if not tool_name:
                        continue

                    # Count by name
                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

                    # Count by category
                    category = _categorize_tool(tool_name)
                    category_counts[category] += 1

                    # Extract search queries
                    search_type = _classify_search_tool(tool_name)
                    if search_type is not None:
                        tool_input = block.get("input") or {}
                        query_text = _extract_query_text(tool_input)
                        if query_text:
                            search_queries.append(SearchQuery(
                                tool_name=tool_name,
                                query_text=query_text,
                                category=search_type,
                            ))

                        if search_type == "keyword":
                            keyword_count += 1
                        elif search_type == "nls":
                            nls_count += 1
                        elif search_type == "deep_search":
                            deep_search_count += 1

        # Also handle top-level tool_use entries (alternate format)
        elif entry_type == "tool_use":
            tool_name = entry.get("name", "")
            if tool_name:
                tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
                category = _categorize_tool(tool_name)
                category_counts[category] += 1

                search_type = _classify_search_tool(tool_name)
                if search_type is not None:
                    tool_input = entry.get("input") or {}
                    query_text = _extract_query_text(tool_input)
                    if query_text:
                        search_queries.append(SearchQuery(
                            tool_name=tool_name,
                            query_text=query_text,
                            category=search_type,
                        ))

                    if search_type == "keyword":
                        keyword_count += 1
                    elif search_type == "nls":
                        nls_count += 1
                    elif search_type == "deep_search":
                        deep_search_count += 1

        # Extract summary from result entry
        elif entry_type == "result":
            total_cost = entry.get("total_cost_usd", 0.0) or 0.0
            duration_ms = entry.get("duration_ms", 0) or 0
            num_turns = entry.get("num_turns", 0) or 0

            # Result entry has authoritative token totals
            result_usage = entry.get("usage") or {}
            if result_usage:
                cumulative_input = (
                    (result_usage.get("input_tokens", 0) or 0)
                    + (result_usage.get("cache_creation_input_tokens", 0) or 0)
                )
                cumulative_output = result_usage.get("output_tokens", 0) or 0
                cumulative_cached = result_usage.get("cache_read_input_tokens", 0) or 0

    # Compute ratios
    total_keyword = keyword_count + nls_count  # Both are keyword-style searches
    deep_vs_keyword = 0.0
    if total_keyword > 0:
        deep_vs_keyword = deep_search_count / total_keyword
    elif deep_search_count > 0:
        deep_vs_keyword = float("inf")

    # Clamp inf for storage
    if deep_vs_keyword == float("inf"):
        deep_vs_keyword = 999.0

    # Context fill rate: total input tokens (including cached reads) / model limit
    total_context_tokens = cumulative_input + cumulative_cached
    context_fill_rate = total_context_tokens / MODEL_CONTEXT_LIMIT if MODEL_CONTEXT_LIMIT > 0 else 0.0

    total_calls = sum(category_counts.values())

    # Convert tool_counts dict to sorted tuple for frozen dataclass
    sorted_tool_counts = tuple(
        sorted(tool_counts.items(), key=lambda x: -x[1])
    )

    return ToolUtilizationMetrics(
        tool_calls_by_name=sorted_tool_counts,
        mcp_calls=category_counts[ToolCategory.MCP],
        deep_search_calls=category_counts[ToolCategory.DEEP_SEARCH],
        local_calls=category_counts[ToolCategory.LOCAL],
        other_calls=category_counts[ToolCategory.OTHER],
        total_tool_calls=total_calls,
        search_queries=tuple(search_queries),
        keyword_search_count=keyword_count,
        nls_search_count=nls_count,
        deep_search_query_count=deep_search_count,
        deep_search_vs_keyword_ratio=deep_vs_keyword,
        cumulative_input_tokens=cumulative_input,
        cumulative_output_tokens=cumulative_output,
        cumulative_cached_tokens=cumulative_cached,
        context_fill_rate=context_fill_rate,
        total_cost_usd=total_cost,
        duration_ms=duration_ms,
        num_turns=num_turns,
        skipped_lines=skipped,
    )
