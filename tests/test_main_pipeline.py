"""Unit tests for scripts/ccb_pipeline/__main__.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.ccb_pipeline.__main__ import (
    _count_artifacts,
    _count_configs,
    _count_trials,
    main,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_result_json(trial_dir: Path, *, task_name: str = "test-task") -> None:
    """Create a minimal result.json in a trial directory."""
    trial_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "task_name": task_name,
        "trial_name": trial_dir.name,
        "task_id": {"path": f"/benchmarks/big_code_mcp/{task_name}"},
        "agent_info": {"name": "claude-code"},
        "agent_result": {
            "n_input_tokens": 5000,
            "n_output_tokens": 1000,
            "n_cache_tokens": 200,
        },
        "verifier_result": {"rewards": {"reward": 1.0}},
        "started_at": "2026-01-31T13:04:54.109208",
        "finished_at": "2026-01-31T13:18:56.677395",
        "agent_execution": {
            "started_at": "2026-01-31T13:06:43.029615",
            "finished_at": "2026-01-31T13:18:42.928355",
        },
    }
    (trial_dir / "result.json").write_text(json.dumps(data), encoding="utf-8")


def _make_runs_dir(tmp_path: Path) -> Path:
    """Create a minimal runs directory with one trial."""
    runs_dir = tmp_path / "runs"
    trial_dir = runs_dir / "official" / "exp1" / "baseline" / "20260201" / "trial1"
    _make_result_json(trial_dir)
    return runs_dir


def _make_metrics_json(path: Path, *, configs: list[str] | None = None) -> None:
    """Write a minimal experiment_metrics.json."""
    if configs is None:
        configs = ["BASELINE", "MCP_FULL"]
    trials = [
        {
            "trial_id": f"trial-{i}",
            "task_name": f"task-{i}",
            "benchmark": "big_code_mcp",
            "agent_config": cfg,
            "reward": 1.0,
            "pass_fail": "pass",
            "duration_seconds": 100.0,
            "input_tokens": 5000,
            "output_tokens": 1000,
            "cached_tokens": 200,
            "tool_utilization": {},
        }
        for i, cfg in enumerate(configs)
    ]
    categories = [
        {
            "run_category": "official",
            "experiments": [
                {"experiment_id": "exp1", "trials": trials}
            ],
        }
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(categories, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests for helper functions
# ---------------------------------------------------------------------------


class TestCountTrials:
    def test_counts_trials(self, tmp_path: Path) -> None:
        metrics_path = tmp_path / "metrics.json"
        _make_metrics_json(metrics_path, configs=["BASELINE", "MCP_BASE", "MCP_FULL"])
        assert _count_trials(metrics_path) == 3

    def test_returns_zero_for_missing_file(self, tmp_path: Path) -> None:
        assert _count_trials(tmp_path / "nonexistent.json") == 0

    def test_returns_zero_for_invalid_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json", encoding="utf-8")
        assert _count_trials(bad_file) == 0

    def test_returns_zero_for_non_list(self, tmp_path: Path) -> None:
        path = tmp_path / "obj.json"
        path.write_text("{}", encoding="utf-8")
        assert _count_trials(path) == 0


class TestCountConfigs:
    def test_returns_sorted_configs(self, tmp_path: Path) -> None:
        metrics_path = tmp_path / "metrics.json"
        _make_metrics_json(metrics_path, configs=["MCP_FULL", "BASELINE", "MCP_BASE"])
        result = _count_configs(metrics_path)
        assert result == ["BASELINE", "MCP_BASE", "MCP_FULL"]

    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        assert _count_configs(tmp_path / "nonexistent.json") == []

    def test_skips_none_config(self, tmp_path: Path) -> None:
        path = tmp_path / "metrics.json"
        categories = [
            {
                "run_category": "official",
                "experiments": [
                    {
                        "experiment_id": "exp1",
                        "trials": [
                            {"agent_config": None, "trial_id": "t1"},
                            {"agent_config": "BASELINE", "trial_id": "t2"},
                        ],
                    }
                ],
            }
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(categories), encoding="utf-8")
        assert _count_configs(path) == ["BASELINE"]


class TestCountArtifacts:
    def test_counts_files_in_tables_and_figures(self, tmp_path: Path) -> None:
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        (tables_dir / "table_agg.tex").write_text("tex", encoding="utf-8")
        (tables_dir / "table_bench.tex").write_text("tex", encoding="utf-8")

        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()
        (figures_dir / "fig.pdf").write_text("pdf", encoding="utf-8")

        assert _count_artifacts(tmp_path) == 3

    def test_returns_zero_for_empty_dir(self, tmp_path: Path) -> None:
        assert _count_artifacts(tmp_path) == 0

    def test_returns_zero_for_nonexistent_dir(self, tmp_path: Path) -> None:
        assert _count_artifacts(tmp_path / "nonexistent") == 0


# ---------------------------------------------------------------------------
# Tests for main() pipeline orchestration
# ---------------------------------------------------------------------------


class TestMainPipeline:
    def test_nonexistent_runs_dir_returns_1(self, tmp_path: Path) -> None:
        rc = main([
            "--runs-dir", str(tmp_path / "nonexistent"),
            "--output-dir", str(tmp_path / "output"),
        ])
        assert rc == 1

    @patch("scripts.ccb_pipeline.__main__.extract")
    def test_extract_failure_returns_1(
        self, mock_extract: object, tmp_path: Path
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        mock_extract.main = lambda argv: 1  # type: ignore[attr-defined]
        rc = main([
            "--runs-dir", str(runs_dir),
            "--output-dir", str(tmp_path / "output"),
        ])
        assert rc == 1

    @patch("scripts.ccb_pipeline.__main__.publish")
    @patch("scripts.ccb_pipeline.__main__.analyze")
    @patch("scripts.ccb_pipeline.__main__.judge")
    @patch("scripts.ccb_pipeline.__main__.extract")
    def test_judge_failure_returns_1(
        self,
        mock_extract: object,
        mock_judge: object,
        mock_analyze: object,
        mock_publish: object,
        tmp_path: Path,
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        output_dir = tmp_path / "output"
        metrics_path = output_dir / "experiment_metrics.json"

        def fake_extract(argv: list[str]) -> int:
            _make_metrics_json(metrics_path)
            return 0

        mock_extract.main = fake_extract  # type: ignore[attr-defined]
        mock_judge.main = lambda argv: 1  # type: ignore[attr-defined]
        rc = main([
            "--runs-dir", str(runs_dir),
            "--output-dir", str(output_dir),
        ])
        assert rc == 1

    @patch("scripts.ccb_pipeline.__main__.publish")
    @patch("scripts.ccb_pipeline.__main__.analyze")
    @patch("scripts.ccb_pipeline.__main__.judge")
    @patch("scripts.ccb_pipeline.__main__.extract")
    def test_analyze_failure_returns_1(
        self,
        mock_extract: object,
        mock_judge: object,
        mock_analyze: object,
        mock_publish: object,
        tmp_path: Path,
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        output_dir = tmp_path / "output"
        metrics_path = output_dir / "experiment_metrics.json"

        def fake_extract(argv: list[str]) -> int:
            _make_metrics_json(metrics_path)
            return 0

        mock_extract.main = fake_extract  # type: ignore[attr-defined]
        mock_judge.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_analyze.main = lambda argv: 1  # type: ignore[attr-defined]
        rc = main([
            "--runs-dir", str(runs_dir),
            "--output-dir", str(output_dir),
        ])
        assert rc == 1

    @patch("scripts.ccb_pipeline.__main__.publish")
    @patch("scripts.ccb_pipeline.__main__.analyze")
    @patch("scripts.ccb_pipeline.__main__.judge")
    @patch("scripts.ccb_pipeline.__main__.extract")
    def test_publish_failure_returns_1(
        self,
        mock_extract: object,
        mock_judge: object,
        mock_analyze: object,
        mock_publish: object,
        tmp_path: Path,
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        output_dir = tmp_path / "output"
        metrics_path = output_dir / "experiment_metrics.json"

        def fake_extract(argv: list[str]) -> int:
            _make_metrics_json(metrics_path)
            return 0

        mock_extract.main = fake_extract  # type: ignore[attr-defined]
        mock_judge.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_analyze.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_publish.main = lambda argv: 1  # type: ignore[attr-defined]
        rc = main([
            "--runs-dir", str(runs_dir),
            "--output-dir", str(output_dir),
        ])
        assert rc == 1

    @patch("scripts.ccb_pipeline.__main__.publish")
    @patch("scripts.ccb_pipeline.__main__.analyze")
    @patch("scripts.ccb_pipeline.__main__.judge")
    @patch("scripts.ccb_pipeline.__main__.extract")
    def test_all_stages_succeed_returns_0(
        self,
        mock_extract: object,
        mock_judge: object,
        mock_analyze: object,
        mock_publish: object,
        tmp_path: Path,
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        output_dir = tmp_path / "output"
        metrics_path = output_dir / "experiment_metrics.json"

        def fake_extract(argv: list[str]) -> int:
            _make_metrics_json(metrics_path)
            return 0

        mock_extract.main = fake_extract  # type: ignore[attr-defined]
        mock_judge.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_analyze.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_publish.main = lambda argv: 0  # type: ignore[attr-defined]
        rc = main([
            "--runs-dir", str(runs_dir),
            "--output-dir", str(output_dir),
        ])
        assert rc == 0

    @patch("scripts.ccb_pipeline.__main__.publish")
    @patch("scripts.ccb_pipeline.__main__.analyze")
    @patch("scripts.ccb_pipeline.__main__.judge")
    @patch("scripts.ccb_pipeline.__main__.extract")
    def test_skip_judge_passes_flag(
        self,
        mock_extract: object,
        mock_judge: object,
        mock_analyze: object,
        mock_publish: object,
        tmp_path: Path,
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        output_dir = tmp_path / "output"
        metrics_path = output_dir / "experiment_metrics.json"

        def fake_extract(argv: list[str]) -> int:
            _make_metrics_json(metrics_path)
            return 0

        judge_calls: list[list[str]] = []

        def fake_judge(argv: list[str]) -> int:
            judge_calls.append(argv)
            return 0

        mock_extract.main = fake_extract  # type: ignore[attr-defined]
        mock_judge.main = fake_judge  # type: ignore[attr-defined]
        mock_analyze.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_publish.main = lambda argv: 0  # type: ignore[attr-defined]
        rc = main([
            "--runs-dir", str(runs_dir),
            "--output-dir", str(output_dir),
            "--skip-judge",
        ])
        assert rc == 0
        assert len(judge_calls) == 1
        assert "--skip-judge" in judge_calls[0]

    @patch("scripts.ccb_pipeline.__main__.publish")
    @patch("scripts.ccb_pipeline.__main__.analyze")
    @patch("scripts.ccb_pipeline.__main__.judge")
    @patch("scripts.ccb_pipeline.__main__.extract")
    def test_judge_template_passed_through(
        self,
        mock_extract: object,
        mock_judge: object,
        mock_analyze: object,
        mock_publish: object,
        tmp_path: Path,
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        output_dir = tmp_path / "output"
        metrics_path = output_dir / "experiment_metrics.json"
        template_path = tmp_path / "template.json"
        template_path.write_text("{}", encoding="utf-8")

        def fake_extract(argv: list[str]) -> int:
            _make_metrics_json(metrics_path)
            return 0

        judge_calls: list[list[str]] = []

        def fake_judge(argv: list[str]) -> int:
            judge_calls.append(argv)
            return 0

        mock_extract.main = fake_extract  # type: ignore[attr-defined]
        mock_judge.main = fake_judge  # type: ignore[attr-defined]
        mock_analyze.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_publish.main = lambda argv: 0  # type: ignore[attr-defined]
        rc = main([
            "--runs-dir", str(runs_dir),
            "--output-dir", str(output_dir),
            "--judge-template", str(template_path),
        ])
        assert rc == 0
        assert len(judge_calls) == 1
        assert "--judge-template" in judge_calls[0]
        assert str(template_path) in judge_calls[0]

    @patch("scripts.ccb_pipeline.__main__.publish")
    @patch("scripts.ccb_pipeline.__main__.analyze")
    @patch("scripts.ccb_pipeline.__main__.judge")
    @patch("scripts.ccb_pipeline.__main__.extract")
    def test_extract_receives_correct_args(
        self,
        mock_extract: object,
        mock_judge: object,
        mock_analyze: object,
        mock_publish: object,
        tmp_path: Path,
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        output_dir = tmp_path / "output"
        metrics_path = output_dir / "experiment_metrics.json"

        extract_calls: list[list[str]] = []

        def fake_extract(argv: list[str]) -> int:
            extract_calls.append(argv)
            _make_metrics_json(metrics_path)
            return 0

        mock_extract.main = fake_extract  # type: ignore[attr-defined]
        mock_judge.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_analyze.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_publish.main = lambda argv: 0  # type: ignore[attr-defined]
        main([
            "--runs-dir", str(runs_dir),
            "--output-dir", str(output_dir),
        ])
        assert len(extract_calls) == 1
        assert "--runs-dir" in extract_calls[0]
        assert str(runs_dir) in extract_calls[0]
        assert "--output" in extract_calls[0]
        assert str(metrics_path) in extract_calls[0]

    @patch("scripts.ccb_pipeline.__main__.publish")
    @patch("scripts.ccb_pipeline.__main__.analyze")
    @patch("scripts.ccb_pipeline.__main__.judge")
    @patch("scripts.ccb_pipeline.__main__.extract")
    def test_analyze_receives_correct_args(
        self,
        mock_extract: object,
        mock_judge: object,
        mock_analyze: object,
        mock_publish: object,
        tmp_path: Path,
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        output_dir = tmp_path / "output"
        metrics_path = output_dir / "experiment_metrics.json"
        analysis_path = output_dir / "analysis_results.json"

        analyze_calls: list[list[str]] = []

        def fake_extract(argv: list[str]) -> int:
            _make_metrics_json(metrics_path)
            return 0

        def fake_analyze(argv: list[str]) -> int:
            analyze_calls.append(argv)
            return 0

        mock_extract.main = fake_extract  # type: ignore[attr-defined]
        mock_judge.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_analyze.main = fake_analyze  # type: ignore[attr-defined]
        mock_publish.main = lambda argv: 0  # type: ignore[attr-defined]
        main([
            "--runs-dir", str(runs_dir),
            "--output-dir", str(output_dir),
        ])
        assert len(analyze_calls) == 1
        assert "--input" in analyze_calls[0]
        assert str(metrics_path) in analyze_calls[0]
        assert "--output" in analyze_calls[0]
        assert str(analysis_path) in analyze_calls[0]

    @patch("scripts.ccb_pipeline.__main__.publish")
    @patch("scripts.ccb_pipeline.__main__.analyze")
    @patch("scripts.ccb_pipeline.__main__.judge")
    @patch("scripts.ccb_pipeline.__main__.extract")
    def test_publish_receives_correct_args(
        self,
        mock_extract: object,
        mock_judge: object,
        mock_analyze: object,
        mock_publish: object,
        tmp_path: Path,
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        output_dir = tmp_path / "output"
        metrics_path = output_dir / "experiment_metrics.json"
        analysis_path = output_dir / "analysis_results.json"

        publish_calls: list[list[str]] = []

        def fake_extract(argv: list[str]) -> int:
            _make_metrics_json(metrics_path)
            return 0

        def fake_publish(argv: list[str]) -> int:
            publish_calls.append(argv)
            return 0

        mock_extract.main = fake_extract  # type: ignore[attr-defined]
        mock_judge.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_analyze.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_publish.main = fake_publish  # type: ignore[attr-defined]
        main([
            "--runs-dir", str(runs_dir),
            "--output-dir", str(output_dir),
        ])
        assert len(publish_calls) == 1
        assert "--input" in publish_calls[0]
        assert str(analysis_path) in publish_calls[0]
        assert "--output-dir" in publish_calls[0]
        assert str(output_dir) in publish_calls[0]

    @patch("scripts.ccb_pipeline.__main__.publish")
    @patch("scripts.ccb_pipeline.__main__.analyze")
    @patch("scripts.ccb_pipeline.__main__.judge")
    @patch("scripts.ccb_pipeline.__main__.extract")
    def test_creates_output_dir(
        self,
        mock_extract: object,
        mock_judge: object,
        mock_analyze: object,
        mock_publish: object,
        tmp_path: Path,
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        output_dir = tmp_path / "deep" / "nested" / "output"
        metrics_path = output_dir / "experiment_metrics.json"

        def fake_extract(argv: list[str]) -> int:
            _make_metrics_json(metrics_path)
            return 0

        mock_extract.main = fake_extract  # type: ignore[attr-defined]
        mock_judge.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_analyze.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_publish.main = lambda argv: 0  # type: ignore[attr-defined]
        rc = main([
            "--runs-dir", str(runs_dir),
            "--output-dir", str(output_dir),
        ])
        assert rc == 0
        assert output_dir.is_dir()

    @patch("scripts.ccb_pipeline.__main__.publish")
    @patch("scripts.ccb_pipeline.__main__.analyze")
    @patch("scripts.ccb_pipeline.__main__.judge")
    @patch("scripts.ccb_pipeline.__main__.extract")
    def test_stages_run_in_order(
        self,
        mock_extract: object,
        mock_judge: object,
        mock_analyze: object,
        mock_publish: object,
        tmp_path: Path,
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        output_dir = tmp_path / "output"
        metrics_path = output_dir / "experiment_metrics.json"

        call_order: list[str] = []

        def fake_extract(argv: list[str]) -> int:
            call_order.append("extract")
            _make_metrics_json(metrics_path)
            return 0

        def fake_judge(argv: list[str]) -> int:
            call_order.append("judge")
            return 0

        def fake_analyze(argv: list[str]) -> int:
            call_order.append("analyze")
            return 0

        def fake_publish(argv: list[str]) -> int:
            call_order.append("publish")
            return 0

        mock_extract.main = fake_extract  # type: ignore[attr-defined]
        mock_judge.main = fake_judge  # type: ignore[attr-defined]
        mock_analyze.main = fake_analyze  # type: ignore[attr-defined]
        mock_publish.main = fake_publish  # type: ignore[attr-defined]
        main([
            "--runs-dir", str(runs_dir),
            "--output-dir", str(output_dir),
        ])
        assert call_order == ["extract", "judge", "analyze", "publish"]

    @patch("scripts.ccb_pipeline.__main__.publish")
    @patch("scripts.ccb_pipeline.__main__.analyze")
    @patch("scripts.ccb_pipeline.__main__.judge")
    @patch("scripts.ccb_pipeline.__main__.extract")
    def test_early_failure_stops_pipeline(
        self,
        mock_extract: object,
        mock_judge: object,
        mock_analyze: object,
        mock_publish: object,
        tmp_path: Path,
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        output_dir = tmp_path / "output"

        call_order: list[str] = []

        def fake_extract(argv: list[str]) -> int:
            call_order.append("extract")
            return 1

        def fake_judge(argv: list[str]) -> int:
            call_order.append("judge")
            return 0

        mock_extract.main = fake_extract  # type: ignore[attr-defined]
        mock_judge.main = fake_judge  # type: ignore[attr-defined]
        mock_analyze.main = lambda argv: 0  # type: ignore[attr-defined]
        mock_publish.main = lambda argv: 0  # type: ignore[attr-defined]
        rc = main([
            "--runs-dir", str(runs_dir),
            "--output-dir", str(output_dir),
        ])
        assert rc == 1
        assert call_order == ["extract"]
