"""Tests for dashboard/views/judge_unified.py - unified judge dashboard view."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

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

from dashboard.views.judge_unified import (  # noqa: E402
    _extract_agent_output,
    _load_oracle_data,
    _load_run_dirs,
    _load_templates,
    _serialize_verdict,
    _verdict_to_csv_rows,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_runs_dir(tmp_path: Path) -> Path:
    """Create a temporary runs directory with sample data."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    # Create a run with result.json and agent output
    run1 = runs_dir / "run_001"
    run1.mkdir()
    result = {"task_name": "test_task_alpha", "reward": 0.8}
    (run1 / "result.json").write_text(json.dumps(result))
    agent_dir = run1 / "logs" / "agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "solution.md").write_text("# Solution\nThis is the solution output.")

    # Create a run without task_name (fallback to task_id dict)
    run2 = runs_dir / "run_002"
    run2.mkdir()
    result2 = {"task_id": {"path": "test_task_beta"}, "reward": 0.5}
    (run2 / "result.json").write_text(json.dumps(result2))
    agent_dir2 = run2 / "logs" / "agent"
    agent_dir2.mkdir(parents=True)
    (agent_dir2 / "output.md").write_text("# Output\nBeta output.")

    # Create a run with no task name at all (should be skipped)
    run3 = runs_dir / "run_003"
    run3.mkdir()
    (run3 / "result.json").write_text(json.dumps({"reward": 0.1}))

    return runs_dir


@pytest.fixture()
def tmp_experiments_dir(tmp_path: Path) -> Path:
    """Create a temporary experiments directory."""
    exp_dir = tmp_path / "judge_experiments"
    exp_dir.mkdir()

    exp1 = exp_dir / "exp_abc123"
    exp1.mkdir()
    results = {
        "results": [
            {
                "task_id": "task_001",
                "task_description": "Test task one",
                "agent_output": "Agent output for task 1",
            },
            {
                "task_id": "task_002",
                "task_description": "Test task two",
                "agent_output": "Agent output for task 2",
            },
        ]
    }
    (exp1 / "results.json").write_text(json.dumps(results))
    config = {"model": "test-model", "temperature": 0.0}
    (exp1 / "config.json").write_text(json.dumps(config))

    return exp_dir


@pytest.fixture()
def tmp_oracle_dir(tmp_path: Path) -> Path:
    """Create a temporary oracle data directory."""
    oracle_dir = tmp_path / "oracle"
    oracle_dir.mkdir()

    scenario = {
        "ground_truth": "The correct answer is X.",
        "expected_approach": "Use algorithm Y.",
        "evaluation_criteria": "Must handle edge cases.",
        "context_files": ["src/main.py", "src/utils.py"],
        "task_description": "Implement feature Z",
    }
    (oracle_dir / "test_task_alpha.json").write_text(json.dumps(scenario))

    return oracle_dir


@pytest.fixture()
def tmp_templates_dir(tmp_path: Path) -> Path:
    """Create a temporary templates directory."""
    tpl_dir = tmp_path / "templates"
    tpl_dir.mkdir()
    (tpl_dir / "pairwise_simultaneous.yaml").write_text("name: pairwise_simultaneous\n")
    (tpl_dir / "direct_review.yaml").write_text("name: direct_review\n")
    (tpl_dir / "reference_correctness.yaml").write_text("name: reference_correctness\n")
    return tpl_dir


# ---------------------------------------------------------------------------
# Agent output extraction tests
# ---------------------------------------------------------------------------


