"""Tests for the experiment comparator task alignment module."""

import json
import pytest
from pathlib import Path

from src.analysis.experiment_comparator import (
    TaskAligner,
    AlignmentResult,
    RewardNormalizer,
    BootstrapResult,
    CategoryBreakdown,
    ToolCorrelation,
    pairwise_bootstrap,
    compute_category_breakdown,
    compute_tool_correlation,
    extract_task_category,
)


@pytest.fixture
def aligner():
    """Create a TaskAligner instance."""
    return TaskAligner()


def _make_task_dir(parent: Path, dir_name: str, task_path: str | None = None) -> Path:
    """Helper: create a task directory with optional config.json.

    Args:
        parent: Parent experiment directory.
        dir_name: Directory name for the task.
        task_path: If set, write config.json with this task.path value.

    Returns:
        The created task directory path.
    """
    task_dir = parent / dir_name
    task_dir.mkdir(parents=True, exist_ok=True)

    if task_path is not None:
        config = {"task": {"path": task_path}}
        (task_dir / "config.json").write_text(json.dumps(config))

    return task_dir


def _make_result(task_dir: Path, reward: float | None = None, **extra) -> None:
    """Helper: write a result.json to a task directory."""
    data = {
        "task_name": task_dir.name,
        "started_at": "2025-12-17T21:03:06.052742",
        "finished_at": "2025-12-17T21:06:18.968956",
        "agent_info": {"name": "claude-code"},
        "agent_result": {"n_input_tokens": 100},
        "verifier_result": {
            "rewards": {"reward": reward},
        } if reward is not None else None,
        "exception_info": None,
        **extra,
    }
    (task_dir / "result.json").write_text(json.dumps(data))


class TestTaskAlignerIdenticalSets:
    """Test alignment when both directories have the same tasks."""

    def test_identical_tasks_all_common(self, tmp_path, aligner):
        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"

        for name in ["task-a", "task-b", "task-c"]:
            _make_task_dir(baseline, f"{name}__abc", task_path=f"benchmarks/test/{name}")
            _make_task_dir(treatment, f"{name}__xyz", task_path=f"benchmarks/test/{name}")

        result = aligner.align(baseline, treatment)

        assert sorted(result.common_tasks) == ["task-a", "task-b", "task-c"]
        assert result.baseline_only == []
        assert result.treatment_only == []
        assert result.total_baseline == 3
        assert result.total_treatment == 3


class TestTaskAlignerDisjointSets:
    """Test alignment when directories have no tasks in common."""

    def test_disjoint_tasks_no_overlap(self, tmp_path, aligner):
        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"

        _make_task_dir(baseline, "alpha__abc", task_path="benchmarks/test/alpha")
        _make_task_dir(baseline, "beta__def", task_path="benchmarks/test/beta")
        _make_task_dir(treatment, "gamma__ghi", task_path="benchmarks/test/gamma")

        result = aligner.align(baseline, treatment)

        assert result.common_tasks == []
        assert sorted(result.baseline_only) == ["alpha", "beta"]
        assert result.treatment_only == ["gamma"]
        assert result.total_baseline == 2
        assert result.total_treatment == 1


class TestTaskAlignerPartialOverlap:
    """Test alignment with partial task overlap."""

    def test_partial_overlap(self, tmp_path, aligner):
        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"

        _make_task_dir(baseline, "shared__abc", task_path="benchmarks/test/shared")
        _make_task_dir(baseline, "base-only__def", task_path="benchmarks/test/base-only")
        _make_task_dir(treatment, "shared__xyz", task_path="benchmarks/test/shared")
        _make_task_dir(treatment, "treat-only__ghi", task_path="benchmarks/test/treat-only")

        result = aligner.align(baseline, treatment)

        assert result.common_tasks == ["shared"]
        assert result.baseline_only == ["base-only"]
        assert result.treatment_only == ["treat-only"]
        assert result.total_baseline == 2
        assert result.total_treatment == 2


class TestTaskAlignerMissingConfig:
    """Test alignment when config.json is missing."""

    def test_falls_back_to_directory_name(self, tmp_path, aligner):
        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"

        # No config.json — should strip hash suffix and use dir name
        task_b = baseline / "mytask__abc123"
        task_b.mkdir(parents=True)
        task_t = treatment / "mytask__xyz789"
        task_t.mkdir(parents=True)

        result = aligner.align(baseline, treatment)

        assert result.common_tasks == ["mytask"]

    def test_no_hash_suffix_uses_full_name(self, tmp_path, aligner):
        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"

        (baseline / "plain-task").mkdir(parents=True)
        (treatment / "plain-task").mkdir(parents=True)

        result = aligner.align(baseline, treatment)

        assert result.common_tasks == ["plain-task"]


