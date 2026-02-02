"""Tests for dashboard/views/results_explorer.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dashboard.views.results_explorer import (
    _build_display_dataframe,
    _extract_judge_score,
    _flatten_trials,
    _load_experiment_metrics,
)


def _make_trial(
    trial_id: str = "trial-001",
    task_name: str = "task-a",
    benchmark: str = "big_code_mcp",
    agent_config: str = "BASELINE",
    reward: float | None = 1.0,
    pass_fail: str = "pass",
    duration_seconds: float | None = 120.0,
    input_tokens: int = 5000,
    output_tokens: int = 1000,
    cached_tokens: int = 200,
    tool_utilization: dict | None = None,
    judge_scores: dict | None = None,
) -> dict:
    trial = {
        "trial_id": trial_id,
        "task_name": task_name,
        "benchmark": benchmark,
        "agent_config": agent_config,
        "reward": reward,
        "pass_fail": pass_fail,
        "duration_seconds": duration_seconds,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "tool_utilization": tool_utilization or {
            "mcp_calls": 5,
            "deep_search_calls": 2,
            "total_tool_calls": 20,
            "context_fill_rate": 0.45,
            "tool_calls_by_name": {"Read": 10, "mcp__sg__search": 5},
        },
    }
    if judge_scores is not None:
        trial["judge_scores"] = judge_scores
    return trial


def _make_categories(trials_per_experiment: list[list[dict]] | None = None) -> list[dict]:
    """Build a categories list matching the experiment_metrics.json schema."""
    if trials_per_experiment is None:
        trials_per_experiment = [[_make_trial()]]

    experiments = []
    for i, trials in enumerate(trials_per_experiment):
        experiments.append({
            "experiment_id": f"exp-{i:03d}",
            "trials": trials,
        })

    return [{
        "run_category": "official",
        "experiments": experiments,
    }]


# --------------------------------------------------------------------------
# _load_experiment_metrics
# --------------------------------------------------------------------------

class TestLoadExperimentMetrics:
    def test_loads_valid_json(self, tmp_path: Path) -> None:
        categories = _make_categories()
        (tmp_path / "experiment_metrics.json").write_text(json.dumps(categories))
        result = _load_experiment_metrics(tmp_path)
        assert len(result) == 1
        assert result[0]["run_category"] == "official"

    def test_returns_empty_on_missing_file(self, tmp_path: Path) -> None:
        result = _load_experiment_metrics(tmp_path)
        assert result == []

    def test_returns_empty_on_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "experiment_metrics.json").write_text("{bad json")
        result = _load_experiment_metrics(tmp_path)
        assert result == []

    def test_returns_empty_on_non_list(self, tmp_path: Path) -> None:
        (tmp_path / "experiment_metrics.json").write_text(json.dumps({"not": "a list"}))
        result = _load_experiment_metrics(tmp_path)
        assert result == []


# --------------------------------------------------------------------------
# _flatten_trials
# --------------------------------------------------------------------------

class TestFlattenTrials:
    def test_single_trial(self) -> None:
        categories = _make_categories([[_make_trial(task_name="my-task")]])
        flat = _flatten_trials(categories)
        assert len(flat) == 1
        assert flat[0]["task_name"] == "my-task"
        assert flat[0]["run_category"] == "official"
        assert flat[0]["experiment_id"] == "exp-000"

    def test_multiple_categories_and_experiments(self) -> None:
        categories = [
            {
                "run_category": "official",
                "experiments": [
                    {"experiment_id": "e1", "trials": [_make_trial(trial_id="t1")]},
                    {"experiment_id": "e2", "trials": [_make_trial(trial_id="t2")]},
                ],
            },
            {
                "run_category": "experiment",
                "experiments": [
                    {"experiment_id": "e3", "trials": [
                        _make_trial(trial_id="t3"),
                        _make_trial(trial_id="t4"),
                    ]},
                ],
            },
        ]
        flat = _flatten_trials(categories)
        assert len(flat) == 4
        assert {t["trial_id"] for t in flat} == {"t1", "t2", "t3", "t4"}

    def test_empty_categories(self) -> None:
        assert _flatten_trials([]) == []

    def test_empty_experiments(self) -> None:
        categories = [{"run_category": "official", "experiments": []}]
        assert _flatten_trials(categories) == []


# --------------------------------------------------------------------------
# _extract_judge_score
# --------------------------------------------------------------------------

class TestExtractJudgeScore:
    def test_no_judge_scores(self) -> None:
        assert _extract_judge_score({}) is None

    def test_none_judge_scores(self) -> None:
        assert _extract_judge_score({"judge_scores": None}) is None

    def test_numeric_judge_score(self) -> None:
        assert _extract_judge_score({"judge_scores": 0.85}) == 0.85

    def test_dict_with_dimensions(self) -> None:
        trial = {
            "judge_scores": {
                "dimensions": {
                    "correctness": {"score": 0.8},
                    "completeness": {"score": 0.6},
                },
            },
        }
        result = _extract_judge_score(trial)
        assert result is not None
        assert abs(result - 0.7) < 0.01

    def test_dict_with_top_level_score(self) -> None:
        trial = {"judge_scores": {"score": 0.9}}
        result = _extract_judge_score(trial)
        assert result == 0.9

    def test_dict_with_empty_dimensions(self) -> None:
        trial = {"judge_scores": {"dimensions": {}, "score": 0.5}}
        assert _extract_judge_score(trial) == 0.5


# --------------------------------------------------------------------------
# _build_display_dataframe
# --------------------------------------------------------------------------

class TestBuildDisplayDataframe:
    def test_builds_df_from_flat_trials(self) -> None:
        trials = [
            {
                **_make_trial(task_name="t1", reward=1.0),
                "run_category": "official",
                "experiment_id": "e1",
            },
            {
                **_make_trial(task_name="t2", reward=0.0, pass_fail="fail", agent_config="MCP_FULL"),
                "run_category": "official",
                "experiment_id": "e1",
            },
        ]
        df = _build_display_dataframe(trials)
        assert len(df) == 2
        assert list(df["task_name"]) == ["t1", "t2"]
        assert list(df["config"]) == ["BASELINE", "MCP_FULL"]

    def test_empty_trials_returns_empty_df(self) -> None:
        df = _build_display_dataframe([])
        assert df.empty

    def test_handles_missing_tool_utilization(self) -> None:
        trial = {
            **_make_trial(),
            "run_category": "official",
            "experiment_id": "e1",
        }
        trial["tool_utilization"] = None
        df = _build_display_dataframe([trial])
        assert len(df) == 1
        assert df.iloc[0]["mcp_calls"] == 0

    def test_includes_judge_score_when_present(self) -> None:
        trial = {
            **_make_trial(),
            "run_category": "official",
            "experiment_id": "e1",
            "judge_scores": 0.75,
        }
        df = _build_display_dataframe([trial])
        assert df.iloc[0]["judge_score"] == 0.75

    def test_judge_score_none_when_absent(self) -> None:
        trial = {
            **_make_trial(),
            "run_category": "official",
            "experiment_id": "e1",
        }
        df = _build_display_dataframe([trial])
        assert df.iloc[0]["judge_score"] is None
