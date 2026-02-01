"""
Unit tests for the pre-flight validation module.
"""

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from src.quality.preflight_validator import (
    CheckSeverity,
    CheckStatus,
    PreflightValidator,
    ValidationCheck,
    ValidationReport,
)


class TestValidationCheck:
    """Tests for ValidationCheck dataclass."""

    def test_create_basic_check(self) -> None:
        """Test creating a basic validation check."""
        check = ValidationCheck(
            check_id="PF-001",
            name="test check",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.PASSED,
            message="Check passed",
        )
        assert check.check_id == "PF-001"
        assert check.name == "test check"
        assert check.severity == CheckSeverity.CRITICAL
        assert check.status == CheckStatus.PASSED
        assert check.message == "Check passed"
        assert check.evidence == ""

    def test_check_with_evidence(self) -> None:
        """Test check with evidence field."""
        check = ValidationCheck(
            check_id="PF-002",
            name="evidence check",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.FAILED,
            message="Check failed",
            evidence="Found issue at line 42",
        )
        assert check.evidence == "Found issue at line 42"

    def test_to_dict(self) -> None:
        """Test converting check to dictionary."""
        check = ValidationCheck(
            check_id="PF-001",
            name="test",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.PASSED,
            message="OK",
            evidence="details",
        )
        result = check.to_dict()
        assert result["check_id"] == "PF-001"
        assert result["severity"] == "critical"
        assert result["status"] == "passed"
        assert result["evidence"] == "details"

    def test_from_dict(self) -> None:
        """Test creating check from dictionary."""
        data = {
            "check_id": "PF-003",
            "name": "from dict",
            "severity": "warning",
            "status": "failed",
            "message": "test message",
            "evidence": "test evidence",
        }
        check = ValidationCheck.from_dict(data)
        assert check.check_id == "PF-003"
        assert check.severity == CheckSeverity.WARNING
        assert check.status == CheckStatus.FAILED
        assert check.evidence == "test evidence"


class TestValidationReport:
    """Tests for ValidationReport dataclass."""

    def test_create_basic_report(self) -> None:
        """Test creating a basic validation report."""
        checks = [
            ValidationCheck(
                check_id="PF-001",
                name="check1",
                severity=CheckSeverity.CRITICAL,
                status=CheckStatus.PASSED,
                message="OK",
            ),
        ]
        report = ValidationReport(
            task_id="task_001",
            task_directory="/path/to/task",
            timestamp="2026-01-28T12:00:00",
            checks=checks,
        )
        assert report.task_id == "task_001"
        assert report.overall_passed is True
        assert report.critical_passed == 1
        assert report.critical_total == 1

    def test_report_with_failures(self) -> None:
        """Test report with failed critical checks."""
        checks = [
            ValidationCheck(
                check_id="PF-001",
                name="check1",
                severity=CheckSeverity.CRITICAL,
                status=CheckStatus.PASSED,
                message="OK",
            ),
            ValidationCheck(
                check_id="PF-002",
                name="check2",
                severity=CheckSeverity.CRITICAL,
                status=CheckStatus.FAILED,
                message="Failed",
            ),
        ]
        report = ValidationReport(
            task_id="task_002",
            task_directory="/path",
            timestamp="2026-01-28T12:00:00",
            checks=checks,
        )
        assert report.overall_passed is False
        assert report.critical_passed == 1
        assert report.critical_total == 2

    def test_get_failed_critical(self) -> None:
        """Test getting failed critical checks."""
        checks = [
            ValidationCheck(
                check_id="PF-001",
                name="check1",
                severity=CheckSeverity.CRITICAL,
                status=CheckStatus.FAILED,
                message="Failed 1",
            ),
            ValidationCheck(
                check_id="PF-002",
                name="check2",
                severity=CheckSeverity.WARNING,
                status=CheckStatus.FAILED,
                message="Failed 2",
            ),
            ValidationCheck(
                check_id="PF-003",
                name="check3",
                severity=CheckSeverity.CRITICAL,
                status=CheckStatus.PASSED,
                message="OK",
            ),
        ]
        report = ValidationReport(
            task_id="task_003",
            task_directory="/path",
            timestamp="2026-01-28T12:00:00",
            checks=checks,
        )
        failed = report.get_failed_critical()
        assert len(failed) == 1
        assert failed[0].check_id == "PF-001"

    def test_get_failed_warnings(self) -> None:
        """Test getting failed warning checks."""
        checks = [
            ValidationCheck(
                check_id="PF-001",
                name="check1",
                severity=CheckSeverity.WARNING,
                status=CheckStatus.FAILED,
                message="Warning 1",
            ),
            ValidationCheck(
                check_id="PF-002",
                name="check2",
                severity=CheckSeverity.WARNING,
                status=CheckStatus.PASSED,
                message="OK",
            ),
        ]
        report = ValidationReport(
            task_id="task_004",
            task_directory="/path",
            timestamp="2026-01-28T12:00:00",
            checks=checks,
        )
        warnings = report.get_failed_warnings()
        assert len(warnings) == 1
        assert warnings[0].check_id == "PF-001"

    def test_to_markdown(self) -> None:
        """Test generating markdown report."""
        checks = [
            ValidationCheck(
                check_id="PF-001",
                name="check1",
                severity=CheckSeverity.CRITICAL,
                status=CheckStatus.PASSED,
                message="OK",
            ),
        ]
        report = ValidationReport(
            task_id="task_005",
            task_directory="/path",
            timestamp="2026-01-28T12:00:00",
            checks=checks,
        )
        md = report.to_markdown()
        assert "# Pre-flight Validation Report: task_005" in md
        assert "Overall Status:** PASS" in md
        assert "PF-001" in md