class TestTaskAlignerNullFields:
    """Test handling of null fields in result.json."""

    def test_load_result_with_null_fields(self, tmp_path, aligner):
        task_dir = tmp_path / "task-x__abc"
        task_dir.mkdir(parents=True)

        data = {
            "task_name": None,
            "started_at": None,
            "finished_at": None,
            "agent_info": None,
            "agent_result": None,
            "verifier_result": None,
            "exception_info": None,
        }
        (task_dir / "result.json").write_text(json.dumps(data))

        result = aligner.load_result(task_dir)

        assert result["task_name"] == ""
        assert result["started_at"] == ""
        assert result["finished_at"] == ""
        assert result["agent_info"] == {}
        assert result["agent_result"] == {}
        assert result["verifier_result"] == {}
        assert result["exception_info"] is None

    def test_load_result_missing_file(self, tmp_path, aligner):
        task_dir = tmp_path / "no-result"
        task_dir.mkdir(parents=True)

        result = aligner.load_result(task_dir)
        assert result == {}

    def test_load_result_invalid_json(self, tmp_path, aligner):
        task_dir = tmp_path / "bad-json"
        task_dir.mkdir(parents=True)
        (task_dir / "result.json").write_text("not valid json {{{")

        result = aligner.load_result(task_dir)
        assert result == {}

    def test_load_reward_with_valid_data(self, tmp_path, aligner):
        task_dir = tmp_path / "reward-task"
        task_dir.mkdir(parents=True)
        _make_result(task_dir, reward=0.75)

        reward = aligner.load_reward(task_dir)
        assert reward == pytest.approx(0.75)

    def test_load_reward_with_null_verifier(self, tmp_path, aligner):
        task_dir = tmp_path / "null-verifier"
        task_dir.mkdir(parents=True)

        data = {"verifier_result": None}
        (task_dir / "result.json").write_text(json.dumps(data))

        reward = aligner.load_reward(task_dir)
        assert reward is None

    def test_load_reward_missing_result(self, tmp_path, aligner):
        task_dir = tmp_path / "no-result"
        task_dir.mkdir(parents=True)

        reward = aligner.load_reward(task_dir)
        assert reward is None


class TestTaskAlignerEdgeCases:
    """Edge cases for task alignment."""

    def test_empty_directories(self, tmp_path, aligner):
        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"
        baseline.mkdir()
        treatment.mkdir()

        result = aligner.align(baseline, treatment)

        assert result.common_tasks == []
        assert result.baseline_only == []
        assert result.treatment_only == []
        assert result.total_baseline == 0
        assert result.total_treatment == 0

    def test_nonexistent_directory(self, tmp_path, aligner):
        baseline = tmp_path / "does-not-exist"
        treatment = tmp_path / "also-missing"

        result = aligner.align(baseline, treatment)

        assert result.common_tasks == []
        assert result.total_baseline == 0
        assert result.total_treatment == 0

    def test_skips_hidden_directories(self, tmp_path, aligner):
        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"

        _make_task_dir(baseline, ".hidden", task_path="benchmarks/test/.hidden")
        _make_task_dir(baseline, "visible__abc", task_path="benchmarks/test/visible")
        _make_task_dir(treatment, "visible__xyz", task_path="benchmarks/test/visible")

        result = aligner.align(baseline, treatment)

        assert result.common_tasks == ["visible"]
        assert result.baseline_only == []

    def test_config_with_empty_task_path(self, tmp_path, aligner):
        """Config exists but task.path is empty string."""
        baseline = tmp_path / "baseline"
        task_dir = baseline / "fallback-name__abc"
        task_dir.mkdir(parents=True)

        config = {"task": {"path": ""}}
        (task_dir / "config.json").write_text(json.dumps(config))

        treatment = tmp_path / "treatment"
        treatment.mkdir()

        result = aligner.align(baseline, treatment)

        # Should fall back to directory name stripping
        assert result.baseline_only == ["fallback-name"]

    def test_alignment_result_is_frozen(self, aligner, tmp_path):
        """AlignmentResult should be immutable."""
        baseline = tmp_path / "b"
        baseline.mkdir()
        treatment = tmp_path / "t"
        treatment.mkdir()

        result = aligner.align(baseline, treatment)

        with pytest.raises(AttributeError):
            result.total_baseline = 999


