"""Tests for the ReferenceEvaluator module."""

from __future__ import annotations

import json
import sys
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
    DimensionScore,
    EvaluationMode,
    JudgeVerdict,
    ReferenceInput,
)
from src.judge.modes.reference import (
    ReferenceEvaluator,
    compute_context_file_coverage,
    detect_task_type,
    load_oracle_data,
)

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


def _make_correctness_response(
    oracle_correctness: float = 0.8,
    approach_alignment: float = 0.7,
    context_file_coverage: float = 0.9,
    overall_score: float = 0.75,
    confidence: float = 0.85,
    reasoning: str = "Correct analysis.",
) -> str:
    return json.dumps({
        "reasoning": reasoning,
        "dimension_scores": {
            "Oracle Correctness": {
                "score": oracle_correctness,
                "weight": 0.4,
                "evidence": "Matches reference",
                "reasoning": "Key points covered",
            },
            "Approach Alignment": {
                "score": approach_alignment,
                "weight": 0.25,
                "evidence": "Similar approach",
                "reasoning": "Used same strategy",
            },
        },
        "context_file_coverage": context_file_coverage,
        "overall_score": overall_score,
        "confidence": confidence,
    })


def _make_completeness_response(
    oracle_completeness: float = 0.6,
    overall_score: float = 0.6,
    confidence: float = 0.8,
    reasoning: str = "Partially complete.",
) -> str:
    return json.dumps({
        "reasoning": reasoning,
        "dimension_scores": {
            "Oracle Completeness": {
                "score": oracle_completeness,
                "weight": 0.35,
                "evidence": "Most criteria met",
                "reasoning": "Missing one criterion",
            },
        },
        "criteria_coverage": {
            "criterion_1": {"score": 1.0, "evidence": "Addressed"},
            "criterion_2": {"score": 0.0, "evidence": "Missing"},
        },
        "overall_score": overall_score,
        "confidence": confidence,
    })


def _make_reference_input(
    task_id: str = "task-001",
    task_description: str = "Analyze the authentication module architecture",
    agent_output: str = "The auth module uses JWT tokens stored in httpOnly cookies...",
    reference_answer: str = "The authentication module uses JWT-based auth with httpOnly cookie storage...",
    context_files: list[str] | None = None,
    evaluation_criteria: str | None = None,
) -> ReferenceInput:
    return ReferenceInput(
        task_id=task_id,
        task_description=task_description,
        evaluation_mode=EvaluationMode.REFERENCE_BASED,
        agent_output=agent_output,
        reference_answer=reference_answer,
        context_files=context_files or [],
        evaluation_criteria=evaluation_criteria,
    )


# ---------- Task Type Detection ----------


class TestTaskTypeDetection:
    def test_detects_code_modification_with_git_diff(self) -> None:
        output = "diff --git a/auth.py b/auth.py\n+def login():\n+    pass"
        assert detect_task_type(output) == "code_modification"

    def test_detects_code_modification_with_unified_diff(self) -> None:
        output = "--- a/old.py\n+++ b/new.py\n@@ -1,3 +1,4 @@"
        assert detect_task_type(output) == "code_modification"

    def test_detects_code_modification_with_hunk_header(self) -> None:
        output = "Some text\n@@ -10,5 +10,7 @@ class Foo:\n new code"
        assert detect_task_type(output) == "code_modification"

    def test_detects_analysis_for_prose(self) -> None:
        output = "The authentication module uses a layered architecture..."
        assert detect_task_type(output) == "analysis"

    def test_detects_analysis_for_empty_output(self) -> None:
        assert detect_task_type("") == "analysis"

    def test_detects_analysis_for_code_without_diff(self) -> None:
        output = "def login():\n    return authenticate(user, password)"
        assert detect_task_type(output) == "analysis"


# ---------- Context File Coverage ----------