class TestPreflightValidator:
    """Tests for PreflightValidator class."""

    @pytest.fixture
    def validator(self) -> PreflightValidator:
        """Create a validator instance."""
        return PreflightValidator()

    @pytest.fixture
    def valid_task_dir(self) -> Generator[Path, None, None]:
        """Create a valid task directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task_001"
            task_dir.mkdir()

            # Create task.toml
            task_toml = task_dir / "task.toml"
            task_toml.write_text("""
version = "1.0"

[metadata]
task_id = "task_001"
benchmark_name = "test"

[verifier]
timeout_sec = 600.0
command = "bash /tests/test.sh"

[agent]
timeout_sec = 1200.0

[environment]
build_timeout_sec = 300.0
cpus = 2
memory = "8G"
storage = "20G"
""")

            # Create environment directory and Dockerfile
            env_dir = task_dir / "environment"
            env_dir.mkdir()
            dockerfile = env_dir / "Dockerfile"
            dockerfile.write_text("FROM python:3.10-slim\n")

            # Create tests directory
            tests_dir = task_dir / "tests"
            tests_dir.mkdir()

            # Create test.sh with executable permissions
            test_sh = tests_dir / "test.sh"
            test_sh.write_text("#!/bin/bash\necho 'test'\n")
            os.chmod(test_sh, os.stat(test_sh).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

            # Create ground_truth.json
            ground_truth = tests_dir / "ground_truth.json"
            ground_truth.write_text('{"expected": "value"}')

            # Create instruction.md
            instruction = task_dir / "instruction.md"
            instruction.write_text("""# Task Instructions

This is a test task for the benchmark.

## Requirements

1. Complete the implementation
2. Pass all tests
3. Follow the coding guidelines

## Expected Output

The solution should produce correct results.
""")

            yield task_dir

    def test_validate_valid_task(
        self, validator: PreflightValidator, valid_task_dir: Path
    ) -> None:
        """Test validating a fully valid task directory."""
        report = validator.validate_task_directory(valid_task_dir)
        assert report.overall_passed is True
        assert report.critical_passed == report.critical_total
        assert len(report.get_failed_critical()) == 0

    def test_check_task_toml_missing(self, validator: PreflightValidator) -> None:
        """Test detecting missing task.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()

            report = validator.validate_task_directory(task_dir)
            assert report.overall_passed is False
            failed = report.get_failed_critical()
            assert any(c.check_id == "PF-001" for c in failed)

    def test_check_task_toml_invalid(self, validator: PreflightValidator) -> None:
        """Test detecting invalid TOML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()
            task_toml = task_dir / "task.toml"
            task_toml.write_text("invalid = [toml content")

            report = validator.validate_task_directory(task_dir)
            assert report.overall_passed is False
            failed = report.get_failed_critical()
            assert any(c.check_id == "PF-001" for c in failed)

    def test_check_task_toml_missing_fields(self, validator: PreflightValidator) -> None:
        """Test detecting missing required fields in task.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()
            task_toml = task_dir / "task.toml"
            task_toml.write_text('version = "1.0"\n')

            report = validator.validate_task_directory(task_dir)
            assert report.overall_passed is False
            failed = report.get_failed_critical()
            assert any(c.check_id == "PF-001" for c in failed)

    def test_check_dockerfile_missing(self, validator: PreflightValidator) -> None:
        """Test detecting missing Dockerfile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()
            task_toml = task_dir / "task.toml"
            task_toml.write_text("""
