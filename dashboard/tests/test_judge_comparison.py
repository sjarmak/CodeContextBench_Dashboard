"""Tests for judge_comparison utility."""

import json
from pathlib import Path

import pytest

from dashboard.utils.judge_comparison import (
    ComparativeReport,
    TaskPairJudgeResult,
    TaskPairMetrics,
    build_comparative_report,
    compute_pair_metrics,
    find_matched_pairs,
    load_comparative_reports,
    save_comparative_report,
)


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

def _make_run(mode: str, exp: str = "exp1", reward: float = 0.5, **kwargs):
    """Create a minimal run dict for testing."""
    base = {
        "exp_name": exp,
        "folder": "official",
        "mode": mode,
        "mode_label": mode,
        "reward": reward,
        "status": "completed",
        "input_tokens": 5000,
        "output_tokens": 1000,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "duration": 120.0,
        "instance_dir": "/tmp/fake",
        "model": "claude-haiku-4-5",
    }
    return {**base, **kwargs}


# ---------------------------------------------------------------------------
# find_matched_pairs
# ---------------------------------------------------------------------------

class TestFindMatchedPairs:
    def test_basic_matching(self):
        tasks = {
            "task_a": [_make_run("baseline"), _make_run("deepsearch")],
            "task_b": [_make_run("baseline")],  # No variant
        }
        pairs = find_matched_pairs(tasks, "bench")
        assert len(pairs) == 1
        assert pairs[0][0] == "task_a"
        assert pairs[0][1]["mode"] == "baseline"
        assert pairs[0][2]["mode"] == "deepsearch"

    def test_same_experiment_preferred(self):
        tasks = {
            "task_a": [
                _make_run("baseline", exp="exp1"),
                _make_run("baseline", exp="exp2"),
                _make_run("deepsearch", exp="exp2"),
            ],
        }
        pairs = find_matched_pairs(tasks, "bench")
        assert len(pairs) == 1
        # Should prefer exp2 baseline since variant is exp2
        assert pairs[0][1]["exp_name"] == "exp2"

    def test_cross_experiment_fallback(self):
        tasks = {
            "task_a": [
                _make_run("baseline", exp="exp1"),
                _make_run("deepsearch", exp="exp2"),
            ],
        }
        pairs = find_matched_pairs(tasks, "bench")
        assert len(pairs) == 1
        assert pairs[0][1]["exp_name"] == "exp1"
        assert pairs[0][2]["exp_name"] == "exp2"

    def test_no_match_when_only_baseline(self):
        tasks = {"task_a": [_make_run("baseline")]}
        pairs = find_matched_pairs(tasks, "bench")
        assert len(pairs) == 0

    def test_no_match_when_only_variant(self):
        tasks = {"task_a": [_make_run("deepsearch")]}
        pairs = find_matched_pairs(tasks, "bench")
        assert len(pairs) == 0

    def test_multiple_tasks(self):
        tasks = {
            "task_a": [_make_run("baseline"), _make_run("deepsearch")],
            "task_b": [_make_run("baseline"), _make_run("sourcegraph")],
            "task_c": [_make_run("single")],  # No variant
        }
        pairs = find_matched_pairs(tasks, "bench")
        assert len(pairs) == 2
        names = [p[0] for p in pairs]
        assert "task_a" in names
        assert "task_b" in names

    def test_single_mode_treated_as_baseline(self):
        tasks = {
            "task_a": [_make_run("single"), _make_run("deepsearch")],
        }
        pairs = find_matched_pairs(tasks, "bench")
        assert len(pairs) == 1
        assert pairs[0][1]["mode"] == "single"


# ---------------------------------------------------------------------------
# compute_pair_metrics
# ---------------------------------------------------------------------------

