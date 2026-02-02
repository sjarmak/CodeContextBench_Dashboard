"""Tests for scripts.ccb_pipeline.sdlc_mapping module."""

from __future__ import annotations

import pytest

from scripts.ccb_pipeline.sdlc_mapping import (
    BENCHMARK_SDLC_MAP,
    get_benchmark_name,
    get_sdlc_phases,
)


class TestGetSdlcPhases:
    """Tests for get_sdlc_phases function."""

    def test_exact_match_kubernetes_docs(self) -> None:
        result = get_sdlc_phases("ccb-kubernetes-docs")
        assert result == ["Documentation"]

    def test_exact_match_pytorch_issues(self) -> None:
        result = get_sdlc_phases("ccb-pytorch-issues")
        assert result == ["Implementation"]

    def test_exact_match_crossrepo(self) -> None:
        result = get_sdlc_phases("ccb-crossrepo")
        assert result == ["Implementation", "Maintenance"]

    def test_exact_match_largerepo(self) -> None:
        result = get_sdlc_phases("ccb-largerepo")
        assert result == ["Implementation"]

    def test_exact_match_swe_bench_pro(self) -> None:
        result = get_sdlc_phases("swe-bench-pro")
        assert result == ["Implementation", "Testing"]

    def test_exact_match_locobench(self) -> None:
        result = get_sdlc_phases("locobench")
        assert result == ["Implementation", "Code Review"]

    def test_exact_match_repoqa(self) -> None:
        result = get_sdlc_phases("repoqa")
        assert result == ["Requirements"]

    def test_exact_match_di_bench(self) -> None:
        result = get_sdlc_phases("di-bench")
        assert result == ["Maintenance"]

    def test_exact_match_swe_perf(self) -> None:
        result = get_sdlc_phases("swe-perf")
        assert result == ["Implementation", "Testing"]

    def test_exact_match_dependeval(self) -> None:
        result = get_sdlc_phases("dependeval")
        assert result == ["Maintenance"]

    def test_exact_match_the_agent_company(self) -> None:
        result = get_sdlc_phases("the-agent-company")
        assert result == ["Multiple"]

    def test_exact_match_big_code_mcp(self) -> None:
        result = get_sdlc_phases("big_code_mcp")
        assert result == ["Implementation"]

    def test_fuzzy_match_case_insensitive(self) -> None:
        result = get_sdlc_phases("SWE-BENCH-PRO")
        assert result == ["Implementation", "Testing"]

    def test_fuzzy_match_substring(self) -> None:
        result = get_sdlc_phases("my-locobench-tasks")
        assert result == ["Implementation", "Code Review"]

    def test_fuzzy_match_with_prefix(self) -> None:
        result = get_sdlc_phases("harbor-swe-bench-pro-v2")
        assert result == ["Implementation", "Testing"]

    def test_specific_pattern_preferred_over_general(self) -> None:
        """More specific patterns (longer) should match before shorter ones."""
        # "swe-bench-pro" should match before "swe-bench"
        result = get_sdlc_phases("swe-bench-pro")
        assert result == ["Implementation", "Testing"]

    def test_swe_bench_without_pro(self) -> None:
        result = get_sdlc_phases("swe-bench")
        assert result == ["Implementation", "Testing"]

    def test_unknown_benchmark(self) -> None:
        result = get_sdlc_phases("some-unknown-benchmark")
        assert result == ["Unknown"]

    def test_empty_string(self) -> None:
        result = get_sdlc_phases("")
        assert result == ["Unknown"]

    def test_whitespace_handling(self) -> None:
        result = get_sdlc_phases("  locobench  ")
        assert result == ["Implementation", "Code Review"]

    def test_returns_new_list_each_call(self) -> None:
        """Ensure immutability: returned lists are independent."""
        result1 = get_sdlc_phases("locobench")
        result2 = get_sdlc_phases("locobench")
        assert result1 == result2
        assert result1 is not result2

    def test_tac_shortname(self) -> None:
        result = get_sdlc_phases("tac")
        assert result == ["Multiple"]

    def test_github_mined(self) -> None:
        result = get_sdlc_phases("github_mined")
        assert result == ["Implementation"]

    def test_tac_mcp_value(self) -> None:
        result = get_sdlc_phases("tac_mcp_value")
        assert result == ["Multiple"]


class TestGetBenchmarkName:
    """Tests for get_benchmark_name function."""

    def test_standard_task_path(self) -> None:
        path = "benchmarks/big_code_mcp/big-code-k8s-001"
        assert get_benchmark_name(path) == "big_code_mcp"

    def test_nested_task_path(self) -> None:
        path = "/home/user/project/benchmarks/locobench/task-42"
        assert get_benchmark_name(path) == "locobench"

    def test_relative_task_path(self) -> None:
        path = "./benchmarks/swe-bench-pro/django__django-12345"
        assert get_benchmark_name(path) == "swe-bench-pro"

    def test_backslash_path(self) -> None:
        path = "C:\\projects\\benchmarks\\di-bench\\task-1"
        assert get_benchmark_name(path) == "di-bench"

    def test_no_benchmarks_segment(self) -> None:
        path = "/home/user/project/tasks/my-task"
        assert get_benchmark_name(path) == "unknown"

    def test_benchmarks_at_end(self) -> None:
        """If 'benchmarks' is the last segment, no benchmark name follows."""
        path = "/home/user/benchmarks"
        assert get_benchmark_name(path) == "unknown"

    def test_empty_string(self) -> None:
        assert get_benchmark_name("") == "unknown"

    def test_deep_nested_path(self) -> None:
        path = "data/runs/official/benchmarks/github_mined/pytorch-commit-abc/trial-1"
        assert get_benchmark_name(path) == "github_mined"


class TestBenchmarkSdlcMap:
    """Tests for the BENCHMARK_SDLC_MAP constant."""

    def test_all_values_are_tuples(self) -> None:
        for key, value in BENCHMARK_SDLC_MAP.items():
            assert isinstance(value, tuple), f"Value for {key} is not a tuple"

    def test_all_values_non_empty(self) -> None:
        for key, value in BENCHMARK_SDLC_MAP.items():
            assert len(value) > 0, f"Value for {key} is empty"

    def test_all_phases_are_strings(self) -> None:
        for key, value in BENCHMARK_SDLC_MAP.items():
            for phase in value:
                assert isinstance(phase, str), f"Phase in {key} is not a string"

    def test_covers_paper_table2_benchmarks(self) -> None:
        """Verify all benchmarks from Table 2 are covered."""
        required = [
            "kubernetes-docs",
            "pytorch-issues",
            "crossrepo",
            "largerepo",
            "swe-bench-pro",
            "locobench",
            "repoqa",
            "di-bench",
            "swe-perf",
            "dependeval",
            "the-agent-company",
        ]
        for benchmark in required:
            phases = get_sdlc_phases(benchmark)
            assert phases != ["Unknown"], f"Missing mapping for {benchmark}"
