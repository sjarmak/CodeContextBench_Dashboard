"""Tests for paired vs individual experiment mode toggle (US-005)."""

import json
import tempfile
from pathlib import Path
import pytest


# Import the functions under test
from dashboard.views.run_results import (
    _find_common_task_runs,
    _find_experiment_for_run,
    _get_experiment_task_ids,
    _load_manifest_pairs,
)


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def _make_experiment(
    tmp_dir: Path, name: str, *, is_paired: bool = False, modes: dict | None = None
) -> dict:
    """Create a minimal experiment dict with a real directory."""
    exp_path = tmp_dir / name
    exp_path.mkdir(parents=True, exist_ok=True)
    exp = {
        "path": exp_path,
        "name": name,
        "result": {},
        "config": {},
        "is_paired": is_paired,
    }
    if modes is not None:
        exp["modes"] = modes
    return exp


def _write_manifest(exp_path: Path, manifest_data: dict) -> None:
    """Write a manifest.json file to the experiment directory."""
    with open(exp_path / "manifest.json", "w") as f:
        json.dump(manifest_data, f)


class TestLoadManifestPairs:
    """Tests for _load_manifest_pairs()."""

    def test_no_manifest_returns_empty(self, tmp_dir: Path):
        exp = _make_experiment(tmp_dir, "exp1")
        result = _load_manifest_pairs([exp])
        assert result == []

    def test_manifest_without_pairs_returns_empty(self, tmp_dir: Path):
        exp = _make_experiment(tmp_dir, "exp1")
        _write_manifest(exp["path"], {"runs": [], "pairs": []})
        result = _load_manifest_pairs([exp])
        assert result == []

    def test_manifest_with_pairs_returns_pair_dicts(self, tmp_dir: Path):
        exp = _make_experiment(tmp_dir, "combined_exp")
        _write_manifest(
            exp["path"],
            {
                "runs": [
                    {"run_id": "run_baseline", "mcp_mode": "baseline"},
                    {"run_id": "run_variant", "mcp_mode": "deepsearch_hybrid"},
                ],
                "pairs": [
                    {
                        "pair_id": "pair_1",
                        "baseline_run_id": "run_baseline",
                        "mcp_run_id": "run_variant",
                        "status": "completed",
                    }
                ],
            },
        )
        result = _load_manifest_pairs([exp])
        assert len(result) == 1
        assert result[0]["pair_id"] == "pair_1"
        assert result[0]["baseline_run_id"] == "run_baseline"
        assert result[0]["variant_run_id"] == "run_variant"
        assert result[0]["status"] == "completed"
        assert result[0]["source_experiment"] == "combined_exp"

    def test_malformed_manifest_skipped(self, tmp_dir: Path):
        exp = _make_experiment(tmp_dir, "bad_exp")
        with open(exp["path"] / "manifest.json", "w") as f:
            f.write("not valid json")
        result = _load_manifest_pairs([exp])
        assert result == []

    def test_multiple_experiments_multiple_pairs(self, tmp_dir: Path):
        exp1 = _make_experiment(tmp_dir, "exp1")
        exp2 = _make_experiment(tmp_dir, "exp2")

        _write_manifest(
            exp1["path"],
            {
                "runs": [{"run_id": "a", "mcp_mode": "baseline"}],
                "pairs": [
                    {
                        "pair_id": "p1",
                        "baseline_run_id": "a",
                        "mcp_run_id": "b",
                        "status": "completed",
                    }
                ],
            },
        )
        _write_manifest(
            exp2["path"],
            {
                "runs": [{"run_id": "c", "mcp_mode": "baseline"}],
                "pairs": [
                    {
                        "pair_id": "p2",
                        "baseline_run_id": "c",
                        "mcp_run_id": "d",
                        "status": "completed",
                    }
                ],
            },
        )

        result = _load_manifest_pairs([exp1, exp2])
        assert len(result) == 2
        pair_ids = {p["pair_id"] for p in result}
        assert pair_ids == {"p1", "p2"}


class TestFindExperimentForRun:
    """Tests for _find_experiment_for_run()."""

    def test_returns_none_for_empty_run_id(self, tmp_dir: Path):
        exp = _make_experiment(tmp_dir, "exp1")
        result = _find_experiment_for_run([exp], exp, "")
        assert result is None

    def test_matches_paired_mode(self, tmp_dir: Path):
        exp = _make_experiment(
            tmp_dir,
            "paired_exp",
            is_paired=True,
            modes={
                "baseline": {"path": tmp_dir / "baseline", "tasks": []},
                "deepsearch_hybrid": {
                    "path": tmp_dir / "deepsearch",
                    "tasks": [],
                },
            },
        )
        result = _find_experiment_for_run(
            [exp], exp, "run_id_baseline"
        )
        assert result is not None
        assert result["_matched_mode"] == "baseline"

    def test_matches_by_experiment_name(self, tmp_dir: Path):
        exp1 = _make_experiment(tmp_dir, "swebenchpro_run_baseline")
        exp2 = _make_experiment(tmp_dir, "swebenchpro_run_variant")

        result = _find_experiment_for_run(
            [exp1, exp2],
            exp1,
            "swebenchpro_run_baseline_extra_suffix",
        )
        assert result is not None
        assert result["name"] == "swebenchpro_run_baseline"

    def test_no_match_returns_none(self, tmp_dir: Path):
        exp = _make_experiment(tmp_dir, "exp1")
        result = _find_experiment_for_run(
            [exp], exp, "completely_different_id"
        )
        assert result is None


