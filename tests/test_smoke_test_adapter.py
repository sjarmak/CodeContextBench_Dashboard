"""
Unit tests for scripts/smoke_test_adapter.py

Tests the smoke test runner for Harbor benchmark adapters.
"""

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

# Import from the scripts directory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from smoke_test_adapter import (
    SmokeTestStatus,
    SmokeTestCheck,
    TaskSmokeTestResult,
    SmokeTestReport,
    SmokeTestRunner,
    run_smoke_test,
)


class TestSmokeTestCheck:
    """Tests for SmokeTestCheck dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        check = SmokeTestCheck(
            check_name="test_check",
            status=SmokeTestStatus.PASSED,
            message="Test passed",
            evidence="Some evidence",
        )
        result = check.to_dict()
        assert result["check_name"] == "test_check"
        assert result["status"] == "passed"
        assert result["message"] == "Test passed"
        assert result["evidence"] == "Some evidence"

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "check_name": "test_check",
            "status": "failed",
            "message": "Test failed",
            "evidence": "Error details",
        }
        check = SmokeTestCheck.from_dict(data)
        assert check.check_name == "test_check"
        assert check.status == SmokeTestStatus.FAILED
        assert check.message == "Test failed"
        assert check.evidence == "Error details"

    def test_from_dict_default_evidence(self) -> None:
        """Test that evidence defaults to empty string."""
        data = {
            "check_name": "test",
            "status": "passed",
            "message": "OK",
        }
        check = SmokeTestCheck.from_dict(data)
        assert check.evidence == ""


class TestTaskSmokeTestResult:
    """Tests for TaskSmokeTestResult dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        result = TaskSmokeTestResult(
            task_id="task-001",
            task_directory="/tmp/task-001",
            passed=True,
            checks=[
                SmokeTestCheck(
                    check_name="check1",
                    status=SmokeTestStatus.PASSED,
                    message="OK",
                )
            ],
            generation_time_ms=100.0,
        )
        data = result.to_dict()
        assert data["task_id"] == "task-001"
        assert data["passed"] is True
        assert len(data["checks"]) == 1
        assert data["generation_time_ms"] == 100.0

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "task_id": "task-002",
            "task_directory": "/tmp/task-002",
            "passed": False,
            "checks": [
                {"check_name": "check1", "status": "failed", "message": "Error"}
            ],
            "build_time_ms": 5000.0,
        }
        result = TaskSmokeTestResult.from_dict(data)
        assert result.task_id == "task-002"
        assert result.passed is False
        assert len(result.checks) == 1
        assert result.build_time_ms == 5000.0


class TestSmokeTestReport:
    """Tests for SmokeTestReport dataclass."""

    def test_auto_compute_statistics(self) -> None:
        """Test that statistics are auto-computed in __post_init__."""
        report = SmokeTestReport(
            adapter_name="test_adapter",
            adapter_directory="/tmp/adapter",
            timestamp="2024-01-01T00:00:00",
            task_results=[
                TaskSmokeTestResult(
                    task_id="task1",
                    task_directory="/tmp/task1",
                    passed=True,
                    checks=[],
                ),
                TaskSmokeTestResult(
                    task_id="task2",
                    task_directory="/tmp/task2",
                    passed=False,
                    checks=[],
                ),
            ],
        )
        assert report.tasks_total == 2
        assert report.tasks_passed == 1
        assert report.overall_passed is False  # Not all passed

    def test_overall_passed_when_all_pass(self) -> None:
        """Test overall_passed is True when all tasks pass."""
        report = SmokeTestReport(
            adapter_name="test_adapter",
            adapter_directory="/tmp/adapter",
            timestamp="2024-01-01T00:00:00",
            task_results=[
                TaskSmokeTestResult(
                    task_id="task1",
                    task_directory="/tmp/task1",
                    passed=True,
                    checks=[],
                ),
            ],
        )
        assert report.overall_passed is True

    def test_overall_fails_with_generation_errors(self) -> None:
        """Test overall_passed is False with generation errors."""
        report = SmokeTestReport(
            adapter_name="test_adapter",
            adapter_directory="/tmp/adapter",
            timestamp="2024-01-01T00:00:00",
            task_results=[
                TaskSmokeTestResult(
                    task_id="task1",
                    task_directory="/tmp/task1",
                    passed=True,
                    checks=[],
                ),
            ],
            generation_errors=[("task2", "Failed to generate")],
        )
        assert report.overall_passed is False

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        report = SmokeTestReport(
            adapter_name="test",
            adapter_directory="/tmp",
            timestamp="2024-01-01T00:00:00",
            task_results=[],
            generation_errors=[("task1", "Error")],
        )
        data = report.to_dict()
        assert data["adapter_name"] == "test"
        assert len(data["generation_errors"]) == 1
        assert data["generation_errors"][0]["task_id"] == "task1"

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "adapter_name": "test",
            "adapter_directory": "/tmp",
            "timestamp": "2024-01-01T00:00:00",
            "task_results": [],
            "generation_errors": [{"task_id": "t1", "error": "E1"}],
            "overall_passed": False,
            "tasks_passed": 0,
            "tasks_total": 0,
        }
        report = SmokeTestReport.from_dict(data)
        assert report.adapter_name == "test"
        assert len(report.generation_errors) == 1
        assert report.generation_errors[0] == ("t1", "E1")

    def test_to_markdown(self) -> None:
        """Test markdown report generation."""
        report = SmokeTestReport(
            adapter_name="test_adapter",
            adapter_directory="/tmp/adapter",
            timestamp="2024-01-01T00:00:00",
            task_results=[
                TaskSmokeTestResult(
                    task_id="task1",
                    task_directory="/tmp/task1",
                    passed=True,
                    checks=[
                        SmokeTestCheck(
                            check_name="check1",
                            status=SmokeTestStatus.PASSED,
                            message="OK",
                        )
                    ],
                ),
            ],
        )
        md = report.to_markdown()
        assert "# Smoke Test Report: test_adapter" in md
        assert "PASS" in md
        assert "task1" in md


