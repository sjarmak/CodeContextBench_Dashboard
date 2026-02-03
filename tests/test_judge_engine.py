"""Tests for the UnifiedJudge engine core."""

from __future__ import annotations

import json
import sys
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

from src.judge.engine import (
    JudgeConfig,
    JudgeError,
    UnifiedJudge,
    _build_dimension_scores,
    _compute_weighted_score,
    _extract_json_object,
    _parse_line_comments,
    _strip_markdown_code_blocks,
    _truncate,
    parse_json_response,
)
from src.judge.models import (
    CommentCategory,
    DimensionScore,
    DirectInput,
    EvaluationMode,
    JudgeInput,
    JudgeVerdict,
    PairwiseInput,
    PairwiseVerdict,
    ReferenceInput,
    Severity,
)


# ---------- Helpers ----------


def _make_mock_backend(response: str = '{"reasoning": "ok"}', model_id: str = "test-model") -> MagicMock:
    """Create a mock JudgeBackend."""
    backend = MagicMock()
    backend.model_id = model_id
    backend.evaluate = AsyncMock(return_value=response)
    return backend


# ---------- JudgeConfig tests ----------


class TestJudgeConfig:
    def test_defaults(self):
        cfg = JudgeConfig()
        assert cfg.temperature == 0.0
        assert cfg.max_tokens == 2000
        assert "Correctness" in cfg.dimensions
        assert cfg.scoring_scale == "0.0-1.0"
        assert cfg.pairwise_method == "simultaneous"

    def test_custom_values(self):
        cfg = JudgeConfig(temperature=0.5, max_tokens=4000, scoring_scale="0-4")
        assert cfg.temperature == 0.5
        assert cfg.max_tokens == 4000

    def test_frozen(self):
        cfg = JudgeConfig()
        with pytest.raises(AttributeError):
            cfg.temperature = 1.0  # type: ignore[misc]


# ---------- Truncation tests ----------


class TestTruncate:
    def test_no_truncation_needed(self):
        assert _truncate("short text", 100) == "short text"

    def test_truncation_at_word_boundary(self):
        text = "hello world this is a test"
        result = _truncate(text, 15)
        assert result.endswith("... [truncated]")
        assert len(result) < len(text) + 20

    def test_truncation_exact_limit(self):
        text = "exact"
        assert _truncate(text, 5) == "exact"

    def test_empty_string(self):
        assert _truncate("", 100) == ""


# ---------- Markdown stripping tests ----------


class TestStripMarkdownCodeBlocks:
    def test_json_code_block(self):
        text = '```json\n{"key": "value"}\n```'
        assert _strip_markdown_code_blocks(text) == '{"key": "value"}'

    def test_plain_code_block(self):
        text = '```\n{"key": "value"}\n```'
        assert _strip_markdown_code_blocks(text) == '{"key": "value"}'

    def test_no_code_block(self):
        text = '{"key": "value"}'
        assert _strip_markdown_code_blocks(text) == '{"key": "value"}'

    def test_whitespace_around(self):
        text = '  ```json\n{"key": "value"}\n```  '
        assert _strip_markdown_code_blocks(text) == '{"key": "value"}'


# ---------- JSON extraction tests ----------


class TestExtractJsonObject:
    def test_simple_object(self):
        text = 'some text {"a": 1} more text'
        assert _extract_json_object(text) == '{"a": 1}'

    def test_nested_object(self):
        text = '{"outer": {"inner": 1}}'
        assert _extract_json_object(text) == '{"outer": {"inner": 1}}'

    def test_string_with_braces(self):
        text = '{"key": "value with {braces}"}'
        assert _extract_json_object(text) == '{"key": "value with {braces}"}'

    def test_no_json(self):
        with pytest.raises(JudgeError, match="No JSON object"):
            _extract_json_object("no json here")

    def test_unterminated(self):
        with pytest.raises(JudgeError, match="Unterminated"):
            _extract_json_object('{"key": "value"')


# ---------- parse_json_response tests ----------