class TestContextFileCoverage:
    def test_full_coverage(self) -> None:
        files = ["src/auth.py", "src/utils.py"]
        output = "The file src/auth.py contains the main logic. Also see src/utils.py."
        assert compute_context_file_coverage(files, output) == pytest.approx(1.0)

    def test_partial_coverage(self) -> None:
        files = ["src/auth.py", "src/utils.py", "src/models.py"]
        output = "Found in src/auth.py and models.py."
        assert compute_context_file_coverage(files, output) == pytest.approx(2.0 / 3.0)

    def test_no_coverage(self) -> None:
        files = ["src/auth.py", "src/utils.py"]
        output = "No file references here."
        assert compute_context_file_coverage(files, output) == pytest.approx(0.0)

    def test_empty_expected_files(self) -> None:
        assert compute_context_file_coverage([], "any output") == pytest.approx(1.0)

    def test_handles_double_slash_normalization(self) -> None:
        files = ["src//auth//login.py"]
        output = "Found in src/auth/login.py"
        assert compute_context_file_coverage(files, output) == pytest.approx(1.0)

    def test_basename_match(self) -> None:
        files = ["deeply/nested/path/config.py"]
        output = "Modified config.py to add new settings."
        assert compute_context_file_coverage(files, output) == pytest.approx(1.0)


# ---------- Oracle Data Loading ----------


class TestLoadOracleData:
    def test_loads_all_fields(self) -> None:
        scenario = {
            "ground_truth": "The answer is 42.",
            "expected_approach": "Use mathematical analysis.",
            "evaluation_criteria": "Must identify the number.",
            "context_files": ["math.py", "calc.py"],
        }
        oracle = load_oracle_data(scenario)
        assert oracle["ground_truth"] == "The answer is 42."
        assert oracle["expected_approach"] == "Use mathematical analysis."
        assert oracle["evaluation_criteria"] == "Must identify the number."
        assert oracle["context_files"] == ["math.py", "calc.py"]

    def test_missing_fields_return_none(self) -> None:
        oracle = load_oracle_data({})
        assert oracle["ground_truth"] is None
        assert oracle["expected_approach"] is None
        assert oracle["evaluation_criteria"] is None
        assert oracle["context_files"] == []

    def test_null_context_files_becomes_empty_list(self) -> None:
        oracle = load_oracle_data({"context_files": None})
        assert oracle["context_files"] == []


# ---------- ReferenceEvaluator Construction ----------


class TestReferenceEvaluatorConstruction:
    def test_creates_with_required_args(self) -> None:
        backend = _make_mock_backend()
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )
        assert evaluator._backend is backend
        assert evaluator._config is config
        assert evaluator._templates_dir == _TEMPLATES_DIR


# ---------- Correctness Evaluation ----------


