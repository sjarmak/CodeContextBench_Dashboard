"""Unit tests for scripts/ccb_pipeline/extract.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ccb_pipeline.extract import (
    ExperimentData,
    ExtractionResult,
    TrialMetrics,
    extract_metrics,
    main,
    _classify_pass_fail,
    _extract_benchmark_name,
    _extract_reward,
    _extract_task_name,
    _extract_timing,
    _extract_tokens_from_result,
    _extract_trial,
    _find_trials,
    _is_trial_dir,
    _tool_utilization_to_dict,
)
from src.ingest.config_detector import AgentConfig
from src.ingest.transcript_tool_extractor import ToolUtilizationMetrics


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_result_json(
    trial_dir: Path,
    *,
    task_name: str = "test-task-001",
    reward: float = 1.0,
    started_at: str = "2026-01-31T13:04:54.109208",
    finished_at: str = "2026-01-31T13:18:56.677395",
    agent_started: str = "2026-01-31T13:06:43.029615",
    agent_finished: str = "2026-01-31T13:18:42.928355",
    input_tokens: int = 5000,
    output_tokens: int = 1000,
    cache_tokens: int = 200,
) -> None:
    data = {
        "task_name": task_name,
        "trial_name": trial_dir.name,
        "task_id": {"path": f"/benchmarks/big_code_mcp/{task_name}"},
        "agent_info": {"name": "claude-code"},
        "agent_result": {
            "n_input_tokens": input_tokens,
            "n_output_tokens": output_tokens,
            "n_cache_tokens": cache_tokens,
        },
        "verifier_result": {"rewards": {"reward": reward}},
        "started_at": started_at,
        "finished_at": finished_at,
        "agent_execution": {
            "started_at": agent_started,
            "finished_at": agent_finished,
        },
        "config": {
            "task": {
                "path": f"/benchmarks/big_code_mcp/{task_name}",
            }
        },
    }
    trial_dir.mkdir(parents=True, exist_ok=True)
    (trial_dir / "result.json").write_text(json.dumps(data), encoding="utf-8")


def _make_config_json(trial_dir: Path, task_path: str) -> None:
    data = {"task": {"path": task_path}}
    trial_dir.mkdir(parents=True, exist_ok=True)
    (trial_dir / "config.json").write_text(json.dumps(data), encoding="utf-8")


def _make_reward_txt(trial_dir: Path, reward: float) -> None:
    verifier_dir = trial_dir / "verifier"
    verifier_dir.mkdir(parents=True, exist_ok=True)
    (verifier_dir / "reward.txt").write_text(str(reward), encoding="utf-8")


def _make_task_metrics_json(
    trial_dir: Path,
    *,
    benchmark: str = "ccb_swebenchpro",
    input_tokens: int = 3000,
    output_tokens: int = 500,
    cached_tokens: int = 100,
) -> None:
    data = {
        "benchmark": benchmark,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
    }
    trial_dir.mkdir(parents=True, exist_ok=True)
    (trial_dir / "task_metrics.json").write_text(json.dumps(data), encoding="utf-8")


def _make_transcript(trial_dir: Path, lines: list[str] | None = None) -> None:
    agent_dir = trial_dir / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines) if lines else ""
    (agent_dir / "claude-code.txt").write_text(content, encoding="utf-8")


def _make_mcp_json(trial_dir: Path, data: dict) -> None:
    agent_dir = trial_dir / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / ".mcp.json").write_text(json.dumps(data), encoding="utf-8")


def _build_full_trial(
    parent: Path,
    trial_name: str = "test-task-001__abc123",
    *,
    task_name: str = "test-task-001",
    reward: float = 1.0,
    benchmark_path: str = "/benchmarks/big_code_mcp/test-task-001",
) -> Path:
    trial_dir = parent / trial_name
    _make_result_json(trial_dir, task_name=task_name, reward=reward)
    _make_transcript(trial_dir)
    return trial_dir


# ---------------------------------------------------------------------------
# Tests: _classify_pass_fail
# ---------------------------------------------------------------------------


class TestClassifyPassFail:
    def test_pass(self) -> None:
        assert _classify_pass_fail(1.0) == "pass"

    def test_fail(self) -> None:
        assert _classify_pass_fail(0.0) == "fail"

    def test_partial(self) -> None:
        assert _classify_pass_fail(0.5) == "partial"

    def test_unknown(self) -> None:
        assert _classify_pass_fail(None) == "unknown"

    def test_above_one_is_pass(self) -> None:
        assert _classify_pass_fail(1.5) == "pass"


# ---------------------------------------------------------------------------
# Tests: _extract_reward
# ---------------------------------------------------------------------------


class TestExtractReward:
    def test_from_reward_txt(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        trial.mkdir()
        _make_reward_txt(trial, 0.75)
        assert _extract_reward(trial) == pytest.approx(0.75)

    def test_from_result_json(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        _make_result_json(trial, reward=0.5)
        assert _extract_reward(trial) == pytest.approx(0.5)

    def test_reward_txt_takes_precedence(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        _make_result_json(trial, reward=0.5)
        _make_reward_txt(trial, 1.0)
        assert _extract_reward(trial) == pytest.approx(1.0)

    def test_missing_both_returns_none(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        trial.mkdir()
        assert _extract_reward(trial) is None

    def test_malformed_reward_txt(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        trial.mkdir()
        verifier_dir = trial / "verifier"
        verifier_dir.mkdir()
        (verifier_dir / "reward.txt").write_text("not-a-number", encoding="utf-8")
        assert _extract_reward(trial) is None


# ---------------------------------------------------------------------------
# Tests: _extract_timing
# ---------------------------------------------------------------------------


class TestExtractTiming:
    def test_agent_execution_timing(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        _make_result_json(
            trial,
            agent_started="2026-01-31T13:00:00.000000",
            agent_finished="2026-01-31T13:10:00.000000",
        )
        duration = _extract_timing(trial)
        assert duration is not None
        assert duration == pytest.approx(600.0)

    def test_top_level_timing_fallback(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        trial.mkdir()
        data = {
            "started_at": "2026-01-31T13:00:00.000000",
            "finished_at": "2026-01-31T13:05:00.000000",
        }
        (trial / "result.json").write_text(json.dumps(data), encoding="utf-8")
        duration = _extract_timing(trial)
        assert duration is not None
        assert duration == pytest.approx(300.0)

    def test_no_result_json(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        trial.mkdir()
        assert _extract_timing(trial) is None


# ---------------------------------------------------------------------------
# Tests: _extract_tokens_from_result
# ---------------------------------------------------------------------------


class TestExtractTokens:
    def test_from_task_metrics(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        _make_task_metrics_json(trial, input_tokens=3000, output_tokens=500, cached_tokens=100)
        inp, out, cached = _extract_tokens_from_result(trial)
        assert inp == 3000
        assert out == 500
        assert cached == 100

    def test_from_result_json(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        _make_result_json(trial, input_tokens=5000, output_tokens=1000, cache_tokens=200)
        inp, out, cached = _extract_tokens_from_result(trial)
        assert inp == 5000
        assert out == 1000
        # n_cache_tokens in result.json
        assert cached == 200

    def test_task_metrics_takes_precedence(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        _make_result_json(trial, input_tokens=5000, output_tokens=1000)
        _make_task_metrics_json(trial, input_tokens=3000, output_tokens=500, cached_tokens=100)
        inp, out, cached = _extract_tokens_from_result(trial)
        assert inp == 3000
        assert out == 500

    def test_no_files_returns_zeros(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        trial.mkdir()
        inp, out, cached = _extract_tokens_from_result(trial)
        assert (inp, out, cached) == (0, 0, 0)


# ---------------------------------------------------------------------------
# Tests: _extract_benchmark_name
# ---------------------------------------------------------------------------


class TestExtractBenchmark:
    def test_from_task_metrics(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        _make_task_metrics_json(trial, benchmark="ccb_swebenchpro")
        assert _extract_benchmark_name(trial) == "ccb_swebenchpro"

    def test_from_config_json(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        _make_config_json(trial, "/home/user/benchmarks/big_code_mcp/big-code-k8s-001")
        assert _extract_benchmark_name(trial) == "big_code_mcp"

    def test_unknown_fallback(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        trial.mkdir()
        assert _extract_benchmark_name(trial) == "unknown"


# ---------------------------------------------------------------------------
# Tests: _extract_task_name
# ---------------------------------------------------------------------------


class TestExtractTaskName:
    def test_from_result_json(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        _make_result_json(trial, task_name="big-code-k8s-001")
        assert _extract_task_name(trial) == "big-code-k8s-001"

    def test_from_config_json(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        _make_config_json(trial, "/benchmarks/big_code_mcp/big-code-k8s-001")
        assert _extract_task_name(trial) == "big-code-k8s-001"

    def test_fallback_to_dirname(self, tmp_path: Path) -> None:
        trial = tmp_path / "my-trial-dir"
        trial.mkdir()
        assert _extract_task_name(trial) == "my-trial-dir"


# ---------------------------------------------------------------------------
# Tests: _is_trial_dir and _find_trials
# ---------------------------------------------------------------------------


class TestTrialDiscovery:
    def test_is_trial_dir_true(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        _make_result_json(trial)
        assert _is_trial_dir(trial) is True

    def test_is_trial_dir_false(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        assert _is_trial_dir(empty) is False

    def test_find_trials_nested(self, tmp_path: Path) -> None:
        # Simulate: config_type / timestamp / trial
        config_dir = tmp_path / "baseline" / "2026-01-31__13-04-54"
        config_dir.mkdir(parents=True)
        t1 = config_dir / "trial1"
        _make_result_json(t1)
        t2 = config_dir / "trial2"
        _make_result_json(t2)

        trials = _find_trials(tmp_path)
        assert len(trials) == 2
        names = {t.name for t in trials}
        assert names == {"trial1", "trial2"}

    def test_find_trials_empty(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        assert _find_trials(empty) == []

    def test_find_trials_nonexistent(self, tmp_path: Path) -> None:
        assert _find_trials(tmp_path / "nope") == []


# ---------------------------------------------------------------------------
# Tests: _tool_utilization_to_dict
# ---------------------------------------------------------------------------


class TestToolUtilizationDict:
    def test_empty_metrics(self) -> None:
        metrics = ToolUtilizationMetrics()
        result = _tool_utilization_to_dict(metrics)
        assert isinstance(result, dict)
        assert result["tool_calls_by_name"] == {}
        assert result["search_queries"] == []
        assert result["mcp_calls"] == 0

    def test_with_data(self) -> None:
        metrics = ToolUtilizationMetrics(
            tool_calls_by_name=(("Read", 5), ("Bash", 3)),
            mcp_calls=2,
            total_tool_calls=10,
        )
        result = _tool_utilization_to_dict(metrics)
        assert result["tool_calls_by_name"] == {"Read": 5, "Bash": 3}
        assert result["mcp_calls"] == 2


# ---------------------------------------------------------------------------
# Tests: _extract_trial
# ---------------------------------------------------------------------------


class TestExtractTrial:
    def test_full_trial(self, tmp_path: Path) -> None:
        trial = tmp_path / "baseline" / "2026-01-31" / "test-task__abc"
        _make_result_json(trial, task_name="test-task", reward=1.0)
        _make_transcript(trial)

        metrics = _extract_trial(trial)
        assert isinstance(metrics, TrialMetrics)
        assert metrics.task_name == "test-task"
        assert metrics.reward == pytest.approx(1.0)
        assert metrics.pass_fail == "pass"
        assert metrics.agent_config == AgentConfig.BASELINE.value
        assert isinstance(metrics.tool_utilization, dict)

    def test_mcp_full_config(self, tmp_path: Path) -> None:
        trial = tmp_path / "trial1"
        _make_result_json(trial)
        _make_transcript(trial)
        _make_mcp_json(trial, {
            "mcpServers": {
                "sourcegraph": {"url": "https://sg.example.com/.api/mcp/deepsearch"}
            }
        })

        metrics = _extract_trial(trial)
        assert metrics.agent_config == AgentConfig.MCP_FULL.value


# ---------------------------------------------------------------------------
# Tests: extract_metrics (full pipeline)
# ---------------------------------------------------------------------------


class TestExtractMetrics:
    def test_full_extraction(self, tmp_path: Path) -> None:
        # Build: runs_dir / official / experiment1 / baseline / timestamp / trial
        experiment = tmp_path / "official" / "bigcode_test"
        timestamp = experiment / "baseline" / "2026-01-31__13-00-00"
        timestamp.mkdir(parents=True)

        t1 = timestamp / "task-001__abc"
        _make_result_json(t1, task_name="task-001", reward=1.0)
        _make_transcript(t1)

        t2 = timestamp / "task-002__def"
        _make_result_json(t2, task_name="task-002", reward=0.0)
        _make_transcript(t2)

        categories = extract_metrics(tmp_path)
        assert len(categories) == 1
        assert categories[0]["run_category"] == "official"
        assert len(categories[0]["experiments"]) == 1
        assert categories[0]["experiments"][0]["experiment_id"] == "bigcode_test"
        assert len(categories[0]["experiments"][0]["trials"]) == 2

    def test_multiple_categories(self, tmp_path: Path) -> None:
        for cat in ("official", "experiment"):
            exp = tmp_path / cat / "exp1" / "baseline" / "ts"
            exp.mkdir(parents=True)
            _build_full_trial(exp, "trial__abc")

        categories = extract_metrics(tmp_path)
        cat_names = {c["run_category"] for c in categories}
        assert cat_names == {"official", "experiment"}

    def test_empty_runs_dir(self, tmp_path: Path) -> None:
        categories = extract_metrics(tmp_path)
        assert categories == []

    def test_skips_incomplete_trials(self, tmp_path: Path) -> None:
        # Experiment with one complete and one incomplete trial
        experiment = tmp_path / "official" / "exp1" / "baseline" / "ts"
        experiment.mkdir(parents=True)
        _build_full_trial(experiment, "complete__abc")

        incomplete = experiment / "incomplete__xyz"
        incomplete.mkdir()
        # No result.json -> not discovered as trial

        categories = extract_metrics(tmp_path)
        assert len(categories[0]["experiments"][0]["trials"]) == 1


# ---------------------------------------------------------------------------
# Tests: CLI main()
# ---------------------------------------------------------------------------


class TestMain:
    def test_with_valid_runs_dir(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        experiment = runs_dir / "official" / "exp1" / "baseline" / "ts"
        experiment.mkdir(parents=True)
        _build_full_trial(experiment, "trial__abc")

        output_path = tmp_path / "output" / "metrics.json"
        exit_code = main([
            "--runs-dir", str(runs_dir),
            "--output", str(output_path),
        ])

        assert exit_code == 0
        assert output_path.is_file()

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 1

    def test_nonexistent_runs_dir(self, tmp_path: Path) -> None:
        exit_code = main([
            "--runs-dir", str(tmp_path / "nonexistent"),
            "--output", str(tmp_path / "out.json"),
        ])
        assert exit_code == 1

    def test_creates_output_directory(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        experiment = runs_dir / "official" / "exp1" / "baseline" / "ts"
        experiment.mkdir(parents=True)
        _build_full_trial(experiment, "trial__abc")

        output_path = tmp_path / "nested" / "deep" / "metrics.json"
        exit_code = main([
            "--runs-dir", str(runs_dir),
            "--output", str(output_path),
        ])
        assert exit_code == 0
        assert output_path.is_file()


# ---------------------------------------------------------------------------
# Tests: Frozen dataclasses
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_trial_metrics_frozen(self) -> None:
        m = TrialMetrics(
            trial_id="t1",
            task_name="task",
            benchmark="bench",
            agent_config="BASELINE",
            reward=1.0,
            pass_fail="pass",
            duration_seconds=100.0,
            input_tokens=500,
            output_tokens=100,
            cached_tokens=50,
            tool_utilization={},
        )
        with pytest.raises(AttributeError):
            m.reward = 0.5  # type: ignore[misc]

    def test_experiment_data_frozen(self) -> None:
        e = ExperimentData(experiment_id="exp1", trials=())
        with pytest.raises(AttributeError):
            e.experiment_id = "exp2"  # type: ignore[misc]

    def test_extraction_result_frozen(self) -> None:
        r = ExtractionResult(run_category="official", experiments=())
        with pytest.raises(AttributeError):
            r.run_category = "test"  # type: ignore[misc]
