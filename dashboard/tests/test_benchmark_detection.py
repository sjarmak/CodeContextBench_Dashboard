"""
Tests for benchmark set detection utility.

Verifies detection from manifest.json config.benchmarks field
and fallback to directory name pattern matching.
"""

import json
import pytest
from pathlib import Path
import tempfile

from dashboard.utils.benchmark_detection import (
    detect_benchmark_set,
    UNKNOWN_BENCHMARK,
    _detect_from_manifest,
    _detect_from_directory_name,
)


@pytest.fixture
def temp_run_dir():
    """Create a temporary run directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def _write_manifest(run_dir: Path, benchmarks: list[str]) -> None:
    """Helper to write a manifest.json with given benchmarks."""
    manifest = {
        "schema_version": "1.0.0",
        "experiment_id": "test_exp",
        "config": {
            "benchmarks": benchmarks,
            "models": ["test-model"],
        },
    }
    manifest_path = run_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f)


class TestDetectFromManifest:
    """Tests for manifest-based benchmark detection."""

    def test_locobench_agent(self, temp_run_dir: Path) -> None:
        _write_manifest(temp_run_dir, ["locobench_agent"])
        assert _detect_from_manifest(temp_run_dir) == "LoCoBench"

    def test_locobench(self, temp_run_dir: Path) -> None:
        _write_manifest(temp_run_dir, ["locobench"])
        assert _detect_from_manifest(temp_run_dir) == "LoCoBench"

    def test_swebench_pro(self, temp_run_dir: Path) -> None:
        _write_manifest(temp_run_dir, ["swebench_pro"])
        assert _detect_from_manifest(temp_run_dir) == "SWE-Bench Pro"

    def test_swebench_pro_hyphen(self, temp_run_dir: Path) -> None:
        _write_manifest(temp_run_dir, ["swebench-pro"])
        assert _detect_from_manifest(temp_run_dir) == "SWE-Bench Pro"

    def test_swebench_verified(self, temp_run_dir: Path) -> None:
        _write_manifest(temp_run_dir, ["swebench_verified"])
        assert _detect_from_manifest(temp_run_dir) == "SWE-Bench Verified"

    def test_repoqa(self, temp_run_dir: Path) -> None:
        _write_manifest(temp_run_dir, ["repoqa"])
        assert _detect_from_manifest(temp_run_dir) == "RepoQA"

    def test_dibench(self, temp_run_dir: Path) -> None:
        _write_manifest(temp_run_dir, ["dibench"])
        assert _detect_from_manifest(temp_run_dir) == "DIBench"

    def test_uses_first_recognized_benchmark(self, temp_run_dir: Path) -> None:
        _write_manifest(temp_run_dir, ["unknown_bench", "swebench_pro"])
        assert _detect_from_manifest(temp_run_dir) == "SWE-Bench Pro"

    def test_no_manifest_returns_none(self, temp_run_dir: Path) -> None:
        assert _detect_from_manifest(temp_run_dir) is None

    def test_malformed_json_returns_none(self, temp_run_dir: Path) -> None:
        manifest_path = temp_run_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            f.write("not valid json{{{")
        assert _detect_from_manifest(temp_run_dir) is None

    def test_missing_config_key_returns_none(self, temp_run_dir: Path) -> None:
        manifest_path = temp_run_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump({"schema_version": "1.0.0"}, f)
        assert _detect_from_manifest(temp_run_dir) is None

    def test_empty_benchmarks_list_returns_none(self, temp_run_dir: Path) -> None:
        _write_manifest(temp_run_dir, [])
        assert _detect_from_manifest(temp_run_dir) is None

    def test_unrecognized_benchmark_id_returns_none(self, temp_run_dir: Path) -> None:
        _write_manifest(temp_run_dir, ["totally_unknown_benchmark"])
        assert _detect_from_manifest(temp_run_dir) is None

    def test_case_insensitive_benchmark_id(self, temp_run_dir: Path) -> None:
        _write_manifest(temp_run_dir, ["SWEBENCH_PRO"])
        assert _detect_from_manifest(temp_run_dir) == "SWE-Bench Pro"


class TestDetectFromDirectoryName:
    """Tests for directory name pattern matching."""

    def test_locobench_prefix(self) -> None:
        assert _detect_from_directory_name("locobench_50_tasks_20260124") == "LoCoBench"

    def test_locobench_simple(self) -> None:
        assert _detect_from_directory_name("locobench_agent_run") == "LoCoBench"

    def test_swebenchpro_prefix(self) -> None:
        assert (
            _detect_from_directory_name("swebenchpro_run_baseline_opus_seed0")
            == "SWE-Bench Pro"
        )

    def test_swebench_pro_underscore(self) -> None:
        assert (
            _detect_from_directory_name("swebench_pro_combined") == "SWE-Bench Pro"
        )

    def test_repoqa_prefix(self) -> None:
        assert _detect_from_directory_name("repoqa_run_20260127") == "RepoQA"

    def test_dibench_prefix(self) -> None:
        assert _detect_from_directory_name("dibench_experiment_1") == "DIBench"

    def test_swebench_verified(self) -> None:
        assert (
            _detect_from_directory_name("swebench_verified_run1")
            == "SWE-Bench Verified"
        )

    def test_swebench_hyphen_verified(self) -> None:
        assert (
            _detect_from_directory_name("swebench-verified_run1")
            == "SWE-Bench Verified"
        )

    def test_unknown_pattern(self) -> None:
        assert _detect_from_directory_name("my_custom_experiment") == UNKNOWN_BENCHMARK

    def test_empty_string(self) -> None:
        assert _detect_from_directory_name("") == UNKNOWN_BENCHMARK

    def test_case_insensitive_directory(self) -> None:
        assert _detect_from_directory_name("LoCoBench_test_run") == "LoCoBench"


class TestDetectBenchmarkSet:
    """Integration tests for the main detect_benchmark_set function."""

    def test_manifest_takes_priority(self, temp_run_dir: Path) -> None:
        """Manifest detection should be preferred over directory name."""
        # Create a dir named like swebench but with locobench in manifest
        swebench_dir = temp_run_dir / "swebenchpro_run_test"
        swebench_dir.mkdir()
        _write_manifest(swebench_dir, ["locobench_agent"])
        assert detect_benchmark_set(swebench_dir) == "LoCoBench"

    def test_falls_back_to_directory_name(self, temp_run_dir: Path) -> None:
        """Without manifest, should use directory name."""
        loco_dir = temp_run_dir / "locobench_50_tasks_20260124"
        loco_dir.mkdir()
        assert detect_benchmark_set(loco_dir) == "LoCoBench"

    def test_string_path_accepted(self, temp_run_dir: Path) -> None:
        """Should accept string paths as well as Path objects."""
        loco_dir = temp_run_dir / "locobench_run"
        loco_dir.mkdir()
        assert detect_benchmark_set(str(loco_dir)) == "LoCoBench"

    def test_unknown_with_no_manifest_and_no_pattern(self, temp_run_dir: Path) -> None:
        """Returns Unknown when neither detection method succeeds."""
        unknown_dir = temp_run_dir / "my_random_experiment"
        unknown_dir.mkdir()
        assert detect_benchmark_set(unknown_dir) == UNKNOWN_BENCHMARK

    def test_real_locobench_dir_name(self) -> None:
        """Test with actual directory name from the codebase."""
        assert (
            _detect_from_directory_name("locobench_50_tasks_20260124_225159")
            == "LoCoBench"
        )

    def test_real_swebenchpro_dir_name(self) -> None:
        """Test with actual directory name from the codebase."""
        assert (
            _detect_from_directory_name(
                "swebenchpro_run_baseline_opus_nodebb_seed0_b3515e"
            )
            == "SWE-Bench Pro"
        )

    def test_real_swebenchpro_combined_dir_name(self) -> None:
        """Test with actual directory name from the codebase."""
        assert (
            _detect_from_directory_name("swebenchpro_combined") == "SWE-Bench Pro"
        )