class TestParseJsonResponse:
    def test_clean_json(self):
        result = parse_json_response('{"score": 0.8}')
        assert result == {"score": 0.8}

    def test_json_in_code_block(self):
        text = '```json\n{"score": 0.8}\n```'
        result = parse_json_response(text)
        assert result == {"score": 0.8}

    def test_json_with_preamble(self):
        text = 'Here is the result:\n{"score": 0.8}'
        result = parse_json_response(text)
        assert result == {"score": 0.8}

    def test_empty_response(self):
        with pytest.raises(JudgeError, match="Empty response"):
            parse_json_response("")

    def test_whitespace_only(self):
        with pytest.raises(JudgeError, match="Empty response"):
            parse_json_response("   ")

    def test_no_json_at_all(self):
        with pytest.raises(JudgeError, match="Failed to parse JSON"):
            parse_json_response("This is just text with no JSON.")

    def test_complex_nested_json(self):
        data = {
            "reasoning": "test",
            "dimension_scores": {"Correctness": {"score": 0.9, "evidence": "good"}},
            "overall_score": 0.9,
        }
        result = parse_json_response(json.dumps(data))
        assert result["overall_score"] == 0.9


# ---------- _build_dimension_scores tests ----------


class TestBuildDimensionScores:
    def test_dict_data(self):
        raw = {
            "Correctness": {"score": 0.8, "weight": 0.3, "evidence": "good", "reasoning": "solid"},
        }
        result = _build_dimension_scores(raw, {"Correctness": 0.3})
        assert "Correctness" in result
        assert result["Correctness"].score == 0.8
        assert result["Correctness"].weight == 0.3

    def test_scalar_data(self):
        raw = {"Correctness": 0.7}
        result = _build_dimension_scores(raw, {"Correctness": 0.3})
        assert result["Correctness"].score == 0.7
        assert result["Correctness"].weight == 0.3

    def test_missing_weight_uses_default(self):
        raw = {"Correctness": {"score": 0.8, "evidence": "ok", "reasoning": "ok"}}
        result = _build_dimension_scores(raw, {"Correctness": 0.5})
        assert result["Correctness"].weight == 0.5

    def test_none_scalar(self):
        raw = {"Correctness": None}
        result = _build_dimension_scores(raw, {"Correctness": 0.3})
        assert result["Correctness"].score == 0.0


# ---------- _compute_weighted_score tests ----------


class TestComputeWeightedScore:
    def test_basic_computation(self):
        scores = {
            "A": DimensionScore(dimension="A", score=1.0, weight=0.5, evidence="", reasoning=""),
            "B": DimensionScore(dimension="B", score=0.0, weight=0.5, evidence="", reasoning=""),
        }
        assert _compute_weighted_score(scores) == pytest.approx(0.5)

    def test_empty_scores(self):
        assert _compute_weighted_score({}) == 0.0

    def test_zero_weight(self):
        scores = {
            "A": DimensionScore(dimension="A", score=1.0, weight=0.0, evidence="", reasoning=""),
        }
        assert _compute_weighted_score(scores) == 0.0


# ---------- _parse_line_comments tests ----------


class TestParseLineComments:
    def test_valid_comment(self):
        raw = [
            {
                "file_path": "src/foo.py",
                "line_range": [10, 15],
                "severity": "WARNING",
                "comment": "Fix this",
                "category": "CORRECTNESS",
            }
        ]
        result = _parse_line_comments(raw)
        assert len(result) == 1
        assert result[0].file_path == "src/foo.py"
        assert result[0].line_range == (10, 15)
        assert result[0].severity == Severity.WARNING
        assert result[0].category == CommentCategory.CORRECTNESS

    def test_unknown_severity_fallback(self):
        raw = [{"file_path": "x.py", "line_range": [1, 1], "severity": "UNKNOWN", "comment": "test", "category": "STYLE"}]
        result = _parse_line_comments(raw)
        assert result[0].severity == Severity.SUGGESTION

    def test_non_dict_skipped(self):
        raw = ["not a dict", {"file_path": "x.py", "line_range": [1, 1], "severity": "CRITICAL", "comment": "ok", "category": "SECURITY"}]
        result = _parse_line_comments(raw)
        assert len(result) == 1

    def test_empty_list(self):
        assert _parse_line_comments([]) == []


# ---------- UnifiedJudge dispatch tests ----------


class TestUnifiedJudgeDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_direct(self):
        response = json.dumps({
            "reasoning": "Good code",
            "dimension_scores": {
                "Correctness": {"score": 0.9, "weight": 0.3, "evidence": "Correct", "reasoning": "Works"},
            },
            "overall_score": 0.9,
            "confidence": 0.85,
            "line_comments": [],
        })
        backend = _make_mock_backend(response)
        judge = UnifiedJudge(backend)
        inp = DirectInput(
            task_id="t1",
            task_description="Test task",
            evaluation_mode=EvaluationMode.DIRECT,
            agent_output="print('hello')",
        )
        verdict = await judge.evaluate(inp)
        assert isinstance(verdict, JudgeVerdict)
        assert verdict.mode == EvaluationMode.DIRECT
        assert verdict.overall_score == 0.9
        assert verdict.model_id == "test-model"
        backend.evaluate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dispatch_reference(self):
        response = json.dumps({
            "reasoning": "Matches reference",
            "dimension_scores": {
                "Oracle Correctness": {"score": 1.0, "evidence": "Match", "reasoning": "Correct"},
            },
            "overall_score": 1.0,
            "confidence": 0.95,
            "context_file_coverage": 0.8,
        })
        backend = _make_mock_backend(response)
        judge = UnifiedJudge(backend)
        inp = ReferenceInput(
            task_id="t2",
            task_description="Reference task",
            evaluation_mode=EvaluationMode.REFERENCE_BASED,
            agent_output="The answer is 42",
            reference_answer="42",
        )
        verdict = await judge.evaluate(inp)
        assert isinstance(verdict, JudgeVerdict)
        assert verdict.mode == EvaluationMode.REFERENCE_BASED
        assert verdict.overall_score == 1.0
        # Context file coverage is now computed by ReferenceEvaluator from actual
        # file matching. With no context_files in input, coverage defaults to 1.0.
        # The LLM-reported value is preserved in correctness_response metadata.
        assert verdict.metadata.get("context_file_coverage") == 1.0
        assert verdict.metadata["correctness_response"]["context_file_coverage"] == 0.8

    @pytest.mark.asyncio
    async def test_dispatch_pairwise(self):
        response = json.dumps({
            "reasoning": "A is better",
            "rankings": ["BASELINE", "MCP"],
            "per_output_scores": {
                "BASELINE": {"Correctness": {"score": 0.9, "evidence": "Good", "reasoning": "Right"}},
                "MCP": {"Correctness": {"score": 0.6, "evidence": "Ok", "reasoning": "Partial"}},
            },
            "ties": [],
            "confidence": 0.9,
        })
        backend = _make_mock_backend(response)
        judge = UnifiedJudge(backend)
        inp = PairwiseInput(
            task_id="t3",
            task_description="Compare outputs",
            evaluation_mode=EvaluationMode.PAIRWISE,
            outputs={"BASELINE": "output A", "MCP": "output B"},
        )
        verdict = await judge.evaluate(inp)
        assert isinstance(verdict, PairwiseVerdict)
        assert verdict.mode == EvaluationMode.PAIRWISE
        assert verdict.rankings == ["BASELINE", "MCP"]
        assert "BASELINE" in verdict.win_rates
        assert "MCP" in verdict.win_rates

    @pytest.mark.asyncio
    async def test_wrong_input_type_for_pairwise(self):
        backend = _make_mock_backend()
        judge = UnifiedJudge(backend)
        inp = DirectInput(
            task_id="t1",
            task_description="Test",
            evaluation_mode=EvaluationMode.PAIRWISE,
            agent_output="test",
        )
        with pytest.raises(ValueError, match="PairwiseInput"):
            await judge.evaluate(inp)

    @pytest.mark.asyncio
    async def test_wrong_input_type_for_direct(self):
        backend = _make_mock_backend()
        judge = UnifiedJudge(backend)
        inp = PairwiseInput(
            task_id="t1",
            task_description="Test",
            evaluation_mode=EvaluationMode.DIRECT,
            outputs={"A": "a"},
        )
        with pytest.raises(ValueError, match="DirectInput"):
            await judge.evaluate(inp)

    @pytest.mark.asyncio
    async def test_wrong_input_type_for_reference(self):
        backend = _make_mock_backend()
        judge = UnifiedJudge(backend)
        inp = DirectInput(
            task_id="t1",
            task_description="Test",
            evaluation_mode=EvaluationMode.REFERENCE_BASED,
            agent_output="test",
        )
        with pytest.raises(ValueError, match="ReferenceInput"):
            await judge.evaluate(inp)


