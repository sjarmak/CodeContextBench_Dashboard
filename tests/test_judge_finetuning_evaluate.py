"""Tests for judge quality evaluation script."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# --- Together SDK mock setup (required before importing src.judge) ---
_together_mock_needed = "together" not in sys.modules

if _together_mock_needed:
    _together_module = ModuleType("together")
    _together_error = ModuleType("together.error")

    class _MockTogetherRateLimitError(Exception):
        pass

    _together_error.RateLimitError = _MockTogetherRateLimitError  # type: ignore[attr-defined]
    _together_module.error = _together_error  # type: ignore[attr-defined]
    _together_module.AsyncTogether = MagicMock  # type: ignore[attr-defined]
    sys.modules["together"] = _together_module
    sys.modules["together.error"] = _together_error

import pytest  # noqa: E402

from scripts.judge_finetuning.evaluate_judge import (  # noqa: E402
    EvalConfig,
    EvaluationReport,
    ModelMetrics,
    _categorize_score,
    _extract_dimension_scores,
    _extract_human_scores,
    _metrics_to_dict,
    _report_to_dict,
    compute_alignment_metrics,
    compute_cost_metrics,
    compute_dimension_accuracy,
    evaluate_judge,
    load_eval_data,
    load_human_annotations,
    main,
    save_report,
)


# -- Fixtures --


def _make_eval_item(
    task_id: str = "t1",
    prompt: str = "Task: evaluate this",
    chosen: str = "good output",
    rejected: str = "bad output",
    model_score: float | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"task_id": task_id, "source": "test"}
    if model_score is not None:
        metadata["model_score"] = model_score
    return {
        "prompt": prompt,
        "chosen": chosen,
        "rejected": rejected,
        "metadata": metadata,
    }


def _make_annotation(
    task_id: str = "t1",
    mode: str = "direct",
    scores: dict[str, Any] | None = None,
    preference: str = "",
) -> dict[str, Any]:
    ann: dict[str, Any] = {
        "task_id": task_id,
        "mode": mode,
        "annotator_id": "tester",
        "timestamp": "2026-01-01T00:00:00",
    }
    if scores is not None:
        ann["scores"] = scores
    if preference:
        ann["preference"] = preference
    return ann


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


# -- EvalConfig tests --


class TestEvalConfig:
    """Tests for EvalConfig frozen dataclass."""

    def test_construction(self) -> None:
        config = EvalConfig(model_ids=("model-a",))
        assert config.model_ids == ("model-a",)
        assert config.temperature == 0.0
        assert config.max_tokens == 2000

    def test_immutability(self) -> None:
        config = EvalConfig()
        with pytest.raises(AttributeError):
            config.temperature = 0.5  # type: ignore[misc]

    def test_defaults(self) -> None:
        config = EvalConfig()
        assert config.model_ids == ()
        assert config.eval_data_path == ""
        assert config.output_path == "evaluation_report.json"
        assert config.max_samples == 0


# -- ModelMetrics tests --


class TestModelMetrics:
    """Tests for ModelMetrics frozen dataclass."""

    def test_construction(self) -> None:
        m = ModelMetrics(
            model_id="test-model",
            spearman_rho=0.85,
            cohens_kappa=0.72,
            total_evaluations=50,
        )
        assert m.model_id == "test-model"
        assert m.spearman_rho == 0.85
        assert m.cohens_kappa == 0.72

    def test_immutability(self) -> None:
        m = ModelMetrics(model_id="m")
        with pytest.raises(AttributeError):
            m.spearman_rho = 0.9  # type: ignore[misc]

    def test_defaults(self) -> None:
        m = ModelMetrics(model_id="m")
        assert m.spearman_rho == 0.0
        assert m.spearman_p_value == 1.0
        assert m.avg_latency_ms == 0.0
        assert m.per_dimension_accuracy == {}


# -- EvaluationReport tests --


class TestEvaluationReport:
    """Tests for EvaluationReport frozen dataclass."""

    def test_construction(self) -> None:
        metrics = ModelMetrics(model_id="m1", spearman_rho=0.9)
        report = EvaluationReport(
            model_metrics=(metrics,),
            eval_samples=100,
            human_samples=50,
            best_model_id="m1",
            best_spearman=0.9,
        )
        assert len(report.model_metrics) == 1
        assert report.best_model_id == "m1"

    def test_immutability(self) -> None:
        report = EvaluationReport()
        with pytest.raises(AttributeError):
            report.eval_samples = 99  # type: ignore[misc]


# -- load_eval_data tests --


class TestLoadEvalData:
    """Tests for eval data loading."""

    def test_valid_data(self, tmp_path: Path) -> None:
        items = [_make_eval_item("t1"), _make_eval_item("t2")]
        _write_jsonl(tmp_path / "eval.jsonl", items)
        result = load_eval_data(tmp_path / "eval.jsonl")
        assert len(result) == 2

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_eval_data(tmp_path / "missing.jsonl")

    def test_corrupt_lines_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "eval.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(json.dumps(_make_eval_item("t1")) + "\n")
            f.write("not json\n")
            f.write(json.dumps(_make_eval_item("t2")) + "\n")
        result = load_eval_data(path)
        assert len(result) == 2

    def test_missing_fields_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "eval.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(json.dumps({"prompt": "x"}) + "\n")
            f.write(json.dumps(_make_eval_item("t1")) + "\n")
        result = load_eval_data(path)
        assert len(result) == 1

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "eval.jsonl"
        path.write_text("\n\n")
        result = load_eval_data(path)
        assert result == []


# -- load_human_annotations tests --


class TestLoadHumanAnnotations:
    """Tests for human annotation loading."""

    def test_valid_annotations(self, tmp_path: Path) -> None:
        anns = [_make_annotation("t1"), _make_annotation("t2")]
        _write_jsonl(tmp_path / "annotations.jsonl", anns)
        result = load_human_annotations(tmp_path / "annotations.jsonl")
        assert len(result) == 2

    def test_missing_file(self, tmp_path: Path) -> None:
        result = load_human_annotations(tmp_path / "missing.jsonl")
        assert result == []

    def test_corrupt_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "annotations.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(json.dumps(_make_annotation("t1")) + "\n")
            f.write("bad json\n")
        result = load_human_annotations(path)
        assert len(result) == 1


# -- _categorize_score tests --


class TestCategorizeScore:
    """Tests for score categorization."""

    def test_pass(self) -> None:
        assert _categorize_score(0.75) == "pass"
        assert _categorize_score(1.0) == "pass"

    def test_partial(self) -> None:
        assert _categorize_score(0.25) == "partial"
        assert _categorize_score(0.5) == "partial"
        assert _categorize_score(0.74) == "partial"

    def test_fail(self) -> None:
        assert _categorize_score(0.0) == "fail"
        assert _categorize_score(0.24) == "fail"


# -- _extract_human_scores tests --


class TestExtractHumanScores:
    """Tests for human score extraction."""

    def test_direct_mode(self) -> None:
        anns = [
            _make_annotation("t1", "direct", {"correctness": 4.0, "quality": 3.0}),
        ]
        scores = _extract_human_scores(anns)
        assert "t1" in scores
        assert scores["t1"] == pytest.approx(3.5)

    def test_reference_mode(self) -> None:
        anns = [
            _make_annotation("t1", "reference", {"correctness": "pass", "completeness": "partial"}),
        ]
        scores = _extract_human_scores(anns)
        assert scores["t1"] == pytest.approx(0.75)

    def test_pairwise_mode(self) -> None:
        anns = [
            {
                "task_id": "t1",
                "mode": "pairwise",
                "preference": "model_a",
                "scores": {},
            },
        ]
        scores = _extract_human_scores(anns)
        assert scores["t1"] == 1.0

    def test_pairwise_tie_excluded(self) -> None:
        anns = [
            {
                "task_id": "t1",
                "mode": "pairwise",
                "preference": "Tie",
                "scores": {},
            },
        ]
        scores = _extract_human_scores(anns)
        assert "t1" not in scores

    def test_missing_task_id(self) -> None:
        anns = [_make_annotation("", "direct", {"score": 3.0})]
        scores = _extract_human_scores(anns)
        assert len(scores) == 0

    def test_multiple_annotations_averaged(self) -> None:
        anns = [
            _make_annotation("t1", "direct", {"score": 4.0}),
            _make_annotation("t1", "direct", {"score": 2.0}),
        ]
        scores = _extract_human_scores(anns)
        assert scores["t1"] == pytest.approx(3.0)


# -- _extract_dimension_scores tests --


class TestExtractDimensionScores:
    """Tests for per-dimension score extraction."""

    def test_extracts_dimensions(self) -> None:
        anns = [
            _make_annotation("t1", "direct", {"correctness": 4.0, "quality": 3.0}),
            _make_annotation("t2", "direct", {"correctness": 2.0}),
        ]
        dims = _extract_dimension_scores(anns)
        assert "correctness" in dims
        assert "t1" in dims["correctness"]
        assert dims["correctness"]["t1"] == [4.0]
        assert dims["correctness"]["t2"] == [2.0]

    def test_only_direct_mode(self) -> None:
        anns = [
            _make_annotation("t1", "reference", {"correctness": "pass"}),
        ]
        dims = _extract_dimension_scores(anns)
        assert len(dims) == 0

    def test_non_numeric_skipped(self) -> None:
        anns = [
            _make_annotation("t1", "direct", {"correctness": 4.0, "notes": "good"}),
        ]
        dims = _extract_dimension_scores(anns)
        assert "correctness" in dims
        assert "notes" not in dims


# -- compute_alignment_metrics tests --


class TestComputeAlignmentMetrics:
    """Tests for alignment metric computation."""

    def test_perfect_alignment(self) -> None:
        model = {"t1": 0.9, "t2": 0.5, "t3": 0.1}
        human = {"t1": 0.9, "t2": 0.5, "t3": 0.1}
        rho, p, kappa = compute_alignment_metrics(model, human)
        assert rho == pytest.approx(1.0)
        assert kappa == pytest.approx(1.0)

    def test_inverse_alignment(self) -> None:
        model = {"t1": 0.9, "t2": 0.5, "t3": 0.1}
        human = {"t1": 0.1, "t2": 0.5, "t3": 0.9}
        rho, p, kappa = compute_alignment_metrics(model, human)
        assert rho < 0

    def test_insufficient_tasks(self) -> None:
        model = {"t1": 0.9}
        human = {"t1": 0.9}
        rho, p, kappa = compute_alignment_metrics(model, human)
        assert rho == 0.0
        assert kappa == 0.0

    def test_no_overlap(self) -> None:
        model = {"t1": 0.9}
        human = {"t2": 0.9}
        rho, p, kappa = compute_alignment_metrics(model, human)
        assert rho == 0.0

    def test_partial_overlap(self) -> None:
        model = {"t1": 0.9, "t2": 0.5, "t3": 0.1}
        human = {"t2": 0.5, "t3": 0.1, "t4": 0.8}
        rho, p, kappa = compute_alignment_metrics(model, human)
        # Only t2 and t3 overlap
        assert rho == pytest.approx(1.0)


# -- compute_dimension_accuracy tests --


class TestComputeDimensionAccuracy:
    """Tests for per-dimension accuracy computation."""

    def test_perfect_accuracy(self) -> None:
        model_dims = {"correctness": {"t1": 0.9, "t2": 0.1}}
        human_dims = {"correctness": {"t1": [0.85], "t2": [0.1]}}
        acc = compute_dimension_accuracy(model_dims, human_dims)
        assert acc["correctness"] == 1.0

    def test_zero_accuracy(self) -> None:
        model_dims = {"correctness": {"t1": 0.1}}
        human_dims = {"correctness": {"t1": [0.9]}}
        acc = compute_dimension_accuracy(model_dims, human_dims)
        assert acc["correctness"] == 0.0

    def test_missing_model_dimension(self) -> None:
        model_dims: dict[str, dict[str, float]] = {}
        human_dims = {"correctness": {"t1": [0.9]}}
        acc = compute_dimension_accuracy(model_dims, human_dims)
        assert len(acc) == 0

    def test_no_task_overlap(self) -> None:
        model_dims = {"correctness": {"t1": 0.9}}
        human_dims = {"correctness": {"t2": [0.9]}}
        acc = compute_dimension_accuracy(model_dims, human_dims)
        # No overlap => no total => dimension not in result
        assert acc.get("correctness") is None


# -- compute_cost_metrics tests --


class TestComputeCostMetrics:
    """Tests for cost metric computation."""

    def test_basic_cost(self) -> None:
        latencies = [100.0, 200.0, 300.0]
        tokens = [1000, 2000, 3000]
        avg_lat, total_tok, cost = compute_cost_metrics(latencies, tokens)
        assert avg_lat == pytest.approx(200.0)
        assert total_tok == 6000
        assert cost > 0

    def test_empty_inputs(self) -> None:
        avg_lat, total_tok, cost = compute_cost_metrics([], [])
        assert avg_lat == 0.0
        assert total_tok == 0
        assert cost == 0.0

    def test_custom_cost_rates(self) -> None:
        latencies = [100.0]
        tokens = [1000]
        _, _, cost_default = compute_cost_metrics(latencies, tokens)
        _, _, cost_expensive = compute_cost_metrics(
            latencies, tokens, cost_per_1k_input=0.01, cost_per_1k_output=0.03
        )
        assert cost_expensive > cost_default

    def test_cost_per_100_scaling(self) -> None:
        latencies = [100.0]
        tokens = [4000]  # 4000 tokens per eval
        _, _, cost = compute_cost_metrics(
            latencies, tokens,
            cost_per_1k_input=0.001,
            cost_per_1k_output=0.002,
        )
        # 4000 tokens: 80% input (3200), 20% output (800)
        # cost = (3.2 * 0.001 + 0.8 * 0.002) * 100
        expected = (3.2 * 0.001 + 0.8 * 0.002) * 100
        assert cost == pytest.approx(expected)


# -- serialization tests --


class TestSerialization:
    """Tests for report serialization."""

    def test_metrics_to_dict(self) -> None:
        m = ModelMetrics(
            model_id="m1",
            spearman_rho=0.85,
            cohens_kappa=0.72,
            total_evaluations=50,
            per_dimension_accuracy={"correctness": 0.9},
        )
        d = _metrics_to_dict(m)
        assert d["model_id"] == "m1"
        assert d["spearman_rho"] == 0.85
        assert d["per_dimension_accuracy"]["correctness"] == 0.9

    def test_report_to_dict(self) -> None:
        m = ModelMetrics(model_id="m1")
        report = EvaluationReport(
            model_metrics=(m,),
            eval_samples=100,
            best_model_id="m1",
        )
        d = _report_to_dict(report)
        assert d["eval_samples"] == 100
        assert len(d["model_metrics"]) == 1
        assert d["best_model_id"] == "m1"

    def test_save_report_creates_file(self, tmp_path: Path) -> None:
        report = EvaluationReport(
            model_metrics=(ModelMetrics(model_id="m1"),),
            eval_samples=10,
        )
        output = tmp_path / "report.json"
        save_report(report, output)
        assert output.exists()
        data = json.loads(output.read_text())
        assert data["eval_samples"] == 10

    def test_save_report_creates_directories(self, tmp_path: Path) -> None:
        report = EvaluationReport()
        output = tmp_path / "nested" / "dir" / "report.json"
        save_report(report, output)
        assert output.exists()

    def test_round_trip(self, tmp_path: Path) -> None:
        m = ModelMetrics(
            model_id="m1",
            spearman_rho=0.85,
            cohens_kappa=0.72,
            total_evaluations=50,
            avg_latency_ms=150.5,
            total_tokens=5000,
            estimated_cost_per_100=0.05,
        )
        report = EvaluationReport(
            model_metrics=(m,),
            eval_samples=100,
            human_samples=50,
            best_model_id="m1",
            best_spearman=0.85,
        )
        output = tmp_path / "report.json"
        save_report(report, output)
        data = json.loads(output.read_text())
        assert data["model_metrics"][0]["spearman_rho"] == 0.85
        assert data["model_metrics"][0]["avg_latency_ms"] == 150.5


# -- evaluate_judge integration tests --


class TestEvaluateJudge:
    """Tests for the evaluate_judge function."""

    def test_single_model_with_prescored_data(self) -> None:
        """Test evaluation with pre-computed model scores in metadata."""
        eval_data = [
            _make_eval_item("t1", model_score=0.9),
            _make_eval_item("t2", model_score=0.5),
            _make_eval_item("t3", model_score=0.1),
        ]
        human_scores = {"t1": 0.85, "t2": 0.45, "t3": 0.15}
        human_dims: dict[str, dict[str, list[float]]] = {}

        report = evaluate_judge(
            model_ids=["test-model"],
            eval_data=eval_data,
            human_scores=human_scores,
            human_dim_scores=human_dims,
        )

        assert len(report.model_metrics) == 1
        assert report.model_metrics[0].model_id == "test-model"
        assert report.model_metrics[0].total_evaluations == 3
        assert report.model_metrics[0].spearman_rho > 0.9
        assert report.best_model_id == "test-model"

    def test_multiple_models_comparison(self) -> None:
        """Test comparison mode with multiple models."""
        eval_data = [
            _make_eval_item("t1", model_score=0.9),
            _make_eval_item("t2", model_score=0.5),
            _make_eval_item("t3", model_score=0.1),
        ]
        human_scores = {"t1": 0.9, "t2": 0.5, "t3": 0.1}
        human_dims: dict[str, dict[str, list[float]]] = {}

        report = evaluate_judge(
            model_ids=["model-a", "model-b"],
            eval_data=eval_data,
            human_scores=human_scores,
            human_dim_scores=human_dims,
        )

        assert len(report.model_metrics) == 2
        assert report.comparison_summary.get("models_compared") == 2
        assert "ranking_by_spearman" in report.comparison_summary

    def test_no_human_scores(self) -> None:
        """Test with no human annotations (alignment = 0)."""
        eval_data = [
            _make_eval_item("t1", model_score=0.9),
        ]
        human_scores: dict[str, float] = {}
        human_dims: dict[str, dict[str, list[float]]] = {}

        report = evaluate_judge(
            model_ids=["model-a"],
            eval_data=eval_data,
            human_scores=human_scores,
            human_dim_scores=human_dims,
        )

        assert report.model_metrics[0].spearman_rho == 0.0
        assert report.model_metrics[0].cohens_kappa == 0.0

    def test_empty_model_list(self) -> None:
        """Test with no models to evaluate."""
        report = evaluate_judge(
            model_ids=[],
            eval_data=[_make_eval_item()],
            human_scores={"t1": 0.9},
            human_dim_scores={},
        )
        assert len(report.model_metrics) == 0
        assert report.best_model_id == ""


# -- CLI tests --


class TestCLI:
    """Tests for CLI entry point."""

    def test_missing_required_args(self) -> None:
        with pytest.raises(SystemExit):
            main([])

    def test_missing_model(self) -> None:
        with pytest.raises(SystemExit):
            main(["--eval-data", "test.jsonl"])

    def test_missing_eval_data(self) -> None:
        with pytest.raises(SystemExit):
            main(["--model", "test-model"])

    def test_file_not_found(self, tmp_path: Path) -> None:
        result = main([
            "--model", "test-model",
            "--eval-data", str(tmp_path / "nonexistent.jsonl"),
            "--output", str(tmp_path / "report.json"),
        ])
        assert result == 1

    def test_successful_run(self, tmp_path: Path) -> None:
        eval_data = [
            _make_eval_item("t1", model_score=0.9),
            _make_eval_item("t2", model_score=0.5),
        ]
        eval_path = tmp_path / "eval.jsonl"
        _write_jsonl(eval_path, eval_data)

        ann_path = tmp_path / "annotations.jsonl"
        anns = [
            _make_annotation("t1", "direct", {"score": 4.0}),
            _make_annotation("t2", "direct", {"score": 2.0}),
        ]
        _write_jsonl(ann_path, anns)

        output = tmp_path / "report.json"
        result = main([
            "--model", "test-model",
            "--eval-data", str(eval_path),
            "--annotations", str(ann_path),
            "--output", str(output),
        ])
        assert result == 0
        assert output.exists()
        data = json.loads(output.read_text())
        assert data["eval_samples"] == 2

    def test_multiple_models(self, tmp_path: Path) -> None:
        eval_data = [_make_eval_item("t1", model_score=0.9)]
        eval_path = tmp_path / "eval.jsonl"
        _write_jsonl(eval_path, eval_data)

        output = tmp_path / "report.json"
        result = main([
            "--model", "model-a",
            "--model", "model-b",
            "--eval-data", str(eval_path),
            "--output", str(output),
        ])
        assert result == 0
        data = json.loads(output.read_text())
        assert len(data["model_metrics"]) == 2

    def test_max_samples(self, tmp_path: Path) -> None:
        eval_data = [
            _make_eval_item("t1", model_score=0.9),
            _make_eval_item("t2", model_score=0.5),
            _make_eval_item("t3", model_score=0.1),
        ]
        eval_path = tmp_path / "eval.jsonl"
        _write_jsonl(eval_path, eval_data)

        output = tmp_path / "report.json"
        result = main([
            "--model", "test-model",
            "--eval-data", str(eval_path),
            "--output", str(output),
            "--max-samples", "2",
        ])
        assert result == 0
        data = json.loads(output.read_text())
        assert data["eval_samples"] == 2