class TestExtractAgentOutput:
    """Tests for _extract_agent_output."""

    def test_solution_md_preferred(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        agent_dir = run_dir / "logs" / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "solution.md").write_text("Solution content")
        (agent_dir / "other.md").write_text("Other content")

        result = _extract_agent_output(str(run_dir))
        assert result == "Solution content"

    def test_fallback_to_other_md(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        agent_dir = run_dir / "logs" / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "analysis.md").write_text("Analysis content")

        result = _extract_agent_output(str(run_dir))
        assert result == "Analysis content"

    def test_fallback_to_submission(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "submission.txt").write_text("Submission content")

        result = _extract_agent_output(str(run_dir))
        assert result == "Submission content"

    def test_no_output_returns_empty(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        result = _extract_agent_output(str(run_dir))
        assert result == ""

    def test_truncation_at_20000(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        agent_dir = run_dir / "logs" / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "solution.md").write_text("x" * 30000)

        result = _extract_agent_output(str(run_dir))
        assert len(result) == 20000


# ---------------------------------------------------------------------------
# Oracle data loading tests
# ---------------------------------------------------------------------------


class TestLoadOracleData:
    """Tests for _load_oracle_data."""

    def test_direct_match(self, tmp_oracle_dir: Path) -> None:
        data = _load_oracle_data(tmp_oracle_dir, "test_task_alpha")
        assert data["ground_truth"] == "The correct answer is X."
        assert data["expected_approach"] == "Use algorithm Y."
        assert len(data["context_files"]) == 2

    def test_no_match_returns_empty(self, tmp_oracle_dir: Path) -> None:
        data = _load_oracle_data(tmp_oracle_dir, "nonexistent_task")
        assert data == {}

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        data = _load_oracle_data(tmp_path / "does_not_exist", "task")
        assert data == {}

    def test_corrupt_json(self, tmp_path: Path) -> None:
        oracle_dir = tmp_path / "oracle"
        oracle_dir.mkdir()
        (oracle_dir / "bad_task.json").write_text("{invalid json")

        data = _load_oracle_data(oracle_dir, "bad_task")
        assert data == {}


# ---------------------------------------------------------------------------
# Template loading tests
# ---------------------------------------------------------------------------


class TestLoadTemplates:
    """Tests for _load_templates."""

    def test_load_templates(self, tmp_templates_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "dashboard.views.judge_unified._TEMPLATES_DIR",
            tmp_templates_dir,
        )
        templates = _load_templates()
        assert "pairwise_simultaneous" in templates
        assert "direct_review" in templates
        assert "reference_correctness" in templates

    def test_empty_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.setattr(
            "dashboard.views.judge_unified._TEMPLATES_DIR",
            empty_dir,
        )
        templates = _load_templates()
        assert templates == []

    def test_nonexistent_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "dashboard.views.judge_unified._TEMPLATES_DIR",
            tmp_path / "no_dir",
        )
        templates = _load_templates()
        assert templates == []


# ---------------------------------------------------------------------------
# Verdict serialization tests
# ---------------------------------------------------------------------------


class TestSerializeVerdict:
    """Tests for _serialize_verdict."""

    def test_serialize_judge_verdict(self) -> None:
        from src.judge.models import (
            CommentCategory,
            DimensionScore,
            EvaluationMode,
            JudgeVerdict,
            LineComment,
            Severity,
        )

        verdict = JudgeVerdict(
            mode=EvaluationMode.DIRECT,
            scores={
                "Correctness": DimensionScore(
                    dimension="Correctness",
                    score=0.8,
                    weight=0.3,
                    evidence="Good logic",
                    reasoning="Well structured",
                ),
            },
            overall_score=0.8,
            reasoning="Good overall",
            evidence=["ev1"],
            confidence=0.9,
            model_id="test-model",
            line_comments=[
                LineComment(
                    file_path="src/main.py",
                    line_range=(10, 15),
                    severity=Severity.WARNING,
                    comment="Potential issue",
                    category=CommentCategory.CORRECTNESS,
                ),
            ],
            metadata={"task_type": "analysis"},
        )

        serialized = _serialize_verdict(verdict)
        assert serialized["mode"] == "direct"
        assert serialized["overall_score"] == 0.8
        assert serialized["confidence"] == 0.9
        assert serialized["model_id"] == "test-model"
        assert "Correctness" in serialized["scores"]
        assert serialized["scores"]["Correctness"]["score"] == 0.8
        assert len(serialized["line_comments"]) == 1
        assert serialized["line_comments"][0]["severity"] == "warning"
        assert serialized["line_comments"][0]["category"] == "correctness"
        assert serialized["line_comments"][0]["line_range"] == [10, 15]

    def test_serialize_ensemble_verdict(self) -> None:
        from src.judge.models import (
            DimensionScore,
            EnsembleVerdict,
            EvaluationMode,
            JudgeVerdict,
        )

        inner_verdict = JudgeVerdict(
            mode=EvaluationMode.DIRECT,
            scores={
                "Correctness": DimensionScore(
                    dimension="Correctness",
                    score=0.7,
                    weight=0.3,
                    evidence="OK",
                    reasoning="Decent",
                ),
            },
            overall_score=0.7,
            reasoning="Decent",
            evidence=[],
            confidence=0.85,
            model_id="model-a",
        )

        ensemble = EnsembleVerdict(
            consensus_score=0.75,
            per_model_verdicts=[inner_verdict],
            vote_distribution={"pass": 1},
            agreement_score=0.6,
            confidence=0.88,
        )

        serialized = _serialize_verdict(ensemble)
        assert serialized["consensus_score"] == 0.75
        assert serialized["agreement_score"] == 0.6
        assert serialized["confidence"] == 0.88
        assert len(serialized["per_model_verdicts"]) == 1