# =============================================================================
# RewardNormalizer Tests
# =============================================================================


@pytest.fixture
def normalizer():
    """Create a RewardNormalizer instance."""
    return RewardNormalizer()


class TestRewardNormalizerLoCoBench:
    """LoCoBench rewards are already 0-1, passthrough."""

    def test_passthrough_zero(self, normalizer):
        assert normalizer.normalize(0.0, "locobench") == pytest.approx(0.0)

    def test_passthrough_one(self, normalizer):
        assert normalizer.normalize(1.0, "locobench") == pytest.approx(1.0)

    def test_passthrough_mid(self, normalizer):
        assert normalizer.normalize(0.45, "locobench") == pytest.approx(0.45)

    def test_locobench_alias(self, normalizer):
        """locobench_agent path variant should also work."""
        assert normalizer.normalize(0.75, "locobench_agent") == pytest.approx(0.75)


class TestRewardNormalizerSWEBench:
    """SWE-bench rewards are binary 0/1, passthrough."""

    def test_passthrough_zero(self, normalizer):
        assert normalizer.normalize(0.0, "swebench") == pytest.approx(0.0)

    def test_passthrough_one(self, normalizer):
        assert normalizer.normalize(1.0, "swebench") == pytest.approx(1.0)

    def test_swebench_pro_alias(self, normalizer):
        assert normalizer.normalize(1.0, "swebench_pro") == pytest.approx(1.0)


class TestRewardNormalizerBigCodeMCP:
    """big_code_mcp uses min-max normalization from benchmark metadata."""

    def test_min_value_maps_to_zero(self, normalizer):
        assert normalizer.normalize(0.0, "big_code_mcp") == pytest.approx(0.0)

    def test_max_value_maps_to_one(self, normalizer):
        assert normalizer.normalize(1.0, "big_code_mcp") == pytest.approx(1.0)

    def test_mid_value(self, normalizer):
        assert normalizer.normalize(0.5, "big_code_mcp") == pytest.approx(0.5)


class TestRewardNormalizerInferBenchmark:
    """Test benchmark type inference from task directory paths."""

    def test_infer_from_locobench_path(self, normalizer):
        assert normalizer.infer_benchmark_type(
            Path("benchmarks/locobench_agent/task-1")
        ) == "locobench_agent"

    def test_infer_from_swebench_path(self, normalizer):
        assert normalizer.infer_benchmark_type(
            Path("benchmarks/swebench_pro/django__django-12345")
        ) == "swebench_pro"

    def test_infer_from_big_code_path(self, normalizer):
        assert normalizer.infer_benchmark_type(
            Path("benchmarks/big_code_mcp/task-001")
        ) == "big_code_mcp"

    def test_infer_from_config_metadata(self, tmp_path, normalizer):
        task_dir = tmp_path / "some_task__abc"
        task_dir.mkdir()
        config = {"task": {"path": "benchmarks/locobench_agent/task-x"}}
        (task_dir / "config.json").write_text(json.dumps(config))

        assert normalizer.infer_benchmark_type(task_dir) == "locobench_agent"

    def test_infer_unknown_returns_none(self, normalizer):
        assert normalizer.infer_benchmark_type(Path("unknown/path/task")) is None


class TestRewardNormalizerUnknownType:
    """Unknown benchmark types raise ValueError."""

    def test_unknown_type_raises(self, normalizer):
        with pytest.raises(ValueError, match="Unknown benchmark type"):
            normalizer.normalize(0.5, "nonexistent_benchmark")

    def test_empty_string_raises(self, normalizer):
        with pytest.raises(ValueError, match="Unknown benchmark type"):
            normalizer.normalize(0.5, "")


class TestRewardNormalizerClamping:
    """Normalized values should be clamped to [0.0, 1.0]."""

    def test_clamp_above_one(self, normalizer):
        result = normalizer.normalize(1.5, "locobench")
        assert result == pytest.approx(1.0)

    def test_clamp_below_zero(self, normalizer):
        result = normalizer.normalize(-0.2, "locobench")
        assert result == pytest.approx(0.0)


# =============================================================================
# Pairwise Bootstrap Tests
# =============================================================================


