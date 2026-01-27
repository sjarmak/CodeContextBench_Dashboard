"""
Tests for experiment grouping by benchmark set in run_results.

Verifies that _group_experiments_by_benchmark correctly groups
experiments using the benchmark detection utility.
"""

import tempfile
from pathlib import Path

import pytest

from dashboard.views.run_results import _group_experiments_by_benchmark


@pytest.fixture
def temp_dirs():
    """Create temporary experiment directories with known benchmark names."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        # Create locobench directories
        loco1 = base / "locobench_run1"
        loco1.mkdir()
        loco2 = base / "locobench_run2"
        loco2.mkdir()

        # Create swebenchpro directory
        swe1 = base / "swebenchpro_run1"
        swe1.mkdir()

        # Create unknown directory
        unk1 = base / "my_custom_run"
        unk1.mkdir()

        experiments = [
            {"path": loco1, "name": "locobench_run1", "is_paired": False},
            {"path": loco2, "name": "locobench_run2", "is_paired": True},
            {"path": swe1, "name": "swebenchpro_run1", "is_paired": False},
            {"path": unk1, "name": "my_custom_run", "is_paired": False},
        ]

        yield experiments


class TestGroupExperimentsByBenchmark:
    """Tests for _group_experiments_by_benchmark."""

    def test_groups_by_benchmark_name(self, temp_dirs):
        groups = _group_experiments_by_benchmark(temp_dirs)

        assert "LoCoBench" in groups
        assert len(groups["LoCoBench"]) == 2

    def test_swebench_group(self, temp_dirs):
        groups = _group_experiments_by_benchmark(temp_dirs)

        assert "SWE-Bench Pro" in groups
        assert len(groups["SWE-Bench Pro"]) == 1

    def test_unknown_group(self, temp_dirs):
        groups = _group_experiments_by_benchmark(temp_dirs)

        assert "Unknown" in groups
        assert len(groups["Unknown"]) == 1

    def test_empty_experiments(self):
        groups = _group_experiments_by_benchmark([])

        assert groups == {}

    def test_preserves_experiment_data(self, temp_dirs):
        groups = _group_experiments_by_benchmark(temp_dirs)

        loco_exps = groups["LoCoBench"]
        assert loco_exps[0]["name"] == "locobench_run1"
        assert loco_exps[1]["name"] == "locobench_run2"
        assert loco_exps[1]["is_paired"] is True

    def test_no_empty_groups(self, temp_dirs):
        groups = _group_experiments_by_benchmark(temp_dirs)

        for name, exps in groups.items():
            assert len(exps) > 0, f"Group '{name}' is empty"

    def test_all_experiments_accounted_for(self, temp_dirs):
        groups = _group_experiments_by_benchmark(temp_dirs)

        total = sum(len(exps) for exps in groups.values())
        assert total == len(temp_dirs)
