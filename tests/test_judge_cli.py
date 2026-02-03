"""Integration tests for the judge CLI (scripts/judge/__main__.py).

Tests cover: argument parsing, evaluate/compare/report/export subcommands
with sample data fixtures and mocked backends.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Must mock together before importing src.judge
sys.modules.setdefault("together", MagicMock())

from scripts.judge.__main__ import (
    _extract_task_id,
    _find_result_files,
    _run_report,
    _run_export,
    _verdict_to_dict,
    build_parser,
    main,
)
from src.judge.models import (
    DimensionScore,
    EvaluationMode,
    JudgeVerdict,
    Severity,
    CommentCategory,
    LineComment,
)


@pytest.fixture()
def sample_result_json() -> dict[str, Any]:
    """A minimal Harbor result.json fixture."""
    return {
        "id": "test-run-001",
        "task_name": "test_task_001",
        "trial_name": "task__abc123",
        "task_id": {"path": "benchmarks/locobench/test_task_001"},
        "agent_info": {
            "name": "test-agent",
            "model_info": {"name": "claude-sonnet-4", "provider": "anthropic"},
        },
        "agent_result": {
            "n_input_tokens": 1000,
            "n_output_tokens": 500,
            "cost_usd": 0.01,
        },
        "verifier_result": {"rewards": {"reward": 0.5}},
        "started_at": "2026-01-01T00:00:00",
        "finished_at": "2026-01-01T00:05:00",
    }


@pytest.fixture()
def runs_dir(tmp_path: Path, sample_result_json: dict[str, Any]) -> Path:
    """Create a temporary runs directory with result.json files."""
    for i in range(3):
        task_dir = tmp_path / f"task_{i:03d}"
        task_dir.mkdir()
        result = {**sample_result_json, "task_name": f"test_task_{i:03d}"}
        (task_dir / "result.json").write_text(json.dumps(result))
        logs_dir = task_dir / "logs" / "agent"
        logs_dir.mkdir(parents=True)
        (logs_dir / "solution.md").write_text(f"Solution for task {i}")
    return tmp_path


@pytest.fixture()
def sample_verdict() -> JudgeVerdict:
    """A sample JudgeVerdict for testing serialization."""
    return JudgeVerdict(
        mode=EvaluationMode.DIRECT,
        scores={
            "Correctness": DimensionScore(
                dimension="Correctness",
                score=0.8,
                weight=0.3,
                evidence="Good implementation",
                reasoning="Matches requirements",
            ),
        },
        overall_score=0.8,
        reasoning="Solid implementation",
        evidence=["file.py:10"],
        confidence=0.9,
        model_id="test-model",
        line_comments=[
            LineComment(
                file_path="src/main.py",
                line_range=(10, 15),
                severity=Severity.WARNING,
                comment="Consider error handling",
                category=CommentCategory.CORRECTNESS,
            ),
        ],
        metadata={},
    )


@pytest.fixture()
def sample_results_json(tmp_path: Path) -> Path:
    """Create a sample results JSON file for report/export tests."""
    data = {
        "mode": "direct",
        "runs_dir": "/tmp/runs",
        "total_tasks": 3,
        "successful": 2,
        "failed": 1,
        "results": [
            {
                "task_id": "task_001",
                "overall_score": 0.8,
                "confidence": 0.9,
                "reasoning": "Good",
                "mode": "direct",
                "model_id": "test-model",
                "scores": {
                    "Correctness": {"dimension": "Correctness", "score": 0.8, "weight": 0.3, "evidence": "", "reasoning": ""},
                },
            },
            {
                "task_id": "task_002",
                "overall_score": 0.6,
                "confidence": 0.7,
                "reasoning": "Partial",
                "mode": "direct",
                "model_id": "test-model",
                "scores": {
                    "Correctness": {"dimension": "Correctness", "score": 0.6, "weight": 0.3, "evidence": "", "reasoning": ""},
                },
            },
        ],
        "errors": [
            {"task_id": "task_003", "error": "Parse failure"},
        ],
    }
    path = tmp_path / "results.json"
    path.write_text(json.dumps(data))
    return path


class TestArgumentParsing:
    """Tests for CLI argument parser construction."""

    def test_parser_has_all_subcommands(self) -> None:
        parser = build_parser()
        # Verify subcommands exist by parsing valid args
        args = parser.parse_args(["evaluate", "--mode", "direct", "--runs-dir", ".", "--output", "out.json"])
        assert args.command == "evaluate"
        assert args.mode == "direct"

    def test_evaluate_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["evaluate", "--runs-dir", ".", "--output", "out.json"])
        assert args.mode == "direct"
        assert args.ensemble is False
        assert args.models is None
        assert args.config is None
        assert args.oracle_dir is None

    def test_evaluate_all_options(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "evaluate", "--mode", "reference", "--runs-dir", "/data/runs",
            "--output", "results.json", "--config", "/templates",
            "--oracle-dir", "/oracle", "--ensemble", "--models", "model-a,model-b",
        ])
        assert args.mode == "reference"
        assert args.ensemble is True
        assert args.models == "model-a,model-b"
        assert args.oracle_dir == "/oracle"

    def test_compare_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "compare", "--baseline-dir", "./baseline",
            "--treatment-dirs", "./mcp", "./deep",
            "--output", "compare.json", "--method", "round_robin",
        ])
        assert args.command == "compare"
        assert args.baseline_dir == "./baseline"
        assert args.treatment_dirs == ["./mcp", "./deep"]
        assert args.method == "round_robin"

    def test_report_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["report", "--input", "results.json", "--output", "summary.md"])
        assert args.command == "report"

    def test_export_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["export", "--input", "results.json", "--format", "csv", "--output", "out.csv"])
        assert args.command == "export"
        assert args.format == "csv"

    def test_no_command_returns_1(self) -> None:
        result = main([])
        assert result == 1


class TestHelpers:
    """Tests for helper functions."""

    def test_extract_task_id_from_task_name(self) -> None:
        result = {"task_name": "my_task"}
        assert _extract_task_id(result) == "my_task"

    def test_extract_task_id_from_task_id_dict(self) -> None:
        result = {"task_name": "", "task_id": {"path": "benchmarks/test/my_task"}}
        assert _extract_task_id(result) == "benchmarks/test/my_task"

    def test_extract_task_id_fallback(self) -> None:
        result = {}
        assert _extract_task_id(result) == ""

    def test_find_result_files(self, runs_dir: Path) -> None:
        files = _find_result_files(runs_dir)
        assert len(files) == 3
        for f in files:
            assert f.name == "result.json"

    def test_find_result_files_empty_dir(self, tmp_path: Path) -> None:
        files = _find_result_files(tmp_path)
        assert files == []


class TestVerdictSerialization:
    """Tests for verdict serialization."""

    def test_verdict_to_dict(self, sample_verdict: JudgeVerdict) -> None:
        result = _verdict_to_dict(sample_verdict)
        assert result["overall_score"] == 0.8
        assert result["model_id"] == "test-model"
        assert result["mode"] == "direct"
        assert "Correctness" in result["scores"]
        assert result["scores"]["Correctness"]["score"] == 0.8
        assert len(result["line_comments"]) == 1
        assert result["line_comments"][0]["severity"] == "warning"
        assert result["line_comments"][0]["category"] == "correctness"

    def test_verdict_to_dict_empty_comments(self) -> None:
        verdict = JudgeVerdict(
            mode=EvaluationMode.DIRECT,
            scores={},
            overall_score=0.5,
            reasoning="",
            evidence=[],
            confidence=0.5,
            model_id="test",
        )
        result = _verdict_to_dict(verdict)
        assert result["line_comments"] == []
        assert result["scores"] == {}


class TestReportSubcommand:
    """Tests for the report subcommand."""

    def test_report_generates_markdown(self, sample_results_json: Path, tmp_path: Path) -> None:
        import argparse
        output_path = tmp_path / "report.md"
        args = argparse.Namespace(input=str(sample_results_json), output=str(output_path))
        result = _run_report(args)
        assert result == 0
        content = output_path.read_text()
        assert "# Judge Evaluation Report" in content
        assert "**Mode:** direct" in content
        assert "Mean Score" in content
        assert "task_001" in content
        assert "task_003" in content  # error section
        assert "Parse failure" in content

    def test_report_missing_input(self, tmp_path: Path) -> None:
        import argparse
        args = argparse.Namespace(input=str(tmp_path / "nonexistent.json"), output=str(tmp_path / "out.md"))
        result = _run_report(args)
        assert result == 1

    def test_report_pairwise_mode(self, tmp_path: Path) -> None:
        import argparse
        data = {
            "mode": "pairwise",
            "common_tasks": 2,
            "successful": 2,
            "failed": 0,
            "results": [
                {
                    "task_id": "t1",
                    "overall_score": 0.7,
                    "confidence": 0.8,
                    "win_rates": {"BASELINE": 0.3, "MCP": 0.7},
                },
                {
                    "task_id": "t2",
                    "overall_score": 0.5,
                    "confidence": 0.6,
                    "win_rates": {"BASELINE": 0.5, "MCP": 0.5},
                },
            ],
            "errors": [],
        }
        input_path = tmp_path / "pairwise.json"
        input_path.write_text(json.dumps(data))
        output_path = tmp_path / "pw_report.md"
        args = argparse.Namespace(input=str(input_path), output=str(output_path))
        result = _run_report(args)
        assert result == 0
        content = output_path.read_text()
        assert "Pairwise Rankings" in content
        assert "MCP" in content
        assert "BASELINE" in content


class TestExportSubcommand:
    """Tests for the export subcommand."""

    def test_export_json(self, sample_results_json: Path, tmp_path: Path) -> None:
        import argparse
        output_path = tmp_path / "exported.json"
        args = argparse.Namespace(input=str(sample_results_json), output=str(output_path), format="json")
        result = _run_export(args)
        assert result == 0
        exported = json.loads(output_path.read_text())
        assert len(exported) == 2
        assert exported[0]["task_id"] == "task_001"

    def test_export_csv(self, sample_results_json: Path, tmp_path: Path) -> None:
        import argparse
        output_path = tmp_path / "exported.csv"
        args = argparse.Namespace(input=str(sample_results_json), output=str(output_path), format="csv")
        result = _run_export(args)
        assert result == 0
        content = output_path.read_text()
        assert "task_id" in content
        assert "overall_score" in content
        assert "task_001" in content
        assert "score_Correctness" in content

    def test_export_missing_input(self, tmp_path: Path) -> None:
        import argparse
        args = argparse.Namespace(input=str(tmp_path / "missing.json"), output=str(tmp_path / "out.json"), format="json")
        result = _run_export(args)
        assert result == 1

    def test_export_unsupported_format(self, sample_results_json: Path, tmp_path: Path) -> None:
        import argparse
        args = argparse.Namespace(input=str(sample_results_json), output=str(tmp_path / "out.xml"), format="xml")
        result = _run_export(args)
        assert result == 1

    def test_export_empty_results(self, tmp_path: Path) -> None:
        import argparse
        data = {"mode": "direct", "results": []}
        input_path = tmp_path / "empty.json"
        input_path.write_text(json.dumps(data))
        output_path = tmp_path / "out.json"
        args = argparse.Namespace(input=str(input_path), output=str(output_path), format="json")
        result = _run_export(args)
        assert result == 0


class TestEvaluateSubcommand:
    """Tests for the evaluate subcommand with mocked backend."""

    @pytest.mark.asyncio
    async def test_evaluate_direct_mode(self, runs_dir: Path, tmp_path: Path) -> None:
        """Test evaluate in direct mode with mocked backend."""
        from scripts.judge.__main__ import _run_evaluate

        mock_verdict = JudgeVerdict(
            mode=EvaluationMode.DIRECT,
            scores={"Correctness": DimensionScore("Correctness", 0.8, 0.3, "evidence", "reasoning")},
            overall_score=0.8,
            reasoning="Good",
            evidence=["test"],
            confidence=0.9,
            model_id="mock-model",
        )

        output_path = tmp_path / "eval_results.json"
        args = build_parser().parse_args([
            "evaluate", "--mode", "direct",
            "--runs-dir", str(runs_dir),
            "--output", str(output_path),
        ])

        with patch("scripts.judge.__main__._create_backend") as mock_create:
            mock_backend = MagicMock()
            mock_backend.model_id = "mock-model"
            mock_backend.evaluate = AsyncMock(return_value='{"scores": {"Correctness": {"score": 0.8, "weight": 0.3, "evidence": "e", "reasoning": "r"}}, "overall_score": 0.8, "reasoning": "Good", "evidence": ["test"], "confidence": 0.9}')
            mock_create.return_value = mock_backend

            with patch("src.judge.engine.UnifiedJudge.evaluate", new_callable=AsyncMock, return_value=mock_verdict):
                result = await _run_evaluate(args)

        assert result == 0
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["mode"] == "direct"
        assert data["successful"] == 3

    @pytest.mark.asyncio
    async def test_evaluate_missing_dir(self, tmp_path: Path) -> None:
        from scripts.judge.__main__ import _run_evaluate
        args = build_parser().parse_args([
            "evaluate", "--mode", "direct",
            "--runs-dir", str(tmp_path / "nonexistent"),
            "--output", str(tmp_path / "out.json"),
        ])
        result = await _run_evaluate(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_evaluate_empty_dir(self, tmp_path: Path) -> None:
        from scripts.judge.__main__ import _run_evaluate
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        args = build_parser().parse_args([
            "evaluate", "--mode", "direct",
            "--runs-dir", str(empty_dir),
            "--output", str(tmp_path / "out.json"),
        ])
        result = await _run_evaluate(args)
        assert result == 1


class TestCompareSubcommand:
    """Tests for the compare subcommand with mocked backend."""

    @pytest.mark.asyncio
    async def test_compare_missing_dir(self, tmp_path: Path) -> None:
        from scripts.judge.__main__ import _run_compare
        args = build_parser().parse_args([
            "compare", "--baseline-dir", str(tmp_path / "nonexistent"),
            "--treatment-dirs", str(tmp_path / "also_nonexistent"),
            "--output", str(tmp_path / "out.json"),
        ])
        result = await _run_compare(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_compare_no_common_tasks(self, tmp_path: Path) -> None:
        """Baseline and treatment have different task names -> no common tasks."""
        from scripts.judge.__main__ import _run_compare

        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"

        for name, d in [("task_A", baseline), ("task_B", treatment)]:
            task_dir = d / "run_001"
            task_dir.mkdir(parents=True)
            (task_dir / "result.json").write_text(json.dumps({"task_name": name}))

        args = build_parser().parse_args([
            "compare", "--baseline-dir", str(baseline),
            "--treatment-dirs", str(treatment),
            "--output", str(tmp_path / "out.json"),
        ])
        result = await _run_compare(args)
        assert result == 1


class TestMainEntryPoint:
    """Tests for the main() function routing."""

    def test_main_report(self, sample_results_json: Path, tmp_path: Path) -> None:
        output = tmp_path / "report.md"
        result = main(["report", "--input", str(sample_results_json), "--output", str(output)])
        assert result == 0
        assert output.exists()

    def test_main_export_json(self, sample_results_json: Path, tmp_path: Path) -> None:
        output = tmp_path / "out.json"
        result = main(["export", "--input", str(sample_results_json), "--format", "json", "--output", str(output)])
        assert result == 0
        assert output.exists()

    def test_main_export_csv(self, sample_results_json: Path, tmp_path: Path) -> None:
        output = tmp_path / "out.csv"
        result = main(["export", "--input", str(sample_results_json), "--format", "csv", "--output", str(output)])
        assert result == 0
        assert output.exists()