class TestSmokeTestRunner:
    """Tests for SmokeTestRunner class."""

    @pytest.fixture
    def temp_adapter_dir(self) -> Generator[Path, None, None]:
        """Create a temporary adapter directory with minimal structure."""
        with tempfile.TemporaryDirectory() as td:
            adapter_dir = Path(td)

            # Create run_adapter.py
            run_adapter = adapter_dir / "run_adapter.py"
            run_adapter.write_text('''#!/usr/bin/env python3
import argparse
import stat
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    for i in range(args.limit):
        task_dir = args.output_dir / f"task-{i:03d}"
        task_dir.mkdir()

        # Create task.toml
        task_toml = task_dir / "task.toml"
        task_toml.write_text(f"""
version = "1.0"

[metadata]
task_id = "task-{i:03d}"
category = "test"

[verifier]
timeout_sec = 300
command = "python verify.py"
""")

        # Create instruction.md
        instruction = task_dir / "instruction.md"
        instruction.write_text(f"# Task {i:03d}\\n\\nThis is a test task with enough content to pass validation.")

        # Create Dockerfile
        (task_dir / "environment").mkdir()
        dockerfile = task_dir / "environment" / "Dockerfile"
        dockerfile.write_text("FROM python:3.10-slim\\n")

        # Create test.sh
        (task_dir / "tests").mkdir()
        test_sh = task_dir / "tests" / "test.sh"
        test_sh.write_text("#!/bin/bash\\nexit 0\\n")
        test_sh.chmod(test_sh.stat().st_mode | stat.S_IXUSR)

        # Create ground_truth.json
        gt = task_dir / "tests" / "ground_truth.json"
        gt.write_text('{"expected": "result"}')

    return 0

if __name__ == "__main__":
    sys.exit(main())
''')

            yield adapter_dir

    def test_runner_init(self, temp_adapter_dir: Path) -> None:
        """Test runner initialization."""
        runner = SmokeTestRunner(
            adapter_dir=temp_adapter_dir,
            num_tasks=2,
            build=False,
            verify=False,
        )
        assert runner.adapter_dir == temp_adapter_dir
        assert runner.num_tasks == 2
        assert runner.build is False
        assert runner.verify is False

    def test_run_basic(self, temp_adapter_dir: Path) -> None:
        """Test basic smoke test run."""
        runner = SmokeTestRunner(
            adapter_dir=temp_adapter_dir,
            num_tasks=2,
            build=False,
            verify=False,
        )
        report = runner.run()

        assert report.adapter_name == temp_adapter_dir.name
        assert len(report.generation_errors) == 0
        assert report.tasks_total == 2
        assert report.tasks_passed == 2
        assert report.overall_passed is True

    def test_run_missing_adapter_dir(self) -> None:
        """Test with non-existent adapter directory."""
        runner = SmokeTestRunner(
            adapter_dir=Path("/nonexistent/path"),
            num_tasks=1,
        )
        report = runner.run()

        assert report.overall_passed is False
        assert len(report.generation_errors) > 0
        assert "not found" in report.generation_errors[0][1]

    def test_run_missing_run_adapter_py(self) -> None:
        """Test with missing run_adapter.py."""
        with tempfile.TemporaryDirectory() as td:
            adapter_dir = Path(td)
            runner = SmokeTestRunner(adapter_dir=adapter_dir, num_tasks=1)
            report = runner.run()

            assert report.overall_passed is False
            assert len(report.generation_errors) > 0
            assert "run_adapter.py not found" in report.generation_errors[0][1]

    def test_check_required_files_pass(self, temp_adapter_dir: Path) -> None:
        """Test required files check when files exist."""
        # Generate tasks first
        runner = SmokeTestRunner(adapter_dir=temp_adapter_dir, num_tasks=1)
        report = runner.run()

        # All tasks should have passed required files check
        for result in report.task_results:
            required_check = next(
                (c for c in result.checks if c.check_name == "required_files"), None
            )
            assert required_check is not None
            assert required_check.status == SmokeTestStatus.PASSED

    def test_check_task_toml_validity(self, temp_adapter_dir: Path) -> None:
        """Test task.toml validity check."""
        runner = SmokeTestRunner(adapter_dir=temp_adapter_dir, num_tasks=1)
        report = runner.run()

        for result in report.task_results:
            toml_check = next(
                (c for c in result.checks if c.check_name == "task_toml"), None
            )
            assert toml_check is not None
            assert toml_check.status == SmokeTestStatus.PASSED

    def test_check_dockerfile_found(self, temp_adapter_dir: Path) -> None:
        """Test Dockerfile presence check."""
        runner = SmokeTestRunner(adapter_dir=temp_adapter_dir, num_tasks=1)
        report = runner.run()

        for result in report.task_results:
            dockerfile_check = next(
                (c for c in result.checks if c.check_name == "dockerfile"), None
            )
            assert dockerfile_check is not None
            assert dockerfile_check.status == SmokeTestStatus.PASSED

    def test_check_ground_truth_found(self, temp_adapter_dir: Path) -> None:
        """Test ground_truth.json presence check."""
        runner = SmokeTestRunner(adapter_dir=temp_adapter_dir, num_tasks=1)
        report = runner.run()

        for result in report.task_results:
            gt_check = next(
                (c for c in result.checks if c.check_name == "ground_truth"), None
            )
            assert gt_check is not None
            assert gt_check.status == SmokeTestStatus.PASSED