class TestBootstrapResultDataclass:
    """BootstrapResult is a frozen dataclass with expected fields."""

    def test_fields_present(self):
        br = BootstrapResult(
            mean_delta=0.1,
            ci_lower=-0.05,
            ci_upper=0.25,
            p_value=0.04,
            effect_size=0.3,
            effect_interpretation="small",
            n_resamples=1000,
            n_tasks=10,
        )
        assert br.mean_delta == pytest.approx(0.1)
        assert br.effect_interpretation == "small"
        assert br.n_resamples == 1000
        assert br.n_tasks == 10

    def test_frozen(self):
        br = BootstrapResult(
            mean_delta=0.0, ci_lower=0.0, ci_upper=0.0,
            p_value=1.0, effect_size=0.0,
            effect_interpretation="negligible",
            n_resamples=100, n_tasks=5,
        )
        with pytest.raises(AttributeError):
            br.mean_delta = 999.0


class TestPairwiseBootstrapIdentical:
    """Identical rewards should produce delta=0, high p-value."""

    def test_identical_rewards(self):
        baseline = [0.5, 0.5, 0.5, 0.5, 0.5]
        treatment = [0.5, 0.5, 0.5, 0.5, 0.5]
        result = pairwise_bootstrap(baseline, treatment, n_resamples=1000, random_seed=42)

        assert result.mean_delta == pytest.approx(0.0)
        assert result.p_value == pytest.approx(1.0)
        assert result.effect_interpretation == "negligible"
        assert result.n_tasks == 5


class TestPairwiseBootstrapLargePositiveDelta:
    """Treatment much better than baseline -> positive delta, low p-value."""

    def test_large_positive_delta(self):
        baseline = [0.1, 0.2, 0.1, 0.2, 0.1, 0.2, 0.1, 0.2, 0.1, 0.2]
        treatment = [0.9, 0.8, 0.9, 0.8, 0.9, 0.8, 0.9, 0.8, 0.9, 0.8]
        result = pairwise_bootstrap(baseline, treatment, n_resamples=5000, random_seed=42)

        assert result.mean_delta > 0.5
        assert result.p_value < 0.05
        assert result.effect_size > 0.8
        assert result.effect_interpretation == "large"
        assert result.n_tasks == 10


class TestPairwiseBootstrapLargeNegativeDelta:
    """Treatment worse than baseline -> negative delta."""

    def test_large_negative_delta(self):
        baseline = [0.9, 0.8, 0.9, 0.8, 0.9, 0.8, 0.9, 0.8, 0.9, 0.8]
        treatment = [0.1, 0.2, 0.1, 0.2, 0.1, 0.2, 0.1, 0.2, 0.1, 0.2]
        result = pairwise_bootstrap(baseline, treatment, n_resamples=5000, random_seed=42)

        assert result.mean_delta < -0.5
        assert result.p_value < 0.05
        assert result.effect_size > 0.8  # absolute value
        assert result.effect_interpretation == "large"


class TestPairwiseBootstrapSingleTask:
    """Edge case: single task pair."""

    def test_single_task(self):
        result = pairwise_bootstrap([0.3], [0.7], n_resamples=1000, random_seed=42)

        assert result.mean_delta == pytest.approx(0.4)
        assert result.n_tasks == 1
        # With one task, bootstrap always resamples the same pair
        assert result.p_value == pytest.approx(0.0)


class TestPairwiseBootstrapSeedReproducibility:
    """Same seed produces identical results."""

    def test_reproducible_with_seed(self):
        baseline = [0.3, 0.4, 0.5, 0.6, 0.7]
        treatment = [0.35, 0.45, 0.55, 0.65, 0.75]

        r1 = pairwise_bootstrap(baseline, treatment, n_resamples=2000, random_seed=123)
        r2 = pairwise_bootstrap(baseline, treatment, n_resamples=2000, random_seed=123)

        assert r1.mean_delta == pytest.approx(r2.mean_delta)
        assert r1.ci_lower == pytest.approx(r2.ci_lower)
        assert r1.ci_upper == pytest.approx(r2.ci_upper)
        assert r1.p_value == pytest.approx(r2.p_value)
        assert r1.effect_size == pytest.approx(r2.effect_size)

    def test_different_seeds_may_differ(self):
        baseline = [0.3, 0.4, 0.5, 0.6, 0.7]
        treatment = [0.35, 0.45, 0.55, 0.65, 0.75]

        r1 = pairwise_bootstrap(baseline, treatment, n_resamples=2000, random_seed=1)
        r2 = pairwise_bootstrap(baseline, treatment, n_resamples=2000, random_seed=2)

        # CIs may differ slightly with different seeds
        # Just verify both produce valid results
        assert r1.n_tasks == r2.n_tasks == 5