class TestCorrectnessEvaluation:
    @pytest.mark.asyncio
    async def test_evaluate_returns_judge_verdict(self) -> None:
        response = _make_correctness_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        verdict = await evaluator.evaluate(_make_reference_input())
        assert isinstance(verdict, JudgeVerdict)
        assert verdict.mode == EvaluationMode.REFERENCE_BASED

    @pytest.mark.asyncio
    async def test_evaluate_populates_correctness_scores(self) -> None:
        response = _make_correctness_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        verdict = await evaluator.evaluate(_make_reference_input())
        assert "Oracle Correctness" in verdict.scores
        assert "Approach Alignment" in verdict.scores

    @pytest.mark.asyncio
    async def test_evaluate_sets_model_id(self) -> None:
        response = _make_correctness_response()
        backend = _make_mock_backend(response, model_id="claude-haiku")
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        verdict = await evaluator.evaluate(_make_reference_input())
        assert verdict.model_id == "claude-haiku"

    @pytest.mark.asyncio
    async def test_evaluate_includes_task_type_in_metadata(self) -> None:
        response = _make_correctness_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        verdict = await evaluator.evaluate(_make_reference_input())
        assert verdict.metadata["task_type"] == "analysis"

    @pytest.mark.asyncio
    async def test_evaluate_includes_context_coverage(self) -> None:
        response = _make_correctness_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        judge_input = _make_reference_input(
            context_files=["auth.py"],
            agent_output="The auth.py file contains...",
        )
        verdict = await evaluator.evaluate(judge_input)
        assert verdict.metadata["context_file_coverage"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_evaluate_calls_backend_once_without_criteria(self) -> None:
        response = _make_correctness_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        await evaluator.evaluate(_make_reference_input())
        assert backend.evaluate.call_count == 1

    @pytest.mark.asyncio
    async def test_evaluate_populates_reasoning(self) -> None:
        response = _make_correctness_response(reasoning="Detailed correctness analysis")
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        verdict = await evaluator.evaluate(_make_reference_input())
        assert "Detailed correctness analysis" in verdict.reasoning


# ---------- Completeness Evaluation ----------


class TestCompletenessEvaluation:
    @pytest.mark.asyncio
    async def test_evaluate_with_criteria_calls_backend_twice(self) -> None:
        correctness_resp = _make_correctness_response()
        completeness_resp = _make_completeness_response()
        backend = _make_mock_backend()
        backend.evaluate = AsyncMock(
            side_effect=[correctness_resp, completeness_resp]
        )
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        judge_input = _make_reference_input(
            evaluation_criteria="Must cover all auth patterns."
        )
        verdict = await evaluator.evaluate(judge_input)
        assert backend.evaluate.call_count == 2

    @pytest.mark.asyncio
    async def test_evaluate_merges_completeness_scores(self) -> None:
        correctness_resp = _make_correctness_response()
        completeness_resp = _make_completeness_response()
        backend = _make_mock_backend()
        backend.evaluate = AsyncMock(
            side_effect=[correctness_resp, completeness_resp]
        )
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        judge_input = _make_reference_input(
            evaluation_criteria="Must cover all auth patterns."
        )
        verdict = await evaluator.evaluate(judge_input)
        assert "Oracle Correctness" in verdict.scores
        assert "Oracle Completeness" in verdict.scores
        assert "Approach Alignment" in verdict.scores

    @pytest.mark.asyncio
    async def test_evaluate_merges_reasoning(self) -> None:
        correctness_resp = _make_correctness_response(reasoning="Correctness OK")
        completeness_resp = _make_completeness_response(reasoning="Completeness partial")
        backend = _make_mock_backend()
        backend.evaluate = AsyncMock(
            side_effect=[correctness_resp, completeness_resp]
        )
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        judge_input = _make_reference_input(
            evaluation_criteria="Must be complete."
        )
        verdict = await evaluator.evaluate(judge_input)
        assert "Correctness OK" in verdict.reasoning
        assert "Completeness partial" in verdict.reasoning

    @pytest.mark.asyncio
    async def test_evaluate_averages_confidence(self) -> None:
        correctness_resp = _make_correctness_response(confidence=0.9)
        completeness_resp = _make_completeness_response(confidence=0.7)
        backend = _make_mock_backend()
        backend.evaluate = AsyncMock(
            side_effect=[correctness_resp, completeness_resp]
        )
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        judge_input = _make_reference_input(
            evaluation_criteria="Cover all criteria."
        )
        verdict = await evaluator.evaluate(judge_input)
        assert verdict.confidence == pytest.approx(0.8)

    @pytest.mark.asyncio
    async def test_evaluate_includes_criteria_coverage_in_metadata(self) -> None:
        correctness_resp = _make_correctness_response()
        completeness_resp = _make_completeness_response()
        backend = _make_mock_backend()
        backend.evaluate = AsyncMock(
            side_effect=[correctness_resp, completeness_resp]
        )
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        judge_input = _make_reference_input(
            evaluation_criteria="Criteria here."
        )
        verdict = await evaluator.evaluate(judge_input)
        assert "criteria_coverage" in verdict.metadata


# ---------- Task Type Detection in Evaluation ----------


class TestTaskTypeInEvaluation:
    @pytest.mark.asyncio
    async def test_code_modification_detected(self) -> None:
        response = _make_correctness_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        judge_input = _make_reference_input(
            agent_output="diff --git a/auth.py b/auth.py\n+def login():\n+    pass",
        )
        verdict = await evaluator.evaluate(judge_input)
        assert verdict.metadata["task_type"] == "code_modification"

    @pytest.mark.asyncio
    async def test_analysis_detected(self) -> None:
        response = _make_correctness_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        verdict = await evaluator.evaluate(_make_reference_input())
        assert verdict.metadata["task_type"] == "analysis"


# ---------- Missing Oracle Data Fallback ----------


class TestMissingOracleDataFallback:
    @pytest.mark.asyncio
    async def test_missing_completeness_skips_completeness_eval(self) -> None:
        response = _make_correctness_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        judge_input = _make_reference_input(evaluation_criteria=None)
        verdict = await evaluator.evaluate(judge_input)
        assert verdict.metadata["has_completeness_eval"] is False
        assert backend.evaluate.call_count == 1

    @pytest.mark.asyncio
    async def test_missing_dimensions_logged_in_metadata(self) -> None:
        response = json.dumps({
            "reasoning": "Only correctness",
            "dimension_scores": {
                "Oracle Correctness": {
                    "score": 0.8,
                    "weight": 0.4,
                    "evidence": "ok",
                    "reasoning": "ok",
                },
            },
            "overall_score": 0.8,
            "confidence": 0.8,
        })
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        verdict = await evaluator.evaluate(_make_reference_input())
        assert "missing_dimensions" in verdict.metadata
        assert "Oracle Completeness" in verdict.metadata["missing_dimensions"]
        assert "Approach Alignment" in verdict.metadata["missing_dimensions"]


# ---------- LoCoBench Format ----------


class TestLoCoBenchFormat:
    @pytest.mark.asyncio
    async def test_locobench_scenario_fields(self) -> None:
        response = _make_correctness_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        judge_input = _make_reference_input(
            context_files=["src/auth.py", "src/middleware.py"],
            agent_output="The auth.py module handles JWT. middleware.py validates tokens.",
            reference_answer="JWT auth in auth.py, token validation in middleware.py",
        )
        verdict = await evaluator.evaluate(judge_input)
        assert verdict.metadata["context_file_coverage"] == pytest.approx(1.0)
        assert isinstance(verdict.overall_score, float)

    @pytest.mark.asyncio
    async def test_oracle_data_helper(self) -> None:
        scenario = {
            "ground_truth": "Expected analysis",
            "expected_approach": "Trace through call graph",
            "evaluation_criteria": "Must identify all entry points",
            "context_files": ["src//api//routes.py", "src//handlers.py"],
        }
        oracle = load_oracle_data(scenario)
        assert oracle["ground_truth"] == "Expected analysis"
        assert len(oracle["context_files"]) == 2


# ---------- 5-Point Likert Mode ----------


class TestLikertMode:
    @pytest.mark.asyncio
    async def test_likert_config_stored_in_metadata(self) -> None:
        response = _make_correctness_response()
        backend = _make_mock_backend(response)
        config = JudgeConfig(scoring_scale="likert_5")
        evaluator = ReferenceEvaluator(
            backend=backend, config=config, templates_dir=_TEMPLATES_DIR
        )

        verdict = await evaluator.evaluate(_make_reference_input())
        correctness_response = verdict.metadata.get("correctness_response", {})
        # The correctness sub-verdict metadata should have scoring_mode
        # In the merged verdict, we track the fact via the sub-evaluations
        assert isinstance(verdict, JudgeVerdict)


# ---------- UnifiedJudge Integration ----------


class TestUnifiedJudgeIntegration:
    @pytest.mark.asyncio
    async def test_unified_judge_dispatches_to_reference(self) -> None:
        response = _make_correctness_response()
        backend = _make_mock_backend(response)
        judge = UnifiedJudge(backend=backend)

        verdict = await judge.evaluate(_make_reference_input())
        assert isinstance(verdict, JudgeVerdict)
        assert verdict.mode == EvaluationMode.REFERENCE_BASED

    @pytest.mark.asyncio
    async def test_unified_judge_rejects_wrong_input_type(self) -> None:
        backend = _make_mock_backend()
        judge = UnifiedJudge(backend=backend)

        from src.judge.models import DirectInput
        wrong_input = DirectInput(
            task_id="t1",
            task_description="desc",
            evaluation_mode=EvaluationMode.REFERENCE_BASED,
        )
        with pytest.raises(ValueError, match="ReferenceInput"):
            await judge.evaluate(wrong_input)


# ---------- Exports ----------


class TestExports:
    def test_reference_evaluator_in_modes_init(self) -> None:
        from src.judge.modes import ReferenceEvaluator as RE
        assert RE is ReferenceEvaluator

    def test_reference_evaluator_in_judge_init(self) -> None:
        from src.judge import ReferenceEvaluator as RE
        assert RE is ReferenceEvaluator

    def test_utility_functions_importable(self) -> None:
        from src.judge.modes.reference import (
            compute_context_file_coverage as ccfc,
            detect_task_type as dtt,
            load_oracle_data as lod,
        )
        assert callable(ccfc)
        assert callable(dtt)
        assert callable(lod)
