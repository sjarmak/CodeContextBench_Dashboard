"""
Pre-flight validation checks for Harbor benchmark adapters.

Provides automated validation of adapter output before deployment,
checking task.toml schema, file presence, executability, and quality.

Usage:
    validator = PreflightValidator()
    report = validator.validate_task_directory(task_dir)
    if report.overall_passed:
        print("Task is ready for deployment")
"""

import os
import re
import stat
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


class CheckSeverity(Enum):
    """Severity levels for validation checks."""

    CRITICAL = "critical"  # Must pass for deployment
    WARNING = "warning"  # Should pass, may indicate issues
    INFO = "info"  # Informational, best practice


class CheckStatus(Enum):
    """Status of a validation check."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ValidationCheck:
    """
    Result of a single validation check.

    Attributes:
        check_id: Unique identifier for the check
        name: Human-readable name of the check
        severity: How critical this check is
        status: Whether the check passed, failed, or was skipped
        message: Detailed message about the result
        evidence: Supporting evidence or details
    """

    check_id: str
    name: str
    severity: CheckSeverity
    status: CheckStatus
    message: str
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "check_id": self.check_id,
            "name": self.name,
            "severity": self.severity.value,
            "status": self.status.value,
            "message": self.message,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationCheck":
        """Create from dictionary representation."""
        return cls(
            check_id=data["check_id"],
            name=data["name"],
            severity=CheckSeverity(data["severity"]),
            status=CheckStatus(data["status"]),
            message=data["message"],
            evidence=data.get("evidence", ""),
        )


@dataclass
class ValidationReport:
    """
    Aggregated validation report for a task or adapter.

    Attributes:
        task_id: Identifier for the validated task
        task_directory: Path to the task directory
        timestamp: When the validation was performed
        checks: List of individual check results
        overall_passed: Whether critical checks all passed
        critical_passed: Count of passed critical checks
        critical_total: Total count of critical checks
        warning_passed: Count of passed warning-level checks
        warning_total: Total count of warning-level checks
        metadata: Additional metadata about the validation
    """

    task_id: str
    task_directory: str
    timestamp: str
    checks: list[ValidationCheck]
    overall_passed: bool = False
    critical_passed: int = 0
    critical_total: int = 0
    warning_passed: int = 0
    warning_total: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Compute aggregate statistics if not provided."""
        if self.critical_total == 0 and self.warning_total == 0:
            self._compute_statistics()

    def _compute_statistics(self) -> None:
        """Compute pass/fail statistics from checks."""
        critical_passed = 0
        critical_total = 0
        warning_passed = 0
        warning_total = 0

        for check in self.checks:
            if check.severity == CheckSeverity.CRITICAL:
                critical_total += 1
                if check.status == CheckStatus.PASSED:
                    critical_passed += 1
            elif check.severity == CheckSeverity.WARNING:
                warning_total += 1
                if check.status == CheckStatus.PASSED:
                    warning_passed += 1

        self.critical_passed = critical_passed
        self.critical_total = critical_total
        self.warning_passed = warning_passed
        self.warning_total = warning_total

        # Overall passes if all critical checks pass
        self.overall_passed = critical_passed == critical_total

    def get_failed_critical(self) -> list[ValidationCheck]:
        """Get list of failed critical checks."""
        return [
            c
            for c in self.checks
            if c.severity == CheckSeverity.CRITICAL and c.status == CheckStatus.FAILED
        ]

    def get_failed_warnings(self) -> list[ValidationCheck]:
        """Get list of failed warning-level checks."""
        return [
            c
            for c in self.checks
            if c.severity == CheckSeverity.WARNING and c.status == CheckStatus.FAILED
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "task_id": self.task_id,
            "task_directory": self.task_directory,
            "timestamp": self.timestamp,
            "checks": [c.to_dict() for c in self.checks],
            "overall_passed": self.overall_passed,
            "critical_passed": self.critical_passed,
            "critical_total": self.critical_total,
            "warning_passed": self.warning_passed,
            "warning_total": self.warning_total,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationReport":
        """Create from dictionary representation."""
        checks = [ValidationCheck.from_dict(c) for c in data.get("checks", [])]
        return cls(
            task_id=data["task_id"],
            task_directory=data["task_directory"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            checks=checks,
            overall_passed=data.get("overall_passed", False),
            critical_passed=data.get("critical_passed", 0),
            critical_total=data.get("critical_total", 0),
            warning_passed=data.get("warning_passed", 0),
            warning_total=data.get("warning_total", 0),
            metadata=data.get("metadata", {}),
        )

    def to_markdown(self) -> str:
        """Generate markdown report."""
        status_emoji = "PASS" if self.overall_passed else "FAIL"
        lines = [
            f"# Pre-flight Validation Report: {self.task_id}",
            "",
            f"**Directory:** `{self.task_directory}`",
            f"**Timestamp:** {self.timestamp}",
            f"**Overall Status:** {status_emoji}",
            "",
            "## Summary",
            "",
            f"| Severity | Passed | Total |",
            f"|----------|--------|-------|",
            f"| Critical | {self.critical_passed} | {self.critical_total} |",
            f"| Warning | {self.warning_passed} | {self.warning_total} |",
            "",
        ]

        # Add failed critical items
        failed_critical = self.get_failed_critical()
        if failed_critical:
            lines.append("## Failed Critical Checks")
            lines.append("")
            for check in failed_critical:
                lines.append(f"- **{check.check_id}** ({check.name}): {check.message}")
                if check.evidence:
                    lines.append(f"  - Evidence: {check.evidence}")
            lines.append("")

        # Add failed warnings
        failed_warnings = self.get_failed_warnings()
        if failed_warnings:
            lines.append("## Warnings")
            lines.append("")
            for check in failed_warnings:
                lines.append(f"- **{check.check_id}** ({check.name}): {check.message}")
                if check.evidence:
                    lines.append(f"  - Evidence: {check.evidence}")
            lines.append("")

        # Add all checks detail
        lines.append("## All Checks")
        lines.append("")
        lines.append("| ID | Name | Severity | Status | Message |")
        lines.append("|----|------|----------|--------|---------|")
        for check in self.checks:
            status_str = check.status.value.upper()
            lines.append(
                f"| {check.check_id} | {check.name} | {check.severity.value} | "
                f"{status_str} | {check.message} |"
            )

        return "\n".join(lines)


class PreflightValidator:
    """
    Pre-flight validation for Harbor benchmark adapters.

    Validates task directories before deployment, checking:
    - task.toml schema validity
    - Dockerfile presence
    - test.sh executability
    - ground_truth.json presence
    - instruction.md completeness
    - No hardcoded secrets
    - Valid timeout values
    - Resource limits set
    """

    # Patterns for detecting potential secrets
    SECRET_PATTERNS = [
        (r"(?i)(api[_-]?ke[y]s?|apikey)\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{20,}['\"]?", "API key"),
        (r"(?i)(secret[_-]?ke[y]s?|secretkey)\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{20,}['\"]?", "Secret key"),
        (r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"]{8,}['\"]?", "Password"),
        (r"(?i)(token|auth[_-]?token)\s*[:=]\s*['\"]?[a-zA-Z0-9_\-\.]{20,}['\"]?", "Token"),
        (r"(?i)(private[_-]?ke[y])\s*[:=]", "Private key"),
        (r"-----BEGIN\s+(RSA|DSA|EC|OPENSSH)\s+PRIVATE\s+KEY-----", "Private key block"),
        (r"(?i)aws[_-]?(access[_-]?ke[y]|secret)\s*[:=]\s*['\"]?[A-Z0-9]{16,}['\"]?", "AWS credential"),
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub personal access token"),
        (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth token"),
        (r"sk-[a-zA-Z0-9]{32,}", "OpenAI API key"),
        (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Bearer token"),
    ]

    # Required fields in task.toml
    REQUIRED_TOML_FIELDS = {
        "version": str,
        "metadata": dict,
        "verifier": dict,
    }

    # Required fields in metadata section
    REQUIRED_METADATA_FIELDS = ["task_id"]

    # Required fields in verifier section
    REQUIRED_VERIFIER_FIELDS = ["timeout_sec", "command"]

    # Minimum and maximum timeout values (seconds)
    MIN_TIMEOUT = 10.0
    MAX_TIMEOUT = 86400.0  # 24 hours

    # Resource limit constraints
    MIN_CPUS = 1
    MAX_CPUS = 64
    MIN_MEMORY_GB = 1
    MAX_MEMORY_GB = 512

    def __init__(self) -> None:
        """Initialize the validator."""
        self._compiled_patterns = [
            (re.compile(pattern), name)
            for pattern, name in self.SECRET_PATTERNS
        ]

    def validate_task_directory(self, task_dir: Path | str) -> ValidationReport:
        """
        Validate a task directory against all pre-flight checks.

        Args:
            task_dir: Path to the task directory

        Returns:
            ValidationReport with all check results
        """
        task_dir = Path(task_dir)
        checks: list[ValidationCheck] = []

        # Extract task ID from directory name or task.toml
        task_id = task_dir.name
        toml_data: dict[str, Any] = {}

        # Check 1: task.toml presence and schema validity
        task_toml_check, toml_data = self._check_task_toml(task_dir)
        checks.append(task_toml_check)

        # Update task_id from toml if available
        if toml_data and "metadata" in toml_data:
            task_id = toml_data["metadata"].get("task_id", task_id)

        # Check 2: Dockerfile presence
        checks.append(self._check_dockerfile_presence(task_dir))

        # Check 3: test.sh executability
        checks.append(self._check_test_sh_executability(task_dir))

        # Check 4: ground_truth.json presence
        checks.append(self._check_ground_truth_presence(task_dir))

        # Check 5: instruction.md completeness
        checks.append(self._check_instruction_md(task_dir))

        # Check 6: No hardcoded secrets
        checks.append(self._check_no_secrets(task_dir))

        # Check 7: Valid timeout values
        checks.append(self._check_timeout_values(toml_data))

        # Check 8: Resource limits set
        checks.append(self._check_resource_limits(toml_data))

        return ValidationReport(
            task_id=task_id,
            task_directory=str(task_dir),
            timestamp=datetime.now().isoformat(),
            checks=checks,
        )

    def validate_adapter_directory(self, adapter_dir: Path | str) -> list[ValidationReport]:
        """
        Validate all tasks in an adapter output directory.

        Args:
            adapter_dir: Path to the adapter output directory containing task directories

        Returns:
            List of ValidationReports, one per task
        """
        adapter_dir = Path(adapter_dir)
        reports: list[ValidationReport] = []

        # Look for task directories (directories containing task.toml)
        for item in adapter_dir.iterdir():
            if item.is_dir():
                task_toml = item / "task.toml"
                if task_toml.exists():
                    reports.append(self.validate_task_directory(item))

        return reports

    def _check_task_toml(self, task_dir: Path) -> tuple[ValidationCheck, dict[str, Any]]:
        """
        Check task.toml presence and schema validity.

        Returns:
            Tuple of (ValidationCheck, parsed toml data or empty dict)
        """
        task_toml = task_dir / "task.toml"

        if not task_toml.exists():
            return (
                ValidationCheck(
                    check_id="PF-001",
                    name="task.toml presence",
                    severity=CheckSeverity.CRITICAL,
                    status=CheckStatus.FAILED,
                    message="task.toml file not found",
                    evidence=f"Expected at: {task_toml}",
                ),
                {},
            )

        try:
            with open(task_toml, "rb") as f:
                toml_data = tomllib.load(f)
        except Exception as e:
            return (
                ValidationCheck(
                    check_id="PF-001",
                    name="task.toml validity",
                    severity=CheckSeverity.CRITICAL,
                    status=CheckStatus.FAILED,
                    message="task.toml is not valid TOML",
                    evidence=str(e),
                ),
                {},
            )

        # Check required fields
        missing_fields: list[str] = []
        for field_name in self.REQUIRED_TOML_FIELDS:
            if field_name not in toml_data:
                missing_fields.append(field_name)

        if missing_fields:
            return (
                ValidationCheck(
                    check_id="PF-001",
                    name="task.toml schema",
                    severity=CheckSeverity.CRITICAL,
                    status=CheckStatus.FAILED,
                    message="task.toml missing required fields",
                    evidence=f"Missing: {', '.join(missing_fields)}",
                ),
                toml_data,
            )

        # Check metadata section
        metadata = toml_data.get("metadata", {})
        missing_metadata: list[str] = []
        for field_name in self.REQUIRED_METADATA_FIELDS:
            if field_name not in metadata:
                missing_metadata.append(field_name)

        if missing_metadata:
            return (
                ValidationCheck(
                    check_id="PF-001",
                    name="task.toml metadata",
                    severity=CheckSeverity.CRITICAL,
                    status=CheckStatus.FAILED,
                    message="task.toml metadata missing required fields",
                    evidence=f"Missing: {', '.join(missing_metadata)}",
                ),
                toml_data,
            )

        # Check verifier section
        verifier = toml_data.get("verifier", {})
        missing_verifier: list[str] = []
        for field_name in self.REQUIRED_VERIFIER_FIELDS:
            if field_name not in verifier:
                missing_verifier.append(field_name)

        if missing_verifier:
            return (
                ValidationCheck(
                    check_id="PF-001",
                    name="task.toml verifier",
                    severity=CheckSeverity.CRITICAL,
                    status=CheckStatus.FAILED,
                    message="task.toml verifier missing required fields",
                    evidence=f"Missing: {', '.join(missing_verifier)}",
                ),
                toml_data,
            )

        return (
            ValidationCheck(
                check_id="PF-001",
                name="task.toml schema",
                severity=CheckSeverity.CRITICAL,
                status=CheckStatus.PASSED,
                message="task.toml is valid and contains required fields",
            ),
            toml_data,
        )

    def _check_dockerfile_presence(self, task_dir: Path) -> ValidationCheck:
        """Check that Dockerfile exists in the task directory."""
        # Check common locations for Dockerfile
        dockerfile_locations = [
            task_dir / "Dockerfile",
            task_dir / "environment" / "Dockerfile",
            task_dir / "docker" / "Dockerfile",
        ]

        for location in dockerfile_locations:
            if location.exists():
                return ValidationCheck(
                    check_id="PF-002",
                    name="Dockerfile presence",
                    severity=CheckSeverity.CRITICAL,
                    status=CheckStatus.PASSED,
                    message="Dockerfile found",
                    evidence=str(location),
                )

        return ValidationCheck(
            check_id="PF-002",
            name="Dockerfile presence",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAILED,
            message="Dockerfile not found",
            evidence=f"Searched: {', '.join(str(loc) for loc in dockerfile_locations)}",
        )

    def _check_test_sh_executability(self, task_dir: Path) -> ValidationCheck:
        """Check that test.sh exists and is executable."""
        # Check common locations for test.sh
        test_sh_locations = [
            task_dir / "test.sh",
            task_dir / "tests" / "test.sh",
        ]

        for location in test_sh_locations:
            if location.exists():
                # Check if file is executable
                file_stat = location.stat()
                is_executable = bool(file_stat.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))

                if is_executable:
                    return ValidationCheck(
                        check_id="PF-003",
                        name="test.sh executability",
                        severity=CheckSeverity.CRITICAL,
                        status=CheckStatus.PASSED,
                        message="test.sh found and is executable",
                        evidence=str(location),
                    )
                else:
                    return ValidationCheck(
                        check_id="PF-003",
                        name="test.sh executability",
                        severity=CheckSeverity.CRITICAL,
                        status=CheckStatus.FAILED,
                        message="test.sh found but is not executable",
                        evidence=f"File: {location}, Mode: {oct(file_stat.st_mode)}",
                    )

        return ValidationCheck(
            check_id="PF-003",
            name="test.sh presence",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAILED,
            message="test.sh not found",
            evidence=f"Searched: {', '.join(str(loc) for loc in test_sh_locations)}",
        )

    def _check_ground_truth_presence(self, task_dir: Path) -> ValidationCheck:
        """Check that ground_truth.json exists."""
        # Check common locations for ground_truth.json
        gt_locations = [
            task_dir / "ground_truth.json",
            task_dir / "tests" / "ground_truth.json",
        ]

        for location in gt_locations:
            if location.exists():
                # Try to parse it as valid JSON
                try:
                    import json
                    with open(location) as f:
                        json.load(f)
                    return ValidationCheck(
                        check_id="PF-004",
                        name="ground_truth.json presence",
                        severity=CheckSeverity.CRITICAL,
                        status=CheckStatus.PASSED,
                        message="ground_truth.json found and is valid JSON",
                        evidence=str(location),
                    )
                except json.JSONDecodeError as e:
                    return ValidationCheck(
                        check_id="PF-004",
                        name="ground_truth.json validity",
                        severity=CheckSeverity.CRITICAL,
                        status=CheckStatus.FAILED,
                        message="ground_truth.json found but is not valid JSON",
                        evidence=str(e),
                    )

        return ValidationCheck(
            check_id="PF-004",
            name="ground_truth.json presence",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.FAILED,
            message="ground_truth.json not found",
            evidence=f"Searched: {', '.join(str(loc) for loc in gt_locations)}",
        )

    def _check_instruction_md(self, task_dir: Path) -> ValidationCheck:
        """Check that instruction.md exists and has reasonable content."""
        instruction_md = task_dir / "instruction.md"

        if not instruction_md.exists():
            return ValidationCheck(
                check_id="PF-005",
                name="instruction.md presence",
                severity=CheckSeverity.CRITICAL,
                status=CheckStatus.FAILED,
                message="instruction.md not found",
                evidence=str(instruction_md),
            )

        try:
            content = instruction_md.read_text(encoding="utf-8")
        except Exception as e:
            return ValidationCheck(
                check_id="PF-005",
                name="instruction.md readability",
                severity=CheckSeverity.CRITICAL,
                status=CheckStatus.FAILED,
                message="instruction.md could not be read",
                evidence=str(e),
            )

        # Check minimum content length
        min_length = 100  # characters
        if len(content.strip()) < min_length:
            return ValidationCheck(
                check_id="PF-005",
                name="instruction.md completeness",
                severity=CheckSeverity.WARNING,
                status=CheckStatus.FAILED,
                message=f"instruction.md is too short (< {min_length} chars)",
                evidence=f"Length: {len(content.strip())} characters",
            )

        # Check for empty placeholders
        placeholder_patterns = [
            r"\{[a-zA-Z_]+\}",  # {placeholder}
            r"\[\[.*?\]\]",  # [[placeholder]]
            r"TODO",
            r"FIXME",
        ]
        found_placeholders: list[str] = []
        for pattern in placeholder_patterns:
            matches = re.findall(pattern, content)
            found_placeholders.extend(matches)

        if found_placeholders:
            return ValidationCheck(
                check_id="PF-005",
                name="instruction.md completeness",
                severity=CheckSeverity.WARNING,
                status=CheckStatus.FAILED,
                message="instruction.md contains unresolved placeholders",
                evidence=f"Found: {', '.join(found_placeholders[:5])}",
            )

        return ValidationCheck(
            check_id="PF-005",
            name="instruction.md completeness",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.PASSED,
            message="instruction.md is complete and readable",
            evidence=f"Length: {len(content.strip())} characters",
        )

    def _check_no_secrets(self, task_dir: Path) -> ValidationCheck:
        """Check that no hardcoded secrets are present in task files."""
        # Files to check for secrets
        files_to_check = [
            task_dir / "task.toml",
            task_dir / "instruction.md",
            task_dir / "Dockerfile",
            task_dir / "environment" / "Dockerfile",
            task_dir / "test.sh",
            task_dir / "tests" / "test.sh",
            task_dir / "ground_truth.json",
            task_dir / "tests" / "ground_truth.json",
        ]

        found_secrets: list[str] = []

        for file_path in files_to_check:
            if not file_path.exists():
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern, secret_type in self._compiled_patterns:
                matches = pattern.findall(content)
                if matches:
                    # Filter out obvious false positives
                    for match in matches:
                        match_str = match if isinstance(match, str) else str(match)
                        # Skip environment variable references
                        if "${" in match_str or "$(" in match_str:
                            continue
                        # Skip template placeholders
                        if "{" in match_str and "}" in match_str:
                            continue
                        found_secrets.append(f"{secret_type} in {file_path.name}")

        if found_secrets:
            return ValidationCheck(
                check_id="PF-006",
                name="No hardcoded secrets",
                severity=CheckSeverity.CRITICAL,
                status=CheckStatus.FAILED,
                message="Potential hardcoded secrets detected",
                evidence="; ".join(found_secrets[:5]),
            )

        return ValidationCheck(
            check_id="PF-006",
            name="No hardcoded secrets",
            severity=CheckSeverity.CRITICAL,
            status=CheckStatus.PASSED,
            message="No hardcoded secrets detected",
        )

    def _check_timeout_values(self, toml_data: dict[str, Any]) -> ValidationCheck:
        """Check that timeout values are valid and reasonable."""
        if not toml_data:
            return ValidationCheck(
                check_id="PF-007",
                name="Valid timeout values",
                severity=CheckSeverity.WARNING,
                status=CheckStatus.SKIPPED,
                message="Could not check timeouts (task.toml not parsed)",
            )

        invalid_timeouts: list[str] = []

        # Check verifier timeout
        verifier = toml_data.get("verifier", {})
        verifier_timeout = verifier.get("timeout_sec")
        if verifier_timeout is not None:
            try:
                timeout_val = float(verifier_timeout)
                if timeout_val < self.MIN_TIMEOUT:
                    invalid_timeouts.append(
                        f"verifier.timeout_sec too low: {timeout_val} < {self.MIN_TIMEOUT}"
                    )
                elif timeout_val > self.MAX_TIMEOUT:
                    invalid_timeouts.append(
                        f"verifier.timeout_sec too high: {timeout_val} > {self.MAX_TIMEOUT}"
                    )
            except (TypeError, ValueError):
                invalid_timeouts.append(f"verifier.timeout_sec not a number: {verifier_timeout}")

        # Check agent timeout
        agent = toml_data.get("agent", {})
        agent_timeout = agent.get("timeout_sec")
        if agent_timeout is not None:
            try:
                timeout_val = float(agent_timeout)
                if timeout_val < self.MIN_TIMEOUT:
                    invalid_timeouts.append(
                        f"agent.timeout_sec too low: {timeout_val} < {self.MIN_TIMEOUT}"
                    )
                elif timeout_val > self.MAX_TIMEOUT:
                    invalid_timeouts.append(
                        f"agent.timeout_sec too high: {timeout_val} > {self.MAX_TIMEOUT}"
                    )
            except (TypeError, ValueError):
                invalid_timeouts.append(f"agent.timeout_sec not a number: {agent_timeout}")

        # Check environment build timeout
        environment = toml_data.get("environment", {})
        build_timeout = environment.get("build_timeout_sec")
        if build_timeout is not None:
            try:
                timeout_val = float(build_timeout)
                if timeout_val < self.MIN_TIMEOUT:
                    invalid_timeouts.append(
                        f"environment.build_timeout_sec too low: {timeout_val} < {self.MIN_TIMEOUT}"
                    )
                elif timeout_val > self.MAX_TIMEOUT:
                    invalid_timeouts.append(
                        f"environment.build_timeout_sec too high: {timeout_val} > {self.MAX_TIMEOUT}"
                    )
            except (TypeError, ValueError):
                invalid_timeouts.append(
                    f"environment.build_timeout_sec not a number: {build_timeout}"
                )

        if invalid_timeouts:
            return ValidationCheck(
                check_id="PF-007",
                name="Valid timeout values",
                severity=CheckSeverity.WARNING,
                status=CheckStatus.FAILED,
                message="Invalid timeout values detected",
                evidence="; ".join(invalid_timeouts),
            )

        return ValidationCheck(
            check_id="PF-007",
            name="Valid timeout values",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.PASSED,
            message="All timeout values are valid",
        )

    def _check_resource_limits(self, toml_data: dict[str, Any]) -> ValidationCheck:
        """Check that resource limits are set and valid."""
        if not toml_data:
            return ValidationCheck(
                check_id="PF-008",
                name="Resource limits set",
                severity=CheckSeverity.WARNING,
                status=CheckStatus.SKIPPED,
                message="Could not check resource limits (task.toml not parsed)",
            )

        environment = toml_data.get("environment", {})
        issues: list[str] = []

        # Check CPUs
        cpus = environment.get("cpus")
        if cpus is None:
            issues.append("cpus not specified")
        else:
            try:
                cpus_val = int(cpus)
                if cpus_val < self.MIN_CPUS:
                    issues.append(f"cpus too low: {cpus_val} < {self.MIN_CPUS}")
                elif cpus_val > self.MAX_CPUS:
                    issues.append(f"cpus too high: {cpus_val} > {self.MAX_CPUS}")
            except (TypeError, ValueError):
                issues.append(f"cpus not a valid integer: {cpus}")

        # Check memory
        memory = environment.get("memory")
        if memory is None:
            issues.append("memory not specified")
        else:
            # Parse memory value (e.g., "8G", "8GB", "8192M")
            memory_str = str(memory).upper()
            memory_gb: float | None = None
            try:
                if memory_str.endswith("G") or memory_str.endswith("GB"):
                    memory_gb = float(memory_str.rstrip("GB"))
                elif memory_str.endswith("M") or memory_str.endswith("MB"):
                    memory_gb = float(memory_str.rstrip("MB")) / 1024
                elif memory_str.endswith("T") or memory_str.endswith("TB"):
                    memory_gb = float(memory_str.rstrip("TB")) * 1024
                else:
                    # Assume bytes if no unit
                    memory_gb = float(memory_str) / (1024 * 1024 * 1024)
            except ValueError:
                issues.append(f"memory not a valid value: {memory}")

            if memory_gb is not None:
                if memory_gb < self.MIN_MEMORY_GB:
                    issues.append(f"memory too low: {memory_gb}GB < {self.MIN_MEMORY_GB}GB")
                elif memory_gb > self.MAX_MEMORY_GB:
                    issues.append(f"memory too high: {memory_gb}GB > {self.MAX_MEMORY_GB}GB")

        # Check storage (optional but recommended)
        storage = environment.get("storage")
        if storage is None:
            issues.append("storage not specified (recommended)")

        if issues:
            # Determine severity based on issues
            has_critical = any(
                "not specified" in issue and "storage" not in issue
                for issue in issues
            )
            return ValidationCheck(
                check_id="PF-008",
                name="Resource limits set",
                severity=CheckSeverity.WARNING,
                status=CheckStatus.FAILED,
                message="Resource limit issues detected",
                evidence="; ".join(issues),
            )

        return ValidationCheck(
            check_id="PF-008",
            name="Resource limits set",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.PASSED,
            message="All resource limits are properly set",
        )

    def get_all_check_ids(self) -> list[str]:
        """Get list of all check IDs performed by this validator."""
        return [
            "PF-001",  # task.toml schema
            "PF-002",  # Dockerfile presence
            "PF-003",  # test.sh executability
            "PF-004",  # ground_truth.json presence
            "PF-005",  # instruction.md completeness
            "PF-006",  # No hardcoded secrets
            "PF-007",  # Valid timeout values
            "PF-008",  # Resource limits set
        ]

    def get_check_descriptions(self) -> dict[str, str]:
        """Get descriptions for all checks."""
        return {
            "PF-001": "task.toml is present, valid TOML, and contains required fields",
            "PF-002": "Dockerfile is present in the task directory",
            "PF-003": "test.sh is present and has executable permissions",
            "PF-004": "ground_truth.json is present and contains valid JSON",
            "PF-005": "instruction.md is present, readable, and has sufficient content",
            "PF-006": "No hardcoded secrets or credentials in task files",
            "PF-007": "All timeout values are within reasonable bounds",
            "PF-008": "Resource limits (CPU, memory, storage) are specified",
        }
