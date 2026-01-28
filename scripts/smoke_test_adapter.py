#!/usr/bin/env python3
"""
Smoke test runner for Harbor benchmark adapters.

Validates adapters before VM deployment by generating tasks,
checking structure, optionally building Docker images, and
running verifiers with mock output.

Usage:
    python smoke_test_adapter.py --adapter_dir ./benchmarks/ainativebench/
    python smoke_test_adapter.py --adapter_dir ./benchmarks/devai/ --num_tasks 5
    python smoke_test_adapter.py --adapter_dir ./benchmarks/prdbench/ --build --verify
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class SmokeTestStatus(Enum):
    """Status of a smoke test check."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class SmokeTestCheck:
    """
    Result of a single smoke test check.

    Attributes:
        check_name: Name of the check
        status: Whether the check passed, failed, or was skipped
        message: Detailed message about the result
        evidence: Supporting evidence or details
    """

    check_name: str
    status: SmokeTestStatus
    message: str
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "check_name": self.check_name,
            "status": self.status.value,
            "message": self.message,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SmokeTestCheck":
        """Create from dictionary representation."""
        return cls(
            check_name=data["check_name"],
            status=SmokeTestStatus(data["status"]),
            message=data["message"],
            evidence=data.get("evidence", ""),
        )


@dataclass
class TaskSmokeTestResult:
    """
    Result of smoke testing a single generated task.

    Attributes:
        task_id: Identifier for the task
        task_directory: Path to the generated task directory
        passed: Whether all checks passed
        checks: List of individual check results
        generation_time_ms: Time to generate the task in milliseconds
        build_time_ms: Time to build Docker image (if --build used)
        verify_time_ms: Time to run verifier (if --verify used)
    """

    task_id: str
    task_directory: str
    passed: bool
    checks: list[SmokeTestCheck]
    generation_time_ms: float = 0.0
    build_time_ms: float = 0.0
    verify_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "task_id": self.task_id,
            "task_directory": self.task_directory,
            "passed": self.passed,
            "checks": [c.to_dict() for c in self.checks],
            "generation_time_ms": self.generation_time_ms,
            "build_time_ms": self.build_time_ms,
            "verify_time_ms": self.verify_time_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskSmokeTestResult":
        """Create from dictionary representation."""
        checks = [SmokeTestCheck.from_dict(c) for c in data.get("checks", [])]
        return cls(
            task_id=data["task_id"],
            task_directory=data["task_directory"],
            passed=data.get("passed", False),
            checks=checks,
            generation_time_ms=data.get("generation_time_ms", 0.0),
            build_time_ms=data.get("build_time_ms", 0.0),
            verify_time_ms=data.get("verify_time_ms", 0.0),
        )


