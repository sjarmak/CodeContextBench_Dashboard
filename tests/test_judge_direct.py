"""Tests for the DirectEvaluator module."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

# --- Together SDK mock setup (needed because src.judge.__init__ imports backends) ---
if "together" not in sys.modules:
    _together_module = ModuleType("together")
    _together_error = ModuleType("together.error")

    class _MockTogetherRateLimitError(Exception):
        pass

    _together_error.RateLimitError = _MockTogetherRateLimitError  # type: ignore[attr-defined]
    _together_module.error = _together_error  # type: ignore[attr-defined]
    _together_module.AsyncTogether = MagicMock  # type: ignore[attr-defined]
    sys.modules["together"] = _together_module
    sys.modules["together.error"] = _together_error

from src.judge.engine import JudgeConfig, UnifiedJudge
from src.judge.models import (
    CommentCategory,
    DimensionScore,
    DirectInput,
    EvaluationMode,
    JudgeVerdict,
    Severity,
)
from src.judge.modes.direct import DirectEvaluator, load_rubric

_TEMPLATES_DIR = str(
    Path(__file__).resolve().parent.parent / "configs" / "judge_prompts"
)


# ---------- Helpers ----------


def _make_mock_backend(
    response: str = '{"reasoning": "ok"}', model_id: str = "test-model"
) -> MagicMock:
    backend = MagicMock()
    backend.model_id = model_id
    backend.evaluate = AsyncMock(return_value=response)
    return backend


def _make_direct_response(
    dimension_scores: dict | None = None,
    line_comments: list | None = None,
    overall_score: float = 0.75,
    confidence: float = 0.85,
    reasoning: str = "Good implementation overall.",
) -> str:
    if dimension_scores is None:
        dimension_scores = {
            "Correctness": {"score": 0.8, "weight": 0.3, "evidence": "Correct logic", "reasoning": "Passes tests"},
            "Completeness": {"score": 0.7, "weight": 0.25, "evidence": "Mostly complete", "reasoning": "Missing edge case"},
            "Code Quality": {"score": 0.9, "weight": 0.2, "evidence": "Clean code", "reasoning": "Well-structured"},
            "Efficiency": {"score": 0.6, "weight": 0.15, "evidence": "Could optimize", "reasoning": "O(n^2) loop"},
            "Security": {"score": 1.0, "weight": 0.1, "evidence": "No issues", "reasoning": "Input validated"},
        }
    if line_comments is None:
        line_comments = []
    return json.dumps({
        "reasoning": reasoning,
        "dimension_scores": dimension_scores,
        "line_comments": line_comments,
        "overall_score": overall_score,
        "confidence": confidence,
    })


def _make_direct_input(
    task_id: str = "task-001",
    task_description: str = "Implement a user authentication system",
    agent_output: str = "Here is the authentication implementation...",
    code_changes: str | None = "diff --git a/auth.py\n+def login():\n+    pass",
) -> DirectInput:
    return DirectInput(
        task_id=task_id,
        task_description=task_description,
        evaluation_mode=EvaluationMode.DIRECT,
        agent_output=agent_output,
        code_changes=code_changes,
    )


# ---------- DirectEvaluator Construction ----------


class TestDirectEvaluatorConstruction:
    def test_creates_with_required_args(self) -> None:
        backend = _make_mock_backend()
        config = JudgeConfig()
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir=_TEMPLATES_DIR)
        assert evaluator._backend is backend
        assert evaluator._config is config
        assert evaluator._templates_dir == _TEMPLATES_DIR

    def test_stores_templates_dir_as_string(self) -> None:
        backend = _make_mock_backend()
        config = JudgeConfig()
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir="/some/path")
        assert evaluator._templates_dir == "/some/path"


# ---------- Basic Evaluation ----------


class TestDirectEvaluation:
    @pytest.mark.asyncio
    async def test_evaluate_returns_judge_verdict(self) -> None:
        response = _make_direct_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert isinstance(verdict, JudgeVerdict)
        assert verdict.mode == EvaluationMode.DIRECT

    @pytest.mark.asyncio
    async def test_evaluate_populates_scores(self) -> None:
        response = _make_direct_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert "Correctness" in verdict.scores
        assert "Completeness" in verdict.scores
        assert "Code Quality" in verdict.scores
        assert "Efficiency" in verdict.scores
        assert "Security" in verdict.scores

    @pytest.mark.asyncio
    async def test_evaluate_overall_score_from_response(self) -> None:
        response = _make_direct_response(overall_score=0.82)
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert verdict.overall_score == pytest.approx(0.82)

    @pytest.mark.asyncio
    async def test_evaluate_computes_weighted_score_when_not_provided(self) -> None:
        scores = {
            "Correctness": {"score": 0.8, "weight": 0.3, "evidence": "", "reasoning": ""},
            "Completeness": {"score": 0.6, "weight": 0.7, "evidence": "", "reasoning": ""},
        }
        response = json.dumps({
            "reasoning": "ok",
            "dimension_scores": scores,
            "line_comments": [],
            "confidence": 0.8,
        })
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        expected = (0.8 * 0.3 + 0.6 * 0.7) / (0.3 + 0.7)
        assert verdict.overall_score == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_evaluate_populates_reasoning(self) -> None:
        response = _make_direct_response(reasoning="Detailed analysis")
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert verdict.reasoning == "Detailed analysis"

    @pytest.mark.asyncio
    async def test_evaluate_populates_confidence(self) -> None:
        response = _make_direct_response(confidence=0.92)
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert verdict.confidence == pytest.approx(0.92)

    @pytest.mark.asyncio
    async def test_evaluate_sets_model_id(self) -> None:
        response = _make_direct_response()
        backend = _make_mock_backend(response, model_id="claude-3-haiku")
        config = JudgeConfig()
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert verdict.model_id == "claude-3-haiku"

    @pytest.mark.asyncio
    async def test_evaluate_includes_metadata(self) -> None:
        response = _make_direct_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert "raw_response" in verdict.metadata

    @pytest.mark.asyncio
    async def test_evaluate_calls_backend(self) -> None:
        response = _make_direct_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir=_TEMPLATES_DIR)

        await evaluator.evaluate(_make_direct_input())
        backend.evaluate.assert_called_once()
        call_kwargs = backend.evaluate.call_args
        assert "prompt" in call_kwargs.kwargs or len(call_kwargs.args) > 0

    @pytest.mark.asyncio
    async def test_evaluate_without_code_changes(self) -> None:
        response = _make_direct_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir=_TEMPLATES_DIR)

        judge_input = _make_direct_input(code_changes=None)
        verdict = await evaluator.evaluate(judge_input)
        assert isinstance(verdict, JudgeVerdict)


# ---------- Severity Levels ----------


class TestSeverityLevels:
    @pytest.mark.asyncio
    async def test_critical_severity(self) -> None:
        comments = [
            {"file_path": "auth.py", "line_range": [10, 15], "severity": "CRITICAL", "comment": "SQL injection", "category": "SECURITY"},
        ]
        response = _make_direct_response(line_comments=comments)
        backend = _make_mock_backend(response)
        evaluator = DirectEvaluator(backend=backend, config=JudgeConfig(), templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert len(verdict.line_comments) == 1
        assert verdict.line_comments[0].severity == Severity.CRITICAL

    @pytest.mark.asyncio
    async def test_warning_severity(self) -> None:
        comments = [
            {"file_path": "utils.py", "line_range": [5, 8], "severity": "WARNING", "comment": "Missing null check", "category": "CORRECTNESS"},
        ]
        response = _make_direct_response(line_comments=comments)
        backend = _make_mock_backend(response)
        evaluator = DirectEvaluator(backend=backend, config=JudgeConfig(), templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert verdict.line_comments[0].severity == Severity.WARNING

    @pytest.mark.asyncio
    async def test_suggestion_severity(self) -> None:
        comments = [
            {"file_path": "main.py", "line_range": [20, 22], "severity": "SUGGESTION", "comment": "Consider using f-string", "category": "STYLE"},
        ]
        response = _make_direct_response(line_comments=comments)
        backend = _make_mock_backend(response)
        evaluator = DirectEvaluator(backend=backend, config=JudgeConfig(), templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert verdict.line_comments[0].severity == Severity.SUGGESTION

    @pytest.mark.asyncio
    async def test_praise_severity(self) -> None:
        comments = [
            {"file_path": "test.py", "line_range": [1, 5], "severity": "PRAISE", "comment": "Great error handling", "category": "CORRECTNESS"},
        ]
        response = _make_direct_response(line_comments=comments)
        backend = _make_mock_backend(response)
        evaluator = DirectEvaluator(backend=backend, config=JudgeConfig(), templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert verdict.line_comments[0].severity == Severity.PRAISE

    @pytest.mark.asyncio
    async def test_all_severity_levels_together(self) -> None:
        comments = [
            {"file_path": "a.py", "line_range": [1, 2], "severity": "CRITICAL", "comment": "c1", "category": "SECURITY"},
            {"file_path": "b.py", "line_range": [3, 4], "severity": "WARNING", "comment": "c2", "category": "CORRECTNESS"},
            {"file_path": "c.py", "line_range": [5, 6], "severity": "SUGGESTION", "comment": "c3", "category": "STYLE"},
            {"file_path": "d.py", "line_range": [7, 8], "severity": "PRAISE", "comment": "c4", "category": "PERFORMANCE"},
        ]
        response = _make_direct_response(line_comments=comments)
        backend = _make_mock_backend(response)
        evaluator = DirectEvaluator(backend=backend, config=JudgeConfig(), templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        severities = [c.severity for c in verdict.line_comments]
        assert severities == [Severity.CRITICAL, Severity.WARNING, Severity.SUGGESTION, Severity.PRAISE]


# ---------- Line Comment Categories ----------


class TestLineCommentCategories:
    @pytest.mark.asyncio
    async def test_correctness_category(self) -> None:
        comments = [
            {"file_path": "f.py", "line_range": [1, 2], "severity": "WARNING", "comment": "Bug", "category": "CORRECTNESS"},
        ]
        response = _make_direct_response(line_comments=comments)
        backend = _make_mock_backend(response)
        evaluator = DirectEvaluator(backend=backend, config=JudgeConfig(), templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert verdict.line_comments[0].category == CommentCategory.CORRECTNESS

    @pytest.mark.asyncio
    async def test_style_category(self) -> None:
        comments = [
            {"file_path": "f.py", "line_range": [1, 2], "severity": "SUGGESTION", "comment": "Naming", "category": "STYLE"},
        ]
        response = _make_direct_response(line_comments=comments)
        backend = _make_mock_backend(response)
        evaluator = DirectEvaluator(backend=backend, config=JudgeConfig(), templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert verdict.line_comments[0].category == CommentCategory.STYLE

    @pytest.mark.asyncio
    async def test_security_category(self) -> None:
        comments = [
            {"file_path": "f.py", "line_range": [1, 2], "severity": "CRITICAL", "comment": "Vuln", "category": "SECURITY"},
        ]
        response = _make_direct_response(line_comments=comments)
        backend = _make_mock_backend(response)
        evaluator = DirectEvaluator(backend=backend, config=JudgeConfig(), templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert verdict.line_comments[0].category == CommentCategory.SECURITY

    @pytest.mark.asyncio
    async def test_performance_category(self) -> None:
        comments = [
            {"file_path": "f.py", "line_range": [1, 2], "severity": "WARNING", "comment": "Slow", "category": "PERFORMANCE"},
        ]
        response = _make_direct_response(line_comments=comments)
        backend = _make_mock_backend(response)
        evaluator = DirectEvaluator(backend=backend, config=JudgeConfig(), templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert verdict.line_comments[0].category == CommentCategory.PERFORMANCE

    @pytest.mark.asyncio
    async def test_line_comment_file_path_and_range(self) -> None:
        comments = [
            {"file_path": "src/auth/login.py", "line_range": [42, 58], "severity": "WARNING", "comment": "Check null", "category": "CORRECTNESS"},
        ]
        response = _make_direct_response(line_comments=comments)
        backend = _make_mock_backend(response)
        evaluator = DirectEvaluator(backend=backend, config=JudgeConfig(), templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert verdict.line_comments[0].file_path == "src/auth/login.py"
        assert verdict.line_comments[0].line_range == (42, 58)


# ---------- Custom Dimensions ----------


class TestCustomDimensions:
    @pytest.mark.asyncio
    async def test_custom_dimensions_via_config(self) -> None:
        custom_dims = {"Accuracy": 0.5, "Readability": 0.3, "Testability": 0.2}
        scores = {
            "Accuracy": {"score": 0.9, "weight": 0.5, "evidence": "", "reasoning": ""},
            "Readability": {"score": 0.8, "weight": 0.3, "evidence": "", "reasoning": ""},
            "Testability": {"score": 0.7, "weight": 0.2, "evidence": "", "reasoning": ""},
        }
        response = _make_direct_response(dimension_scores=scores, overall_score=0.84)
        backend = _make_mock_backend(response)
        config = JudgeConfig(dimensions=custom_dims)
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert "Accuracy" in verdict.scores
        assert "Readability" in verdict.scores
        assert "Testability" in verdict.scores
        assert "Correctness" not in verdict.scores

    @pytest.mark.asyncio
    async def test_dimensions_text_passed_to_prompt(self) -> None:
        custom_dims = {"MyDim": 0.5, "OtherDim": 0.5}
        response = _make_direct_response(
            dimension_scores={
                "MyDim": {"score": 0.7, "weight": 0.5, "evidence": "", "reasoning": ""},
                "OtherDim": {"score": 0.8, "weight": 0.5, "evidence": "", "reasoning": ""},
            }
        )
        backend = _make_mock_backend(response)
        config = JudgeConfig(dimensions=custom_dims)
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir=_TEMPLATES_DIR)

        await evaluator.evaluate(_make_direct_input())
        call_kwargs = backend.evaluate.call_args.kwargs
        assert "MyDim" in call_kwargs["prompt"]
        assert "OtherDim" in call_kwargs["prompt"]


# ---------- Weighted Aggregation ----------


class TestWeightedAggregation:
    @pytest.mark.asyncio
    async def test_weighted_score_computation(self) -> None:
        scores = {
            "A": {"score": 1.0, "weight": 0.6, "evidence": "", "reasoning": ""},
            "B": {"score": 0.0, "weight": 0.4, "evidence": "", "reasoning": ""},
        }
        response = json.dumps({
            "reasoning": "ok",
            "dimension_scores": scores,
            "line_comments": [],
            "confidence": 0.9,
        })
        backend = _make_mock_backend(response)
        evaluator = DirectEvaluator(backend=backend, config=JudgeConfig(), templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        expected = (1.0 * 0.6 + 0.0 * 0.4) / (0.6 + 0.4)
        assert verdict.overall_score == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_explicit_overall_score_overrides_computed(self) -> None:
        scores = {
            "A": {"score": 1.0, "weight": 0.5, "evidence": "", "reasoning": ""},
            "B": {"score": 1.0, "weight": 0.5, "evidence": "", "reasoning": ""},
        }
        response = json.dumps({
            "reasoning": "ok",
            "dimension_scores": scores,
            "line_comments": [],
            "overall_score": 0.42,
            "confidence": 0.9,
        })
        backend = _make_mock_backend(response)
        evaluator = DirectEvaluator(backend=backend, config=JudgeConfig(), templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert verdict.overall_score == pytest.approx(0.42)

    @pytest.mark.asyncio
    async def test_dimension_score_objects_have_correct_fields(self) -> None:
        scores = {
            "Correctness": {"score": 0.8, "weight": 0.3, "evidence": "ev1", "reasoning": "rs1"},
        }
        response = _make_direct_response(dimension_scores=scores)
        backend = _make_mock_backend(response)
        evaluator = DirectEvaluator(backend=backend, config=JudgeConfig(), templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        ds = verdict.scores["Correctness"]
        assert isinstance(ds, DimensionScore)
        assert ds.dimension == "Correctness"
        assert ds.score == pytest.approx(0.8)
        assert ds.weight == pytest.approx(0.3)
        assert ds.evidence == "ev1"
        assert ds.reasoning == "rs1"


# ---------- Rubric Loading ----------


class TestRubricLoading:
    def test_load_rubric_from_yaml(self, tmp_path: Path) -> None:
        rubric_file = tmp_path / "rubric.yaml"
        rubric_file.write_text(
            "dimensions:\n  Accuracy: 0.4\n  Clarity: 0.35\n  Brevity: 0.25\n"
        )
        result = load_rubric(rubric_file)
        assert result == {"Accuracy": 0.4, "Clarity": 0.35, "Brevity": 0.25}

    def test_load_rubric_flat_yaml(self, tmp_path: Path) -> None:
        rubric_file = tmp_path / "rubric.yaml"
        rubric_file.write_text("Accuracy: 0.6\nClarity: 0.4\n")
        result = load_rubric(rubric_file)
        assert result == {"Accuracy": 0.6, "Clarity": 0.4}

    def test_load_rubric_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_rubric("/nonexistent/rubric.yaml")

    def test_load_rubric_invalid_format(self, tmp_path: Path) -> None:
        rubric_file = tmp_path / "rubric.yaml"
        rubric_file.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="YAML mapping"):
            load_rubric(rubric_file)

    @pytest.mark.asyncio
    async def test_evaluator_uses_rubric_when_present(self, tmp_path: Path) -> None:
        configs_dir = tmp_path / "configs"
        judge_prompts = configs_dir / "judge_prompts"
        judge_templates = configs_dir / "judge_templates"
        judge_prompts.mkdir(parents=True)
        judge_templates.mkdir(parents=True)

        # Copy the real template
        import shutil
        real_template = Path(_TEMPLATES_DIR) / "direct_review.yaml"
        shutil.copy(real_template, judge_prompts / "direct_review.yaml")

        # Create rubric
        rubric = judge_templates / "direct_rubric.yaml"
        rubric.write_text("dimensions:\n  CustomDim: 1.0\n")

        scores = {
            "CustomDim": {"score": 0.9, "weight": 1.0, "evidence": "", "reasoning": ""},
        }
        response = _make_direct_response(dimension_scores=scores)
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = DirectEvaluator(
            backend=backend, config=config, templates_dir=str(judge_prompts)
        )

        verdict = await evaluator.evaluate(_make_direct_input())
        assert "CustomDim" in verdict.scores

    @pytest.mark.asyncio
    async def test_evaluator_falls_back_when_no_rubric(self) -> None:
        response = _make_direct_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = DirectEvaluator(backend=backend, config=config, templates_dir=_TEMPLATES_DIR)

        verdict = await evaluator.evaluate(_make_direct_input())
        assert "Correctness" in verdict.scores


# ---------- UnifiedJudge Integration ----------


class TestUnifiedJudgeIntegration:
    @pytest.mark.asyncio
    async def test_unified_judge_dispatches_to_direct(self) -> None:
        response = _make_direct_response()
        backend = _make_mock_backend(response)
        judge = UnifiedJudge(backend=backend)

        verdict = await judge.evaluate(_make_direct_input())
        assert isinstance(verdict, JudgeVerdict)
        assert verdict.mode == EvaluationMode.DIRECT

    @pytest.mark.asyncio
    async def test_unified_judge_passes_config(self) -> None:
        custom_dims = {"Only": 1.0}
        scores = {
            "Only": {"score": 0.5, "weight": 1.0, "evidence": "", "reasoning": ""},
        }
        response = _make_direct_response(dimension_scores=scores)
        backend = _make_mock_backend(response)
        config = JudgeConfig(dimensions=custom_dims)
        judge = UnifiedJudge(backend=backend, config=config)

        verdict = await judge.evaluate(_make_direct_input())
        assert "Only" in verdict.scores

    @pytest.mark.asyncio
    async def test_unified_judge_rejects_wrong_input_type(self) -> None:
        backend = _make_mock_backend()
        judge = UnifiedJudge(backend=backend)

        from src.judge.models import PairwiseInput
        wrong_input = PairwiseInput(
            task_id="t1",
            task_description="desc",
            evaluation_mode=EvaluationMode.DIRECT,
        )
        with pytest.raises(ValueError, match="DirectInput"):
            await judge.evaluate(wrong_input)


# ---------- Exports ----------


class TestExports:
    def test_direct_evaluator_in_modes_init(self) -> None:
        from src.judge.modes import DirectEvaluator as DE
        assert DE is DirectEvaluator

    def test_direct_evaluator_in_judge_init(self) -> None:
        from src.judge import DirectEvaluator as DE
        assert DE is DirectEvaluator

    def test_load_rubric_importable(self) -> None:
        from src.judge.modes.direct import load_rubric as lr
        assert lr is load_rubric