# ---------- UnifiedJudge parsing edge cases ----------


class TestUnifiedJudgeParsing:
    @pytest.mark.asyncio
    async def test_response_with_markdown_code_block(self):
        inner = json.dumps({
            "reasoning": "analysis",
            "dimension_scores": {"Correctness": {"score": 0.7, "weight": 0.3, "evidence": "ok", "reasoning": "ok"}},
            "overall_score": 0.7,
            "confidence": 0.8,
            "line_comments": [],
        })
        response = f"```json\n{inner}\n```"
        backend = _make_mock_backend(response)
        judge = UnifiedJudge(backend)
        inp = DirectInput(
            task_id="t1",
            task_description="Test",
            evaluation_mode=EvaluationMode.DIRECT,
            agent_output="code here",
        )
        verdict = await judge.evaluate(inp)
        assert verdict.overall_score == 0.7

    @pytest.mark.asyncio
    async def test_parse_failure_raises_judge_error(self):
        backend = _make_mock_backend("This is not JSON at all")
        judge = UnifiedJudge(backend)
        inp = DirectInput(
            task_id="t1",
            task_description="Test",
            evaluation_mode=EvaluationMode.DIRECT,
            agent_output="code",
        )
        with pytest.raises(JudgeError):
            await judge.evaluate(inp)


# ---------- UnifiedJudge truncation tests ----------


class TestUnifiedJudgeTruncation:
    @pytest.mark.asyncio
    async def test_long_input_truncated(self):
        response = json.dumps({
            "reasoning": "ok",
            "dimension_scores": {},
            "overall_score": 0.5,
            "confidence": 0.5,
            "line_comments": [],
        })
        backend = _make_mock_backend(response)
        config = JudgeConfig(truncation_limits={"task_description": 50, "agent_output": 100, "code_changes": 100})
        judge = UnifiedJudge(backend, config)
        inp = DirectInput(
            task_id="t1",
            task_description="A" * 200,
            evaluation_mode=EvaluationMode.DIRECT,
            agent_output="B" * 500,
        )
        verdict = await judge.evaluate(inp)
        assert verdict.overall_score == 0.5
        # Verify backend was called (implicitly tests truncation happened without error)
        backend.evaluate.assert_awaited_once()
        call_args = backend.evaluate.call_args
        assert "... [truncated]" in call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")


# ---------- UnifiedJudge line comments parsing ----------


class TestUnifiedJudgeLineComments:
    @pytest.mark.asyncio
    async def test_direct_with_line_comments(self):
        response = json.dumps({
            "reasoning": "review",
            "dimension_scores": {
                "Correctness": {"score": 0.6, "weight": 0.3, "evidence": "bug", "reasoning": "off by one"},
            },
            "overall_score": 0.6,
            "confidence": 0.7,
            "line_comments": [
                {
                    "file_path": "src/main.py",
                    "line_range": [10, 12],
                    "severity": "CRITICAL",
                    "comment": "Off by one error",
                    "category": "CORRECTNESS",
                },
                {
                    "file_path": "src/utils.py",
                    "line_range": [5, 5],
                    "severity": "PRAISE",
                    "comment": "Good naming",
                    "category": "STYLE",
                },
            ],
        })
        backend = _make_mock_backend(response)
        judge = UnifiedJudge(backend)
        inp = DirectInput(
            task_id="t1",
            task_description="Review code",
            evaluation_mode=EvaluationMode.DIRECT,
            agent_output="some code",
        )
        verdict = await judge.evaluate(inp)
        assert len(verdict.line_comments) == 2
        assert verdict.line_comments[0].severity == Severity.CRITICAL
        assert verdict.line_comments[1].severity == Severity.PRAISE


# ---------- Export tests ----------


class TestEngineExports:
    def test_judge_error_importable(self):
        from src.judge.engine import JudgeError
        assert issubclass(JudgeError, Exception)

    def test_judge_config_importable(self):
        from src.judge.engine import JudgeConfig
        assert JudgeConfig is not None

    def test_unified_judge_importable(self):
        from src.judge.engine import UnifiedJudge
        assert UnifiedJudge is not None

    def test_parse_json_response_importable(self):
        from src.judge.engine import parse_json_response
        assert callable(parse_json_response)
