"""
HOW2BENCH checklist data model for benchmark quality assurance.

Implements the 55-criteria HOW2BENCH checklist as structured data,
organized into categories: data_quality, reproducibility, and methodology.
Each criterion has severity (critical/important/recommended) and
an automated flag indicating if it can be automatically verified.

Usage:
    checklist = HOW2BenchChecklist()
    criteria = checklist.get_all_criteria()
    critical = checklist.get_by_severity(CriterionSeverity.CRITICAL)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class CriterionCategory(Enum):
    """Categories for HOW2BENCH checklist criteria."""

    DATA_QUALITY = "data_quality"
    REPRODUCIBILITY = "reproducibility"
    METHODOLOGY = "methodology"


class CriterionSeverity(Enum):
    """Severity levels for HOW2BENCH criteria."""

    CRITICAL = "critical"  # Must pass for benchmark to be valid
    IMPORTANT = "important"  # Should pass, failures need justification
    RECOMMENDED = "recommended"  # Best practice, optional


@dataclass
class ChecklistCriterion:
    """
    A single HOW2BENCH checklist criterion.

    Attributes:
        id: Unique identifier for the criterion (e.g., "DQ-001")
        category: Category this criterion belongs to
        description: Human-readable description of the criterion
        severity: How critical this criterion is
        automated: Whether this can be automatically verified
        verification_hint: Guidance on how to verify this criterion
    """

    id: str
    category: CriterionCategory
    description: str
    severity: CriterionSeverity
    automated: bool
    verification_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "category": self.category.value,
            "description": self.description,
            "severity": self.severity.value,
            "automated": self.automated,
            "verification_hint": self.verification_hint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChecklistCriterion":
        """Create from dictionary representation."""
        return cls(
            id=data["id"],
            category=CriterionCategory(data["category"]),
            description=data["description"],
            severity=CriterionSeverity(data["severity"]),
            automated=data.get("automated", False),
            verification_hint=data.get("verification_hint", ""),
        )


@dataclass
class ChecklistResult:
    """
    Result of evaluating a single criterion.

    Attributes:
        criterion_id: ID of the evaluated criterion
        passed: Whether the criterion was satisfied
        evidence: Evidence supporting the result
        notes: Additional notes or context
    """

    criterion_id: str
    passed: bool
    evidence: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "criterion_id": self.criterion_id,
            "passed": self.passed,
            "evidence": self.evidence,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChecklistResult":
        """Create from dictionary representation."""
        return cls(
            criterion_id=data["criterion_id"],
            passed=data["passed"],
            evidence=data.get("evidence", ""),
            notes=data.get("notes", ""),
        )


@dataclass
class BenchmarkAuditReport:
    """
    Aggregated audit report for a benchmark.

    Attributes:
        benchmark_name: Name of the audited benchmark
        timestamp: When the audit was performed
        results: List of individual criterion results
        overall_passed: Whether the benchmark passes overall
        critical_passed: Count of passed critical criteria
        critical_total: Total count of critical criteria
        important_passed: Count of passed important criteria
        important_total: Total count of important criteria
        recommended_passed: Count of passed recommended criteria
        recommended_total: Total count of recommended criteria
        metadata: Additional metadata about the audit
    """

    benchmark_name: str
    timestamp: str
    results: list[ChecklistResult]
    overall_passed: bool = False
    critical_passed: int = 0
    critical_total: int = 0
    important_passed: int = 0
    important_total: int = 0
    recommended_passed: int = 0
    recommended_total: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Compute aggregate statistics if not provided."""
        if self.critical_total == 0 and self.important_total == 0:
            self._compute_statistics()

    def _compute_statistics(self) -> None:
        """Compute pass/fail statistics from results."""
        checklist = HOW2BenchChecklist()
        criteria_map = {c.id: c for c in checklist.get_all_criteria()}

        critical_passed = 0
        critical_total = 0
        important_passed = 0
        important_total = 0
        recommended_passed = 0
        recommended_total = 0

        for result in self.results:
            criterion = criteria_map.get(result.criterion_id)
            if not criterion:
                continue

            if criterion.severity == CriterionSeverity.CRITICAL:
                critical_total += 1
                if result.passed:
                    critical_passed += 1
            elif criterion.severity == CriterionSeverity.IMPORTANT:
                important_total += 1
                if result.passed:
                    important_passed += 1
            else:
                recommended_total += 1
                if result.passed:
                    recommended_passed += 1

        self.critical_passed = critical_passed
        self.critical_total = critical_total
        self.important_passed = important_passed
        self.important_total = important_total
        self.recommended_passed = recommended_passed
        self.recommended_total = recommended_total

        # Overall passes if all critical criteria pass
        self.overall_passed = critical_passed == critical_total

    def get_pass_rate(self) -> float:
        """Calculate overall pass rate as a percentage."""
        total = self.critical_total + self.important_total + self.recommended_total
        if total == 0:
            return 0.0
        passed = self.critical_passed + self.important_passed + self.recommended_passed
        return (passed / total) * 100.0

    def get_failed_critical(self) -> list[ChecklistResult]:
        """Get list of failed critical criteria results."""
        checklist = HOW2BenchChecklist()
        criteria_map = {c.id: c for c in checklist.get_all_criteria()}
        return [
            r
            for r in self.results
            if not r.passed
            and criteria_map.get(r.criterion_id, ChecklistCriterion(
                id="", category=CriterionCategory.DATA_QUALITY,
                description="", severity=CriterionSeverity.RECOMMENDED, automated=False
            )).severity == CriterionSeverity.CRITICAL
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "benchmark_name": self.benchmark_name,
            "timestamp": self.timestamp,
            "results": [r.to_dict() for r in self.results],
            "overall_passed": self.overall_passed,
            "critical_passed": self.critical_passed,
            "critical_total": self.critical_total,
            "important_passed": self.important_passed,
            "important_total": self.important_total,
            "recommended_passed": self.recommended_passed,
            "recommended_total": self.recommended_total,
            "pass_rate": self.get_pass_rate(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchmarkAuditReport":
        """Create from dictionary representation."""
        results = [ChecklistResult.from_dict(r) for r in data.get("results", [])]
        return cls(
            benchmark_name=data["benchmark_name"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            results=results,
            overall_passed=data.get("overall_passed", False),
            critical_passed=data.get("critical_passed", 0),
            critical_total=data.get("critical_total", 0),
            important_passed=data.get("important_passed", 0),
            important_total=data.get("important_total", 0),
            recommended_passed=data.get("recommended_passed", 0),
            recommended_total=data.get("recommended_total", 0),
            metadata=data.get("metadata", {}),
        )

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            f"# Benchmark Audit Report: {self.benchmark_name}",
            "",
            f"**Timestamp:** {self.timestamp}",
            f"**Overall Status:** {'PASS' if self.overall_passed else 'FAIL'}",
            f"**Pass Rate:** {self.get_pass_rate():.1f}%",
            "",
            "## Summary",
            "",
            f"| Severity | Passed | Total | Rate |",
            f"|----------|--------|-------|------|",
            f"| Critical | {self.critical_passed} | {self.critical_total} | "
            f"{(self.critical_passed / self.critical_total * 100) if self.critical_total else 0:.1f}% |",
            f"| Important | {self.important_passed} | {self.important_total} | "
            f"{(self.important_passed / self.important_total * 100) if self.important_total else 0:.1f}% |",
            f"| Recommended | {self.recommended_passed} | {self.recommended_total} | "
            f"{(self.recommended_passed / self.recommended_total * 100) if self.recommended_total else 0:.1f}% |",
            "",
        ]

        # Add failed critical items
        failed_critical = self.get_failed_critical()
        if failed_critical:
            lines.append("## Failed Critical Criteria")
            lines.append("")
            for result in failed_critical:
                lines.append(f"- **{result.criterion_id}**: {result.notes or 'No notes'}")
            lines.append("")

        return "\n".join(lines)


class HOW2BenchChecklist:
    """
    HOW2BENCH checklist containing 55 quality criteria for benchmarks.

    Criteria are organized into three categories:
    - Data Quality (DQ): Ensuring data integrity and validity
    - Reproducibility (RP): Enabling consistent reproduction of results
    - Methodology (MT): Proper experimental design and evaluation
    """

    def __init__(self) -> None:
        """Initialize the checklist with all 55 criteria."""
        self._criteria: list[ChecklistCriterion] = self._build_criteria()

    def _build_criteria(self) -> list[ChecklistCriterion]:
        """Build the complete list of 55 HOW2BENCH criteria."""
        criteria: list[ChecklistCriterion] = []

        # === DATA QUALITY CRITERIA (DQ-001 to DQ-020) ===
        criteria.extend([
            ChecklistCriterion(
                id="DQ-001",
                category=CriterionCategory.DATA_QUALITY,
                description="Task descriptions are clear and unambiguous",
                severity=CriterionSeverity.CRITICAL,
                automated=False,
                verification_hint="Review task descriptions for clarity and specificity",
            ),
            ChecklistCriterion(
                id="DQ-002",
                category=CriterionCategory.DATA_QUALITY,
                description="Ground truth solutions are verified as correct",
                severity=CriterionSeverity.CRITICAL,
                automated=False,
                verification_hint="Manually verify ground truth against task requirements",
            ),
            ChecklistCriterion(
                id="DQ-003",
                category=CriterionCategory.DATA_QUALITY,
                description="Test cases cover all specified requirements",
                severity=CriterionSeverity.CRITICAL,
                automated=True,
                verification_hint="Check test coverage against requirements list",
            ),
            ChecklistCriterion(
                id="DQ-004",
                category=CriterionCategory.DATA_QUALITY,
                description="No data leakage between train/test splits",
                severity=CriterionSeverity.CRITICAL,
                automated=True,
                verification_hint="Verify no overlap in task IDs or content between splits",
            ),
            ChecklistCriterion(
                id="DQ-005",
                category=CriterionCategory.DATA_QUALITY,
                description="Tasks are free from personally identifiable information (PII)",
                severity=CriterionSeverity.CRITICAL,
                automated=True,
                verification_hint="Scan for PII patterns (emails, names, addresses)",
            ),
            ChecklistCriterion(
                id="DQ-006",
                category=CriterionCategory.DATA_QUALITY,
                description="Code samples are syntactically valid",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Parse code samples to verify syntax",
            ),
            ChecklistCriterion(
                id="DQ-007",
                category=CriterionCategory.DATA_QUALITY,
                description="Dependencies are explicitly listed",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Check for requirements.txt, package.json, or similar",
            ),
            ChecklistCriterion(
                id="DQ-008",
                category=CriterionCategory.DATA_QUALITY,
                description="File paths are normalized and consistent",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Verify path separators and relative/absolute consistency",
            ),
            ChecklistCriterion(
                id="DQ-009",
                category=CriterionCategory.DATA_QUALITY,
                description="Encoding is consistent (UTF-8 recommended)",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Check file encodings for consistency",
            ),
            ChecklistCriterion(
                id="DQ-010",
                category=CriterionCategory.DATA_QUALITY,
                description="Task difficulty labels are calibrated",
                severity=CriterionSeverity.IMPORTANT,
                automated=False,
                verification_hint="Validate difficulty ratings against actual complexity",
            ),
            ChecklistCriterion(
                id="DQ-011",
                category=CriterionCategory.DATA_QUALITY,
                description="No hardcoded secrets or credentials in tasks",
                severity=CriterionSeverity.CRITICAL,
                automated=True,
                verification_hint="Scan for API tokens, passwords, private keys",
            ),
            ChecklistCriterion(
                id="DQ-012",
                category=CriterionCategory.DATA_QUALITY,
                description="Task IDs are unique across the benchmark",
                severity=CriterionSeverity.CRITICAL,
                automated=True,
                verification_hint="Verify no duplicate task IDs exist",
            ),
            ChecklistCriterion(
                id="DQ-013",
                category=CriterionCategory.DATA_QUALITY,
                description="JSON/YAML/TOML files are valid",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Parse all configuration files to verify validity",
            ),
            ChecklistCriterion(
                id="DQ-014",
                category=CriterionCategory.DATA_QUALITY,
                description="Natural language is grammatically correct",
                severity=CriterionSeverity.RECOMMENDED,
                automated=True,
                verification_hint="Run grammar checker on task descriptions",
            ),
            ChecklistCriterion(
                id="DQ-015",
                category=CriterionCategory.DATA_QUALITY,
                description="Numeric values are within reasonable bounds",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Validate numeric fields against expected ranges",
            ),
            ChecklistCriterion(
                id="DQ-016",
                category=CriterionCategory.DATA_QUALITY,
                description="Required fields are present in all tasks",
                severity=CriterionSeverity.CRITICAL,
                automated=True,
                verification_hint="Check schema compliance for all tasks",
            ),
            ChecklistCriterion(
                id="DQ-017",
                category=CriterionCategory.DATA_QUALITY,
                description="Data sources are attributed and licensed",
                severity=CriterionSeverity.IMPORTANT,
                automated=False,
                verification_hint="Verify attribution for all external data",
            ),
            ChecklistCriterion(
                id="DQ-018",
                category=CriterionCategory.DATA_QUALITY,
                description="Sample size is statistically meaningful",
                severity=CriterionSeverity.IMPORTANT,
                automated=False,
                verification_hint="Ensure sufficient tasks for meaningful evaluation",
            ),
            ChecklistCriterion(
                id="DQ-019",
                category=CriterionCategory.DATA_QUALITY,
                description="No broken or invalid URLs in tasks",
                severity=CriterionSeverity.RECOMMENDED,
                automated=True,
                verification_hint="Validate all URLs are reachable",
            ),
            ChecklistCriterion(
                id="DQ-020",
                category=CriterionCategory.DATA_QUALITY,
                description="Timestamps and dates are in ISO 8601 format",
                severity=CriterionSeverity.RECOMMENDED,
                automated=True,
                verification_hint="Verify date/time format compliance",
            ),
        ])

        # === REPRODUCIBILITY CRITERIA (RP-001 to RP-018) ===
        criteria.extend([
            ChecklistCriterion(
                id="RP-001",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Evaluation scripts produce deterministic results",
                severity=CriterionSeverity.CRITICAL,
                automated=True,
                verification_hint="Run evaluation twice and compare results",
            ),
            ChecklistCriterion(
                id="RP-002",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Random seeds are documented and settable",
                severity=CriterionSeverity.CRITICAL,
                automated=True,
                verification_hint="Check for seed parameters in configuration",
            ),
            ChecklistCriterion(
                id="RP-003",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Docker/container configuration is provided",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Verify Dockerfile or docker-compose.yml exists",
            ),
            ChecklistCriterion(
                id="RP-004",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Dependency versions are pinned",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Check for pinned versions in requirements",
            ),
            ChecklistCriterion(
                id="RP-005",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Setup instructions are documented and tested",
                severity=CriterionSeverity.CRITICAL,
                automated=False,
                verification_hint="Follow setup instructions on a clean system",
            ),
            ChecklistCriterion(
                id="RP-006",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Evaluation timeouts are specified",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Check for timeout configuration in task definitions",
            ),
            ChecklistCriterion(
                id="RP-007",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Resource limits are documented (CPU, memory, disk)",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Verify resource limits in configuration files",
            ),
            ChecklistCriterion(
                id="RP-008",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Versioning scheme is consistent (semver recommended)",
                severity=CriterionSeverity.RECOMMENDED,
                automated=True,
                verification_hint="Check version format compliance",
            ),
            ChecklistCriterion(
                id="RP-009",
                category=CriterionCategory.REPRODUCIBILITY,
                description="CI/CD pipeline configuration is included",
                severity=CriterionSeverity.RECOMMENDED,
                automated=True,
                verification_hint="Check for .github/workflows or similar CI config",
            ),
            ChecklistCriterion(
                id="RP-010",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Test fixtures are version controlled",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Verify test data is in repository",
            ),
            ChecklistCriterion(
                id="RP-011",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Output format is documented (reward.json schema)",
                severity=CriterionSeverity.CRITICAL,
                automated=True,
                verification_hint="Check for output schema documentation",
            ),
            ChecklistCriterion(
                id="RP-012",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Environment variables are documented",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Check for .env.example or environment documentation",
            ),
            ChecklistCriterion(
                id="RP-013",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Platform requirements are specified (OS, architecture)",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Verify platform requirements in documentation",
            ),
            ChecklistCriterion(
                id="RP-014",
                category=CriterionCategory.REPRODUCIBILITY,
                description="External service dependencies are documented",
                severity=CriterionSeverity.IMPORTANT,
                automated=False,
                verification_hint="List all required external services",
            ),
            ChecklistCriterion(
                id="RP-015",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Caching behavior is documented and controllable",
                severity=CriterionSeverity.RECOMMENDED,
                automated=True,
                verification_hint="Check for cache configuration options",
            ),
            ChecklistCriterion(
                id="RP-016",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Network access requirements are documented",
                severity=CriterionSeverity.IMPORTANT,
                automated=False,
                verification_hint="Document required network connectivity",
            ),
            ChecklistCriterion(
                id="RP-017",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Logging is configurable and consistent",
                severity=CriterionSeverity.RECOMMENDED,
                automated=True,
                verification_hint="Check for logging configuration options",
            ),
            ChecklistCriterion(
                id="RP-018",
                category=CriterionCategory.REPRODUCIBILITY,
                description="Benchmark version is included in output metadata",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Verify version is captured in results",
            ),
        ])

        # === METHODOLOGY CRITERIA (MT-001 to MT-017) ===
        criteria.extend([
            ChecklistCriterion(
                id="MT-001",
                category=CriterionCategory.METHODOLOGY,
                description="Evaluation metrics are clearly defined",
                severity=CriterionSeverity.CRITICAL,
                automated=False,
                verification_hint="Review metric definitions for precision",
            ),
            ChecklistCriterion(
                id="MT-002",
                category=CriterionCategory.METHODOLOGY,
                description="Baseline results are provided for comparison",
                severity=CriterionSeverity.IMPORTANT,
                automated=False,
                verification_hint="Verify baseline results are documented",
            ),
            ChecklistCriterion(
                id="MT-003",
                category=CriterionCategory.METHODOLOGY,
                description="Scoring rubric is explicit and objective",
                severity=CriterionSeverity.CRITICAL,
                automated=False,
                verification_hint="Review scoring criteria for objectivity",
            ),
            ChecklistCriterion(
                id="MT-004",
                category=CriterionCategory.METHODOLOGY,
                description="Edge cases are documented and tested",
                severity=CriterionSeverity.IMPORTANT,
                automated=False,
                verification_hint="Review test coverage for edge cases",
            ),
            ChecklistCriterion(
                id="MT-005",
                category=CriterionCategory.METHODOLOGY,
                description="Task selection methodology is documented",
                severity=CriterionSeverity.IMPORTANT,
                automated=False,
                verification_hint="Verify task selection rationale is explained",
            ),
            ChecklistCriterion(
                id="MT-006",
                category=CriterionCategory.METHODOLOGY,
                description="Partial credit scoring is implemented where appropriate",
                severity=CriterionSeverity.RECOMMENDED,
                automated=True,
                verification_hint="Check if scoring supports partial credit",
            ),
            ChecklistCriterion(
                id="MT-007",
                category=CriterionCategory.METHODOLOGY,
                description="Task difficulty distribution is balanced",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Analyze difficulty distribution statistics",
            ),
            ChecklistCriterion(
                id="MT-008",
                category=CriterionCategory.METHODOLOGY,
                description="Tasks cover diverse programming concepts",
                severity=CriterionSeverity.IMPORTANT,
                automated=False,
                verification_hint="Review concept coverage across tasks",
            ),
            ChecklistCriterion(
                id="MT-009",
                category=CriterionCategory.METHODOLOGY,
                description="Human evaluation guidelines are provided",
                severity=CriterionSeverity.RECOMMENDED,
                automated=False,
                verification_hint="Check for human evaluator instructions",
            ),
            ChecklistCriterion(
                id="MT-010",
                category=CriterionCategory.METHODOLOGY,
                description="Inter-rater reliability is measured (for human eval)",
                severity=CriterionSeverity.RECOMMENDED,
                automated=False,
                verification_hint="Verify IRR scores are documented",
            ),
            ChecklistCriterion(
                id="MT-011",
                category=CriterionCategory.METHODOLOGY,
                description="Statistical significance thresholds are defined",
                severity=CriterionSeverity.RECOMMENDED,
                automated=False,
                verification_hint="Check for significance level documentation",
            ),
            ChecklistCriterion(
                id="MT-012",
                category=CriterionCategory.METHODOLOGY,
                description="Error analysis methodology is documented",
                severity=CriterionSeverity.RECOMMENDED,
                automated=False,
                verification_hint="Verify error categorization scheme exists",
            ),
            ChecklistCriterion(
                id="MT-013",
                category=CriterionCategory.METHODOLOGY,
                description="Contamination checks are documented",
                severity=CriterionSeverity.IMPORTANT,
                automated=False,
                verification_hint="Verify contamination prevention measures",
            ),
            ChecklistCriterion(
                id="MT-014",
                category=CriterionCategory.METHODOLOGY,
                description="Evaluation order is randomized or controlled",
                severity=CriterionSeverity.IMPORTANT,
                automated=True,
                verification_hint="Check for evaluation order configuration",
            ),
            ChecklistCriterion(
                id="MT-015",
                category=CriterionCategory.METHODOLOGY,
                description="Multiple evaluation runs are supported",
                severity=CriterionSeverity.RECOMMENDED,
                automated=True,
                verification_hint="Verify multiple run support in evaluation script",
            ),
            ChecklistCriterion(
                id="MT-016",
                category=CriterionCategory.METHODOLOGY,
                description="Confidence intervals are computed for metrics",
                severity=CriterionSeverity.RECOMMENDED,
                automated=True,
                verification_hint="Check if CI computation is implemented",
            ),
            ChecklistCriterion(
                id="MT-017",
                category=CriterionCategory.METHODOLOGY,
                description="Failure modes are documented and categorized",
                severity=CriterionSeverity.IMPORTANT,
                automated=False,
                verification_hint="Review failure mode documentation",
            ),
        ])

        return criteria

    def get_all_criteria(self) -> list[ChecklistCriterion]:
        """Get all 55 HOW2BENCH criteria."""
        return self._criteria.copy()

    def get_by_id(self, criterion_id: str) -> ChecklistCriterion | None:
        """Get a criterion by its ID."""
        for criterion in self._criteria:
            if criterion.id == criterion_id:
                return criterion
        return None

    def get_by_category(self, category: CriterionCategory) -> list[ChecklistCriterion]:
        """Get all criteria in a specific category."""
        return [c for c in self._criteria if c.category == category]

    def get_by_severity(self, severity: CriterionSeverity) -> list[ChecklistCriterion]:
        """Get all criteria with a specific severity."""
        return [c for c in self._criteria if c.severity == severity]

    def get_automated(self) -> list[ChecklistCriterion]:
        """Get all criteria that can be automatically verified."""
        return [c for c in self._criteria if c.automated]

    def get_manual(self) -> list[ChecklistCriterion]:
        """Get all criteria that require manual verification."""
        return [c for c in self._criteria if not c.automated]

    def count_by_category(self) -> dict[str, int]:
        """Count criteria by category."""
        return {
            CriterionCategory.DATA_QUALITY.value: len(
                self.get_by_category(CriterionCategory.DATA_QUALITY)
            ),
            CriterionCategory.REPRODUCIBILITY.value: len(
                self.get_by_category(CriterionCategory.REPRODUCIBILITY)
            ),
            CriterionCategory.METHODOLOGY.value: len(
                self.get_by_category(CriterionCategory.METHODOLOGY)
            ),
        }

    def count_by_severity(self) -> dict[str, int]:
        """Count criteria by severity."""
        return {
            CriterionSeverity.CRITICAL.value: len(
                self.get_by_severity(CriterionSeverity.CRITICAL)
            ),
            CriterionSeverity.IMPORTANT.value: len(
                self.get_by_severity(CriterionSeverity.IMPORTANT)
            ),
            CriterionSeverity.RECOMMENDED.value: len(
                self.get_by_severity(CriterionSeverity.RECOMMENDED)
            ),
        }

    def create_audit_report(
        self,
        benchmark_name: str,
        results: list[ChecklistResult],
        metadata: dict[str, Any] | None = None,
    ) -> BenchmarkAuditReport:
        """
        Create an audit report from evaluation results.

        Args:
            benchmark_name: Name of the benchmark being audited
            results: List of ChecklistResult from evaluation
            metadata: Optional additional metadata

        Returns:
            BenchmarkAuditReport with computed statistics
        """
        return BenchmarkAuditReport(
            benchmark_name=benchmark_name,
            timestamp=datetime.now().isoformat(),
            results=results,
            metadata=metadata or {},
        )
