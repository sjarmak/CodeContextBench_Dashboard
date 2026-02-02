"""Tests for src/ingest/transcript_tool_extractor.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ingest.transcript_tool_extractor import (
    ToolUtilizationMetrics,
    SearchQuery,
    extract_tool_utilization,
    _categorize_tool,
    _classify_search_tool,
)
from src.ingest.transcript_parser import ToolCategory


# ---------------------------------------------------------------------------
# Fixtures: sample JSONL content
# ---------------------------------------------------------------------------

def _build_system_init() -> str:
    return json.dumps({
        "type": "system",
        "subtype": "init",
        "cwd": "/app",
        "session_id": "test-session",
        "tools": ["Read", "Write", "Bash"],
        "model": "claude-haiku-4-5-20251001",
    })


def _build_assistant_with_tool(
    tool_name: str,
    tool_input: dict | None = None,
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_read: int = 0,
    cache_creation: int = 0,
) -> str:
    return json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_creation,
            },
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_test",
                    "name": tool_name,
                    "input": tool_input or {},
                }
            ],
        },
    })


def _build_assistant_text(
    text: str = "Thinking...",
    input_tokens: int = 50,
    output_tokens: int = 20,
) -> str:
    return json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
            "content": [{"type": "text", "text": text}],
        },
    })


def _build_tool_result(content: str = "OK") -> str:
    return json.dumps({
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_test",
                    "content": content,
                }
            ],
        },
    })


def _build_result_entry(
    cost: float = 1.5,
    duration_ms: int = 60000,
    num_turns: int = 10,
    input_tokens: int = 5000,
    output_tokens: int = 1000,
    cache_read: int = 3000,
    cache_creation: int = 500,
) -> str:
    return json.dumps({
        "type": "result",
        "subtype": "success",
        "total_cost_usd": cost,
        "duration_ms": duration_ms,
        "num_turns": num_turns,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_creation,
        },
    })


def _write_jsonl(tmp_path: Path, lines: list[str], filename: str = "claude-code.txt") -> Path:
    filepath = tmp_path / filename
    filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return filepath


# ---------------------------------------------------------------------------
# Tests: _categorize_tool
# ---------------------------------------------------------------------------

class TestCategorizeTool:
    def test_mcp_sourcegraph_keyword(self):
        assert _categorize_tool("mcp__sourcegraph__sg_keyword_search") == ToolCategory.MCP

    def test_mcp_sourcegraph_read_file(self):
        assert _categorize_tool("mcp__sourcegraph__sg_read_file") == ToolCategory.MCP

    def test_mcp_sourcegraph_nls(self):
        assert _categorize_tool("mcp__sourcegraph__sg_nls_search") == ToolCategory.MCP

    def test_deep_search(self):
        assert _categorize_tool("mcp__sourcegraph__sg_deepsearch") == ToolCategory.DEEP_SEARCH

    def test_deep_search_underscore(self):
        assert _categorize_tool("mcp__deep_search__query") == ToolCategory.DEEP_SEARCH

    def test_local_bash(self):
        assert _categorize_tool("Bash") == ToolCategory.LOCAL

    def test_local_read(self):
        assert _categorize_tool("Read") == ToolCategory.LOCAL

    def test_local_write(self):
        assert _categorize_tool("Write") == ToolCategory.LOCAL

    def test_local_edit(self):
        assert _categorize_tool("Edit") == ToolCategory.LOCAL

    def test_local_glob(self):
        assert _categorize_tool("Glob") == ToolCategory.LOCAL

    def test_local_grep(self):
        assert _categorize_tool("Grep") == ToolCategory.LOCAL

    def test_local_todowrite(self):
        assert _categorize_tool("TodoWrite") == ToolCategory.LOCAL

    def test_other_unknown(self):
        assert _categorize_tool("SomethingNew") == ToolCategory.OTHER


# ---------------------------------------------------------------------------
# Tests: _classify_search_tool
# ---------------------------------------------------------------------------

class TestClassifySearchTool:
    def test_keyword_search(self):
        assert _classify_search_tool("mcp__sourcegraph__sg_keyword_search") == "keyword"

    def test_nls_search(self):
        assert _classify_search_tool("mcp__sourcegraph__sg_nls_search") == "nls"

    def test_deep_search(self):
        assert _classify_search_tool("mcp__sourcegraph__sg_deepsearch") == "deep_search"

    def test_non_search_tool(self):
        assert _classify_search_tool("Read") is None

    def test_non_search_mcp_tool(self):
        assert _classify_search_tool("mcp__sourcegraph__sg_read_file") is None


# ---------------------------------------------------------------------------
# Tests: extract_tool_utilization
# ---------------------------------------------------------------------------

class TestExtractToolUtilization:
    def test_empty_file(self, tmp_path: Path):
        filepath = _write_jsonl(tmp_path, [])
        result = extract_tool_utilization(filepath)
        assert result.total_tool_calls == 0
        assert result.skipped_lines == 0

    def test_missing_file(self, tmp_path: Path):
        filepath = tmp_path / "nonexistent.txt"
        result = extract_tool_utilization(filepath)
        assert result.total_tool_calls == 0

    def test_malformed_lines_skipped(self, tmp_path: Path):
        lines = [
            _build_system_init(),
            "this is not json",
            "{bad json",
            _build_assistant_text(),
        ]
        filepath = _write_jsonl(tmp_path, lines)
        result = extract_tool_utilization(filepath)
        assert result.skipped_lines == 2

    def test_local_tool_counts(self, tmp_path: Path):
        lines = [
            _build_system_init(),
            _build_assistant_with_tool("Read", {"file_path": "/app/main.py"}),
            _build_tool_result("file content"),
            _build_assistant_with_tool("Read", {"file_path": "/app/utils.py"}),
            _build_tool_result("more content"),
            _build_assistant_with_tool("Bash", {"command": "ls"}),
            _build_tool_result("output"),
        ]
        filepath = _write_jsonl(tmp_path, lines)
        result = extract_tool_utilization(filepath)

        assert result.total_tool_calls == 3
        assert result.local_calls == 3
        assert result.mcp_calls == 0
        assert result.deep_search_calls == 0

        counts_dict = dict(result.tool_calls_by_name)
        assert counts_dict["Read"] == 2
        assert counts_dict["Bash"] == 1

    def test_mcp_tool_counts_and_queries(self, tmp_path: Path):
        lines = [
            _build_system_init(),
            _build_assistant_with_tool(
                "mcp__sourcegraph__sg_keyword_search",
                {"query": "repo:myrepo function_name"},
            ),
            _build_tool_result("search results"),
            _build_assistant_with_tool(
                "mcp__sourcegraph__sg_nls_search",
                {"query": "how does the auth system work"},
            ),
            _build_tool_result("nls results"),
            _build_assistant_with_tool(
                "mcp__sourcegraph__sg_read_file",
                {"repo": "myrepo", "path": "main.py"},
            ),
            _build_tool_result("file content"),
        ]
        filepath = _write_jsonl(tmp_path, lines)
        result = extract_tool_utilization(filepath)

        assert result.total_tool_calls == 3
        assert result.mcp_calls == 3
        assert result.keyword_search_count == 1
        assert result.nls_search_count == 1
        assert len(result.search_queries) == 2

        # Verify query extraction
        queries_by_cat = {q.category: q.query_text for q in result.search_queries}
        assert "keyword" in queries_by_cat
        assert "nls" in queries_by_cat
        assert "repo:myrepo function_name" in queries_by_cat["keyword"]

    def test_deep_search_ratio(self, tmp_path: Path):
        lines = [
            _build_system_init(),
            # 2 keyword searches
            _build_assistant_with_tool(
                "mcp__sourcegraph__sg_keyword_search",
                {"query": "q1"},
            ),
            _build_tool_result(),
            _build_assistant_with_tool(
                "mcp__sourcegraph__sg_keyword_search",
                {"query": "q2"},
            ),
            _build_tool_result(),
            # 1 deep search
            _build_assistant_with_tool(
                "mcp__sourcegraph__sg_deepsearch",
                {"query": "deep question"},
            ),
            _build_tool_result(),
        ]
        filepath = _write_jsonl(tmp_path, lines)
        result = extract_tool_utilization(filepath)

        assert result.keyword_search_count == 2
        assert result.deep_search_query_count == 1
        assert result.deep_search_calls == 1
        assert result.mcp_calls == 2  # 2 keyword searches (not deep search)
        # ratio = 1 deep / 2 keyword = 0.5
        assert result.deep_search_vs_keyword_ratio == pytest.approx(0.5)

    def test_deep_search_ratio_no_keyword(self, tmp_path: Path):
        """When there are deep search calls but no keyword/nls, ratio is clamped."""
        lines = [
            _build_system_init(),
            _build_assistant_with_tool(
                "mcp__sourcegraph__sg_deepsearch",
                {"query": "deep only"},
            ),
            _build_tool_result(),
        ]
        filepath = _write_jsonl(tmp_path, lines)
        result = extract_tool_utilization(filepath)

        assert result.deep_search_query_count == 1
        assert result.deep_search_vs_keyword_ratio == 999.0

    def test_token_accumulation(self, tmp_path: Path):
        lines = [
            _build_system_init(),
            _build_assistant_with_tool(
                "Read", {"file_path": "/app/main.py"},
                input_tokens=100, output_tokens=50, cache_read=200, cache_creation=30,
            ),
            _build_tool_result(),
            _build_assistant_text(input_tokens=80, output_tokens=40),
        ]
        filepath = _write_jsonl(tmp_path, lines)
        result = extract_tool_utilization(filepath)

        # cumulative_input = (100+30) + (80+0) = 210
        # cumulative_output = 50 + 40 = 90
        # cumulative_cached = 200 + 0 = 200
        assert result.cumulative_input_tokens == 210
        assert result.cumulative_output_tokens == 90
        assert result.cumulative_cached_tokens == 200

    def test_result_entry_overrides_tokens(self, tmp_path: Path):
        """Result entry has authoritative token totals that override cumulative."""
        lines = [
            _build_system_init(),
            _build_assistant_with_tool("Read", input_tokens=100, output_tokens=50),
            _build_tool_result(),
            _build_result_entry(
                cost=2.5, duration_ms=120000, num_turns=15,
                input_tokens=5000, output_tokens=1000,
                cache_read=3000, cache_creation=500,
            ),
        ]
        filepath = _write_jsonl(tmp_path, lines)
        result = extract_tool_utilization(filepath)

        assert result.total_cost_usd == pytest.approx(2.5)
        assert result.duration_ms == 120000
        assert result.num_turns == 15
        # Overridden by result entry: input = 5000 + 500 = 5500
        assert result.cumulative_input_tokens == 5500
        assert result.cumulative_output_tokens == 1000
        assert result.cumulative_cached_tokens == 3000

    def test_context_fill_rate(self, tmp_path: Path):
        """Context fill rate = (input + cached) / 200000."""
        lines = [
            _build_system_init(),
            _build_result_entry(
                input_tokens=50000, output_tokens=5000,
                cache_read=100000, cache_creation=10000,
            ),
        ]
        filepath = _write_jsonl(tmp_path, lines)
        result = extract_tool_utilization(filepath)

        # input = 50000 + 10000 = 60000
        # cached = 100000
        # total context = 60000 + 100000 = 160000
        # fill rate = 160000 / 200000 = 0.8
        assert result.context_fill_rate == pytest.approx(0.8)

    def test_frozen_dataclass(self, tmp_path: Path):
        """ToolUtilizationMetrics should be immutable."""
        filepath = _write_jsonl(tmp_path, [_build_system_init()])
        result = extract_tool_utilization(filepath)
        with pytest.raises(AttributeError):
            result.total_tool_calls = 99  # type: ignore[misc]

    def test_mixed_tool_types(self, tmp_path: Path):
        """Full scenario with local, MCP, and deep search tools."""
        lines = [
            _build_system_init(),
            _build_assistant_with_tool("Read", {"file_path": "/app/a.py"}),
            _build_tool_result(),
            _build_assistant_with_tool("Bash", {"command": "ls"}),
            _build_tool_result(),
            _build_assistant_with_tool(
                "mcp__sourcegraph__sg_keyword_search",
                {"query": "auth middleware"},
            ),
            _build_tool_result(),
            _build_assistant_with_tool(
                "mcp__sourcegraph__sg_deepsearch",
                {"query": "how does authentication work"},
            ),
            _build_tool_result(),
            _build_assistant_with_tool("Write", {"file_path": "/app/b.py", "content": "..."}),
            _build_tool_result(),
            _build_result_entry(cost=3.0, duration_ms=90000, num_turns=5),
        ]
        filepath = _write_jsonl(tmp_path, lines)
        result = extract_tool_utilization(filepath)

        assert result.total_tool_calls == 5
        assert result.local_calls == 3  # Read, Bash, Write
        assert result.mcp_calls == 1  # keyword_search
        assert result.deep_search_calls == 1  # deepsearch
        assert result.keyword_search_count == 1
        assert result.deep_search_query_count == 1
        assert len(result.search_queries) == 2
        assert result.total_cost_usd == pytest.approx(3.0)
        assert result.duration_ms == 90000

    def test_top_level_tool_use_format(self, tmp_path: Path):
        """Handle the alternate format where tool_use is a top-level entry."""
        lines = [
            _build_system_init(),
            json.dumps({
                "type": "tool_use",
                "id": "toolu_01",
                "name": "mcp__sourcegraph__sg_keyword_search",
                "input": {"query": "test query"},
            }),
            json.dumps({
                "type": "tool_use",
                "id": "toolu_02",
                "name": "Read",
                "input": {"file_path": "/app/foo.py"},
            }),
        ]
        filepath = _write_jsonl(tmp_path, lines)
        result = extract_tool_utilization(filepath)

        assert result.total_tool_calls == 2
        assert result.mcp_calls == 1
        assert result.local_calls == 1
        assert result.keyword_search_count == 1
        assert len(result.search_queries) == 1