class TestGetExperimentTaskIds:
    """Tests for _get_experiment_task_ids()."""

    def test_paired_experiment_tasks(self, tmp_dir: Path):
        exp = _make_experiment(
            tmp_dir,
            "paired_exp",
            is_paired=True,
            modes={
                "baseline": {
                    "path": tmp_dir / "baseline",
                    "tasks": [
                        {"task_name": "task_a"},
                        {"task_name": "task_b"},
                    ],
                },
                "deepsearch": {
                    "path": tmp_dir / "ds",
                    "tasks": [
                        {"task_name": "task_b"},
                        {"task_name": "task_c"},
                    ],
                },
            },
        )
        task_ids = _get_experiment_task_ids(exp)
        assert task_ids == {"task_a", "task_b", "task_c"}

    def test_single_experiment_with_agent_dirs(self, tmp_dir: Path):
        exp = _make_experiment(tmp_dir, "single_exp")
        # Create task directories with agent/ subdirs
        for task_name in ["task_x", "task_y"]:
            task_dir = exp["path"] / task_name / "agent"
            task_dir.mkdir(parents=True)

        task_ids = _get_experiment_task_ids(exp)
        assert task_ids == {"task_x", "task_y"}

    def test_single_experiment_with_result_json(self, tmp_dir: Path):
        exp = _make_experiment(tmp_dir, "single_exp")
        # Create task directories with result.json
        for task_name in ["task_1", "task_2"]:
            task_dir = exp["path"] / task_name
            task_dir.mkdir(parents=True)
            (task_dir / "result.json").write_text("{}")

        task_ids = _get_experiment_task_ids(exp)
        assert task_ids == {"task_1", "task_2"}

    def test_hidden_dirs_excluded(self, tmp_dir: Path):
        exp = _make_experiment(tmp_dir, "single_exp")
        # Create one real task and one hidden dir
        (exp["path"] / "real_task" / "agent").mkdir(parents=True)
        (exp["path"] / ".hidden" / "agent").mkdir(parents=True)

        task_ids = _get_experiment_task_ids(exp)
        assert task_ids == {"real_task"}

    def test_empty_experiment(self, tmp_dir: Path):
        exp = _make_experiment(tmp_dir, "empty_exp")
        task_ids = _get_experiment_task_ids(exp)
        assert task_ids == set()


class TestFindCommonTaskRuns:
    """Tests for _find_common_task_runs()."""

    def test_common_tasks_found(self, tmp_dir: Path):
        exp_a = _make_experiment(
            tmp_dir,
            "exp_a",
            is_paired=True,
            modes={
                "baseline": {
                    "path": tmp_dir / "a",
                    "tasks": [
                        {"task_name": "task_1"},
                        {"task_name": "task_2"},
                        {"task_name": "task_3"},
                    ],
                }
            },
        )
        exp_b = _make_experiment(
            tmp_dir,
            "exp_b",
            is_paired=True,
            modes={
                "baseline": {
                    "path": tmp_dir / "b",
                    "tasks": [
                        {"task_name": "task_2"},
                        {"task_name": "task_3"},
                        {"task_name": "task_4"},
                    ],
                }
            },
        )
        common = _find_common_task_runs(exp_a, exp_b)
        assert common == {"task_2", "task_3"}

    def test_no_common_tasks(self, tmp_dir: Path):
        exp_a = _make_experiment(
            tmp_dir,
            "exp_a",
            is_paired=True,
            modes={
                "m1": {
                    "path": tmp_dir / "a",
                    "tasks": [{"task_name": "task_1"}],
                }
            },
        )
        exp_b = _make_experiment(
            tmp_dir,
            "exp_b",
            is_paired=True,
            modes={
                "m1": {
                    "path": tmp_dir / "b",
                    "tasks": [{"task_name": "task_99"}],
                }
            },
        )
        common = _find_common_task_runs(exp_a, exp_b)
        assert common == set()

    def test_empty_experiments(self, tmp_dir: Path):
        exp_a = _make_experiment(tmp_dir, "exp_a")
        exp_b = _make_experiment(tmp_dir, "exp_b")
        common = _find_common_task_runs(exp_a, exp_b)
        assert common == set()
