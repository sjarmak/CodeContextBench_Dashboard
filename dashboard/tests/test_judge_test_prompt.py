"""
Tests for dashboard/utils/judge_test_prompt.py

Tests the LLM judge test prompt utility: task data loading,
prompt building, response parsing, experiment discovery, and
UI rendering.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from dashboard.utils.judge_config import (
    JudgeConfig,
    ScoringCriterion,
    ScoringDimension,
)
from dashboard.utils.judge_test_prompt import (
    DimensionResult,
    TestPromptResult,
    _build_evaluation_prompt,
    _display_result,
    _extract_code_changes,
    _extract_description_from_trace,
    _find_experiment_tasks,
    _load_task_data,
    _parse_judge_response,
    _run_and_display_result,
    render_test_prompt_section,
    run_test_prompt,
)


# =============================================================================
# Test Data Factories
# =============================================================================


def _make_config(
    system_prompt: str = "Test judge prompt",
    model: str = "claude-haiku-4-5-20251001",
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> JudgeConfig:
    """Create a test JudgeConfig."""
    return JudgeConfig(
        system_prompt=system_prompt,
        dimensions=(
            ScoringDimension(
                name="Correctness",
                weight=0.5,
                criteria=(
                    ScoringCriterion(1, "Incorrect"),
                    ScoringCriterion(2, "Partially correct"),
                    ScoringCriterion(3, "Mostly correct"),
                    ScoringCriterion(4, "Correct with minor issues"),
                    ScoringCriterion(5, "Fully correct"),
                ),
            ),
            ScoringDimension(
                name="Quality",
                weight=0.5,
                criteria=(
                    ScoringCriterion(1, "Poor"),
                    ScoringCriterion(2, "Below average"),
                    ScoringCriterion(3, "Average"),
                    ScoringCriterion(4, "Good"),
                    ScoringCriterion(5, "Excellent"),
                ),
            ),
        ),
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _make_trace_jsonl(messages: list[dict]) -> str:
    """Create JSONL trace content from message dicts."""
    return "\n".join(json.dumps(m) for m in messages)


def _make_edit_message(file_path: str, old: str, new: str) -> dict:
    return {
        "type": "assistant",
        "content": [
            {
                "type": "tool_use",
                "name": "Edit",
                "input": {
                    "file_path": file_path,
                    "old_string": old,
                    "new_string": new,
                },
            }
        ],
    }


def _make_write_message(file_path: str, content: str) -> dict:
    return {
        "type": "assistant",
        "content": [
            {
                "type": "tool_use",
                "name": "Write",
                "input": {
                    "file_path": file_path,
                    "content": content,
                },
            }
        ],
    }


def _make_system_message(content: str) -> dict:
    return {"type": "system", "content": content}


def _make_system_message_list(text: str) -> dict:
    return {"type": "system", "content": [{"type": "text", "text": text}]}


# =============================================================================
# TestDimensionResult
# =============================================================================


class TestDimensionResult:
    def test_frozen(self):
        result = DimensionResult(name="Test", score="4", reasoning="Good")
        with pytest.raises(AttributeError):
            result.name = "Changed"

    def test_fields(self):
        result = DimensionResult(name="Quality", score="3", reasoning="Okay")
        assert result.name == "Quality"
        assert result.score == "3"
        assert result.reasoning == "Okay"


# =============================================================================
# TestTestPromptResult
# =============================================================================


class TestTestPromptResult:
    def test_frozen(self):
        result = TestPromptResult(
            task_id="t1",
            dimension_results=(),
            overall_score="4",
            overall_reasoning="Good overall",
        )
        with pytest.raises(AttributeError):
            result.task_id = "changed"

    def test_with_error(self):
        result = TestPromptResult(
            task_id="t1",
            dimension_results=(),
            overall_score="N/A",
            overall_reasoning="",
            error="API failed",
        )
        assert result.error == "API failed"

    def test_with_dimensions(self):
        dims = (
            DimensionResult(name="A", score="5", reasoning="Perfect"),
            DimensionResult(name="B", score="3", reasoning="OK"),
        )
        result = TestPromptResult(
            task_id="t1",
            dimension_results=dims,
            overall_score="4",
            overall_reasoning="Good",
        )
        assert len(result.dimension_results) == 2
        assert result.dimension_results[0].name == "A"

    def test_default_error_is_none(self):
        result = TestPromptResult(
            task_id="t1",
            dimension_results=(),
            overall_score="3",
            overall_reasoning="Fine",
        )
        assert result.error is None


# =============================================================================
# TestExtractCodeChanges
# =============================================================================


class TestExtractCodeChanges:
    def test_empty_content(self):
        assert _extract_code_changes("") == ""

    def test_no_tool_use_messages(self):
        trace = _make_trace_jsonl([
            {"type": "user", "content": "hello"},
            {"type": "assistant", "content": "hi there"},
        ])
        assert _extract_code_changes(trace) == ""

    def test_edit_extraction(self):
        trace = _make_trace_jsonl([
            _make_edit_message("src/main.py", "old code", "new code"),
        ])
        result = _extract_code_changes(trace)
        assert "src/main.py" in result
        assert "old code" in result
        assert "new code" in result

    def test_write_extraction(self):
        trace = _make_trace_jsonl([
            _make_write_message("src/new_file.py", "print('hello')"),
        ])
        result = _extract_code_changes(trace)
        assert "src/new_file.py" in result
        assert "print('hello')" in result

    def test_multiple_changes(self):
        trace = _make_trace_jsonl([
            _make_edit_message("a.py", "old1", "new1"),
            _make_edit_message("b.py", "old2", "new2"),
        ])
        result = _extract_code_changes(trace)
        assert "a.py" in result
        assert "b.py" in result

    def test_malformed_json_skipped(self):
        trace = "not json\n" + json.dumps(
            _make_edit_message("c.py", "o", "n")
        )
        result = _extract_code_changes(trace)
        assert "c.py" in result

    def test_max_chars_limit(self):
        trace = _make_trace_jsonl([
            _make_write_message("big.py", "x" * 20000),
        ])
        result = _extract_code_changes(trace, max_chars=100)
        assert len(result) <= 100

    def test_non_tool_use_blocks_skipped(self):
        trace = _make_trace_jsonl([
            {
                "type": "assistant",
                "content": [{"type": "text", "text": "thinking..."}],
            }
        ])
        assert _extract_code_changes(trace) == ""

    def test_non_list_content_skipped(self):
        trace = _make_trace_jsonl([
            {"type": "assistant", "content": "just text"},
        ])
        assert _extract_code_changes(trace) == ""


# =============================================================================
# TestExtractDescriptionFromTrace
# =============================================================================


class TestExtractDescriptionFromTrace:
    def test_empty_trace(self):
        assert _extract_description_from_trace("") == ""

    def test_string_system_message(self):
        trace = _make_trace_jsonl([_make_system_message("Fix the bug")])
        assert _extract_description_from_trace(trace) == "Fix the bug"

    def test_list_system_message(self):
        trace = _make_trace_jsonl([
            _make_system_message_list("Task: implement feature X")
        ])
        assert "Task: implement feature X" in _extract_description_from_trace(trace)

    def test_no_system_messages(self):
        trace = _make_trace_jsonl([
            {"type": "assistant", "content": "hi"},
        ])
        assert _extract_description_from_trace(trace) == ""

    def test_truncates_long_content(self):
        trace = _make_trace_jsonl([_make_system_message("x" * 5000)])
        result = _extract_description_from_trace(trace)
        assert len(result) <= 3000


# =============================================================================
# TestLoadTaskData
# =============================================================================


class TestLoadTaskData:
    def test_missing_directory(self, tmp_path):
        missing = tmp_path / "nonexistent"
        data = _load_task_data(missing)
        assert data["task_description"] == ""
        assert data["reward"] == 0.0

    def test_config_json_loading(self, tmp_path):
        config = {"task": {"instruction": "Fix the login bug"}}
        (tmp_path / "config.json").write_text(json.dumps(config))
        data = _load_task_data(tmp_path)
        assert data["task_description"] == "Fix the login bug"

    def test_problem_statement_field(self, tmp_path):
        config = {"problem_statement": "Resolve issue #42"}
        (tmp_path / "config.json").write_text(json.dumps(config))
        data = _load_task_data(tmp_path)
        assert data["task_description"] == "Resolve issue #42"

    def test_tests_config_fallback(self, tmp_path):
        # No main config, but tests/config.json exists
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        config = {"problem_statement": "SWE-Bench task"}
        (tests_dir / "config.json").write_text(json.dumps(config))
        data = _load_task_data(tmp_path)
        assert data["task_description"] == "SWE-Bench task"

    def test_result_json_reward(self, tmp_path):
        result = {"reward": 1.0}
        (tmp_path / "result.json").write_text(json.dumps(result))
        data = _load_task_data(tmp_path)
        assert data["reward"] == 1.0

    def test_result_json_nested_reward(self, tmp_path):
        result = {"verifier_result": {"rewards": {"reward": 0.5}}}
        (tmp_path / "result.json").write_text(json.dumps(result))
        data = _load_task_data(tmp_path)
        assert data["reward"] == 0.5

    def test_trace_content_loading(self, tmp_path):
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        trace = _make_trace_jsonl([_make_edit_message("f.py", "a", "b")])
        (agent_dir / "claude-code.txt").write_text(trace)
        data = _load_task_data(tmp_path)
        assert data["trace_content"] != ""
        assert "f.py" in data["code_changes"]

    def test_solution_md_loading(self, tmp_path):
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "solution.md").write_text("# My solution\nFixed the bug.")
        data = _load_task_data(tmp_path)
        assert data["solution"] == "# My solution\nFixed the bug."

    def test_malformed_config_json(self, tmp_path):
        (tmp_path / "config.json").write_text("not json {{{")
        data = _load_task_data(tmp_path)
        assert data["task_description"] == ""

    def test_malformed_result_json(self, tmp_path):
        (tmp_path / "result.json").write_text("invalid")
        data = _load_task_data(tmp_path)
        assert data["reward"] == 0.0

    def test_trace_description_fallback(self, tmp_path):
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        trace = _make_trace_jsonl([_make_system_message("System task description")])
        (agent_dir / "claude-code.txt").write_text(trace)
        data = _load_task_data(tmp_path)
        assert "System task description" in data["task_description"]


# =============================================================================
# TestBuildEvaluationPrompt
# =============================================================================


class TestBuildEvaluationPrompt:
    def test_includes_system_prompt(self):
        config = _make_config(system_prompt="You are a judge")
        prompt = _build_evaluation_prompt(config, "desc", "changes", 1.0)
        assert "You are a judge" in prompt

    def test_includes_task_description(self):
        config = _make_config()
        prompt = _build_evaluation_prompt(config, "Fix the auth bug", "code", 0.5)
        assert "Fix the auth bug" in prompt

    def test_includes_code_changes(self):
        config = _make_config()
        prompt = _build_evaluation_prompt(config, "desc", "def foo(): pass", 0.0)
        assert "def foo(): pass" in prompt

    def test_includes_reward(self):
        config = _make_config()
        prompt = _build_evaluation_prompt(config, "desc", "code", 0.75)
        assert "0.75" in prompt

    def test_includes_dimensions(self):
        config = _make_config()
        prompt = _build_evaluation_prompt(config, "desc", "code", 1.0)
        assert "Correctness" in prompt
        assert "Quality" in prompt

    def test_includes_criteria(self):
        config = _make_config()
        prompt = _build_evaluation_prompt(config, "desc", "code", 1.0)
        assert "Fully correct" in prompt
        assert "Excellent" in prompt

    def test_includes_json_format(self):
        config = _make_config()
        prompt = _build_evaluation_prompt(config, "desc", "code", 1.0)
        assert '"overall_score"' in prompt
        assert '"dimensions"' in prompt

    def test_no_description_fallback(self):
        config = _make_config()
        prompt = _build_evaluation_prompt(config, "", "code", 0.0)
        assert "No description available" in prompt

    def test_no_code_changes_fallback(self):
        config = _make_config()
        prompt = _build_evaluation_prompt(config, "desc", "", 0.0)
        assert "No code changes extracted" in prompt


# =============================================================================
# TestParseJudgeResponse
# =============================================================================


class TestParseJudgeResponse:
    def test_valid_json(self):
        config = _make_config()
        response = json.dumps({
            "dimensions": [
                {"name": "Correctness", "score": 4, "reasoning": "Mostly correct"},
                {"name": "Quality", "score": 5, "reasoning": "Excellent"},
            ],
            "overall_score": 4,
            "overall_reasoning": "Good solution overall",
        })
        result = _parse_judge_response(response, config)
        assert result.error is None
        assert len(result.dimension_results) == 2
        assert result.dimension_results[0].name == "Correctness"
        assert result.dimension_results[0].score == "4"
        assert result.overall_score == "4"
        assert "Good solution" in result.overall_reasoning

    def test_json_in_code_block(self):
        config = _make_config()
        response = '```json\n{"dimensions": [], "overall_score": 3, "overall_reasoning": "OK"}\n```'
        result = _parse_judge_response(response, config)
        assert result.error is None
        assert result.overall_score == "3"

    def test_json_in_plain_code_block(self):
        config = _make_config()
        response = '```\n{"dimensions": [], "overall_score": 2, "overall_reasoning": "Fair"}\n```'
        result = _parse_judge_response(response, config)
        assert result.error is None
        assert result.overall_score == "2"

    def test_invalid_json(self):
        config = _make_config()
        result = _parse_judge_response("not json at all", config)
        assert result.error is not None
        assert "N/A" in result.overall_score

    def test_partial_json_extraction(self):
        config = _make_config()
        response = 'Here is my evaluation: {"dimensions": [], "overall_score": 5, "overall_reasoning": "Great"} end'
        result = _parse_judge_response(response, config)
        # Should extract the JSON object
        assert result.overall_score == "5"

    def test_empty_dimensions(self):
        config = _make_config()
        response = json.dumps({
            "dimensions": [],
            "overall_score": 3,
            "overall_reasoning": "Average",
        })
        result = _parse_judge_response(response, config)
        assert len(result.dimension_results) == 0
        assert result.overall_score == "3"


# =============================================================================
# TestFindExperimentTasks
# =============================================================================


class TestFindExperimentTasks:
    def test_nonexistent_directory(self, tmp_path):
        tasks = _find_experiment_tasks(tmp_path, "missing_exp")
        assert tasks == []

    def test_standard_harbor_format(self, tmp_path):
        exp_dir = tmp_path / "exp1"
        exp_dir.mkdir()
        for name in ["task_a", "task_b"]:
            task_dir = exp_dir / name
            task_dir.mkdir()
            (task_dir / "agent").mkdir()
        tasks = _find_experiment_tasks(tmp_path, "exp1")
        assert len(tasks) == 2
        task_ids = [t[0] for t in tasks]
        assert "task_a" in task_ids
        assert "task_b" in task_ids

    def test_paired_experiment_structure(self, tmp_path):
        exp_dir = tmp_path / "paired_exp"
        exp_dir.mkdir()
        baseline = exp_dir / "baseline"
        baseline.mkdir()
        task_dir = baseline / "task1"
        task_dir.mkdir()
        (task_dir / "result.json").write_text("{}")
        tasks = _find_experiment_tasks(tmp_path, "paired_exp")
        assert len(tasks) == 1
        assert tasks[0][0] == "task1"

    def test_skips_hidden_dirs(self, tmp_path):
        exp_dir = tmp_path / "exp2"
        exp_dir.mkdir()
        hidden = exp_dir / ".hidden"
        hidden.mkdir()
        (hidden / "agent").mkdir()
        visible = exp_dir / "task1"
        visible.mkdir()
        (visible / "agent").mkdir()
        tasks = _find_experiment_tasks(tmp_path, "exp2")
        assert len(tasks) == 1
        assert tasks[0][0] == "task1"

    def test_result_json_detection(self, tmp_path):
        exp_dir = tmp_path / "exp3"
        exp_dir.mkdir()
        task_dir = exp_dir / "task_x"
        task_dir.mkdir()
        (task_dir / "result.json").write_text("{}")
        tasks = _find_experiment_tasks(tmp_path, "exp3")
        assert len(tasks) == 1

    def test_nested_paired_tasks(self, tmp_path):
        exp_dir = tmp_path / "nested_exp"
        exp_dir.mkdir()
        deepsearch = exp_dir / "deepsearch"
        deepsearch.mkdir()
        ts_dir = deepsearch / "20260101_120000"
        ts_dir.mkdir()
        task_dir = ts_dir / "task_nested"
        task_dir.mkdir()
        (task_dir / "result.json").write_text("{}")
        tasks = _find_experiment_tasks(tmp_path, "nested_exp")
        assert len(tasks) == 1
        assert "task_nested" in tasks[0][0]


# =============================================================================
# TestRunTestPrompt
# =============================================================================


class TestRunTestPrompt:
    def test_missing_anthropic(self, tmp_path):
        config = _make_config()
        with patch.dict("sys.modules", {"anthropic": None}):
            # Force reimport to trigger ImportError
            result = run_test_prompt(config, tmp_path, "test_task")
            # The function catches ImportError internally
            # If anthropic is installed, this won't trigger - test the logic anyway
            assert result.task_id == "test_task"

    def test_missing_api_key(self, tmp_path):
        config = _make_config()
        with patch.dict(os.environ, {}, clear=True):
            result = run_test_prompt(config, tmp_path, "task1")
            assert result.task_id == "task1"
            # Either error about api key or about anthropic
            if result.error:
                assert "API" in result.error or "anthropic" in result.error.lower()

    @patch("dashboard.utils.judge_test_prompt.os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_successful_evaluation(self, tmp_path):
        config = _make_config()

        # Create task directory with data
        (tmp_path / "config.json").write_text(
            json.dumps({"task": {"instruction": "Fix bug"}})
        )
        (tmp_path / "result.json").write_text(json.dumps({"reward": 1.0}))
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        trace = _make_trace_jsonl([
            _make_edit_message("main.py", "old", "new")
        ])
        (agent_dir / "claude-code.txt").write_text(trace)

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text=json.dumps({
                    "dimensions": [
                        {"name": "Correctness", "score": 4, "reasoning": "Good"},
                        {"name": "Quality", "score": 5, "reasoning": "Great"},
                    ],
                    "overall_score": 4,
                    "overall_reasoning": "Well done",
                })
            )
        ]

        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            result = run_test_prompt(config, tmp_path, "test_task")

        assert result.task_id == "test_task"
        assert result.error is None
        assert result.overall_score == "4"
        assert len(result.dimension_results) == 2

    @patch("dashboard.utils.judge_test_prompt.os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_api_exception_handling(self, tmp_path):
        config = _make_config()

        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = Exception("Network error")
            mock_anthropic.return_value = mock_client

            result = run_test_prompt(config, tmp_path, "task_err")

        assert result.task_id == "task_err"
        assert result.error is not None
        assert "Network error" in result.error


# =============================================================================
# TestDisplayResult
# =============================================================================


class TestDisplayResult:
    @patch("dashboard.utils.judge_test_prompt.st")
    def test_display_error(self, mock_st):
        result = TestPromptResult(
            task_id="t1",
            dimension_results=(),
            overall_score="N/A",
            overall_reasoning="",
            error="Something went wrong",
        )
        _display_result(result)
        mock_st.error.assert_called_once()
        assert "Something went wrong" in mock_st.error.call_args[0][0]

    @patch("dashboard.utils.judge_test_prompt.st")
    def test_display_successful_result(self, mock_st):
        dims = (
            DimensionResult(name="Correctness", score="4", reasoning="Good"),
        )
        result = TestPromptResult(
            task_id="t1",
            dimension_results=dims,
            overall_score="4",
            overall_reasoning="Well done",
        )

        # Mock context managers for columns and expander
        mock_expander = MagicMock()
        mock_st.expander.return_value.__enter__ = MagicMock(return_value=mock_expander)
        mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)

        mock_col_score = MagicMock()
        mock_col_reasoning = MagicMock()
        mock_st.columns.return_value = (mock_col_score, mock_col_reasoning)
        mock_col_score.__enter__ = MagicMock(return_value=mock_col_score)
        mock_col_score.__exit__ = MagicMock(return_value=False)
        mock_col_reasoning.__enter__ = MagicMock(return_value=mock_col_reasoning)
        mock_col_reasoning.__exit__ = MagicMock(return_value=False)

        _display_result(result)

        # Verify markdown header is rendered
        mock_st.markdown.assert_any_call("#### Results")
        # Verify error was NOT called
        mock_st.error.assert_not_called()

    @patch("dashboard.utils.judge_test_prompt.st")
    def test_display_no_dimensions(self, mock_st):
        result = TestPromptResult(
            task_id="t1",
            dimension_results=(),
            overall_score="3",
            overall_reasoning="Average",
        )

        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        mock_st.columns.return_value = (mock_col1, mock_col2)
        mock_col1.__enter__ = MagicMock(return_value=mock_col1)
        mock_col1.__exit__ = MagicMock(return_value=False)
        mock_col2.__enter__ = MagicMock(return_value=mock_col2)
        mock_col2.__exit__ = MagicMock(return_value=False)

        _display_result(result)
        mock_st.error.assert_not_called()


# =============================================================================
# TestRenderTestPromptSection
# =============================================================================


class TestRenderTestPromptSection:
    @patch("dashboard.utils.judge_test_prompt.st")
    def test_no_runs_directory(self, mock_st, tmp_path):
        nonexistent = str(tmp_path / "nonexistent")
        with patch.dict(os.environ, {"CCB_EXTERNAL_RUNS_DIR": nonexistent}):
            render_test_prompt_section(tmp_path)
        mock_st.info.assert_called()

    @patch("dashboard.utils.judge_test_prompt.st")
    def test_empty_runs_directory(self, mock_st, tmp_path):
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        with patch.dict(os.environ, {"CCB_EXTERNAL_RUNS_DIR": str(runs_dir)}):
            render_test_prompt_section(tmp_path)
        mock_st.info.assert_called()

    @patch("dashboard.utils.judge_test_prompt.st")
    def test_experiments_listed(self, mock_st, tmp_path):
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        (runs_dir / "exp1").mkdir()
        (runs_dir / "exp2").mkdir()

        mock_st.selectbox.return_value = None
        mock_st.session_state = {}

        with patch.dict(os.environ, {"CCB_EXTERNAL_RUNS_DIR": str(runs_dir)}):
            render_test_prompt_section(tmp_path)

        # selectbox should have been called with experiment list
        calls = mock_st.selectbox.call_args_list
        assert len(calls) >= 1
        # Verify experiments were passed
        assert any("exp" in str(arg) for call in calls for arg in call[0])


# =============================================================================
# TestRunAndDisplayResult
# =============================================================================


class TestRunAndDisplayResult:
    @patch("dashboard.utils.judge_test_prompt._display_result")
    @patch("dashboard.utils.judge_test_prompt.run_test_prompt")
    @patch("dashboard.utils.judge_test_prompt.st")
    @patch("dashboard.utils.judge_editor._session_state_to_config")
    def test_calls_run_and_display(
        self, mock_config_fn, mock_st, mock_run, mock_display, tmp_path
    ):
        mock_config_fn.return_value = _make_config()
        mock_st.session_state = {}
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock(return_value=False)

        mock_result = TestPromptResult(
            task_id="t1",
            dimension_results=(),
            overall_score="4",
            overall_reasoning="Good",
        )
        mock_run.return_value = mock_result

        _run_and_display_result(
            project_root=tmp_path,
            task_id="t1",
            task_dir=tmp_path,
        )

        mock_run.assert_called_once()
        mock_display.assert_called_once_with(mock_result)
        assert mock_st.session_state.get("test_prompt_running") is False

    @patch("dashboard.utils.judge_test_prompt._display_result")
    @patch("dashboard.utils.judge_test_prompt.run_test_prompt")
    @patch("dashboard.utils.judge_test_prompt.st")
    @patch("dashboard.utils.judge_editor._session_state_to_config")
    def test_stores_result_in_session_state(
        self, mock_config_fn, mock_st, mock_run, mock_display, tmp_path
    ):
        mock_config_fn.return_value = _make_config()
        mock_st.session_state = {}
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock(return_value=False)

        mock_result = TestPromptResult(
            task_id="stored",
            dimension_results=(),
            overall_score="5",
            overall_reasoning="Stored",
        )
        mock_run.return_value = mock_result

        _run_and_display_result(tmp_path, "stored", tmp_path)

        assert mock_st.session_state["test_prompt_result"] == mock_result


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    def test_full_pipeline_without_api(self, tmp_path):
        """Test the full pipeline from task data to prompt building."""
        # Set up task directory
        config_data = {"task": {"instruction": "Add error handling to parse_input()"}}
        (tmp_path / "config.json").write_text(json.dumps(config_data))
        (tmp_path / "result.json").write_text(json.dumps({"reward": 0.5}))

        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        trace = _make_trace_jsonl([
            _make_edit_message(
                "src/parser.py",
                "def parse_input(s):\n    return int(s)",
                "def parse_input(s):\n    try:\n        return int(s)\n    except ValueError:\n        return None",
            )
        ])
        (agent_dir / "claude-code.txt").write_text(trace)

        # Load task data
        task_data = _load_task_data(tmp_path)
        assert task_data["task_description"] == "Add error handling to parse_input()"
        assert task_data["reward"] == 0.5
        assert "parser.py" in task_data["code_changes"]

        # Build prompt
        judge_config = _make_config()
        prompt = _build_evaluation_prompt(
            judge_config,
            task_data["task_description"],
            task_data["code_changes"],
            task_data["reward"],
        )
        assert "error handling" in prompt
        assert "parser.py" in prompt
        assert "Correctness" in prompt

    def test_parse_and_display_pipeline(self):
        """Test parsing a response and creating a displayable result."""
        config = _make_config()
        response = json.dumps({
            "dimensions": [
                {"name": "Correctness", "score": 5, "reasoning": "Perfect solution"},
                {"name": "Quality", "score": 4, "reasoning": "Clean code"},
            ],
            "overall_score": 5,
            "overall_reasoning": "Excellent implementation",
        })

        result = _parse_judge_response(response, config)
        assert result.error is None
        assert result.overall_score == "5"
        assert result.dimension_results[0].name == "Correctness"
        assert result.dimension_results[0].score == "5"
        assert result.dimension_results[1].name == "Quality"
        assert result.dimension_results[1].score == "4"

    def test_tab_integration_import(self):
        """Verify the import used in analysis_llm_judge.py works."""
        from dashboard.utils.judge_test_prompt import render_test_prompt_section

        assert callable(render_test_prompt_section)