# ---------------------------------------------------------------------------
# CSV row generation tests
# ---------------------------------------------------------------------------


class TestVerdictToCsvRows:
    """Tests for _verdict_to_csv_rows."""

    def test_basic_csv_rows(self) -> None:
        verdict_data = {
            "overall_score": 0.8,
            "confidence": 0.9,
            "model_id": "test-model",
            "reasoning": "Good",
            "scores": {
                "Correctness": {"score": 0.85, "weight": 0.3},
                "Completeness": {"score": 0.75, "weight": 0.25},
            },
        }
        rows = _verdict_to_csv_rows(verdict_data, "task_001")
        assert len(rows) == 2
        assert rows[0]["task_id"] == "task_001"
        assert rows[0]["dimension"] == "Correctness"
        assert rows[0]["dimension_score"] == "0.85"

    def test_empty_scores(self) -> None:
        verdict_data = {
            "overall_score": 0.5,
            "confidence": 0.7,
            "model_id": "test",
            "reasoning": "",
            "scores": {},
        }
        rows = _verdict_to_csv_rows(verdict_data, "task_002")
        assert len(rows) == 1
        assert rows[0]["dimension"] == ""


# ---------------------------------------------------------------------------
# Run directory loading tests
# ---------------------------------------------------------------------------


class TestLoadRunDirs:
    """Tests for _load_run_dirs."""

    def test_loads_valid_runs(
        self, tmp_runs_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "dashboard.views.judge_unified._EXTERNAL_RUNS_DIR",
            tmp_runs_dir,
        )
        runs = _load_run_dirs()
        # run_001 and run_002 should load; run_003 has no task name
        assert len(runs) == 2
        names = [r["name"] for r in runs]
        assert "run_001" in names
        assert "run_002" in names

    def test_task_name_from_dict(
        self, tmp_runs_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "dashboard.views.judge_unified._EXTERNAL_RUNS_DIR",
            tmp_runs_dir,
        )
        runs = _load_run_dirs()
        run2 = next(r for r in runs if r["name"] == "run_002")
        assert run2["task_name"] == "test_task_beta"

    def test_nonexistent_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "dashboard.views.judge_unified._EXTERNAL_RUNS_DIR",
            tmp_path / "no_dir",
        )
        runs = _load_run_dirs()
        assert runs == []

    def test_corrupt_json_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        run_bad = runs_dir / "run_bad"
        run_bad.mkdir()
        (run_bad / "result.json").write_text("{bad json")

        monkeypatch.setattr(
            "dashboard.views.judge_unified._EXTERNAL_RUNS_DIR",
            runs_dir,
        )
        runs = _load_run_dirs()
        assert runs == []


# ---------------------------------------------------------------------------
# Experiment results loading tests
# ---------------------------------------------------------------------------


class TestLoadExperimentResults:
    """Tests for experiment result loading."""

    def test_loads_experiments(
        self, tmp_experiments_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from dashboard.views.judge_unified import _load_experiment_results

        monkeypatch.setattr(
            "dashboard.views.judge_unified._EXPERIMENTS_DIR",
            tmp_experiments_dir,
        )
        experiments = _load_experiment_results()
        assert len(experiments) == 1
        assert experiments[0]["experiment_id"] == "exp_abc123"
        assert len(experiments[0]["results"]) == 2
        assert experiments[0]["config"]["model"] == "test-model"

    def test_nonexistent_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from dashboard.views.judge_unified import _load_experiment_results

        monkeypatch.setattr(
            "dashboard.views.judge_unified._EXPERIMENTS_DIR",
            tmp_path / "no_dir",
        )
        experiments = _load_experiment_results()
        assert experiments == []