class TestPairwiseBootstrapEffectInterpretation:
    """Effect size interpretation thresholds."""

    def test_negligible_effect(self):
        # Small mean difference with large variance in differences -> negligible Cohen's d
        baseline =  [0.40, 0.50, 0.60, 0.45, 0.55, 0.42, 0.58, 0.48, 0.52, 0.50]
        treatment = [0.42, 0.48, 0.62, 0.43, 0.57, 0.44, 0.56, 0.50, 0.50, 0.52]
        # differences: +.02, -.02, +.02, -.02, +.02, +.02, -.02, +.02, -.02, +.02
        # mean diff = +0.004, std of diffs ~ 0.021 -> d ~ 0.19
        result = pairwise_bootstrap(baseline, treatment, n_resamples=1000, random_seed=42)

        assert abs(result.effect_size) < 0.5  # at most small


class TestPairwiseBootstrapConfidenceInterval:
    """Confidence interval properties."""

    def test_ci_contains_mean(self):
        baseline = [0.3, 0.4, 0.5, 0.6, 0.7]
        treatment = [0.35, 0.45, 0.55, 0.65, 0.75]
        result = pairwise_bootstrap(baseline, treatment, n_resamples=5000, random_seed=42)

        assert result.ci_lower <= result.mean_delta <= result.ci_upper

    def test_custom_confidence_level(self):
        baseline = [0.3, 0.4, 0.5, 0.6, 0.7]
        treatment = [0.35, 0.45, 0.55, 0.65, 0.75]

        r90 = pairwise_bootstrap(baseline, treatment, confidence=0.90, n_resamples=5000, random_seed=42)
        r99 = pairwise_bootstrap(baseline, treatment, confidence=0.99, n_resamples=5000, random_seed=42)

        # 99% CI should be wider than 90% CI
        assert (r99.ci_upper - r99.ci_lower) >= (r90.ci_upper - r90.ci_lower)


class TestPairwiseBootstrapValidation:
    """Input validation."""

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError, match="same length"):
            pairwise_bootstrap([0.1, 0.2], [0.3])

    def test_empty_lists_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            pairwise_bootstrap([], [])


# =============================================================================
# Per-Category Breakdown Tests
# =============================================================================


def _make_aligned_results(tasks: list[tuple[str, float, float]]) -> list[dict]:
    """Helper: create aligned results list from (task_id, baseline, treatment) tuples."""
    return [
        {"task_id": tid, "baseline_reward": br, "treatment_reward": tr}
        for tid, br, tr in tasks
    ]


class TestCategoryBreakdownMultipleCategories:
    """Test breakdown with multiple task categories."""

    def test_two_categories_sorted_by_delta(self):
        results = _make_aligned_results([
            ("t1", 0.3, 0.8),  # arch: delta=+0.5
            ("t2", 0.4, 0.9),  # arch: delta=+0.5
            ("t3", 0.5, 0.7),  # arch: delta=+0.2
            ("t4", 0.6, 0.7),  # arch: delta=+0.1
            ("t5", 0.5, 0.6),  # arch: delta=+0.1
            ("t6", 0.5, 0.5),  # bug: delta=0.0
            ("t7", 0.6, 0.6),  # bug: delta=0.0
            ("t8", 0.7, 0.7),  # bug: delta=0.0
            ("t9", 0.8, 0.8),  # bug: delta=0.0
            ("t10", 0.9, 0.9),  # bug: delta=0.0
        ])
        categories = {
            "t1": "arch", "t2": "arch", "t3": "arch", "t4": "arch", "t5": "arch",
            "t6": "bug", "t7": "bug", "t8": "bug", "t9": "bug", "t10": "bug",
        }

        breakdowns = compute_category_breakdown(
            results, categories, n_resamples=500, random_seed=42,
        )

        # Should have: arch, bug, all
        cats = [b.category for b in breakdowns]
        assert "arch" in cats
        assert "bug" in cats
        assert "all" in cats

        # Sorted by absolute mean_delta descending
        deltas = [abs(b.mean_delta) for b in breakdowns]
        assert deltas == sorted(deltas, reverse=True)

    def test_categories_have_correct_counts(self):
        results = _make_aligned_results([
            ("t1", 0.3, 0.8),
            ("t2", 0.4, 0.9),
            ("t3", 0.5, 0.5),
        ])
        categories = {"t1": "arch", "t2": "arch", "t3": "bug"}

        breakdowns = compute_category_breakdown(
            results, categories, n_resamples=500, random_seed=42,
        )

        by_cat = {b.category: b for b in breakdowns}
        assert by_cat["arch"].n_tasks == 2
        assert by_cat["bug"].n_tasks == 1
        assert by_cat["all"].n_tasks == 3