version = "1.0"
[metadata]
task_id = "test"
[verifier]
timeout_sec = 600
command = "test"
""")

            report = validator.validate_task_directory(task_dir)
            assert report.overall_passed is False
            failed = report.get_failed_critical()
            assert any(c.check_id == "PF-002" for c in failed)

    def test_check_dockerfile_in_environment(self, validator: PreflightValidator) -> None:
        """Test finding Dockerfile in environment directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()
            env_dir = task_dir / "environment"
            env_dir.mkdir()
            dockerfile = env_dir / "Dockerfile"
            dockerfile.write_text("FROM python:3.10\n")

            check, _ = validator._check_task_toml(task_dir)
            dockerfile_check = validator._check_dockerfile_presence(task_dir)
            assert dockerfile_check.status == CheckStatus.PASSED

    def test_check_test_sh_missing(self, validator: PreflightValidator) -> None:
        """Test detecting missing test.sh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()

            check = validator._check_test_sh_executability(task_dir)
            assert check.status == CheckStatus.FAILED
            assert check.check_id == "PF-003"

    def test_check_test_sh_not_executable(self, validator: PreflightValidator) -> None:
        """Test detecting non-executable test.sh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()
            tests_dir = task_dir / "tests"
            tests_dir.mkdir()
            test_sh = tests_dir / "test.sh"
            test_sh.write_text("#!/bin/bash\necho test\n")
            # Remove execute permission
            os.chmod(test_sh, stat.S_IRUSR | stat.S_IWUSR)

            check = validator._check_test_sh_executability(task_dir)
            assert check.status == CheckStatus.FAILED
            assert "not executable" in check.message

    def test_check_ground_truth_missing(self, validator: PreflightValidator) -> None:
        """Test detecting missing ground_truth.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()

            check = validator._check_ground_truth_presence(task_dir)
            assert check.status == CheckStatus.FAILED
            assert check.check_id == "PF-004"

    def test_check_ground_truth_invalid_json(self, validator: PreflightValidator) -> None:
        """Test detecting invalid JSON in ground_truth.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()
            tests_dir = task_dir / "tests"
            tests_dir.mkdir()
            gt = tests_dir / "ground_truth.json"
            gt.write_text("{invalid json}")

            check = validator._check_ground_truth_presence(task_dir)
            assert check.status == CheckStatus.FAILED
            assert "not valid JSON" in check.message

    def test_check_instruction_md_missing(self, validator: PreflightValidator) -> None:
        """Test detecting missing instruction.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()

            check = validator._check_instruction_md(task_dir)
            assert check.status == CheckStatus.FAILED
            assert check.check_id == "PF-005"

    def test_check_instruction_md_too_short(self, validator: PreflightValidator) -> None:
        """Test detecting too short instruction.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()
            instruction = task_dir / "instruction.md"
            instruction.write_text("Short")

            check = validator._check_instruction_md(task_dir)
            assert check.status == CheckStatus.FAILED
            assert check.severity == CheckSeverity.WARNING

    def test_check_instruction_md_with_placeholders(
        self, validator: PreflightValidator
    ) -> None:
        """Test detecting unresolved placeholders in instruction.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()
            instruction = task_dir / "instruction.md"
            instruction.write_text(
                "# Task\n\nThis has {placeholder} that needs to be filled.\n" * 10
            )

            check = validator._check_instruction_md(task_dir)
            assert check.status == CheckStatus.FAILED
            assert "placeholders" in check.message

    def test_check_no_secrets_clean(self, validator: PreflightValidator) -> None:
        """Test clean files pass secrets check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()
            task_toml = task_dir / "task.toml"
            task_toml.write_text('version = "1.0"\n[metadata]\ntask_id = "test"\n')
            instruction = task_dir / "instruction.md"
            instruction.write_text("# Clean instruction file\n")

            check = validator._check_no_secrets(task_dir)
            assert check.status == CheckStatus.PASSED

    def test_check_no_secrets_detects_api_key(
        self, validator: PreflightValidator
    ) -> None:
        """Test detecting hardcoded API keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()
            instruction = task_dir / "instruction.md"
            instruction.write_text(
                "Use this api_key = 'sk-proj-abcdefghijklmnopqrstuvwxyz123456'"
            )

            check = validator._check_no_secrets(task_dir)
            assert check.status == CheckStatus.FAILED

    def test_check_no_secrets_detects_github_token(
        self, validator: PreflightValidator
    ) -> None:
        """Test detecting GitHub tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()
            instruction = task_dir / "instruction.md"
            instruction.write_text("Token: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

            check = validator._check_no_secrets(task_dir)
            assert check.status == CheckStatus.FAILED

    def test_check_no_secrets_ignores_env_vars(
        self, validator: PreflightValidator
    ) -> None:
        """Test that environment variable references are not flagged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()
            instruction = task_dir / "instruction.md"
            instruction.write_text("Use api_key=${API_KEY} from environment")

            check = validator._check_no_secrets(task_dir)
            assert check.status == CheckStatus.PASSED

    def test_check_timeout_values_valid(self, validator: PreflightValidator) -> None:
        """Test valid timeout values pass."""
        toml_data = {
            "verifier": {"timeout_sec": 600.0},
            "agent": {"timeout_sec": 1200.0},
            "environment": {"build_timeout_sec": 300.0},
        }
        check = validator._check_timeout_values(toml_data)
        assert check.status == CheckStatus.PASSED

    def test_check_timeout_values_too_low(self, validator: PreflightValidator) -> None:
        """Test detecting too low timeout values."""
        toml_data = {
            "verifier": {"timeout_sec": 1.0},  # Too low
            "agent": {"timeout_sec": 1200.0},
        }
        check = validator._check_timeout_values(toml_data)
        assert check.status == CheckStatus.FAILED
        assert "too low" in check.evidence

    def test_check_timeout_values_too_high(self, validator: PreflightValidator) -> None:
        """Test detecting too high timeout values."""
        toml_data = {
            "verifier": {"timeout_sec": 100000.0},  # Too high
        }
        check = validator._check_timeout_values(toml_data)
        assert check.status == CheckStatus.FAILED
        assert "too high" in check.evidence

    def test_check_timeout_values_invalid_type(
        self, validator: PreflightValidator
    ) -> None:
        """Test detecting non-numeric timeout values."""
        toml_data = {
            "verifier": {"timeout_sec": "not a number"},
        }
        check = validator._check_timeout_values(toml_data)
        assert check.status == CheckStatus.FAILED
        assert "not a number" in check.evidence

    def test_check_resource_limits_valid(self, validator: PreflightValidator) -> None:
        """Test valid resource limits pass."""
        toml_data = {
            "environment": {
                "cpus": 4,
                "memory": "16G",
                "storage": "50G",
            }
        }
        check = validator._check_resource_limits(toml_data)
        assert check.status == CheckStatus.PASSED

    def test_check_resource_limits_missing_cpus(
        self, validator: PreflightValidator
    ) -> None:
        """Test detecting missing CPU limit."""
        toml_data = {
            "environment": {
                "memory": "16G",
            }
        }
        check = validator._check_resource_limits(toml_data)
        assert check.status == CheckStatus.FAILED
        assert "cpus not specified" in check.evidence

    def test_check_resource_limits_missing_memory(
        self, validator: PreflightValidator
    ) -> None:
        """Test detecting missing memory limit."""
        toml_data = {
            "environment": {
                "cpus": 4,
            }
        }
        check = validator._check_resource_limits(toml_data)
        assert check.status == CheckStatus.FAILED
        assert "memory not specified" in check.evidence

    def test_check_resource_limits_various_memory_formats(
        self, validator: PreflightValidator
    ) -> None:
        """Test parsing various memory format strings."""
        test_cases = [
            {"memory": "8G"},
            {"memory": "8GB"},
            {"memory": "8192M"},
            {"memory": "8192MB"},
        ]
        for case in test_cases:
            toml_data = {"environment": {"cpus": 2, "storage": "20G", **case}}
            check = validator._check_resource_limits(toml_data)
            assert check.status == CheckStatus.PASSED, f"Failed for {case}"

    def test_check_resource_limits_memory_too_high(
        self, validator: PreflightValidator
    ) -> None:
        """Test detecting memory limit that's too high."""
        toml_data = {"environment": {"cpus": 2, "storage": "20G", "memory": "1T"}}
        check = validator._check_resource_limits(toml_data)
        assert check.status == CheckStatus.FAILED
        assert "too high" in check.evidence

    def test_validate_adapter_directory(
        self, validator: PreflightValidator, valid_task_dir: Path
    ) -> None:
        """Test validating an adapter directory with multiple tasks."""
        # Create adapter dir containing the valid task
        adapter_dir = valid_task_dir.parent

        reports = validator.validate_adapter_directory(adapter_dir)
        assert len(reports) == 1
        assert reports[0].overall_passed is True

    def test_validate_adapter_directory_empty(
        self, validator: PreflightValidator
    ) -> None:
        """Test validating an empty adapter directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter_dir = Path(tmpdir)
            reports = validator.validate_adapter_directory(adapter_dir)
            assert len(reports) == 0

    def test_get_all_check_ids(self, validator: PreflightValidator) -> None:
        """Test getting all check IDs."""
        ids = validator.get_all_check_ids()
        assert "PF-001" in ids
        assert "PF-008" in ids
        assert len(ids) == 8

    def test_get_check_descriptions(self, validator: PreflightValidator) -> None:
        """Test getting check descriptions."""
        descriptions = validator.get_check_descriptions()
        assert "PF-001" in descriptions
        assert "task.toml" in descriptions["PF-001"]


class TestCheckEnums:
    """Tests for CheckSeverity and CheckStatus enums."""

    def test_severity_values(self) -> None:
        """Test CheckSeverity enum values."""
        assert CheckSeverity.CRITICAL.value == "critical"
        assert CheckSeverity.WARNING.value == "warning"
        assert CheckSeverity.INFO.value == "info"

    def test_status_values(self) -> None:
        """Test CheckStatus enum values."""
        assert CheckStatus.PASSED.value == "passed"
        assert CheckStatus.FAILED.value == "failed"
        assert CheckStatus.SKIPPED.value == "skipped"


class TestValidationReportSerialization:
    """Tests for report serialization and deserialization."""

    def test_round_trip_json(self) -> None:
        """Test JSON serialization round trip."""
        checks = [
            ValidationCheck(
                check_id="PF-001",
                name="test",
                severity=CheckSeverity.CRITICAL,
                status=CheckStatus.PASSED,
                message="OK",
                evidence="detail",
            ),
            ValidationCheck(
                check_id="PF-002",
                name="test2",
                severity=CheckSeverity.WARNING,
                status=CheckStatus.FAILED,
                message="Failed",
            ),
        ]
        original = ValidationReport(
            task_id="test_task",
            task_directory="/path/to/task",
            timestamp="2026-01-28T12:00:00",
            checks=checks,
            metadata={"key": "value"},
        )

        # Serialize and deserialize
        data = original.to_dict()
        json_str = json.dumps(data)
        loaded_data = json.loads(json_str)
        restored = ValidationReport.from_dict(loaded_data)

        assert restored.task_id == original.task_id
        assert restored.task_directory == original.task_directory
        assert len(restored.checks) == len(original.checks)
        assert restored.overall_passed == original.overall_passed
        assert restored.critical_passed == original.critical_passed


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def validator(self) -> PreflightValidator:
        """Create a validator instance."""
        return PreflightValidator()

    def test_task_toml_missing_metadata_task_id(
        self, validator: PreflightValidator
    ) -> None:
        """Test handling task.toml without task_id in metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()
            task_toml = task_dir / "task.toml"
            task_toml.write_text("""
version = "1.0"
[metadata]
benchmark_name = "test"
[verifier]
timeout_sec = 600
command = "test"
""")

            report = validator.validate_task_directory(task_dir)
            assert report.overall_passed is False
            failed = report.get_failed_critical()
            assert any("task_id" in (c.evidence or "") for c in failed)

    def test_task_toml_missing_verifier_command(
        self, validator: PreflightValidator
    ) -> None:
        """Test handling task.toml without verifier command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "task"
            task_dir.mkdir()
            task_toml = task_dir / "task.toml"
            task_toml.write_text("""
version = "1.0"
[metadata]
task_id = "test"
[verifier]
timeout_sec = 600
""")

            report = validator.validate_task_directory(task_dir)
            assert report.overall_passed is False
            failed = report.get_failed_critical()
            assert any("command" in (c.evidence or "") for c in failed)

    def test_empty_toml_data_for_timeout_check(
        self, validator: PreflightValidator
    ) -> None:
        """Test timeout check with empty toml data."""
        check = validator._check_timeout_values({})
        assert check.status == CheckStatus.SKIPPED

    def test_empty_toml_data_for_resource_check(
        self, validator: PreflightValidator
    ) -> None:
        """Test resource limit check with empty toml data."""
        check = validator._check_resource_limits({})
        assert check.status == CheckStatus.SKIPPED

    def test_task_id_from_directory_name(self, validator: PreflightValidator) -> None:
        """Test that task_id defaults to directory name if not in toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "my_custom_task_name"
            task_dir.mkdir()

            # Create minimal structure that will fail but report task_id
            report = validator.validate_task_directory(task_dir)
            assert report.task_id == "my_custom_task_name"
