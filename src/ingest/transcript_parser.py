"""
Parse agent transcripts (claude-code.txt) to extract tool usage patterns.

Extracts:
- MCP tool calls (Sourcegraph, Deep Search)
- Local tool usage (grep, find, shell)
- Tool call counts and frequencies
- Average tokens per tool
- Tool effectiveness (success/failure)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from enum import Enum


class ToolCategory(str, Enum):
    """Categories of tools used in agent execution."""
    MCP = "mcp"  # Sourcegraph MCP tools
    DEEP_SEARCH = "deep_search"  # Sourcegraph Deep Search
    LOCAL = "local"  # Local shell, grep, find
    OTHER = "other"


@dataclass
class ToolUse:
    """A single tool usage instance."""
    tool_name: str
    category: ToolCategory
    index: int  # Position in transcript
    input_preview: Optional[str] = None  # First 100 chars of input
    output_preview: Optional[str] = None  # First 100 chars of output
    success: bool = True
    tokens_input: int = 0
    tokens_output: int = 0


@dataclass
class TranscriptMetrics:
    """Metrics extracted from an agent transcript."""
    total_tool_calls: int = 0
    mcp_calls: int = 0
    deep_search_calls: int = 0
    local_calls: int = 0
    other_calls: int = 0

    # Tool usage breakdown
    tool_calls_by_name: dict[str, int] = field(default_factory=dict)

    # Token usage
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    avg_tokens_per_call: float = 0.0

    # Extended token tracking (populated from trajectory.json)
    cached_tokens: int = 0
    cost_usd: Optional[float] = None
    tokens_by_category: dict = field(default_factory=dict)  # {ToolCategory: {prompt: X, ...}}
    tokens_by_tool: dict = field(default_factory=dict)  # {tool_name: {prompt: X, ...}}

    # Success metrics
    successful_calls: int = 0
    failed_calls: int = 0
    success_rate: float = 0.0

    # Tool efficiency
    mcp_vs_local_ratio: float = 0.0

    # File access patterns
    files_accessed: set[str] = field(default_factory=set)
    unique_file_count: int = 0

    # Search/retrieval patterns
    search_queries: list[str] = field(default_factory=list)

    # Metadata
    transcript_length: int = 0
    has_errors: bool = False

    def merge_trajectory_metrics(self, trajectory_metrics) -> None:
        """
        Merge token metrics from a TrajectoryMetrics object.

        This populates the extended token tracking fields with accurate
        data from trajectory.json files (ATIF format).

        Args:
            trajectory_metrics: TrajectoryMetrics object with token data
        """
        if trajectory_metrics is None:
            return

        # Update token totals (trajectory.json has more accurate data)
        self.total_input_tokens = trajectory_metrics.total_prompt_tokens
        self.total_output_tokens = trajectory_metrics.total_completion_tokens
        self.cached_tokens = trajectory_metrics.total_cached_tokens

        # Set cost
        self.cost_usd = trajectory_metrics.cost_usd

        # Copy per-category token breakdown
        # Convert ToolCategory keys to strings for JSON serialization
        self.tokens_by_category = {
            cat.value if hasattr(cat, 'value') else str(cat): tokens
            for cat, tokens in trajectory_metrics.tokens_by_category.items()
        }

        # Copy per-tool token breakdown
        self.tokens_by_tool = dict(trajectory_metrics.tokens_by_tool)

        # Recalculate avg_tokens_per_call with new token data
        if self.total_tool_calls > 0:
            self.avg_tokens_per_call = (
                self.total_input_tokens + self.total_output_tokens
            ) / self.total_tool_calls


class TranscriptParser:
    """Parse agent transcripts to extract tool usage."""
    
    # Patterns for different tools
    MCP_TOOL_PATTERN = re.compile(r"<function_calls>.*?<invoke.*?name=['\"]([^'\"]+)", re.DOTALL)
    DEEP_SEARCH_PATTERN = re.compile(r"deepsearch|deep.search", re.IGNORECASE)
    FILE_PATTERN = re.compile(r"(?:file|path)[:\s]+([^\s<>\n]+\.(?:py|ts|js|java|go|rb|rs))")
    GREP_PATTERN = re.compile(r"(?:grep|rg)\s+(?:['\"])?([^'\"<>]+)")
    
    def parse_file(self, transcript_path: Path) -> TranscriptMetrics:
        """
        Parse a transcript file.
        
        Args:
            transcript_path: Path to claude-code.txt or similar
            
        Returns:
            TranscriptMetrics with extracted patterns
        """
        content = transcript_path.read_text(errors="ignore")
        return self.parse_text(content)
    
    def parse_text(self, content: str) -> TranscriptMetrics:
        """
        Parse transcript content as text.
        
        Args:
            content: Full transcript content
            
        Returns:
            TranscriptMetrics with extracted patterns
        """
        metrics = TranscriptMetrics(transcript_length=len(content))
        
        # Extract tool calls
        self._extract_tool_calls(content, metrics)
        
        # Extract file access patterns
        self._extract_file_patterns(content, metrics)
        
        # Extract search queries
        self._extract_search_patterns(content, metrics)
        
        # Calculate derived metrics
        self._calculate_derived_metrics(metrics)
        
        return metrics
    
    def _extract_tool_calls(self, content: str, metrics: TranscriptMetrics) -> None:
        """Extract tool calls from transcript."""
        # Find all function call blocks
        tool_call_pattern = re.compile(
            r"<invoke.*?name=['\"]([^'\"]+)['\"].*?</invoke>",
            re.DOTALL
        )
        
        matches = tool_call_pattern.finditer(content)
        
        for i, match in enumerate(matches):
            tool_name = match.group(1)
            metrics.total_tool_calls += 1
            
            # Categorize tool
            category = self._categorize_tool(tool_name)
            
            # Count by category
            if category == ToolCategory.MCP:
                metrics.mcp_calls += 1
            elif category == ToolCategory.DEEP_SEARCH:
                metrics.deep_search_calls += 1
            elif category == ToolCategory.LOCAL:
                metrics.local_calls += 1
            else:
                metrics.other_calls += 1
            
            # Count by tool name
            metrics.tool_calls_by_name[tool_name] = metrics.tool_calls_by_name.get(tool_name, 0) + 1
            
            # Estimate success based on output
            # Simple heuristic: if there's an error section, mark as failed
            call_section = content[match.start():match.end()]
            if "error" in call_section.lower() or "failed" in call_section.lower():
                metrics.failed_calls += 1
            else:
                metrics.successful_calls += 1
    
    def _extract_file_patterns(self, content: str, metrics: TranscriptMetrics) -> None:
        """Extract file access patterns."""
        # Find file paths mentioned in transcript
        file_pattern = re.compile(r"(?:file|reading|opened?|edited?|created?)[:\s]+[`'\"]?([^\s`'\"<>\n]+\.(?:py|ts|js|java|go|rb|rs|txt|md|json|yaml|toml))")
        
        for match in file_pattern.finditer(content):
            file_path = match.group(1)
            # Normalize path
            file_path = file_path.strip('`"\'/\\')
            metrics.files_accessed.add(file_path)
        
        metrics.unique_file_count = len(metrics.files_accessed)
    
    def _extract_search_patterns(self, content: str, metrics: TranscriptMetrics) -> None:
        """Extract search/query patterns."""
        # Find Deep Search questions
        deep_search_pattern = re.compile(
            r"(?:deepsearch|deep.search)[^\n]*?(?:question|query)[:\s]+['\"]([^'\"]+)['\"]",
            re.IGNORECASE | re.DOTALL
        )
        
        for match in deep_search_pattern.finditer(content):
            query = match.group(1)[:100]  # First 100 chars
            if query and query not in metrics.search_queries:
                metrics.search_queries.append(query)
        
        # Find general search patterns
        search_pattern = re.compile(r"(?:search|query|grep)[:\s]+['\"]([^'\"]+)['\"]", re.IGNORECASE)
        for match in search_pattern.finditer(content):
            query = match.group(1)[:100]
            if query and query not in metrics.search_queries:
                metrics.search_queries.append(query)
    
    def _categorize_tool(self, tool_name: str) -> ToolCategory:
        """Categorize a tool by name."""
        tool_lower = tool_name.lower()
        
        # Deep Search tools
        if "deepsearch" in tool_lower or "deep_search" in tool_lower:
            return ToolCategory.DEEP_SEARCH
        
        # MCP/Sourcegraph tools
        if any(x in tool_lower for x in [
            "sourcegraph", "sg_", "keyword_search", "nls_search",
            "read_file", "list_files", "go_to_definition", "commit_search"
        ]):
            return ToolCategory.MCP
        
        # Local tools
        if any(x in tool_lower for x in [
            "bash", "shell", "grep", "find", "ls", "cat", "sed",
            "awk", "cut", "head", "tail", "sort", "uniq"
        ]):
            return ToolCategory.LOCAL
        
        return ToolCategory.OTHER
    
    def _calculate_derived_metrics(self, metrics: TranscriptMetrics) -> None:
        """Calculate derived metrics."""
        # Success rate
        total_calls = metrics.successful_calls + metrics.failed_calls
        if total_calls > 0:
            metrics.success_rate = metrics.successful_calls / total_calls
        
        # MCP vs local ratio
        mcp_total = metrics.mcp_calls + metrics.deep_search_calls
        if mcp_total > 0 and metrics.local_calls > 0:
            metrics.mcp_vs_local_ratio = mcp_total / metrics.local_calls
        elif mcp_total > 0:
            metrics.mcp_vs_local_ratio = float('inf')  # All MCP, no local
        else:
            metrics.mcp_vs_local_ratio = 0.0
        
        # Handle infinite ratio for storage
        if metrics.mcp_vs_local_ratio == float('inf'):
            metrics.mcp_vs_local_ratio = 999.0  # Use large number instead of inf for DB
        
        # Average tokens per call
        if metrics.total_tool_calls > 0:
            metrics.avg_tokens_per_call = (
                metrics.total_input_tokens + metrics.total_output_tokens
            ) / metrics.total_tool_calls


class AgentToolProfile:
    """Profile of how an agent uses tools."""
    
    def __init__(self, metrics: TranscriptMetrics):
        self.metrics = metrics
    
    @property
    def is_mcp_heavy(self) -> bool:
        """Does the agent heavily use MCP tools?"""
        return self.metrics.mcp_vs_local_ratio > 2.0
    
    @property
    def is_deep_search_strategic(self) -> bool:
        """Does the agent use Deep Search strategically (sparingly but effectively)?"""
        if self.metrics.total_tool_calls == 0:
            return False
        deep_search_ratio = self.metrics.deep_search_calls / self.metrics.total_tool_calls
        return 0.05 < deep_search_ratio < 0.3  # Between 5-30%
    
    @property
    def top_tools(self) -> list[tuple[str, int]]:
        """Get top 5 most used tools."""
        items = sorted(self.metrics.tool_calls_by_name.items(), key=lambda x: x[1], reverse=True)
        return items[:5]
    
    @property
    def tool_diversity(self) -> float:
        """Measure tool diversity (0-1, where 1 is max diversity)."""
        if self.metrics.total_tool_calls == 0:
            return 0.0
        unique_tools = len(self.metrics.tool_calls_by_name)
        max_diversity = min(10, self.metrics.total_tool_calls)  # Max 10 unique tools
        return unique_tools / max_diversity
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "metrics": {
                "total_tool_calls": self.metrics.total_tool_calls,
                "mcp_calls": self.metrics.mcp_calls,
                "deep_search_calls": self.metrics.deep_search_calls,
                "local_calls": self.metrics.local_calls,
                "other_calls": self.metrics.other_calls,
                "tool_calls_by_name": self.metrics.tool_calls_by_name,
                "total_input_tokens": self.metrics.total_input_tokens,
                "total_output_tokens": self.metrics.total_output_tokens,
                "avg_tokens_per_call": self.metrics.avg_tokens_per_call,
                "successful_calls": self.metrics.successful_calls,
                "failed_calls": self.metrics.failed_calls,
                "success_rate": self.metrics.success_rate,
                "mcp_vs_local_ratio": self.metrics.mcp_vs_local_ratio,
                "unique_file_count": self.metrics.unique_file_count,
                "search_query_count": len(self.metrics.search_queries),
                "transcript_length": self.metrics.transcript_length,
            },
            "profile": {
                "is_mcp_heavy": self.is_mcp_heavy,
                "is_deep_search_strategic": self.is_deep_search_strategic,
                "tool_diversity": self.tool_diversity,
                "top_tools": self.top_tools,
            }
        }