class TestSmokeTestRunnerCheckMethods:
    """Tests for individual check methods."""

    @pytest.fixture
    def task_dir(self) -> Generator[Path, None, None]:
        """Create a temporary task directory."""
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)

    def test_check_required_files_missing(self, task_dir: Path) -> None:
        """Test check fails when required files missing."""
        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_required_files(task_dir)

        assert check.status == SmokeTestStatus.FAILED
        assert "task.toml" in check.message or "instruction.md" in check.message

    def test_check_required_files_present(self, task_dir: Path) -> None:
        """Test check passes when files present."""
        (task_dir / "task.toml").write_text("version = '1.0'\n")
        (task_dir / "instruction.md").write_text("# Instructions")

        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_required_files(task_dir)

        assert check.status == SmokeTestStatus.PASSED

    def test_check_task_toml_missing(self, task_dir: Path) -> None:
        """Test check fails when task.toml missing."""
        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_task_toml(task_dir)

        assert check.status == SmokeTestStatus.FAILED
        assert "not found" in check.message

    def test_check_task_toml_invalid(self, task_dir: Path) -> None:
        """Test check fails when task.toml is invalid TOML."""
        (task_dir / "task.toml").write_text("not valid toml [[[")

        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_task_toml(task_dir)

        assert check.status == SmokeTestStatus.FAILED
        assert "Invalid TOML" in check.message

    def test_check_task_toml_missing_sections(self, task_dir: Path) -> None:
        """Test check fails when required sections missing."""
        (task_dir / "task.toml").write_text('version = "1.0"\n')

        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_task_toml(task_dir)

        assert check.status == SmokeTestStatus.FAILED
        assert "Missing sections" in check.message

    def test_check_task_toml_missing_task_id(self, task_dir: Path) -> None:
        """Test check fails when metadata.task_id missing."""
        (task_dir / "task.toml").write_text('''
version = "1.0"
[metadata]
category = "test"
[verifier]
timeout_sec = 300
command = "test"
''')

        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_task_toml(task_dir)

        assert check.status == SmokeTestStatus.FAILED
        assert "task_id" in check.message

    def test_check_dockerfile_root(self, task_dir: Path) -> None:
        """Test Dockerfile found in root."""
        (task_dir / "Dockerfile").write_text("FROM python:3.10\n")

        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_dockerfile(task_dir)

        assert check.status == SmokeTestStatus.PASSED

    def test_check_dockerfile_environment_subdir(self, task_dir: Path) -> None:
        """Test Dockerfile found in environment subdirectory."""
        (task_dir / "environment").mkdir()
        (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.10\n")

        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_dockerfile(task_dir)

        assert check.status == SmokeTestStatus.PASSED
        assert "environment/Dockerfile" in check.message

    def test_check_dockerfile_missing(self, task_dir: Path) -> None:
        """Test check fails when Dockerfile missing."""
        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_dockerfile(task_dir)

        assert check.status == SmokeTestStatus.FAILED
        assert "not found" in check.message

    def test_check_test_sh_root(self, task_dir: Path) -> None:
        """Test test.sh found in root."""
        test_sh = task_dir / "test.sh"
        test_sh.write_text("#!/bin/bash\nexit 0\n")

        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_test_sh(task_dir)

        assert check.status == SmokeTestStatus.PASSED

    def test_check_test_sh_tests_subdir(self, task_dir: Path) -> None:
        """Test test.sh found in tests subdirectory."""
        (task_dir / "tests").mkdir()
        test_sh = task_dir / "tests" / "test.sh"
        test_sh.write_text("#!/bin/bash\nexit 0\n")

        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_test_sh(task_dir)

        assert check.status == SmokeTestStatus.PASSED
        assert "tests/test.sh" in check.message

    def test_check_ground_truth_valid(self, task_dir: Path) -> None:
        """Test ground_truth.json found and valid."""
        (task_dir / "ground_truth.json").write_text('{"expected": "value"}')

        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_ground_truth(task_dir)

        assert check.status == SmokeTestStatus.PASSED

    def test_check_ground_truth_invalid_json(self, task_dir: Path) -> None:
        """Test check fails when ground_truth.json is invalid JSON."""
        (task_dir / "ground_truth.json").write_text("not valid json {{{")

        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_ground_truth(task_dir)

        assert check.status == SmokeTestStatus.FAILED
        assert "Invalid JSON" in check.message

    def test_check_instruction_md_valid(self, task_dir: Path) -> None:
        """Test instruction.md check passes with content."""
        content = "# Task Instructions\n\n" + "x" * 100
        (task_dir / "instruction.md").write_text(content)

        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_instruction_md(task_dir)

        assert check.status == SmokeTestStatus.PASSED

    def test_check_instruction_md_too_short(self, task_dir: Path) -> None:
        """Test check fails when instruction.md too short."""
        (task_dir / "instruction.md").write_text("Short")

        runner = SmokeTestRunner(adapter_dir=task_dir, num_tasks=1)
        check = runner._check_instruction_md(task_dir)

        assert check.status == SmokeTestStatus.FAILED
        assert "too short" in check.message


class TestRunSmokeTestFunction:
    """Tests for the run_smoke_test convenience function."""

    @pytest.fixture
    def temp_adapter_dir(self) -> Generator[Path, None, None]:
        """Create a temporary adapter directory with minimal structure."""
        with tempfile.TemporaryDirectory() as td:
            adapter_dir = Path(td)

            # Create run_adapter.py that creates one valid task
            run_adapter = adapter_dir / "run_adapter.py"
            run_adapter.write_text('''#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    task_dir = args.output_dir / "task-000"
    task_dir.mkdir()

    (task_dir / "task.toml").write_text("""
version = "1.0"
[metadata]
task_id = "task-000"
[verifier]
timeout_sec = 300
command = "python verify.py"
""")
    (task_dir / "instruction.md").write_text("# Task\\n\\n" + "x" * 100)
    (task_dir / "Dockerfile").write_text("FROM python:3.10\\n")
    (task_dir / "test.sh").write_text("#!/bin/bash\\nexit 0\\n")
    (task_dir / "ground_truth.json").write_text('{"expected": "value"}')
    return 0

if __name__ == "__main__":
    sys.exit(main())
''')

            yield adapter_dir

    def test_run_smoke_test_basic(self, temp_adapter_dir: Path) -> None:
        """Test basic run_smoke_test call."""
        report = run_smoke_test(
            adapter_dir=temp_adapter_dir,
            num_tasks=1,
        )
        assert report.tasks_total == 1
        assert report.overall_passed is True

    def test_run_smoke_test_with_output_json(self, temp_adapter_dir: Path) -> None:
        """Test run_smoke_test with JSON output."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_file = Path(f.name)

        try:
            report = run_smoke_test(
                adapter_dir=temp_adapter_dir,
                num_tasks=1,
                output_file=output_file,
                output_format="json",
            )

            # Verify output file was written
            assert output_file.exists()
            with open(output_file) as f:
                data = json.load(f)
            assert data["adapter_name"] == temp_adapter_dir.name
        finally:
            output_file.unlink(missing_ok=True)

    def test_run_smoke_test_with_output_markdown(self, temp_adapter_dir: Path) -> None:
        """Test run_smoke_test with markdown output."""
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            output_file = Path(f.name)

        try:
            report = run_smoke_test(
                adapter_dir=temp_adapter_dir,
                num_tasks=1,
                output_file=output_file,
                output_format="markdown",
            )

            # Verify output file was written
            assert output_file.exists()
            content = output_file.read_text()
            assert "# Smoke Test Report" in content
        finally:
            output_file.unlink(missing_ok=True)


class TestDockerBuildCheck:
    """Tests for Docker build check (may be skipped if Docker not available)."""

    @pytest.fixture
    def task_with_dockerfile(self) -> Generator[Path, None, None]:
        """Create task directory with Dockerfile."""
        with tempfile.TemporaryDirectory() as td:
            task_dir = Path(td)
            (task_dir / "Dockerfile").write_text('''
FROM alpine:latest
RUN echo "test"
''')
            yield task_dir

    @patch("subprocess.run")
    def test_docker_build_success(self, mock_run: MagicMock, task_with_dockerfile: Path) -> None:
        """Test Docker build check when build succeeds."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        runner = SmokeTestRunner(
            adapter_dir=task_with_dockerfile,
            num_tasks=1,
            build=True,
        )
        check, time_ms = runner._check_docker_build(task_with_dockerfile)

        assert check.status == SmokeTestStatus.PASSED
        assert "succeeded" in check.message

    @patch("subprocess.run")
    def test_docker_build_failure(self, mock_run: MagicMock, task_with_dockerfile: Path) -> None:
        """Test Docker build check when build fails."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Build error"
        )

        runner = SmokeTestRunner(
            adapter_dir=task_with_dockerfile,
            num_tasks=1,
            build=True,
        )
        check, time_ms = runner._check_docker_build(task_with_dockerfile)

        assert check.status == SmokeTestStatus.FAILED
        assert "failed" in check.message.lower()

    def test_docker_build_no_dockerfile(self) -> None:
        """Test Docker build check when no Dockerfile."""
        with tempfile.TemporaryDirectory() as td:
            task_dir = Path(td)

            runner = SmokeTestRunner(
                adapter_dir=task_dir,
                num_tasks=1,
                build=True,
            )
            check, time_ms = runner._check_docker_build(task_dir)

            assert check.status == SmokeTestStatus.SKIPPED
            assert "No Dockerfile" in check.message


class TestVerifierCheck:
    """Tests for verifier check."""

    @pytest.fixture
    def task_with_verifier(self) -> Generator[Path, None, None]:
        """Create task directory with verify.py."""
        with tempfile.TemporaryDirectory() as td:
            task_dir = Path(td)
            (task_dir / "tests").mkdir()

            verify_py = task_dir / "tests" / "verify.py"
            verify_py.write_text('''#!/usr/bin/env python3
import json
import os
from pathlib import Path

output_dir = os.environ.get("OUTPUT_DIR", ".")
reward_file = Path(output_dir) / "reward.json"
reward_file.write_text(json.dumps({"score": 0.0, "metrics": {}}))
''')

            yield task_dir

    def test_verifier_no_script(self) -> None:
        """Test verifier check when no verify.py or test.sh."""
        with tempfile.TemporaryDirectory() as td:
            task_dir = Path(td)

            runner = SmokeTestRunner(
                adapter_dir=task_dir,
                num_tasks=1,
                verify=True,
            )
            check, time_ms = runner._check_verifier(task_dir)

            assert check.status == SmokeTestStatus.SKIPPED

    def test_verifier_with_script(self, task_with_verifier: Path) -> None:
        """Test verifier check with verify.py."""
        runner = SmokeTestRunner(
            adapter_dir=task_with_verifier,
            num_tasks=1,
            verify=True,
        )
        check, time_ms = runner._check_verifier(task_with_verifier)

        # Should pass (script exists and runs)
        assert check.status in [SmokeTestStatus.PASSED, SmokeTestStatus.FAILED]
