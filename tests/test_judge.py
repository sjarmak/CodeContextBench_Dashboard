"""Unit tests for scripts/ccb_pipeline/judge.py."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.ccb_pipeline.judge import (
    DimensionScore,
    JudgeVote,
    TrialJudgeResult,
    _augment_metrics,
    _build_prompt,
    _extract_assistant_content,
    _find_trial_dir,
    _flatten_trials,
    _load_solution_text,
    _load_task_description,
    _normalize_score,
    _parse_json_response,
    _select_dimensions,
    _evaluate_dimension,
    evaluate_trial,
    main,
    run_judge,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_categories(trials: list[dict]) -> list[dict]:
    """Build a minimal categories list wrapping trials."""
    return [
        {
            "run_category": "official",
            "experiments": [
                {
                    "experiment_id": "exp-001",
                    "trials": trials,
                }
            ],
        }
    ]


def _make_trial(
    trial_id: str = "trial-001",
    task_name: str = "test-task",
    benchmark: str = "locobench",
    reward: float = 1.0,
    agent_config: str = "BASELINE",
) -> dict:
    return {
        "trial_id": trial_id,
        "task_name": task_name,
        "benchmark": benchmark,
        "agent_config": agent_config,
        "reward": reward,
        "pass_fail": "pass" if reward >= 0.5 else "fail",
        "duration_seconds": 120.0,
        "input_tokens": 5000,
        "output_tokens": 1000,
        "cached_tokens": 200,
        "tool_utilization": {},
    }


def _make_trial_dir(tmp_path: Path, trial_id: str = "trial-001") -> Path:
    """Create a trial directory with result.json and solution files."""
    trial_dir = tmp_path / "official" / "exp-001" / "config" / trial_id
    trial_dir.mkdir(parents=True)
    (trial_dir / "result.json").write_text(json.dumps({"task_name": "test-task"}))

    agent_dir = trial_dir / "agent"
    agent_dir.mkdir()
    (agent_dir / "solution.md").write_text("# Solution\nThis is the agent solution.")

    config_data = {"task": {"description": "Fix the bug in module X"}}
    (trial_dir / "config.json").write_text(json.dumps(config_data))

    return trial_dir


# ---------------------------------------------------------------------------
# _normalize_score
# ---------------------------------------------------------------------------


class TestNormalizeScore:
    def test_pass_variants(self) -> None:
        assert _normalize_score("pass") == (1.0, "pass")
        assert _normalize_score("PASS") == (1.0, "pass")
        assert _normalize_score("full") == (1.0, "pass")
        assert _normalize_score("effective") == (1.0, "pass")
        assert _normalize_score("1") == (1.0, "pass")
        assert _normalize_score("1.0") == (1.0, "pass")

    def test_partial_variants(self) -> None:
        assert _normalize_score("partial") == (0.5, "partial")
        assert _normalize_score("PARTIAL") == (0.5, "partial")
        assert _normalize_score("partially") == (0.5, "partial")
        assert _normalize_score("partially_effective") == (0.5, "partial")
        assert _normalize_score("0.5") == (0.5, "partial")

    def test_fail_variants(self) -> None:
        assert _normalize_score("fail") == (0.0, "fail")
        assert _normalize_score("FAIL") == (0.0, "fail")
        assert _normalize_score("ineffective") == (0.0, "fail")
        assert _normalize_score("0") == (0.0, "fail")
        assert _normalize_score("0.0") == (0.0, "fail")

    def test_unknown_defaults_to_fail(self) -> None:
        assert _normalize_score("garbage") == (0.0, "fail")
        assert _normalize_score("") == (0.0, "fail")

    def test_whitespace_stripped(self) -> None:
        assert _normalize_score("  pass  ") == (1.0, "pass")


# ---------------------------------------------------------------------------
# _parse_json_response
# ---------------------------------------------------------------------------


class TestParseJsonResponse:
    def test_plain_json(self) -> None:
        result = _parse_json_response('{"score": "pass", "reasoning": "Good"}')
        assert result["score"] == "pass"
        assert result["reasoning"] == "Good"

    def test_json_in_markdown_fence(self) -> None:
        text = '```json\n{"score": "partial", "reasoning": "OK"}\n```'
        result = _parse_json_response(text)
        assert result["score"] == "partial"

    def test_json_in_plain_fence(self) -> None:
        text = '```\n{"score": "fail", "reasoning": "Bad"}\n```'
        result = _parse_json_response(text)
        assert result["score"] == "fail"

    def test_malformed_returns_fallback(self) -> None:
        result = _parse_json_response("this is not json at all")
        assert result["score"] == "fail"
        assert "JSON parsing failed" in result["reasoning"]

    def test_embedded_json_object(self) -> None:
        text = 'Some text before {"score": "pass", "reasoning": "Found"} after'
        result = _parse_json_response(text)
        assert result["score"] == "pass"


# ---------------------------------------------------------------------------
# _select_dimensions
# ---------------------------------------------------------------------------


class TestSelectDimensions:
    def test_default_dimensions(self) -> None:
        dims = _select_dimensions("unknown-benchmark", None)
        assert dims == ["correctness", "completeness"]

    def test_swe_benchmark(self) -> None:
        dims = _select_dimensions("swe-bench-pro", None)
        assert dims == ["correctness", "code_quality"]

    def test_locobench(self) -> None:
        dims = _select_dimensions("locobench-task-42", None)
        assert dims == ["correctness", "completeness", "code_quality"]

    def test_custom_template(self, tmp_path: Path) -> None:
        template = tmp_path / "custom.json"
        template.write_text(json.dumps({"dimensions": ["retrieval", "mcp_effectiveness"]}))
        dims = _select_dimensions("anything", template)
        assert dims == ["retrieval", "mcp_effectiveness"]

    def test_invalid_template_falls_back(self, tmp_path: Path) -> None:
        template = tmp_path / "bad.json"
        template.write_text("not json")
        dims = _select_dimensions("locobench", template)
        assert dims == ["correctness", "completeness", "code_quality"]

    def test_empty_template_falls_back(self, tmp_path: Path) -> None:
        template = tmp_path / "empty.json"
        template.write_text(json.dumps({"dimensions": []}))
        dims = _select_dimensions("swe-bench", template)
        assert dims == ["correctness", "code_quality"]

    def test_nonexistent_template(self) -> None:
        dims = _select_dimensions("default", Path("/nonexistent/template.json"))
        assert dims == ["correctness", "completeness"]


# ---------------------------------------------------------------------------
# _load_solution_text
# ---------------------------------------------------------------------------


class TestLoadSolutionText:
    def test_solution_md(self, tmp_path: Path) -> None:
        trial_dir = tmp_path / "trial"
        agent_dir = trial_dir / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "solution.md").write_text("My solution here")
        assert _load_solution_text(trial_dir) == "My solution here"

    def test_claude_code_txt(self, tmp_path: Path) -> None:
        trial_dir = tmp_path / "trial"
        agent_dir = trial_dir / "agent"
        agent_dir.mkdir(parents=True)
        lines = [
            json.dumps({"type": "assistant", "content": "Hello world"}),
            json.dumps({"type": "system", "content": "init"}),
            json.dumps({"type": "assistant", "content": [{"type": "text", "text": "More text"}]}),
        ]
        (agent_dir / "claude-code.txt").write_text("\n".join(lines))
        result = _load_solution_text(trial_dir)
        assert "Hello world" in result
        assert "More text" in result

    def test_patch_file(self, tmp_path: Path) -> None:
        trial_dir = tmp_path / "trial"
        sub_dir = trial_dir / "submission"
        sub_dir.mkdir(parents=True)
        (sub_dir / "diff.patch").write_text("--- a/file.py\n+++ b/file.py\n+new line")
        result = _load_solution_text(trial_dir)
        assert "new line" in result

    def test_empty_trial_dir(self, tmp_path: Path) -> None:
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()
        assert _load_solution_text(trial_dir) == ""

    def test_solution_md_truncated(self, tmp_path: Path) -> None:
        trial_dir = tmp_path / "trial"
        agent_dir = trial_dir / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "solution.md").write_text("x" * 30_000)
        result = _load_solution_text(trial_dir)
        assert len(result) == 20_000


# ---------------------------------------------------------------------------
# _extract_assistant_content
# ---------------------------------------------------------------------------


class TestExtractAssistantContent:
    def test_string_content(self, tmp_path: Path) -> None:
        fpath = tmp_path / "transcript.txt"
        fpath.write_text(json.dumps({"type": "assistant", "content": "Hello"}))
        result = _extract_assistant_content(fpath)
        assert result == "Hello"

    def test_list_content(self, tmp_path: Path) -> None:
        fpath = tmp_path / "transcript.txt"
        event = {
            "type": "assistant",
            "content": [
                {"type": "text", "text": "Part 1"},
                {"type": "tool_use", "name": "bash"},
                {"type": "text", "text": "Part 2"},
            ],
        }
        fpath.write_text(json.dumps(event))
        result = _extract_assistant_content(fpath)
        assert "Part 1" in result
        assert "Part 2" in result

    def test_skips_malformed_lines(self, tmp_path: Path) -> None:
        fpath = tmp_path / "transcript.txt"
        lines = [
            "not json at all",
            json.dumps({"type": "assistant", "content": "Valid"}),
        ]
        fpath.write_text("\n".join(lines))
        result = _extract_assistant_content(fpath)
        assert result == "Valid"

    def test_agent_source_format(self, tmp_path: Path) -> None:
        fpath = tmp_path / "transcript.txt"
        event = {"source": "agent", "content": "Agent output"}
        fpath.write_text(json.dumps(event))
        result = _extract_assistant_content(fpath)
        assert result == "Agent output"

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        fpath = tmp_path / "missing.txt"
        result = _extract_assistant_content(fpath)
        assert result == ""


# ---------------------------------------------------------------------------
# _load_task_description
# ---------------------------------------------------------------------------


class TestLoadTaskDescription:
    def test_from_config_json(self, tmp_path: Path) -> None:
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()
        config = {"task": {"description": "Fix the bug"}}
        (trial_dir / "config.json").write_text(json.dumps(config))
        assert _load_task_description(trial_dir) == "Fix the bug"

    def test_from_instruction_md(self, tmp_path: Path) -> None:
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()
        (trial_dir / "instruction.md").write_text("# Task\nDo something")
        result = _load_task_description(trial_dir)
        assert "Do something" in result

    def test_from_task_subdir(self, tmp_path: Path) -> None:
        trial_dir = tmp_path / "trial"
        task_dir = trial_dir / "task"
        task_dir.mkdir(parents=True)
        (task_dir / "TASK.md").write_text("Task instructions here")
        result = _load_task_description(trial_dir)
        assert "Task instructions here" in result

    def test_fallback_message(self, tmp_path: Path) -> None:
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()
        assert _load_task_description(trial_dir) == "Task description not available"

    def test_config_json_no_description(self, tmp_path: Path) -> None:
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()
        config = {"task": {"path": "/some/path"}}
        (trial_dir / "config.json").write_text(json.dumps(config))
        assert _load_task_description(trial_dir) == "Task description not available"


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_builds_prompt_with_all_fields(self) -> None:
        prompt = _build_prompt(
            task_description="Fix the bug",
            solution_text="I fixed it by changing X",
            reward=1.0,
            dimension="correctness",
        )
        assert "Fix the bug" in prompt
        assert "I fixed it by changing X" in prompt
        assert "1.0" in prompt
        assert "correctness" in prompt

    def test_none_reward(self) -> None:
        prompt = _build_prompt("desc", "solution", None, "completeness")
        assert "N/A" in prompt

    def test_unknown_dimension_uses_correctness_fallback(self) -> None:
        prompt = _build_prompt("desc", "sol", 0.5, "unknown_dim")
        assert "correctly address" in prompt


# ---------------------------------------------------------------------------
# _find_trial_dir
# ---------------------------------------------------------------------------


class TestFindTrialDir:
    def test_finds_trial_by_name(self, tmp_path: Path) -> None:
        trial_dir = tmp_path / "runs" / "official" / "exp" / "trial-001"
        trial_dir.mkdir(parents=True)
        (trial_dir / "result.json").write_text("{}")
        found = _find_trial_dir(tmp_path / "runs", "trial-001")
        assert found == trial_dir

    def test_returns_none_for_missing(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        assert _find_trial_dir(runs_dir, "nonexistent") is None


# ---------------------------------------------------------------------------
# _flatten_trials / _augment_metrics
# ---------------------------------------------------------------------------


class TestFlattenTrials:
    def test_flattens_nested_structure(self) -> None:
        trials = [_make_trial("t1"), _make_trial("t2")]
        categories = _make_categories(trials)
        flat = _flatten_trials(categories)
        assert len(flat) == 2
        assert flat[0]["trial_id"] == "t1"
        assert flat[1]["trial_id"] == "t2"

    def test_empty_categories(self) -> None:
        assert _flatten_trials([]) == []

    def test_multiple_categories(self) -> None:
        cats = [
            {"run_category": "official", "experiments": [{"trials": [_make_trial("t1")]}]},
            {"run_category": "experiment", "experiments": [{"trials": [_make_trial("t2")]}]},
        ]
        assert len(_flatten_trials(cats)) == 2


class TestAugmentMetrics:
    def test_adds_judge_scores(self) -> None:
        trial = _make_trial("t1")
        categories = _make_categories([trial])
        result = TrialJudgeResult(
            trial_id="t1",
            task_name="test-task",
            dimensions=(
                DimensionScore(
                    dimension="correctness",
                    score=1.0,
                    score_label="pass",
                    reasoning="Good",
                    vote_distribution=(("1.0", 3),),
                    confidence=1.0,
                    num_rounds=3,
                ),
            ),
            mean_score=1.0,
            overall_quality="pass",
        )
        augmented = _augment_metrics(categories, {"t1": result})
        trial_out = augmented[0]["experiments"][0]["trials"][0]
        assert "judge_scores" in trial_out
        assert trial_out["judge_scores"]["mean_score"] == 1.0
        assert trial_out["judge_scores"]["overall_quality"] == "pass"

    def test_does_not_mutate_input(self) -> None:
        trial = _make_trial("t1")
        categories = _make_categories([trial])
        original_trial = categories[0]["experiments"][0]["trials"][0]
        _augment_metrics(categories, {})
        # Original should not have judge_scores
        assert "judge_scores" not in original_trial

    def test_missing_trial_id_no_scores(self) -> None:
        trial = _make_trial("t1")
        categories = _make_categories([trial])
        augmented = _augment_metrics(categories, {})
        trial_out = augmented[0]["experiments"][0]["trials"][0]
        assert "judge_scores" not in trial_out


# ---------------------------------------------------------------------------
# Data structure immutability
# ---------------------------------------------------------------------------


class TestDataclassImmutability:
    def test_judge_vote_frozen(self) -> None:
        vote = JudgeVote(
            model="test", dimension="correctness",
            score=1.0, score_label="pass", reasoning="ok"
        )
        with pytest.raises(AttributeError):
            vote.score = 0.5  # type: ignore[misc]

    def test_dimension_score_frozen(self) -> None:
        ds = DimensionScore(
            dimension="correctness", score=1.0, score_label="pass",
            reasoning="ok", vote_distribution=(), confidence=1.0, num_rounds=3,
        )
        with pytest.raises(AttributeError):
            ds.score = 0.0  # type: ignore[misc]

    def test_trial_judge_result_frozen(self) -> None:
        result = TrialJudgeResult(
            trial_id="t1", task_name="task",
            dimensions=(), mean_score=0.0, overall_quality="fail",
        )
        with pytest.raises(AttributeError):
            result.mean_score = 1.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _evaluate_dimension (mocked LLM)
# ---------------------------------------------------------------------------


class TestEvaluateDimension:
    def test_single_model_majority_vote(self) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"score": "pass", "reasoning": "Good", "strengths": ["a"], "weaknesses": []}')]
        mock_client.messages.create.return_value = mock_response

        result = _evaluate_dimension(
            client=mock_client,
            models=("model-a",),
            task_description="Fix bug",
            solution_text="Fixed it",
            reward=1.0,
            dimension="correctness",
            rounds_per_model=3,
        )
        assert result.score == 1.0
        assert result.score_label == "pass"
        assert result.confidence == 1.0
        assert result.num_rounds == 3
        assert mock_client.messages.create.call_count == 3

    def test_mixed_votes_majority_wins(self) -> None:
        mock_client = MagicMock()
        responses = [
            MagicMock(content=[MagicMock(text='{"score": "pass", "reasoning": "Good"}')]),
            MagicMock(content=[MagicMock(text='{"score": "fail", "reasoning": "Bad"}')]),
            MagicMock(content=[MagicMock(text='{"score": "pass", "reasoning": "Also good"}')]),
        ]
        mock_client.messages.create.side_effect = responses

        result = _evaluate_dimension(
            client=mock_client,
            models=("model-a",),
            task_description="Fix bug",
            solution_text="Fixed it",
            reward=1.0,
            dimension="correctness",
            rounds_per_model=3,
        )
        assert result.score == 1.0
        assert result.confidence == pytest.approx(2 / 3)

    def test_multiple_models(self) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"score": "partial", "reasoning": "OK"}')]
        mock_client.messages.create.return_value = mock_response

        result = _evaluate_dimension(
            client=mock_client,
            models=("model-a", "model-b"),
            task_description="Fix bug",
            solution_text="Fixed it",
            reward=0.5,
            dimension="completeness",
            rounds_per_model=1,
        )
        assert result.score == 0.5
        assert result.num_rounds == 2
        assert mock_client.messages.create.call_count == 2


# ---------------------------------------------------------------------------
# evaluate_trial (mocked LLM)
# ---------------------------------------------------------------------------


class TestEvaluateTrial:
    def test_with_solution(self, tmp_path: Path) -> None:
        trial_dir = _make_trial_dir(tmp_path, "trial-001")
        trial = _make_trial("trial-001")

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"score": "pass", "reasoning": "OK"}')]
        mock_client.messages.create.return_value = mock_response

        result = evaluate_trial(
            client=mock_client,
            models=("model-a",),
            trial=trial,
            runs_dir=tmp_path,
            dimensions=["correctness"],
            rounds_per_model=1,
        )
        assert result.trial_id == "trial-001"
        assert result.mean_score == 1.0
        assert result.overall_quality == "pass"
        assert len(result.dimensions) == 1
        assert result.error is None

    def test_no_solution_returns_error(self, tmp_path: Path) -> None:
        # Trial dir exists but has no solution files
        trial_dir = tmp_path / "official" / "exp" / "config" / "trial-empty"
        trial_dir.mkdir(parents=True)
        (trial_dir / "result.json").write_text("{}")

        trial = _make_trial("trial-empty")
        mock_client = MagicMock()

        result = evaluate_trial(
            client=mock_client,
            models=("model-a",),
            trial=trial,
            runs_dir=tmp_path,
            dimensions=["correctness"],
            rounds_per_model=1,
        )
        assert result.mean_score == 0.0
        assert result.overall_quality == "fail"
        assert result.error is not None
        assert "No solution text" in result.error

    def test_no_runs_dir(self) -> None:
        trial = _make_trial("trial-001")
        mock_client = MagicMock()

        result = evaluate_trial(
            client=mock_client,
            models=("model-a",),
            trial=trial,
            runs_dir=None,
            dimensions=["correctness"],
            rounds_per_model=1,
        )
        # No runs_dir means no solution text
        assert result.error is not None

    def test_overall_quality_partial(self, tmp_path: Path) -> None:
        trial_dir = _make_trial_dir(tmp_path, "trial-p")
        trial = _make_trial("trial-p")

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"score": "partial", "reasoning": "OK"}')]
        mock_client.messages.create.return_value = mock_response

        result = evaluate_trial(
            client=mock_client,
            models=("model-a",),
            trial=trial,
            runs_dir=tmp_path,
            dimensions=["correctness", "completeness"],
            rounds_per_model=1,
        )
        assert result.mean_score == 0.5
        assert result.overall_quality == "partial"

    def test_overall_quality_fail(self, tmp_path: Path) -> None:
        trial_dir = _make_trial_dir(tmp_path, "trial-f")
        trial = _make_trial("trial-f")

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"score": "fail", "reasoning": "Bad"}')]
        mock_client.messages.create.return_value = mock_response

        result = evaluate_trial(
            client=mock_client,
            models=("model-a",),
            trial=trial,
            runs_dir=tmp_path,
            dimensions=["correctness"],
            rounds_per_model=1,
        )
        assert result.mean_score == 0.0
        assert result.overall_quality == "fail"


# ---------------------------------------------------------------------------
# CLI (main)
# ---------------------------------------------------------------------------


class TestMain:
    def test_missing_input_file(self, tmp_path: Path) -> None:
        rc = main(["--input", str(tmp_path / "missing.json")])
        assert rc == 1

    def test_skip_judge_copies_input(self, tmp_path: Path) -> None:
        input_path = tmp_path / "input.json"
        output_path = tmp_path / "output.json"
        categories = _make_categories([_make_trial()])
        input_path.write_text(json.dumps(categories))

        rc = main([
            "--input", str(input_path),
            "--output", str(output_path),
            "--skip-judge",
        ])
        assert rc == 0
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert len(data) == 1
        assert data[0]["run_category"] == "official"

    def test_skip_judge_same_file(self, tmp_path: Path) -> None:
        input_path = tmp_path / "metrics.json"
        categories = _make_categories([_make_trial()])
        input_path.write_text(json.dumps(categories))

        rc = main(["--input", str(input_path), "--skip-judge"])
        assert rc == 0
        # File should remain unchanged
        data = json.loads(input_path.read_text())
        assert len(data) == 1

    def test_malformed_json_input(self, tmp_path: Path) -> None:
        input_path = tmp_path / "bad.json"
        input_path.write_text("not json {{{")
        rc = main(["--input", str(input_path)])
        assert rc == 1

    @patch("scripts.ccb_pipeline.judge.run_judge")
    def test_successful_run(self, mock_run_judge: MagicMock, tmp_path: Path) -> None:
        input_path = tmp_path / "input.json"
        output_path = tmp_path / "output.json"
        trial = _make_trial()
        categories = _make_categories([trial])
        input_path.write_text(json.dumps(categories))

        # Return augmented categories with judge_scores
        augmented = _make_categories([{**trial, "judge_scores": {
            "mean_score": 0.8,
            "overall_quality": "pass",
            "dimensions": [],
            "error": None,
        }}])
        mock_run_judge.return_value = augmented

        rc = main([
            "--input", str(input_path),
            "--output", str(output_path),
            "--runs-dir", str(tmp_path),
        ])
        assert rc == 0
        assert output_path.exists()
        mock_run_judge.assert_called_once()

    @patch("scripts.ccb_pipeline.judge.run_judge", side_effect=ValueError("No API key"))
    def test_api_error_returns_1(self, mock_run: MagicMock, tmp_path: Path) -> None:
        input_path = tmp_path / "input.json"
        input_path.write_text(json.dumps(_make_categories([_make_trial()])))

        rc = main(["--input", str(input_path)])
        assert rc == 1

    def test_rounds_argument(self, tmp_path: Path) -> None:
        input_path = tmp_path / "input.json"
        input_path.write_text(json.dumps(_make_categories([_make_trial()])))

        with patch("scripts.ccb_pipeline.judge.run_judge") as mock_run:
            mock_run.return_value = _make_categories([_make_trial()])
            rc = main([
                "--input", str(input_path),
                "--runs-dir", str(tmp_path),
                "--rounds", "5",
            ])
            assert rc == 0
            _, kwargs = mock_run.call_args
            assert kwargs["rounds_per_model"] == 5

    def test_judge_template_argument(self, tmp_path: Path) -> None:
        input_path = tmp_path / "input.json"
        template_path = tmp_path / "template.json"
        input_path.write_text(json.dumps(_make_categories([_make_trial()])))
        template_path.write_text(json.dumps({"dimensions": ["correctness"]}))

        with patch("scripts.ccb_pipeline.judge.run_judge") as mock_run:
            mock_run.return_value = _make_categories([_make_trial()])
            rc = main([
                "--input", str(input_path),
                "--runs-dir", str(tmp_path),
                "--judge-template", str(template_path),
            ])
            assert rc == 0
            _, kwargs = mock_run.call_args
            assert kwargs["template_path"] == template_path


# ---------------------------------------------------------------------------
# run_judge (integration with mocks)
# ---------------------------------------------------------------------------


class TestRunJudge:
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("scripts.ccb_pipeline.judge.evaluate_trial")
    def test_runs_all_trials(self, mock_eval: MagicMock) -> None:
        mock_eval.return_value = TrialJudgeResult(
            trial_id="t1",
            task_name="test-task",
            dimensions=(),
            mean_score=1.0,
            overall_quality="pass",
        )
        trials = [_make_trial("t1"), _make_trial("t2")]
        categories = _make_categories(trials)

        import anthropic as _real_anthropic
        with patch.object(_real_anthropic, "Anthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            result = run_judge(categories, runs_dir=None)

        assert mock_eval.call_count == 2

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""})
    def test_missing_api_key_raises(self) -> None:
        categories = _make_categories([_make_trial()])
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            run_judge(categories, runs_dir=None)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("scripts.ccb_pipeline.judge.evaluate_trial")
    def test_handles_trial_failure(self, mock_eval: MagicMock) -> None:
        mock_eval.side_effect = RuntimeError("LLM timeout")
        categories = _make_categories([_make_trial("t1")])

        import anthropic as _real_anthropic
        with patch.object(_real_anthropic, "Anthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            result = run_judge(categories, runs_dir=None)

        trial_out = result[0]["experiments"][0]["trials"][0]
        assert "judge_scores" in trial_out
        assert trial_out["judge_scores"]["error"] is not None