class TestCategoryBreakdownSingleCategory:
    """Test breakdown when all tasks belong to one category."""

    def test_single_category_plus_all(self):
        results = _make_aligned_results([
            ("t1", 0.3, 0.5),
            ("t2", 0.4, 0.6),
            ("t3", 0.5, 0.7),
            ("t4", 0.6, 0.8),
            ("t5", 0.7, 0.9),
        ])
        categories = {f"t{i}": "arch" for i in range(1, 6)}

        breakdowns = compute_category_breakdown(
            results, categories, n_resamples=500, random_seed=42,
        )

        cats = [b.category for b in breakdowns]
        assert "arch" in cats
        assert "all" in cats
        # arch and all should have same stats
        by_cat = {b.category: b for b in breakdowns}
        assert by_cat["arch"].mean_delta == pytest.approx(by_cat["all"].mean_delta)
        assert by_cat["arch"].n_tasks == by_cat["all"].n_tasks


class TestCategoryBreakdownSmallCategory:
    """Categories with < min_category_size tasks skip bootstrap."""

    def test_small_category_no_bootstrap(self):
        results = _make_aligned_results([
            ("t1", 0.3, 0.8),
            ("t2", 0.4, 0.9),
            ("t3", 0.5, 0.7),
        ])
        categories = {"t1": "arch", "t2": "arch", "t3": "arch"}

        breakdowns = compute_category_breakdown(
            results, categories, n_resamples=500, random_seed=42, min_category_size=5,
        )

        by_cat = {b.category: b for b in breakdowns}

        # 3 tasks < min_category_size=5 -> no bootstrap
        assert by_cat["arch"].bootstrap is None
        assert by_cat["arch"].n_tasks == 3
        # Raw means should still be reported
        assert by_cat["arch"].baseline_mean == pytest.approx(0.4)
        assert by_cat["arch"].treatment_mean == pytest.approx(0.8)
        assert by_cat["arch"].mean_delta == pytest.approx(0.4)

    def test_large_category_has_bootstrap(self):
        results = _make_aligned_results([
            (f"t{i}", 0.3 + i * 0.05, 0.5 + i * 0.05)
            for i in range(6)
        ])
        categories = {f"t{i}": "arch" for i in range(6)}

        breakdowns = compute_category_breakdown(
            results, categories, n_resamples=500, random_seed=42, min_category_size=5,
        )

        by_cat = {b.category: b for b in breakdowns}
        assert by_cat["arch"].bootstrap is not None
        assert by_cat["arch"].bootstrap.n_tasks == 6


class TestCategoryBreakdownMissingCategory:
    """Tasks with missing category metadata default to 'unknown'."""

    def test_missing_category_becomes_unknown(self):
        results = _make_aligned_results([
            ("t1", 0.3, 0.5),
            ("t2", 0.4, 0.6),
        ])
        # t2 is not in the categories dict
        categories = {"t1": "arch"}

        breakdowns = compute_category_breakdown(
            results, categories, n_resamples=500, random_seed=42,
        )

        cats = [b.category for b in breakdowns]
        assert "unknown" in cats


class TestCategoryBreakdownEmptyInput:
    """Empty aligned results produce empty output."""

    def test_empty_results(self):
        breakdowns = compute_category_breakdown([], {})
        assert breakdowns == []


class TestCategoryBreakdownAllPseudoCategory:
    """The 'all' pseudo-category aggregates all tasks."""

    def test_all_includes_every_task(self):
        results = _make_aligned_results([
            ("t1", 0.2, 0.4),
            ("t2", 0.3, 0.5),
            ("t3", 0.4, 0.6),
            ("t4", 0.5, 0.7),
            ("t5", 0.6, 0.8),
        ])
        categories = {"t1": "a", "t2": "a", "t3": "b", "t4": "b", "t5": "b"}

        breakdowns = compute_category_breakdown(
            results, categories, n_resamples=500, random_seed=42,
        )

        by_cat = {b.category: b for b in breakdowns}
        assert by_cat["all"].n_tasks == 5
        assert by_cat["all"].mean_delta == pytest.approx(0.2)


