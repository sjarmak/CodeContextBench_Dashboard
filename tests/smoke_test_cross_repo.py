"""Smoke test for cross-repo task packages.

Validates all cross-repo task directories have correct structure,
valid config files, and consistent metadata.

Run with: python -m pytest tests/smoke_test_cross_repo.py -v
"""

import json
import os
import stat
from pathlib import Path

import pytest

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python < 3.11

BENCHMARK_DIR = Path(__file__).parent.parent / "benchmarks" / "10figure"

CROSS_REPO_TASKS = [
    "cross_api_tracing_01",
    "cross_dependency_impact_01",
    "cross_bug_localization_01",
    "cross_refactor_01",
]

REQUIRED_FILES = [
    "instruction.md",
    "task.toml",
    "task.yaml",
    "environment/Dockerfile",
    "tests/test.sh",
    "tests/expected_changes.json",
]


@pytest.fixture(params=CROSS_REPO_TASKS)
def task_dir(request):
    """Parametrized fixture yielding each cross-repo task directory."""
    return BENCHMARK_DIR / request.param


class TestCrossRepoTaskStructure:
    """Validate that each cross-repo task has all required files."""

    def test_task_directory_exists(self, task_dir):
        assert task_dir.is_dir(), f"Task directory not found: {task_dir}"

    @pytest.mark.parametrize("required_file", REQUIRED_FILES)
    def test_required_files_exist(self, task_dir, required_file):
        filepath = task_dir / required_file
        assert filepath.exists(), f"Missing: {filepath}"

    def test_instruction_md_references_multiple_repos(self, task_dir):
        content = (task_dir / "instruction.md").read_text()
        assert "/10figure/src/" in content, "instruction.md should reference repo paths"
        repo_refs = sum(
            1
            for repo in ["kubernetes", "envoy", "django", "tensorflow"]
            if repo in content.lower()
        )
        assert repo_refs >= 2, f"instruction.md references only {repo_refs} repos (need 2+)"

    def test_test_sh_is_executable(self, task_dir):
        test_sh = task_dir / "tests" / "test.sh"
        mode = test_sh.stat().st_mode
        assert mode & stat.S_IXUSR, f"test.sh is not executable: {test_sh}"


class TestCrossRepoTaskToml:
    """Validate TOML configuration for each task."""

    def test_toml_is_valid(self, task_dir):
        toml_path = task_dir / "task.toml"
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        assert "metadata" in data, "TOML missing [metadata] section"

    def test_toml_has_task_id(self, task_dir):
        with open(task_dir / "task.toml", "rb") as f:
            data = tomllib.load(f)
        assert "task_id" in data["metadata"], "TOML missing task_id"
        assert data["metadata"]["task_id"] == task_dir.name

    def test_toml_lists_multiple_repos(self, task_dir):
        with open(task_dir / "task.toml", "rb") as f:
            data = tomllib.load(f)
        repos = data.get("environment", {}).get("repos", [])
        assert len(repos) >= 2, f"TOML lists only {len(repos)} repos (need 2+)"


class TestCrossRepoTaskYaml:
    """Validate YAML task definition (basic syntax check without pyyaml)."""

    def test_yaml_is_readable(self, task_dir):
        content = (task_dir / "task.yaml").read_text()
        assert len(content) > 100, "task.yaml seems too short"
        assert "task_id:" in content, "task.yaml missing task_id field"
        assert "ground_truth:" in content, "task.yaml missing ground_truth field"

    def test_yaml_references_multiple_repos(self, task_dir):
        content = (task_dir / "task.yaml").read_text()
        assert "repos:" in content, "task.yaml missing repos field"


class TestCrossRepoExpectedChanges:
    """Validate expected_changes.json for each task."""

    def test_json_is_valid(self, task_dir):
        with open(task_dir / "tests" / "expected_changes.json") as f:
            data = json.load(f)
        assert "task_id" in data
        assert data["task_id"] == task_dir.name

    def test_json_has_multiple_repos(self, task_dir):
        with open(task_dir / "tests" / "expected_changes.json") as f:
            data = json.load(f)
        repos = data.get("repos", [])
        assert len(repos) >= 2, f"expected_changes.json lists only {len(repos)} repos"

    def test_scoring_weights_sum_to_one(self, task_dir):
        with open(task_dir / "tests" / "expected_changes.json") as f:
            data = json.load(f)
        weights = data.get("scoring_weights", {})
        assert len(weights) >= 2, "Need weights for at least 2 repos"
        weight_sum = sum(weights.values())
        assert abs(weight_sum - 1.0) < 0.01, f"Weights sum to {weight_sum}, expected 1.0"

    def test_json_has_expected_symbols_or_files(self, task_dir):
        with open(task_dir / "tests" / "expected_changes.json") as f:
            data = json.load(f)
        has_symbols = "expected_symbols" in data
        has_files = "expected_files" in data
        assert has_symbols or has_files, "Need expected_symbols or expected_files"


class TestCrossRepoDockerfile:
    """Validate Dockerfile for each task."""

    def test_dockerfile_inherits_base(self, task_dir):
        content = (task_dir / "environment" / "Dockerfile").read_text()
        assert "harbor-10figure:base" in content, "Dockerfile should inherit from harbor-10figure:base"

    def test_dockerfile_sets_repos_env(self, task_dir):
        content = (task_dir / "environment" / "Dockerfile").read_text()
        assert "REPOS=" in content or "repos" in content.lower(), "Dockerfile should reference repos"
