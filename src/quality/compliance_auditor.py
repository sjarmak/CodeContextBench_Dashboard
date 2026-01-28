"""
Documentation compliance auditor for benchmark quality assurance.

Provides compliance checks against documentation requirements including
README.md presence and sections, DESIGN.md with task selection rationale,
and LICENSE compatibility with data source attribution.

Usage:
    auditor = ComplianceAuditor()
    report = auditor.audit_benchmark(Path("benchmarks/ainativebench"))
    print(report.to_markdown())
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from src.quality.how2bench_checklist import (
    BenchmarkAuditReport,
    ChecklistResult,
)


class ComplianceCategory(Enum):
    """Categories for compliance checks."""

    README = "readme"
    DESIGN = "design"
    LICENSE = "license"
    ATTRIBUTION = "attribution"


class ComplianceSeverity(Enum):
    """Severity levels for compliance checks."""

    CRITICAL = "critical"  # Must pass for benchmark compliance
    IMPORTANT = "important"  # Should pass, failures need justification
    RECOMMENDED = "recommended"  # Best practice, optional


@dataclass
class ComplianceCheck:
    """
    Definition of a single compliance check.

    Attributes:
        check_id: Unique identifier for the check (e.g., "CA-001")
        category: Category this check belongs to
        description: Human-readable description of the check
        severity: How critical this check is
    """

    check_id: str
    category: ComplianceCategory
    description: str
    severity: ComplianceSeverity

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "check_id": self.check_id,
            "category": self.category.value,
            "description": self.description,
            "severity": self.severity.value,
        }


@dataclass
class ComplianceCheckResult:
    """
    Result of a single compliance check.

    Attributes:
        check_id: ID of the evaluated check
        passed: Whether the check was satisfied
        evidence: Evidence supporting the result
        notes: Additional notes or context
    """

    check_id: str
    passed: bool
    evidence: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "evidence": self.evidence,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ComplianceCheckResult":
        """Create from dictionary representation."""
        return cls(
            check_id=data["check_id"],
            passed=data["passed"],
            evidence=data.get("evidence", ""),
            notes=data.get("notes", ""),
        )


@dataclass
class ComplianceReport:
    """
    Aggregated compliance report for a benchmark.

    Attributes:
        benchmark_name: Name of the audited benchmark
        benchmark_directory: Path to the benchmark directory
        timestamp: When the audit was performed
        results: List of individual check results
        overall_passed: Whether the benchmark passes overall
        critical_passed: Count of passed critical checks
        critical_total: Total count of critical checks
        important_passed: Count of passed important checks
        important_total: Total count of important checks
        recommended_passed: Count of passed recommended checks
        recommended_total: Total count of recommended checks
        metadata: Additional metadata about the audit
    """

    benchmark_name: str
    benchmark_directory: str
    timestamp: str
    results: list[ComplianceCheckResult]
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
        auditor = ComplianceAuditor()
        checks_map = {c.check_id: c for c in auditor.get_all_checks()}

        critical_passed = 0
        critical_total = 0
        important_passed = 0
        important_total = 0
        recommended_passed = 0
        recommended_total = 0

        for result in self.results:
            check = checks_map.get(result.check_id)
            if not check:
                continue

            if check.severity == ComplianceSeverity.CRITICAL:
                critical_total += 1
                if result.passed:
                    critical_passed += 1
            elif check.severity == ComplianceSeverity.IMPORTANT:
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

        # Overall passes if all critical checks pass
        self.overall_passed = critical_passed == critical_total

    def get_pass_rate(self) -> float:
        """Calculate overall pass rate as a percentage."""
        total = self.critical_total + self.important_total + self.recommended_total
        if total == 0:
            return 0.0
        passed = self.critical_passed + self.important_passed + self.recommended_passed
        return (passed / total) * 100.0

    def get_failed_critical(self) -> list[ComplianceCheckResult]:
        """Get list of failed critical check results."""
        auditor = ComplianceAuditor()
        checks_map = {c.check_id: c for c in auditor.get_all_checks()}
        return [
            r
            for r in self.results
            if not r.passed
            and checks_map.get(r.check_id, ComplianceCheck(
                check_id="", category=ComplianceCategory.README,
                description="", severity=ComplianceSeverity.RECOMMENDED
            )).severity == ComplianceSeverity.CRITICAL
        ]

    def get_failed_important(self) -> list[ComplianceCheckResult]:
        """Get list of failed important check results."""
        auditor = ComplianceAuditor()
        checks_map = {c.check_id: c for c in auditor.get_all_checks()}
        return [
            r
            for r in self.results
            if not r.passed
            and checks_map.get(r.check_id, ComplianceCheck(
                check_id="", category=ComplianceCategory.README,
                description="", severity=ComplianceSeverity.RECOMMENDED
            )).severity == ComplianceSeverity.IMPORTANT
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "benchmark_name": self.benchmark_name,
            "benchmark_directory": self.benchmark_directory,
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
    def from_dict(cls, data: dict[str, Any]) -> "ComplianceReport":
        """Create from dictionary representation."""
        results = [ComplianceCheckResult.from_dict(r) for r in data.get("results", [])]
        return cls(
            benchmark_name=data["benchmark_name"],
            benchmark_directory=data.get("benchmark_directory", ""),
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
        """Generate markdown compliance report."""
        status_text = "PASS" if self.overall_passed else "FAIL"
        lines = [
            f"# Compliance Report: {self.benchmark_name}",
            "",
            f"**Directory:** `{self.benchmark_directory}`",
            f"**Timestamp:** {self.timestamp}",
            f"**Overall Status:** {status_text}",
            f"**Pass Rate:** {self.get_pass_rate():.1f}%",
            "",
            "## Summary",
            "",
            "| Severity | Passed | Total | Rate |",
            "|----------|--------|-------|------|",
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
            lines.append("## Failed Critical Checks")
            lines.append("")
            for result in failed_critical:
                lines.append(f"- **{result.check_id}**: {result.notes or 'No notes'}")
                if result.evidence:
                    lines.append(f"  - Evidence: {result.evidence}")
            lines.append("")

        # Add failed important items
        failed_important = self.get_failed_important()
        if failed_important:
            lines.append("## Failed Important Checks")
            lines.append("")
            for result in failed_important:
                lines.append(f"- **{result.check_id}**: {result.notes or 'No notes'}")
                if result.evidence:
                    lines.append(f"  - Evidence: {result.evidence}")
            lines.append("")

        # Add all checks detail
        lines.append("## All Checks")
        lines.append("")
        lines.append("| ID | Category | Description | Status |")
        lines.append("|----|----------|-------------|--------|")

        auditor = ComplianceAuditor()
        checks_map = {c.check_id: c for c in auditor.get_all_checks()}

        for result in self.results:
            check = checks_map.get(result.check_id)
            if check:
                status_str = "PASS" if result.passed else "FAIL"
                lines.append(
                    f"| {result.check_id} | {check.category.value} | "
                    f"{check.description} | {status_str} |"
                )

        return "\n".join(lines)

    def to_benchmark_audit_report(self) -> BenchmarkAuditReport:
        """
        Convert to BenchmarkAuditReport for HOW2BENCH compatibility.

        Maps compliance checks to HOW2BENCH criterion IDs where applicable.
        """
        # Map compliance check IDs to HOW2BENCH criterion IDs
        check_to_criterion: dict[str, str] = {
            "CA-001": "DQ-017",  # README -> Data sources attributed
            "CA-004": "DQ-017",  # Data sources -> Attribution
            "CA-005": "MT-005",  # DESIGN -> Task selection documented
            "CA-008": "RP-005",  # Setup instructions
        }

        results: list[ChecklistResult] = []
        for cr in self.results:
            criterion_id = check_to_criterion.get(cr.check_id, cr.check_id)
            results.append(
                ChecklistResult(
                    criterion_id=criterion_id,
                    passed=cr.passed,
                    evidence=cr.evidence,
                    notes=cr.notes,
                )
            )

        return BenchmarkAuditReport(
            benchmark_name=self.benchmark_name,
            timestamp=self.timestamp,
            results=results,
            metadata=self.metadata,
        )


class ComplianceAuditor:
    """
    Documentation compliance auditor for benchmarks.

    Validates benchmark directories against documentation requirements:
    - README.md presence and required sections
    - DESIGN.md with task selection rationale
    - LICENSE compatibility and data source attribution
    """

    # Required sections in README.md
    README_REQUIRED_SECTIONS = [
        "description",
        "usage",
        "task format",
    ]

    # Optional but recommended sections in README.md
    README_RECOMMENDED_SECTIONS = [
        "installation",
        "examples",
        "contributing",
        "license",
    ]

    # Required sections in DESIGN.md
    DESIGN_REQUIRED_SECTIONS = [
        "task selection",
        "rationale",
    ]

    # Common open source licenses
    KNOWN_LICENSES = [
        "MIT",
        "Apache-2.0",
        "Apache License 2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "GPL-2.0",
        "GPL-3.0",
        "LGPL-2.1",
        "LGPL-3.0",
        "MPL-2.0",
        "ISC",
        "Unlicense",
        "CC0",
        "CC-BY-4.0",
        "CC-BY-SA-4.0",
    ]

    def __init__(self) -> None:
        """Initialize the compliance auditor."""
        self._checks = self._build_checks()

    def _build_checks(self) -> list[ComplianceCheck]:
        """Build the list of compliance checks."""
        return [
            # README checks
            ComplianceCheck(
                check_id="CA-001",
                category=ComplianceCategory.README,
                description="README.md file is present",
                severity=ComplianceSeverity.CRITICAL,
            ),
            ComplianceCheck(
                check_id="CA-002",
                category=ComplianceCategory.README,
                description="README.md contains description section",
                severity=ComplianceSeverity.CRITICAL,
            ),
            ComplianceCheck(
                check_id="CA-003",
                category=ComplianceCategory.README,
                description="README.md contains usage section",
                severity=ComplianceSeverity.IMPORTANT,
            ),
            ComplianceCheck(
                check_id="CA-004",
                category=ComplianceCategory.README,
                description="README.md contains data sources section",
                severity=ComplianceSeverity.IMPORTANT,
            ),
            # DESIGN checks
            ComplianceCheck(
                check_id="CA-005",
                category=ComplianceCategory.DESIGN,
                description="DESIGN.md file is present",
                severity=ComplianceSeverity.IMPORTANT,
            ),
            ComplianceCheck(
                check_id="CA-006",
                category=ComplianceCategory.DESIGN,
                description="DESIGN.md contains task selection rationale",
                severity=ComplianceSeverity.IMPORTANT,
            ),
            # LICENSE checks
            ComplianceCheck(
                check_id="CA-007",
                category=ComplianceCategory.LICENSE,
                description="LICENSE file is present",
                severity=ComplianceSeverity.CRITICAL,
            ),
            ComplianceCheck(
                check_id="CA-008",
                category=ComplianceCategory.LICENSE,
                description="LICENSE uses a recognized open source license",
                severity=ComplianceSeverity.IMPORTANT,
            ),
            # ATTRIBUTION checks
            ComplianceCheck(
                check_id="CA-009",
                category=ComplianceCategory.ATTRIBUTION,
                description="Data source attribution is documented",
                severity=ComplianceSeverity.IMPORTANT,
            ),
            ComplianceCheck(
                check_id="CA-010",
                category=ComplianceCategory.ATTRIBUTION,
                description="Third-party code attribution is documented",
                severity=ComplianceSeverity.RECOMMENDED,
            ),
        ]

    def get_all_checks(self) -> list[ComplianceCheck]:
        """Get all compliance checks."""
        return self._checks.copy()

    def get_check_by_id(self, check_id: str) -> ComplianceCheck | None:
        """Get a check by its ID."""
        for check in self._checks:
            if check.check_id == check_id:
                return check
        return None

    def audit_benchmark(self, benchmark_dir: Path | str) -> ComplianceReport:
        """
        Audit a benchmark directory for documentation compliance.

        Args:
            benchmark_dir: Path to the benchmark directory

        Returns:
            ComplianceReport with all check results
        """
        benchmark_dir = Path(benchmark_dir)
        benchmark_name = benchmark_dir.name
        results: list[ComplianceCheckResult] = []

        # Run all checks
        readme_path = benchmark_dir / "README.md"
        readme_content = ""
        if readme_path.exists():
            try:
                readme_content = readme_path.read_text(encoding="utf-8")
            except Exception:
                readme_content = ""

        design_path = benchmark_dir / "DESIGN.md"
        design_content = ""
        if design_path.exists():
            try:
                design_content = design_path.read_text(encoding="utf-8")
            except Exception:
                design_content = ""

        license_path = self._find_license_file(benchmark_dir)
        license_content = ""
        if license_path:
            try:
                license_content = license_path.read_text(encoding="utf-8")
            except Exception:
                license_content = ""

        # CA-001: README.md presence
        results.append(self._check_readme_presence(readme_path))

        # CA-002: README.md description section
        results.append(self._check_readme_description(readme_content))

        # CA-003: README.md usage section
        results.append(self._check_readme_usage(readme_content))

        # CA-004: README.md data sources section
        results.append(self._check_readme_data_sources(readme_content))

        # CA-005: DESIGN.md presence
        results.append(self._check_design_presence(design_path))

        # CA-006: DESIGN.md task selection rationale
        results.append(self._check_design_rationale(design_content))

        # CA-007: LICENSE presence
        results.append(self._check_license_presence(license_path))

        # CA-008: LICENSE is recognized
        results.append(self._check_license_recognized(license_content))

        # CA-009: Data source attribution
        results.append(self._check_data_attribution(benchmark_dir, readme_content))

        # CA-010: Third-party code attribution
        results.append(self._check_code_attribution(benchmark_dir, readme_content))

        return ComplianceReport(
            benchmark_name=benchmark_name,
            benchmark_directory=str(benchmark_dir),
            timestamp=datetime.now().isoformat(),
            results=results,
        )

    def _find_license_file(self, benchmark_dir: Path) -> Path | None:
        """Find the license file in the benchmark directory."""
        license_names = [
            "LICENSE",
            "LICENSE.md",
            "LICENSE.txt",
            "LICENCE",
            "LICENCE.md",
            "LICENCE.txt",
            "license",
            "license.md",
            "license.txt",
        ]
        for name in license_names:
            license_path = benchmark_dir / name
            if license_path.exists():
                return license_path
        return None

    def _check_readme_presence(self, readme_path: Path) -> ComplianceCheckResult:
        """Check if README.md exists."""
        if readme_path.exists():
            return ComplianceCheckResult(
                check_id="CA-001",
                passed=True,
                evidence=str(readme_path),
                notes="README.md file found",
            )
        return ComplianceCheckResult(
            check_id="CA-001",
            passed=False,
            evidence=str(readme_path),
            notes="README.md file not found",
        )

    def _check_readme_description(self, content: str) -> ComplianceCheckResult:
        """Check if README.md contains a description section."""
        if not content:
            return ComplianceCheckResult(
                check_id="CA-002",
                passed=False,
                notes="README.md not available or empty",
            )

        # Look for description patterns
        patterns = [
            r"^#+\s*(description|overview|about|introduction)\s*$",
            r"^#+\s*.*description.*$",
            r"^\*\*description\*\*",
        ]

        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                return ComplianceCheckResult(
                    check_id="CA-002",
                    passed=True,
                    evidence=f"Found pattern: {pattern}",
                    notes="Description section found in README.md",
                )

        # Also accept if README has substantial content at the beginning
        # (implicit description without explicit header)
        lines = content.strip().split("\n")
        non_header_lines = [
            line for line in lines[:20]
            if line.strip() and not line.startswith("#")
        ]
        if len(non_header_lines) >= 3:
            return ComplianceCheckResult(
                check_id="CA-002",
                passed=True,
                evidence="Implicit description in opening paragraphs",
                notes="Description found as opening content",
            )

        return ComplianceCheckResult(
            check_id="CA-002",
            passed=False,
            notes="No description section found in README.md",
        )

    def _check_readme_usage(self, content: str) -> ComplianceCheckResult:
        """Check if README.md contains a usage section."""
        if not content:
            return ComplianceCheckResult(
                check_id="CA-003",
                passed=False,
                notes="README.md not available or empty",
            )

        patterns = [
            r"^#+\s*(usage|getting started|quick start|how to use|installation|setup)\s*$",
            r"^#+\s*.*usage.*$",
            r"^#+\s*.*getting started.*$",
        ]

        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                return ComplianceCheckResult(
                    check_id="CA-003",
                    passed=True,
                    evidence=f"Found pattern: {pattern}",
                    notes="Usage section found in README.md",
                )

        # Look for code blocks (common in usage sections)
        if "```" in content:
            return ComplianceCheckResult(
                check_id="CA-003",
                passed=True,
                evidence="Code blocks found (likely usage examples)",
                notes="Usage examples found via code blocks",
            )

        return ComplianceCheckResult(
            check_id="CA-003",
            passed=False,
            notes="No usage section found in README.md",
        )

    def _check_readme_data_sources(self, content: str) -> ComplianceCheckResult:
        """Check if README.md documents data sources."""
        if not content:
            return ComplianceCheckResult(
                check_id="CA-004",
                passed=False,
                notes="README.md not available or empty",
            )

        patterns = [
            r"^#+\s*(data|dataset|data source|sources?|attribution|credits)\s*$",
            r"^#+\s*.*data.*source.*$",
            r"(?i)data\s+(is\s+)?(sourced|from|based on)",
            r"(?i)(dataset|benchmark)\s+(is\s+)?derived\s+from",
            r"(?i)originally\s+(from|published)",
        ]

        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                return ComplianceCheckResult(
                    check_id="CA-004",
                    passed=True,
                    evidence=f"Found pattern: {pattern}",
                    notes="Data sources documented in README.md",
                )

        return ComplianceCheckResult(
            check_id="CA-004",
            passed=False,
            notes="No data sources section found in README.md",
        )

    def _check_design_presence(self, design_path: Path) -> ComplianceCheckResult:
        """Check if DESIGN.md exists."""
        if design_path.exists():
            return ComplianceCheckResult(
                check_id="CA-005",
                passed=True,
                evidence=str(design_path),
                notes="DESIGN.md file found",
            )
        return ComplianceCheckResult(
            check_id="CA-005",
            passed=False,
            evidence=str(design_path),
            notes="DESIGN.md file not found",
        )

    def _check_design_rationale(self, content: str) -> ComplianceCheckResult:
        """Check if DESIGN.md contains task selection rationale."""
        if not content:
            return ComplianceCheckResult(
                check_id="CA-006",
                passed=False,
                notes="DESIGN.md not available or empty",
            )

        patterns = [
            r"^#+\s*(task selection|selection criteria|rationale|methodology)\s*$",
            r"(?i)task\s+selection",
            r"(?i)selection\s+(criteria|rationale|methodology)",
            r"(?i)(why|how)\s+(we\s+)?(selected|chose|picked)",
            r"(?i)criteria\s+for\s+selection",
        ]

        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                return ComplianceCheckResult(
                    check_id="CA-006",
                    passed=True,
                    evidence=f"Found pattern: {pattern}",
                    notes="Task selection rationale found in DESIGN.md",
                )

        return ComplianceCheckResult(
            check_id="CA-006",
            passed=False,
            notes="No task selection rationale found in DESIGN.md",
        )

    def _check_license_presence(self, license_path: Path | None) -> ComplianceCheckResult:
        """Check if a LICENSE file exists."""
        if license_path:
            return ComplianceCheckResult(
                check_id="CA-007",
                passed=True,
                evidence=str(license_path),
                notes="LICENSE file found",
            )
        return ComplianceCheckResult(
            check_id="CA-007",
            passed=False,
            notes="LICENSE file not found",
        )

    def _check_license_recognized(self, content: str) -> ComplianceCheckResult:
        """Check if the LICENSE uses a recognized open source license."""
        if not content:
            return ComplianceCheckResult(
                check_id="CA-008",
                passed=False,
                notes="LICENSE file not available or empty",
            )

        content_upper = content.upper()
        for license_name in self.KNOWN_LICENSES:
            if license_name.upper() in content_upper:
                return ComplianceCheckResult(
                    check_id="CA-008",
                    passed=True,
                    evidence=f"Detected license: {license_name}",
                    notes="Recognized open source license found",
                )

        # Also check for common license patterns
        license_patterns = [
            (r"(?i)permission\s+is\s+hereby\s+granted", "MIT-style"),
            (r"(?i)apache\s+license", "Apache"),
            (r"(?i)gnu\s+general\s+public\s+license", "GPL"),
            (r"(?i)bsd\s+\d+\-?clause", "BSD"),
            (r"(?i)public\s+domain", "Public Domain"),
            (r"(?i)creative\s+commons", "Creative Commons"),
        ]

        for pattern, license_type in license_patterns:
            if re.search(pattern, content):
                return ComplianceCheckResult(
                    check_id="CA-008",
                    passed=True,
                    evidence=f"Detected license type: {license_type}",
                    notes=f"License appears to be {license_type}",
                )

        return ComplianceCheckResult(
            check_id="CA-008",
            passed=False,
            notes="Could not identify a recognized open source license",
        )

    def _check_data_attribution(
        self, benchmark_dir: Path, readme_content: str
    ) -> ComplianceCheckResult:
        """Check if data source attribution is documented."""
        # Check README for attribution
        attribution_patterns = [
            r"(?i)(source|data|dataset).*?:.*?(http|github|arxiv|doi)",
            r"(?i)cite|citation|reference",
            r"(?i)originally\s+(from|published|created)",
            r"(?i)derived\s+from",
            r"(?i)based\s+on\s+(the\s+)?(.*?)\s+(benchmark|dataset)",
            r"\[@.*?\]",  # BibTeX-style citations
            r"\[.*?\]\(http",  # Markdown links
        ]

        for pattern in attribution_patterns:
            if re.search(pattern, readme_content):
                return ComplianceCheckResult(
                    check_id="CA-009",
                    passed=True,
                    evidence=f"Found attribution pattern: {pattern}",
                    notes="Data source attribution found in README.md",
                )

        # Check for SOURCES.md or ATTRIBUTION.md
        for filename in ["SOURCES.md", "ATTRIBUTION.md", "CREDITS.md", "DATA_SOURCES.md"]:
            if (benchmark_dir / filename).exists():
                return ComplianceCheckResult(
                    check_id="CA-009",
                    passed=True,
                    evidence=filename,
                    notes=f"Data source attribution found in {filename}",
                )

        return ComplianceCheckResult(
            check_id="CA-009",
            passed=False,
            notes="No data source attribution found",
        )

    def _check_code_attribution(
        self, benchmark_dir: Path, readme_content: str
    ) -> ComplianceCheckResult:
        """Check if third-party code attribution is documented."""
        # Check for NOTICE file (common for Apache-licensed projects)
        notice_path = benchmark_dir / "NOTICE"
        if notice_path.exists():
            return ComplianceCheckResult(
                check_id="CA-010",
                passed=True,
                evidence="NOTICE",
                notes="Third-party code attribution found in NOTICE file",
            )

        # Check README for code attribution patterns
        attribution_patterns = [
            r"(?i)third[- ]party",
            r"(?i)acknowledgment",
            r"(?i)dependencies",
            r"(?i)based\s+on\s+code\s+from",
            r"(?i)adapted\s+from",
            r"(?i)originally\s+written\s+by",
        ]

        for pattern in attribution_patterns:
            if re.search(pattern, readme_content):
                return ComplianceCheckResult(
                    check_id="CA-010",
                    passed=True,
                    evidence=f"Found attribution pattern: {pattern}",
                    notes="Third-party code attribution found",
                )

        # Check for requirements.txt or pyproject.toml (indicates dependencies)
        dep_files = ["requirements.txt", "pyproject.toml", "package.json", "Cargo.toml"]
        for dep_file in dep_files:
            if (benchmark_dir / dep_file).exists():
                return ComplianceCheckResult(
                    check_id="CA-010",
                    passed=True,
                    evidence=dep_file,
                    notes="Dependencies documented (implicit code attribution)",
                )

        # This is a recommended check, so not finding it is not critical
        return ComplianceCheckResult(
            check_id="CA-010",
            passed=False,
            notes="No explicit third-party code attribution found",
        )

    def generate_compliance_markdown(self, report: ComplianceReport) -> str:
        """
        Generate a detailed markdown compliance report.

        Args:
            report: The compliance report to format

        Returns:
            Formatted markdown string
        """
        return report.to_markdown()

    def audit_multiple_benchmarks(
        self, benchmark_dirs: Sequence[Path | str]
    ) -> list[ComplianceReport]:
        """
        Audit multiple benchmark directories.

        Args:
            benchmark_dirs: List of paths to benchmark directories

        Returns:
            List of ComplianceReports, one per benchmark
        """
        return [self.audit_benchmark(d) for d in benchmark_dirs]

    def generate_aggregate_summary(
        self, reports: list[ComplianceReport]
    ) -> dict[str, Any]:
        """
        Generate aggregate statistics from multiple reports.

        Args:
            reports: List of compliance reports

        Returns:
            Dictionary with aggregate statistics
        """
        total_benchmarks = len(reports)
        passed_benchmarks = sum(1 for r in reports if r.overall_passed)
        failed_benchmarks = total_benchmarks - passed_benchmarks

        total_critical = sum(r.critical_total for r in reports)
        passed_critical = sum(r.critical_passed for r in reports)
        total_important = sum(r.important_total for r in reports)
        passed_important = sum(r.important_passed for r in reports)
        total_recommended = sum(r.recommended_total for r in reports)
        passed_recommended = sum(r.recommended_passed for r in reports)

        return {
            "total_benchmarks": total_benchmarks,
            "passed_benchmarks": passed_benchmarks,
            "failed_benchmarks": failed_benchmarks,
            "benchmark_pass_rate": (
                passed_benchmarks / total_benchmarks * 100
                if total_benchmarks > 0
                else 0.0
            ),
            "total_critical_checks": total_critical,
            "passed_critical_checks": passed_critical,
            "critical_pass_rate": (
                passed_critical / total_critical * 100 if total_critical > 0 else 0.0
            ),
            "total_important_checks": total_important,
            "passed_important_checks": passed_important,
            "important_pass_rate": (
                passed_important / total_important * 100 if total_important > 0 else 0.0
            ),
            "total_recommended_checks": total_recommended,
            "passed_recommended_checks": passed_recommended,
            "recommended_pass_rate": (
                passed_recommended / total_recommended * 100
                if total_recommended > 0
                else 0.0
            ),
        }