class TestCategoryBreakdownFrozenDataclass:
    """CategoryBreakdown should be immutable."""

    def test_frozen(self):
        bd = CategoryBreakdown(
            category="test", n_tasks=3,
            baseline_mean=0.5, treatment_mean=0.7,
            mean_delta=0.2, bootstrap=None,
        )
        with pytest.raises(AttributeError):
            bd.category = "other"


# =============================================================================
# extract_task_category Tests
# =============================================================================


class TestExtractTaskCategoryFromConfig:
    """Test category extraction from config.json."""

    def test_direct_category_field(self, tmp_path):
        task_dir = tmp_path / "task__abc"
        task_dir.mkdir()
        config = {"task": {"category": "architectural_understanding"}}
        (task_dir / "config.json").write_text(json.dumps(config))

        assert extract_task_category(task_dir) == "architectural_understanding"

    def test_infer_from_task_path(self, tmp_path):
        task_dir = tmp_path / "task__abc"
        task_dir.mkdir()
        config = {"task": {"path": "benchmarks/locobench_agent/bug_investigation/task-42"}}
        (task_dir / "config.json").write_text(json.dumps(config))

        assert extract_task_category(task_dir) == "bug_investigation"

    def test_no_config_returns_unknown(self, tmp_path):
        task_dir = tmp_path / "task__abc"
        task_dir.mkdir()

        assert extract_task_category(task_dir) == "unknown"

    def test_empty_config_returns_unknown(self, tmp_path):
        task_dir = tmp_path / "task__abc"
        task_dir.mkdir()
        (task_dir / "config.json").write_text("{}")

        assert extract_task_category(task_dir) == "unknown"

    def test_invalid_json_returns_unknown(self, tmp_path):
        task_dir = tmp_path / "task__abc"
        task_dir.mkdir()
        (task_dir / "config.json").write_text("not json")

        assert extract_task_category(task_dir) == "unknown"


# =============================================================================
# Tool Usage Correlation Tests
# =============================================================================


def _make_treatment_results(
    tasks: list[tuple[str, int | None]],
) -> list[dict]:
    """Helper: create treatment results with tool call counts.

    Args:
        tasks: List of (task_id, tool_call_count) tuples. None means no tool data.
    """
    results = []
    for task_id, tool_calls in tasks:
        result_data: dict = {
            "agent_info": {"tool_calls": tool_calls} if tool_calls is not None else {},
            "agent_result": {},
        }
        results = [*results, {"task_id": task_id, "result_data": result_data}]
    return results


class TestToolCorrelationPositive:
    """Test positive correlation between tool usage and reward delta."""

    def test_strong_positive_correlation(self):
        treatment = _make_treatment_results([
            ("t1", 5), ("t2", 10), ("t3", 15), ("t4", 20), ("t5", 25),
        ])
        # More tool calls -> better delta (monotonic positive)
        deltas = {"t1": 0.1, "t2": 0.2, "t3": 0.3, "t4": 0.4, "t5": 0.5}

        result = compute_tool_correlation(treatment, deltas)

        assert result is not None
        assert result.spearman_rho > 0.5
        assert result.interpretation == "strong positive"
        assert result.n_tasks == 5
        assert len(result.per_task) == 5


class TestToolCorrelationNoCorrelation:
    """Test weak/no correlation scenario."""

    def test_no_clear_correlation(self):
        treatment = _make_treatment_results([
            ("t1", 5), ("t2", 10), ("t3", 15), ("t4", 20), ("t5", 25),
        ])
        # No monotonic relationship: ranks shuffle (3,1,5,2,4) vs (1,2,3,4,5)
        deltas = {"t1": 0.3, "t2": 0.1, "t3": 0.5, "t4": 0.2, "t5": 0.4}

        result = compute_tool_correlation(treatment, deltas)

        assert result is not None
        assert -0.3 <= result.spearman_rho <= 0.3
        assert result.interpretation == "weak/no correlation"


class TestToolCorrelationMissingToolData:
    """Test when treatment run has no tool call data."""

    def test_no_tool_data_returns_none(self):
        treatment = _make_treatment_results([
            ("t1", None), ("t2", None), ("t3", None),
        ])
        deltas = {"t1": 0.1, "t2": 0.2, "t3": 0.3}

        result = compute_tool_correlation(treatment, deltas)

        assert result is None

    def test_partial_tool_data_below_threshold(self):
        """Fewer than 3 tasks with tool data returns None."""
        treatment = _make_treatment_results([
            ("t1", 5), ("t2", None), ("t3", 15), ("t4", None),
        ])
        deltas = {"t1": 0.1, "t2": 0.2, "t3": 0.3, "t4": 0.4}

        result = compute_tool_correlation(treatment, deltas)

        assert result is None