class TestComputePairMetrics:
    def test_basic_deltas(self):
        baseline = _make_run("baseline", reward=0.5, input_tokens=5000, duration=100.0)
        variant = _make_run("deepsearch", reward=1.0, input_tokens=15000, duration=200.0)

        m = compute_pair_metrics("task_a", baseline, variant)

        assert isinstance(m, TaskPairMetrics)
        assert m.task_name == "task_a"
        assert m.reward_delta == pytest.approx(0.5)
        assert m.token_delta == 10000
        assert m.duration_delta == pytest.approx(100.0)

    def test_none_duration(self):
        baseline = _make_run("baseline", duration=None)
        variant = _make_run("deepsearch", duration=150.0)

        m = compute_pair_metrics("task_a", baseline, variant)
        assert m.duration_delta is None

    def test_both_none_duration(self):
        baseline = _make_run("baseline", duration=None)
        variant = _make_run("deepsearch", duration=None)

        m = compute_pair_metrics("task_a", baseline, variant)
        assert m.duration_delta is None

    def test_negative_reward_delta(self):
        baseline = _make_run("baseline", reward=1.0)
        variant = _make_run("deepsearch", reward=0.0)

        m = compute_pair_metrics("task_a", baseline, variant)
        assert m.reward_delta == pytest.approx(-1.0)

    def test_mcp_call_count(self):
        baseline = _make_run("baseline", mcp_tool_count=0)
        variant = _make_run("deepsearch", mcp_tool_count=12)

        m = compute_pair_metrics("task_a", baseline, variant)
        assert m.baseline_mcp_calls == 0
        assert m.variant_mcp_calls == 12

    def test_frozen(self):
        m = compute_pair_metrics(
            "t", _make_run("baseline"), _make_run("deepsearch")
        )
        with pytest.raises(AttributeError):
            m.reward_delta = 0.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# build_comparative_report
# ---------------------------------------------------------------------------

class TestBuildComparativeReport:
    def _make_pair_result(self, task: str, delta: float = 0.1):
        return TaskPairJudgeResult(
            task_name=task,
            dimensions=("correctness",),
            baseline_scores={"correctness": 0.5},
            variant_scores={"correctness": 0.5 + delta},
            score_deltas={"correctness": delta},
            baseline_reasoning={"correctness": "ok"},
            variant_reasoning={"correctness": "better"},
            judge_model="haiku",
        )

    def _make_pair_metrics(self, task: str, reward_delta: float = 0.1):
        return TaskPairMetrics(
            task_name=task,
            baseline_reward=0.5,
            variant_reward=0.5 + reward_delta,
            reward_delta=reward_delta,
            baseline_input_tokens=5000,
            variant_input_tokens=10000,
            token_delta=5000,
            baseline_duration=100.0,
            variant_duration=200.0,
            duration_delta=100.0,
            baseline_mcp_calls=0,
            variant_mcp_calls=5,
        )

    def test_summary_stats(self):
        results = [
            self._make_pair_result("t1", delta=0.2),
            self._make_pair_result("t2", delta=-0.1),
            self._make_pair_result("t3", delta=0.0),
        ]
        metrics = [
            self._make_pair_metrics("t1", reward_delta=0.5),
            self._make_pair_metrics("t2", reward_delta=-0.5),
            self._make_pair_metrics("t3", reward_delta=0.0),
        ]

        report = build_comparative_report("bench", results, metrics, "haiku", ["correctness"])

        assert isinstance(report, ComparativeReport)
        assert report.benchmark == "bench"
        assert report.summary["variant_wins"] == 1
        assert report.summary["variant_losses"] == 1
        assert report.summary["ties"] == 1
        assert report.summary["mean_reward_delta"] == pytest.approx(0.0)
        assert "correctness" in report.summary["mean_score_deltas"]

    def test_error_handling_in_summary(self):
        results = [
            TaskPairJudgeResult(
                task_name="t1",
                dimensions=("correctness",),
                baseline_scores={},
                variant_scores={},
                score_deltas={},
                baseline_reasoning={},
                variant_reasoning={},
                judge_model="haiku",
                error="API error",
            )
        ]
        metrics = [self._make_pair_metrics("t1")]

        report = build_comparative_report("bench", results, metrics, "haiku", ["correctness"])
        assert report.summary["judge_errors"] == 1


# ---------------------------------------------------------------------------
# save / load comparative reports
# ---------------------------------------------------------------------------

class TestSaveLoadReports:
    def test_round_trip(self, tmp_path):
        report = ComparativeReport(
            benchmark="LoCoBench",
            timestamp="2026-02-02T14:00:00",
            judge_model="haiku",
            dimensions=("correctness",),
            pairs=(),
            metrics=(),
            summary={"variant_wins": 1, "ties": 0, "variant_losses": 0},
        )

        saved = save_comparative_report(report, tmp_path)
        assert saved.exists()
        assert "LoCoBench" in saved.name
        assert "_comparative.json" in saved.name

        loaded = load_comparative_reports(tmp_path)
        assert len(loaded) == 1
        assert loaded[0]["benchmark"] == "LoCoBench"
        assert loaded[0]["summary"]["variant_wins"] == 1

    def test_empty_dir(self, tmp_path):
        loaded = load_comparative_reports(tmp_path)
        assert loaded == []