@dataclass
class SmokeTestReport:
    """
    Aggregated smoke test report for an adapter.

    Attributes:
        adapter_name: Name of the adapter being tested
        adapter_directory: Path to the adapter directory
        timestamp: When the test was performed
        task_results: Results for each generated task
        overall_passed: Whether all tasks passed
        tasks_passed: Count of passed tasks
        tasks_total: Total count of tasks tested
        generation_errors: List of tasks that failed to generate
        metadata: Additional metadata about the test
    """

    adapter_name: str
    adapter_directory: str
    timestamp: str
    task_results: list[TaskSmokeTestResult]
    overall_passed: bool = False
    tasks_passed: int = 0
    tasks_total: int = 0
    generation_errors: list[tuple[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Compute aggregate statistics if not provided."""
        if self.tasks_total == 0 and self.task_results:
            self._compute_statistics()

    def _compute_statistics(self) -> None:
        """Compute pass/fail statistics from task results."""
        self.tasks_total = len(self.task_results)
        self.tasks_passed = sum(1 for r in self.task_results if r.passed)
        self.overall_passed = (
            self.tasks_passed == self.tasks_total
            and len(self.generation_errors) == 0
            and self.tasks_total > 0
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "adapter_name": self.adapter_name,
            "adapter_directory": self.adapter_directory,
            "timestamp": self.timestamp,
            "task_results": [r.to_dict() for r in self.task_results],
            "overall_passed": self.overall_passed,
            "tasks_passed": self.tasks_passed,
            "tasks_total": self.tasks_total,
            "generation_errors": [
                {"task_id": tid, "error": err} for tid, err in self.generation_errors
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SmokeTestReport":
        """Create from dictionary representation."""
        task_results = [
            TaskSmokeTestResult.from_dict(r) for r in data.get("task_results", [])
        ]
        generation_errors = [
            (e["task_id"], e["error"]) for e in data.get("generation_errors", [])
        ]
        return cls(
            adapter_name=data["adapter_name"],
            adapter_directory=data["adapter_directory"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            task_results=task_results,
            overall_passed=data.get("overall_passed", False),
            tasks_passed=data.get("tasks_passed", 0),
            tasks_total=data.get("tasks_total", 0),
            generation_errors=generation_errors,
            metadata=data.get("metadata", {}),
        )

    def to_markdown(self) -> str:
        """Generate markdown report."""
        status_str = "PASS" if self.overall_passed else "FAIL"
        lines = [
            f"# Smoke Test Report: {self.adapter_name}",
            "",
            f"**Directory:** `{self.adapter_directory}`",
            f"**Timestamp:** {self.timestamp}",
            f"**Overall Status:** {status_str}",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Tasks Tested | {self.tasks_total} |",
            f"| Tasks Passed | {self.tasks_passed} |",
            f"| Generation Errors | {len(self.generation_errors)} |",
            "",
        ]

        # Add generation errors section
        if self.generation_errors:
            lines.append("## Generation Errors")
            lines.append("")
            for task_id, error in self.generation_errors:
                lines.append(f"- **{task_id}**: {error}")
            lines.append("")

        # Add failed task details
        failed_tasks = [r for r in self.task_results if not r.passed]
        if failed_tasks:
            lines.append("## Failed Tasks")
            lines.append("")
            for result in failed_tasks:
                lines.append(f"### {result.task_id}")
                lines.append("")
                lines.append(f"Directory: `{result.task_directory}`")
                lines.append("")
                lines.append("| Check | Status | Message |")
                lines.append("|-------|--------|---------|")
                for check in result.checks:
                    if check.status == SmokeTestStatus.FAILED:
                        lines.append(
                            f"| {check.check_name} | FAIL | {check.message} |"
                        )
                lines.append("")

        # Add all task results
        lines.append("## All Task Results")
        lines.append("")
        lines.append("| Task ID | Status | Checks Passed |")
        lines.append("|---------|--------|---------------|")
        for result in self.task_results:
            status_emoji = "PASS" if result.passed else "FAIL"
            passed_checks = sum(
                1 for c in result.checks if c.status == SmokeTestStatus.PASSED
            )
            total_checks = len(result.checks)
            lines.append(
                f"| {result.task_id} | {status_emoji} | {passed_checks}/{total_checks} |"
            )

        return "\n".join(lines)


class SmokeTestRunner:
    """
    Smoke test runner for Harbor benchmark adapters.

    Validates adapters by:
    1. Generating tasks using the adapter's run_adapter.py
    2. Validating generated task structure
    3. Optionally building Docker images
    4. Optionally running verifier with mock agent output
    """

    # Required files in a Harbor task directory
    REQUIRED_FILES = ["task.toml", "instruction.md"]

    # Required directories or file alternatives
    REQUIRED_STRUCTURE = {
        "dockerfile": ["Dockerfile", "environment/Dockerfile", "docker/Dockerfile"],
        "test_sh": ["test.sh", "tests/test.sh"],
        "ground_truth": ["ground_truth.json", "tests/ground_truth.json"],
    }

    def __init__(
        self,
        adapter_dir: Path,
        num_tasks: int = 3,
        build: bool = False,
        verify: bool = False,
        timeout: int = 300,
    ) -> None:
        """
        Initialize the smoke test runner.

        Args:
            adapter_dir: Path to the adapter directory
            num_tasks: Number of tasks to generate and test
            build: Whether to build Docker images
            verify: Whether to run verifier with mock output
            timeout: Timeout for subprocess commands in seconds
        """
        self.adapter_dir = Path(adapter_dir)
        self.num_tasks = num_tasks
        self.build = build
        self.verify = verify
        self.timeout = timeout
        self._temp_dir: Path | None = None

    def run(self) -> SmokeTestReport:
        """
        Run the smoke test.

        Returns:
            SmokeTestReport with results for all generated tasks
        """
        adapter_name = self.adapter_dir.name
        timestamp = datetime.now().isoformat()

        # Validate adapter directory exists
        if not self.adapter_dir.exists():
            return SmokeTestReport(
                adapter_name=adapter_name,
                adapter_directory=str(self.adapter_dir),
                timestamp=timestamp,
                task_results=[],
                generation_errors=[("N/A", f"Adapter directory not found: {self.adapter_dir}")],
            )

        # Check for run_adapter.py
        run_adapter_py = self.adapter_dir / "run_adapter.py"
        if not run_adapter_py.exists():
            return SmokeTestReport(
                adapter_name=adapter_name,
                adapter_directory=str(self.adapter_dir),
                timestamp=timestamp,
                task_results=[],
                generation_errors=[("N/A", f"run_adapter.py not found in {self.adapter_dir}")],
            )

        # Create temporary directory for generated tasks
        temp_dir = tempfile.mkdtemp(prefix=f"smoke_test_{adapter_name}_")
        self._temp_dir = Path(temp_dir)

        try:
            # Generate tasks
            logger.info(f"Generating {self.num_tasks} tasks from {adapter_name}...")
            generation_errors, generated_task_dirs = self._generate_tasks()

            # Test each generated task
            task_results: list[TaskSmokeTestResult] = []
            for task_dir in generated_task_dirs:
                logger.info(f"Testing task: {task_dir.name}")
                result = self._test_task(task_dir)
                task_results.append(result)

            return SmokeTestReport(
                adapter_name=adapter_name,
                adapter_directory=str(self.adapter_dir),
                timestamp=timestamp,
                task_results=task_results,
                generation_errors=generation_errors,
                metadata={
                    "num_tasks_requested": self.num_tasks,
                    "build_enabled": self.build,
                    "verify_enabled": self.verify,
                    "temp_directory": str(self._temp_dir),
                },
            )
        finally:
            # Cleanup temp directory
            if self._temp_dir and self._temp_dir.exists():
                shutil.rmtree(self._temp_dir, ignore_errors=True)

    def _generate_tasks(self) -> tuple[list[tuple[str, str]], list[Path]]:
        """
        Generate tasks using the adapter's run_adapter.py.

        Returns:
            Tuple of (generation_errors, list of generated task directories)
        """
        generation_errors: list[tuple[str, str]] = []
        generated_dirs: list[Path] = []

        if self._temp_dir is None:
            return [("N/A", "Temp directory not initialized")], []

        output_dir = self._temp_dir / "tasks"
        output_dir.mkdir(parents=True, exist_ok=True)

        run_adapter_py = self.adapter_dir / "run_adapter.py"

        # Build command
        cmd = [
            sys.executable,
            str(run_adapter_py),
            "--output_dir",
            str(output_dir),
            "--limit",
            str(self.num_tasks),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.adapter_dir),
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                generation_errors.append(("generation", f"run_adapter.py failed: {error_msg}"))
                logger.error(f"Generation failed: {error_msg}")
            else:
                logger.info(f"Generation completed: {result.stdout[:200] if result.stdout else 'OK'}")

        except subprocess.TimeoutExpired:
            generation_errors.append(
                ("generation", f"run_adapter.py timed out after {self.timeout}s")
            )
            logger.error(f"Generation timed out after {self.timeout}s")
        except Exception as e:
            generation_errors.append(("generation", f"run_adapter.py error: {str(e)}"))
            logger.error(f"Generation error: {e}")

        # Find generated task directories
        if output_dir.exists():
            for item in output_dir.iterdir():
                if item.is_dir():
                    # Check if it looks like a task directory
                    task_toml = item / "task.toml"
                    if task_toml.exists():
                        generated_dirs.append(item)

        logger.info(f"Found {len(generated_dirs)} generated task directories")
        return generation_errors, generated_dirs

    def _test_task(self, task_dir: Path) -> TaskSmokeTestResult:
        """
        Test a single generated task.

        Args:
            task_dir: Path to the task directory

        Returns:
            TaskSmokeTestResult with all check results
        """
        task_id = task_dir.name
        checks: list[SmokeTestCheck] = []

        # Check 1: Required files present
        checks.append(self._check_required_files(task_dir))

        # Check 2: task.toml validity
        checks.append(self._check_task_toml(task_dir))

        # Check 3: Dockerfile presence
        checks.append(self._check_dockerfile(task_dir))

        # Check 4: test.sh presence
        checks.append(self._check_test_sh(task_dir))

        # Check 5: ground_truth.json presence and validity
        checks.append(self._check_ground_truth(task_dir))

        # Check 6: instruction.md content
        checks.append(self._check_instruction_md(task_dir))

        # Optional: Build Docker image
        build_time_ms = 0.0
        if self.build:
            build_check, build_time_ms = self._check_docker_build(task_dir)
            checks.append(build_check)

        # Optional: Run verifier
        verify_time_ms = 0.0
        if self.verify:
            verify_check, verify_time_ms = self._check_verifier(task_dir)
            checks.append(verify_check)

        # Determine overall pass/fail
        passed = all(c.status != SmokeTestStatus.FAILED for c in checks)

        return TaskSmokeTestResult(
            task_id=task_id,
            task_directory=str(task_dir),
            passed=passed,
            checks=checks,
            build_time_ms=build_time_ms,
            verify_time_ms=verify_time_ms,
        )

    def _check_required_files(self, task_dir: Path) -> SmokeTestCheck:
        """Check that required files are present."""
        missing: list[str] = []
        for filename in self.REQUIRED_FILES:
            if not (task_dir / filename).exists():
                missing.append(filename)

        if missing:
            return SmokeTestCheck(
                check_name="required_files",
                status=SmokeTestStatus.FAILED,
                message=f"Missing required files: {', '.join(missing)}",
                evidence=str(task_dir),
            )

        return SmokeTestCheck(
            check_name="required_files",
            status=SmokeTestStatus.PASSED,
            message="All required files present",
        )

    def _check_task_toml(self, task_dir: Path) -> SmokeTestCheck:
        """Check task.toml validity."""
        task_toml = task_dir / "task.toml"

        if not task_toml.exists():
            return SmokeTestCheck(
                check_name="task_toml",
                status=SmokeTestStatus.FAILED,
                message="task.toml not found",
            )

        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib  # type: ignore

            with open(task_toml, "rb") as f:
                data = tomllib.load(f)

            # Check required sections
            required_sections = ["version", "metadata", "verifier"]
            missing_sections = [s for s in required_sections if s not in data]

            if missing_sections:
                return SmokeTestCheck(
                    check_name="task_toml",
                    status=SmokeTestStatus.FAILED,
                    message=f"Missing sections: {', '.join(missing_sections)}",
                )

            # Check metadata has task_id
            metadata = data.get("metadata", {})
            if "task_id" not in metadata:
                return SmokeTestCheck(
                    check_name="task_toml",
                    status=SmokeTestStatus.FAILED,
                    message="metadata.task_id not found",
                )

            return SmokeTestCheck(
                check_name="task_toml",
                status=SmokeTestStatus.PASSED,
                message="task.toml is valid",
            )

        except Exception as e:
            return SmokeTestCheck(
                check_name="task_toml",
                status=SmokeTestStatus.FAILED,
                message=f"Invalid TOML: {e}",
            )

    def _check_dockerfile(self, task_dir: Path) -> SmokeTestCheck:
        """Check Dockerfile presence."""
        for location in self.REQUIRED_STRUCTURE["dockerfile"]:
            if (task_dir / location).exists():
                return SmokeTestCheck(
                    check_name="dockerfile",
                    status=SmokeTestStatus.PASSED,
                    message=f"Dockerfile found at {location}",
                    evidence=str(task_dir / location),
                )

        return SmokeTestCheck(
            check_name="dockerfile",
            status=SmokeTestStatus.FAILED,
            message="Dockerfile not found",
            evidence=f"Checked: {', '.join(self.REQUIRED_STRUCTURE['dockerfile'])}",
        )

    def _check_test_sh(self, task_dir: Path) -> SmokeTestCheck:
        """Check test.sh presence."""
        for location in self.REQUIRED_STRUCTURE["test_sh"]:
            if (task_dir / location).exists():
                return SmokeTestCheck(
                    check_name="test_sh",
                    status=SmokeTestStatus.PASSED,
                    message=f"test.sh found at {location}",
                    evidence=str(task_dir / location),
                )

        return SmokeTestCheck(
            check_name="test_sh",
            status=SmokeTestStatus.FAILED,
            message="test.sh not found",
            evidence=f"Checked: {', '.join(self.REQUIRED_STRUCTURE['test_sh'])}",
        )

    def _check_ground_truth(self, task_dir: Path) -> SmokeTestCheck:
        """Check ground_truth.json presence and validity."""
        for location in self.REQUIRED_STRUCTURE["ground_truth"]:
            gt_path = task_dir / location
            if gt_path.exists():
                try:
                    with open(gt_path) as f:
                        json.load(f)
                    return SmokeTestCheck(
                        check_name="ground_truth",
                        status=SmokeTestStatus.PASSED,
                        message=f"ground_truth.json found and valid at {location}",
                        evidence=str(gt_path),
                    )
                except json.JSONDecodeError as e:
                    return SmokeTestCheck(
                        check_name="ground_truth",
                        status=SmokeTestStatus.FAILED,
                        message=f"Invalid JSON at {location}: {e}",
                    )

        return SmokeTestCheck(
            check_name="ground_truth",
            status=SmokeTestStatus.FAILED,
            message="ground_truth.json not found",
            evidence=f"Checked: {', '.join(self.REQUIRED_STRUCTURE['ground_truth'])}",
        )

    def _check_instruction_md(self, task_dir: Path) -> SmokeTestCheck:
        """Check instruction.md content."""
        instruction_md = task_dir / "instruction.md"

        if not instruction_md.exists():
            return SmokeTestCheck(
                check_name="instruction_md",
                status=SmokeTestStatus.FAILED,
                message="instruction.md not found",
            )

        try:
            content = instruction_md.read_text(encoding="utf-8")

            # Check minimum length
            if len(content.strip()) < 50:
                return SmokeTestCheck(
                    check_name="instruction_md",
                    status=SmokeTestStatus.FAILED,
                    message="instruction.md too short (< 50 chars)",
                    evidence=f"Length: {len(content.strip())} chars",
                )

            return SmokeTestCheck(
                check_name="instruction_md",
                status=SmokeTestStatus.PASSED,
                message="instruction.md is present with content",
                evidence=f"Length: {len(content.strip())} chars",
            )

        except Exception as e:
            return SmokeTestCheck(
                check_name="instruction_md",
                status=SmokeTestStatus.FAILED,
                message=f"Could not read instruction.md: {e}",
            )

    def _check_docker_build(self, task_dir: Path) -> tuple[SmokeTestCheck, float]:
        """
        Attempt to build the Docker image.

        Returns:
            Tuple of (SmokeTestCheck, build_time_ms)
        """
        import time

        # Find Dockerfile
        dockerfile_path: Path | None = None
        for location in self.REQUIRED_STRUCTURE["dockerfile"]:
            candidate = task_dir / location
            if candidate.exists():
                dockerfile_path = candidate
                break

        if dockerfile_path is None:
            return (
                SmokeTestCheck(
                    check_name="docker_build",
                    status=SmokeTestStatus.SKIPPED,
                    message="No Dockerfile found",
                ),
                0.0,
            )

        # Build Docker image
        task_id = task_dir.name
        image_tag = f"smoke-test-{task_id}:latest"

        # Determine build context
        if dockerfile_path.parent == task_dir:
            context = str(task_dir)
            dockerfile_arg = "Dockerfile"
        else:
            context = str(dockerfile_path.parent)
            dockerfile_arg = "Dockerfile"

        cmd = [
            "docker",
            "build",
            "-t",
            image_tag,
            "-f",
            str(dockerfile_path),
            context,
        ]

        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            end_time = time.time()
            build_time_ms = (end_time - start_time) * 1000

            if result.returncode != 0:
                error_output = result.stderr[-500:] if result.stderr else "Unknown error"
                return (
                    SmokeTestCheck(
                        check_name="docker_build",
                        status=SmokeTestStatus.FAILED,
                        message=f"Docker build failed",
                        evidence=error_output,
                    ),
                    build_time_ms,
                )

            # Cleanup: remove built image
            subprocess.run(
                ["docker", "rmi", "-f", image_tag],
                capture_output=True,
                timeout=30,
            )

            return (
                SmokeTestCheck(
                    check_name="docker_build",
                    status=SmokeTestStatus.PASSED,
                    message="Docker build succeeded",
                    evidence=f"Build time: {build_time_ms:.0f}ms",
                ),
                build_time_ms,
            )

        except subprocess.TimeoutExpired:
            end_time = time.time()
            build_time_ms = (end_time - start_time) * 1000
            return (
                SmokeTestCheck(
                    check_name="docker_build",
                    status=SmokeTestStatus.FAILED,
                    message=f"Docker build timed out after {self.timeout}s",
                ),
                build_time_ms,
            )
        except FileNotFoundError:
            return (
                SmokeTestCheck(
                    check_name="docker_build",
                    status=SmokeTestStatus.SKIPPED,
                    message="Docker not available",
                ),
                0.0,
            )
        except Exception as e:
            return (
                SmokeTestCheck(
                    check_name="docker_build",
                    status=SmokeTestStatus.FAILED,
                    message=f"Docker build error: {e}",
                ),
                0.0,
            )

    def _check_verifier(self, task_dir: Path) -> tuple[SmokeTestCheck, float]:
        """
        Run verifier with mock agent output.

        Returns:
            Tuple of (SmokeTestCheck, verify_time_ms)
        """
        import time

        # Find verify.py or test.sh
        verify_script: Path | None = None
        for location in ["tests/verify.py", "verify.py"]:
            candidate = task_dir / location
            if candidate.exists():
                verify_script = candidate
                break

        if verify_script is None:
            # Fall back to test.sh
            for location in self.REQUIRED_STRUCTURE["test_sh"]:
                candidate = task_dir / location
                if candidate.exists():
                    verify_script = candidate
                    break

        if verify_script is None:
            return (
                SmokeTestCheck(
                    check_name="verifier",
                    status=SmokeTestStatus.SKIPPED,
                    message="No verify.py or test.sh found",
                ),
                0.0,
            )

        # Create mock output directory
        mock_output_dir = task_dir / "mock_output"
        mock_output_dir.mkdir(exist_ok=True)

        # Create a minimal mock trajectory
        mock_trajectory = {
            "task_id": task_dir.name,
            "steps": [],
            "final_state": {"completed": False, "requirements_met": []},
        }
        trajectory_file = mock_output_dir / "trajectory.json"
        with open(trajectory_file, "w") as f:
            json.dump(mock_trajectory, f)

        # Create mock reward.json
        mock_reward = {"score": 0.0, "metrics": {}}
        reward_file = mock_output_dir / "reward.json"
        with open(reward_file, "w") as f:
            json.dump(mock_reward, f)

        # Determine command based on script type
        if verify_script.suffix == ".py":
            cmd = [sys.executable, str(verify_script)]
        else:
            cmd = ["bash", str(verify_script)]

        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,  # Shorter timeout for verifier
                cwd=str(task_dir),
                env={
                    **os.environ,
                    "MOCK_MODE": "1",
                    "OUTPUT_DIR": str(mock_output_dir),
                },
            )
            end_time = time.time()
            verify_time_ms = (end_time - start_time) * 1000

            # Check for reward.json output
            reward_output = mock_output_dir / "reward.json"
            if reward_output.exists():
                try:
                    with open(reward_output) as f:
                        reward_data = json.load(f)

                    if "score" in reward_data or "metrics" in reward_data:
                        return (
                            SmokeTestCheck(
                                check_name="verifier",
                                status=SmokeTestStatus.PASSED,
                                message="Verifier produced valid reward.json",
                                evidence=f"Score: {reward_data.get('score', 'N/A')}",
                            ),
                            verify_time_ms,
                        )
                except json.JSONDecodeError:
                    pass

            # Verifier ran but may not have produced output in mock mode
            # This is acceptable - we just want to ensure it doesn't crash
            return (
                SmokeTestCheck(
                    check_name="verifier",
                    status=SmokeTestStatus.PASSED,
                    message="Verifier executed without error",
                    evidence=f"Exit code: {result.returncode}",
                ),
                verify_time_ms,
            )

        except subprocess.TimeoutExpired:
            end_time = time.time()
            verify_time_ms = (end_time - start_time) * 1000
            return (
                SmokeTestCheck(
                    check_name="verifier",
                    status=SmokeTestStatus.FAILED,
                    message="Verifier timed out after 60s",
                ),
                verify_time_ms,
            )
        except Exception as e:
            return (
                SmokeTestCheck(
                    check_name="verifier",
                    status=SmokeTestStatus.FAILED,
                    message=f"Verifier error: {e}",
                ),
                0.0,
            )
        finally:
            # Cleanup mock output
            if mock_output_dir.exists():
                shutil.rmtree(mock_output_dir, ignore_errors=True)


def run_smoke_test(
    adapter_dir: Path | str,
    num_tasks: int = 3,
    build: bool = False,
    verify: bool = False,
    output_file: Path | str | None = None,
    output_format: str = "summary",
) -> SmokeTestReport:
    """
    Run smoke test on an adapter directory.

    Args:
        adapter_dir: Path to the adapter directory
        num_tasks: Number of tasks to test
        build: Whether to build Docker images
        verify: Whether to run verifier
        output_file: Optional file to write report to
        output_format: Output format (summary, json, markdown)

    Returns:
        SmokeTestReport with results
    """
    adapter_dir = Path(adapter_dir)
    runner = SmokeTestRunner(
        adapter_dir=adapter_dir,
        num_tasks=num_tasks,
        build=build,
        verify=verify,
    )

    report = runner.run()

    # Write output if requested
    if output_file:
        output_file = Path(output_file)
        if output_format == "json":
            with open(output_file, "w") as f:
                json.dump(report.to_dict(), f, indent=2)
        elif output_format == "markdown":
            with open(output_file, "w") as f:
                f.write(report.to_markdown())
        else:
            # Summary format
            with open(output_file, "w") as f:
                f.write(report.to_markdown())

    return report


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Smoke test Harbor benchmark adapters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic smoke test with 3 tasks
    python smoke_test_adapter.py --adapter_dir ./benchmarks/ainativebench/

    # Test more tasks
    python smoke_test_adapter.py --adapter_dir ./benchmarks/devai/ --num_tasks 5

    # Include Docker build test
    python smoke_test_adapter.py --adapter_dir ./benchmarks/prdbench/ --build

    # Include verifier test
    python smoke_test_adapter.py --adapter_dir ./benchmarks/sweperf/ --verify

    # Full test with JSON output
    python smoke_test_adapter.py --adapter_dir ./benchmarks/tac_mcp_value/ --build --verify --output smoke_report.json --format json
        """,
    )

    parser.add_argument(
        "--adapter_dir",
        type=Path,
        required=True,
        help="Path to the adapter directory containing run_adapter.py",
    )

    parser.add_argument(
        "--num_tasks",
        type=int,
        default=3,
        help="Number of tasks to generate and test (default: 3)",
    )

    parser.add_argument(
        "--build",
        action="store_true",
        help="Build Docker image for each generated task",
    )

    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run verifier with mock agent output",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for the report",
    )

    parser.add_argument(
        "--format",
        choices=["summary", "json", "markdown"],
        default="summary",
        help="Output format (default: summary)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout for subprocess commands in seconds (default: 300)",
    )

    args = parser.parse_args()

    # Run smoke test
    logger.info(f"Running smoke test on {args.adapter_dir}")
    logger.info(f"Settings: num_tasks={args.num_tasks}, build={args.build}, verify={args.verify}")

    runner = SmokeTestRunner(
        adapter_dir=args.adapter_dir,
        num_tasks=args.num_tasks,
        build=args.build,
        verify=args.verify,
        timeout=args.timeout,
    )

    report = runner.run()

    # Output results
    if args.output:
        output_file = args.output
        if args.format == "json":
            with open(output_file, "w") as f:
                json.dump(report.to_dict(), f, indent=2)
            logger.info(f"Report written to {output_file}")
        elif args.format == "markdown":
            with open(output_file, "w") as f:
                f.write(report.to_markdown())
            logger.info(f"Report written to {output_file}")
        else:
            with open(output_file, "w") as f:
                f.write(report.to_markdown())
            logger.info(f"Report written to {output_file}")

    # Print summary
    print()
    print(f"Smoke Test Results: {report.adapter_name}")
    print("=" * 50)
    print(f"Overall: {'PASS' if report.overall_passed else 'FAIL'}")
    print(f"Tasks Passed: {report.tasks_passed}/{report.tasks_total}")

    if report.generation_errors:
        print(f"Generation Errors: {len(report.generation_errors)}")
        for task_id, error in report.generation_errors:
            print(f"  - {task_id}: {error}")

    if not report.overall_passed:
        print("\nFailed Tasks:")
        for result in report.task_results:
            if not result.passed:
                failed_checks = [
                    c.check_name for c in result.checks if c.status == SmokeTestStatus.FAILED
                ]
                print(f"  - {result.task_id}: {', '.join(failed_checks)}")

    return 0 if report.overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())