class TestToolCorrelationFewerThanThreeTasks:
    """Test edge case with fewer than 3 tasks."""

    def test_two_tasks_returns_none(self):
        treatment = _make_treatment_results([("t1", 5), ("t2", 10)])
        deltas = {"t1": 0.1, "t2": 0.2}

        result = compute_tool_correlation(treatment, deltas)

        assert result is None


class TestToolCorrelationPerTaskData:
    """Test per-task data in the result."""

    def test_per_task_fields_present(self):
        treatment = _make_treatment_results([
            ("t1", 5), ("t2", 10), ("t3", 15),
        ])
        deltas = {"t1": 0.1, "t2": 0.2, "t3": 0.3}

        result = compute_tool_correlation(treatment, deltas)

        assert result is not None
        for entry in result.per_task:
            assert "task_id" in entry
            assert "tool_calls" in entry
            assert "reward_delta" in entry

        task_ids = [e["task_id"] for e in result.per_task]
        assert sorted(task_ids) == ["t1", "t2", "t3"]


class TestToolCorrelationToolUsageSummary:
    """Test extraction from tool_usage dict (alternative format)."""

    def test_tool_usage_dict_format(self):
        results = [
            {
                "task_id": "t1",
                "result_data": {
                    "agent_info": {
                        "tool_usage": {"search": 3, "read_file": 2}
                    },
                    "agent_result": {},
                },
            },
            {
                "task_id": "t2",
                "result_data": {
                    "agent_info": {
                        "tool_usage": {"search": 10, "read_file": 5}
                    },
                    "agent_result": {},
                },
            },
            {
                "task_id": "t3",
                "result_data": {
                    "agent_info": {
                        "tool_usage": {"search": 20, "read_file": 10}
                    },
                    "agent_result": {},
                },
            },
        ]
        deltas = {"t1": 0.1, "t2": 0.3, "t3": 0.5}

        result = compute_tool_correlation(results, deltas)

        assert result is not None
        assert result.n_tasks == 3
        # t1: 5 calls, t2: 15 calls, t3: 30 calls
        counts = {e["task_id"]: e["tool_calls"] for e in result.per_task}
        assert counts["t1"] == 5
        assert counts["t2"] == 15
        assert counts["t3"] == 30


class TestToolCorrelationNToolCallsFormat:
    """Test extraction from agent_result.n_tool_calls field."""

    def test_n_tool_calls_field(self):
        results = [
            {
                "task_id": "t1",
                "result_data": {
                    "agent_info": {},
                    "agent_result": {"n_tool_calls": 8},
                },
            },
            {
                "task_id": "t2",
                "result_data": {
                    "agent_info": {},
                    "agent_result": {"n_tool_calls": 16},
                },
            },
            {
                "task_id": "t3",
                "result_data": {
                    "agent_info": {},
                    "agent_result": {"n_tool_calls": 24},
                },
            },
        ]
        deltas = {"t1": 0.1, "t2": 0.2, "t3": 0.3}

        result = compute_tool_correlation(results, deltas)

        assert result is not None
        assert result.n_tasks == 3


class TestToolCorrelationZeroVariance:
    """Test when all tool counts or all deltas are identical."""

    def test_identical_tool_counts(self):
        treatment = _make_treatment_results([
            ("t1", 10), ("t2", 10), ("t3", 10),
        ])
        deltas = {"t1": 0.1, "t2": 0.2, "t3": 0.3}

        result = compute_tool_correlation(treatment, deltas)

        assert result is not None
        assert result.spearman_rho == 0.0
        assert result.spearman_p_value == 1.0
        assert result.interpretation == "weak/no correlation"

    def test_identical_deltas(self):
        treatment = _make_treatment_results([
            ("t1", 5), ("t2", 10), ("t3", 15),
        ])
        deltas = {"t1": 0.2, "t2": 0.2, "t3": 0.2}

        result = compute_tool_correlation(treatment, deltas)

        assert result is not None
        assert result.spearman_rho == 0.0
        assert result.spearman_p_value == 1.0


class TestToolCorrelationFrozenDataclass:
    """ToolCorrelation should be immutable."""

    def test_frozen(self):
        tc = ToolCorrelation(
            spearman_rho=0.5, spearman_p_value=0.05,
            n_tasks=10, interpretation="strong positive",
            per_task=[],
        )
        with pytest.raises(AttributeError):
            tc.spearman_rho = 0.9
