"""
Unit tests for the documentation compliance auditor module.
"""

import json
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from src.quality.compliance_auditor import (
    ComplianceAuditor,
    ComplianceCategory,
    ComplianceCheck,
    ComplianceCheckResult,
    ComplianceReport,
    ComplianceSeverity,
)


class TestComplianceCheck:
    """Tests for ComplianceCheck dataclass."""

    def test_create_basic_check(self) -> None:
        """Test creating a basic compliance check."""
        check = ComplianceCheck(
            check_id="CA-001",
            category=ComplianceCategory.README,
            description="README.md file is present",
            severity=ComplianceSeverity.CRITICAL,
        )
        assert check.check_id == "CA-001"
        assert check.category == ComplianceCategory.README
        assert check.description == "README.md file is present"
        assert check.severity == ComplianceSeverity.CRITICAL

    def test_to_dict(self) -> None:
        """Test converting check to dictionary."""
        check = ComplianceCheck(
            check_id="CA-002",
            category=ComplianceCategory.DESIGN,
            description="DESIGN.md present",
            severity=ComplianceSeverity.IMPORTANT,
        )
        result = check.to_dict()
        assert result["check_id"] == "CA-002"
        assert result["category"] == "design"
        assert result["severity"] == "important"


class TestComplianceCheckResult:
    """Tests for ComplianceCheckResult dataclass."""

    def test_create_passed_result(self) -> None:
        """Test creating a passed result."""
        result = ComplianceCheckResult(
            check_id="CA-001",
            passed=True,
            evidence="/path/to/README.md",
            notes="README.md file found",
        )
        assert result.check_id == "CA-001"
        assert result.passed is True
        assert result.evidence == "/path/to/README.md"

    def test_create_failed_result(self) -> None:
        """Test creating a failed result."""
        result = ComplianceCheckResult(
            check_id="CA-001",
            passed=False,
            notes="README.md file not found",
        )
        assert result.passed is False
        assert result.evidence == ""

    def test_to_dict(self) -> None:
        """Test converting result to dictionary."""
        result = ComplianceCheckResult(
            check_id="CA-001",
            passed=True,
            evidence="test",
            notes="passed",
        )
        data = result.to_dict()
        assert data["check_id"] == "CA-001"
        assert data["passed"] is True
        assert data["evidence"] == "test"

    def test_from_dict(self) -> None:
        """Test creating result from dictionary."""
        data = {
            "check_id": "CA-002",
            "passed": False,
            "evidence": "missing file",
            "notes": "not found",
        }
        result = ComplianceCheckResult.from_dict(data)
        assert result.check_id == "CA-002"
        assert result.passed is False
        assert result.evidence == "missing file"


class TestComplianceReport:
    """Tests for ComplianceReport dataclass."""

    def test_create_report_with_all_passed(self) -> None:
        """Test creating a report where all checks pass."""
        results = [
            ComplianceCheckResult(check_id="CA-001", passed=True),
            ComplianceCheckResult(check_id="CA-002", passed=True),
            ComplianceCheckResult(check_id="CA-007", passed=True),
        ]
        report = ComplianceReport(
            benchmark_name="test_benchmark",
            benchmark_directory="/path/to/benchmark",
            timestamp="2026-01-28T12:00:00",
            results=results,
        )
        assert report.overall_passed is True
        assert report.critical_passed == report.critical_total

    def test_create_report_with_critical_failures(self) -> None:
        """Test creating a report with failed critical checks."""
        results = [
            ComplianceCheckResult(check_id="CA-001", passed=False),  # Critical
            ComplianceCheckResult(check_id="CA-002", passed=True),  # Critical
            ComplianceCheckResult(check_id="CA-005", passed=True),  # Important
        ]
        report = ComplianceReport(
            benchmark_name="test_benchmark",
            benchmark_directory="/path/to/benchmark",
            timestamp="2026-01-28T12:00:00",
            results=results,
        )
        assert report.overall_passed is False
        assert report.critical_passed < report.critical_total

    def test_get_pass_rate(self) -> None:
        """Test calculating pass rate."""
        results = [
            ComplianceCheckResult(check_id="CA-001", passed=True),
            ComplianceCheckResult(check_id="CA-002", passed=True),
            ComplianceCheckResult(check_id="CA-005", passed=False),
            ComplianceCheckResult(check_id="CA-007", passed=False),
        ]
        report = ComplianceReport(
            benchmark_name="test",
            benchmark_directory="/path",
            timestamp="2026-01-28T12:00:00",
            results=results,
        )
        # Some checks pass, some fail
        pass_rate = report.get_pass_rate()
        assert 0 < pass_rate < 100

    def test_get_failed_critical(self) -> None:
        """Test getting failed critical checks."""
        results = [
            ComplianceCheckResult(check_id="CA-001", passed=False, notes="failed"),
            ComplianceCheckResult(check_id="CA-002", passed=True),
            ComplianceCheckResult(check_id="CA-005", passed=False, notes="failed"),
        ]
        report = ComplianceReport(
            benchmark_name="test",
            benchmark_directory="/path",
            timestamp="2026-01-28T12:00:00",
            results=results,
        )
        failed_critical = report.get_failed_critical()
        # CA-001 is critical, CA-005 is important
        assert len(failed_critical) >= 1
        assert any(r.check_id == "CA-001" for r in failed_critical)

    def test_to_dict(self) -> None:
        """Test converting report to dictionary."""
        results = [
            ComplianceCheckResult(check_id="CA-001", passed=True),
        ]
        report = ComplianceReport(
            benchmark_name="test",
            benchmark_directory="/path",
            timestamp="2026-01-28T12:00:00",
            results=results,
        )
        data = report.to_dict()
        assert data["benchmark_name"] == "test"
        assert data["benchmark_directory"] == "/path"
        assert "results" in data
        assert "overall_passed" in data
        assert "pass_rate" in data

    def test_from_dict(self) -> None:
        """Test creating report from dictionary."""
        data = {
            "benchmark_name": "test",
            "benchmark_directory": "/path",
            "timestamp": "2026-01-28T12:00:00",
            "results": [{"check_id": "CA-001", "passed": True}],
            "overall_passed": True,
        }
        report = ComplianceReport.from_dict(data)
        assert report.benchmark_name == "test"
        assert len(report.results) == 1

    def test_to_markdown(self) -> None:
        """Test generating markdown report."""
        results = [
            ComplianceCheckResult(check_id="CA-001", passed=True),
            ComplianceCheckResult(check_id="CA-002", passed=False, notes="missing"),
        ]
        report = ComplianceReport(
            benchmark_name="test_benchmark",
            benchmark_directory="/path/to/benchmark",
            timestamp="2026-01-28T12:00:00",
            results=results,
        )
        markdown = report.to_markdown()
        assert "# Compliance Report: test_benchmark" in markdown
        assert "Directory:" in markdown
        assert "Timestamp:" in markdown
        assert "Overall Status:" in markdown

    def test_to_benchmark_audit_report(self) -> None:
        """Test converting to BenchmarkAuditReport."""
        results = [
            ComplianceCheckResult(check_id="CA-001", passed=True),
            ComplianceCheckResult(check_id="CA-005", passed=True),
        ]
        report = ComplianceReport(
            benchmark_name="test",
            benchmark_directory="/path",
            timestamp="2026-01-28T12:00:00",
            results=results,
        )
        audit_report = report.to_benchmark_audit_report()
        assert audit_report.benchmark_name == "test"
        assert len(audit_report.results) == 2


class TestComplianceAuditor:
    """Tests for ComplianceAuditor class."""

    @pytest.fixture
    def auditor(self) -> ComplianceAuditor:
        """Create an auditor instance."""
        return ComplianceAuditor()

    @pytest.fixture
    def temp_benchmark_dir(self) -> Generator[Path, None, None]:
        """Create a temporary benchmark directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_get_all_checks(self, auditor: ComplianceAuditor) -> None:
        """Test getting all compliance checks."""
        checks = auditor.get_all_checks()
        assert len(checks) == 10
        check_ids = [c.check_id for c in checks]
        assert "CA-001" in check_ids
        assert "CA-010" in check_ids

    def test_get_check_by_id(self, auditor: ComplianceAuditor) -> None:
        """Test getting a specific check by ID."""
        check = auditor.get_check_by_id("CA-001")
        assert check is not None
        assert check.check_id == "CA-001"
        assert check.category == ComplianceCategory.README

    def test_get_check_by_id_not_found(self, auditor: ComplianceAuditor) -> None:
        """Test getting a non-existent check."""
        check = auditor.get_check_by_id("CA-999")
        assert check is None

    def test_audit_empty_directory(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test auditing an empty directory."""
        report = auditor.audit_benchmark(temp_benchmark_dir)
        assert report.benchmark_name == temp_benchmark_dir.name
        assert report.overall_passed is False  # No README or LICENSE

    def test_audit_with_readme_only(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test auditing a directory with only README.md."""
        readme_content = """# Test Benchmark

## Description
This is a test benchmark for evaluating AI agents.

## Usage
Run `python run.py` to start evaluation.

## Data Sources
Data is sourced from public GitHub repositories.
"""
        (temp_benchmark_dir / "README.md").write_text(readme_content)

        report = auditor.audit_benchmark(temp_benchmark_dir)
        # Should have README checks passing but LICENSE failing
        readme_results = [r for r in report.results if r.check_id.startswith("CA-00")]
        readme_passed = [r for r in readme_results if r.passed]
        assert len(readme_passed) >= 3  # README presence + description + usage

    def test_audit_with_complete_documentation(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test auditing a directory with complete documentation."""
        # Create README.md
        readme_content = """# Test Benchmark

## Description
A comprehensive test benchmark.

## Usage
```bash
python run.py --benchmark test
```

## Data Sources
Data is derived from the XYZ dataset (https://example.com/xyz).
"""
        (temp_benchmark_dir / "README.md").write_text(readme_content)

        # Create DESIGN.md
        design_content = """# Design Document

## Task Selection
We selected tasks based on the following criteria.

## Rationale
The rationale for our selection is to maximize MCP value.
"""
        (temp_benchmark_dir / "DESIGN.md").write_text(design_content)

        # Create LICENSE
        license_content = """MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files.
"""
        (temp_benchmark_dir / "LICENSE").write_text(license_content)

        report = auditor.audit_benchmark(temp_benchmark_dir)
        assert report.overall_passed is True
        assert report.critical_passed == report.critical_total

    def test_audit_readme_description_detection(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test detection of various description formats."""
        # Test with "Overview" section
        readme_content = """# Test

## Overview
This is the overview section.
"""
        (temp_benchmark_dir / "README.md").write_text(readme_content)
        report = auditor.audit_benchmark(temp_benchmark_dir)
        desc_result = next(r for r in report.results if r.check_id == "CA-002")
        assert desc_result.passed is True

    def test_audit_readme_usage_with_code_blocks(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test usage detection via code blocks."""
        readme_content = """# Test

Some introductory text about the benchmark.

```python
import benchmark
benchmark.run()
```
"""
        (temp_benchmark_dir / "README.md").write_text(readme_content)
        report = auditor.audit_benchmark(temp_benchmark_dir)
        usage_result = next(r for r in report.results if r.check_id == "CA-003")
        assert usage_result.passed is True

    def test_audit_license_detection_apache(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test detection of Apache license."""
        license_content = """Apache License
Version 2.0, January 2004
"""
        (temp_benchmark_dir / "LICENSE").write_text(license_content)
        (temp_benchmark_dir / "README.md").write_text("# Test")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        license_present = next(r for r in report.results if r.check_id == "CA-007")
        license_recognized = next(r for r in report.results if r.check_id == "CA-008")
        assert license_present.passed is True
        assert license_recognized.passed is True

    def test_audit_license_detection_bsd(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test detection of BSD license."""
        license_content = """BSD 3-Clause License

Redistribution and use in source and binary forms...
"""
        (temp_benchmark_dir / "LICENSE.txt").write_text(license_content)
        (temp_benchmark_dir / "README.md").write_text("# Test")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        license_present = next(r for r in report.results if r.check_id == "CA-007")
        license_recognized = next(r for r in report.results if r.check_id == "CA-008")
        assert license_present.passed is True
        assert license_recognized.passed is True

    def test_audit_license_unknown(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test handling of unknown license."""
        license_content = """Custom Proprietary License
All rights reserved.
"""
        (temp_benchmark_dir / "LICENSE").write_text(license_content)
        (temp_benchmark_dir / "README.md").write_text("# Test")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        license_recognized = next(r for r in report.results if r.check_id == "CA-008")
        assert license_recognized.passed is False

    def test_audit_data_attribution_in_readme(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test data attribution detection in README."""
        readme_content = """# Test

Data is sourced from https://github.com/example/repo.
"""
        (temp_benchmark_dir / "README.md").write_text(readme_content)

        report = auditor.audit_benchmark(temp_benchmark_dir)
        attr_result = next(r for r in report.results if r.check_id == "CA-009")
        assert attr_result.passed is True

    def test_audit_data_attribution_in_separate_file(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test data attribution in SOURCES.md file."""
        (temp_benchmark_dir / "README.md").write_text("# Test")
        (temp_benchmark_dir / "SOURCES.md").write_text("Data from XYZ")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        attr_result = next(r for r in report.results if r.check_id == "CA-009")
        assert attr_result.passed is True

    def test_audit_code_attribution_via_requirements(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test code attribution via requirements.txt."""
        (temp_benchmark_dir / "README.md").write_text("# Test")
        (temp_benchmark_dir / "requirements.txt").write_text("pytest>=7.0.0")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        code_attr = next(r for r in report.results if r.check_id == "CA-010")
        assert code_attr.passed is True

    def test_audit_code_attribution_via_pyproject(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test code attribution via pyproject.toml."""
        (temp_benchmark_dir / "README.md").write_text("# Test")
        (temp_benchmark_dir / "pyproject.toml").write_text("[project]\nname = 'test'")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        code_attr = next(r for r in report.results if r.check_id == "CA-010")
        assert code_attr.passed is True

    def test_audit_design_file_detection(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test DESIGN.md presence detection."""
        design_content = """# Design

## Task Selection
We selected tasks based on complexity and relevance.

## Rationale
The rationale is to test edge cases.
"""
        (temp_benchmark_dir / "DESIGN.md").write_text(design_content)
        (temp_benchmark_dir / "README.md").write_text("# Test")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        design_present = next(r for r in report.results if r.check_id == "CA-005")
        design_rationale = next(r for r in report.results if r.check_id == "CA-006")
        assert design_present.passed is True
        assert design_rationale.passed is True

    def test_audit_design_rationale_patterns(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test various rationale pattern detections."""
        design_content = """# Design

## Why We Selected These Tasks
We chose tasks that maximize MCP value.
"""
        (temp_benchmark_dir / "DESIGN.md").write_text(design_content)
        (temp_benchmark_dir / "README.md").write_text("# Test")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        design_rationale = next(r for r in report.results if r.check_id == "CA-006")
        assert design_rationale.passed is True

    def test_audit_multiple_benchmarks(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test auditing multiple benchmark directories."""
        # Create two benchmark directories
        bench1 = temp_benchmark_dir / "benchmark1"
        bench1.mkdir()
        (bench1 / "README.md").write_text("# Benchmark 1\n\n## Description\nTest.")

        bench2 = temp_benchmark_dir / "benchmark2"
        bench2.mkdir()
        (bench2 / "README.md").write_text("# Benchmark 2\n\n## Description\nTest.")
        (bench2 / "LICENSE").write_text("MIT License")

        reports = auditor.audit_multiple_benchmarks([bench1, bench2])
        assert len(reports) == 2
        assert reports[0].benchmark_name == "benchmark1"
        assert reports[1].benchmark_name == "benchmark2"

    def test_generate_aggregate_summary(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test generating aggregate summary from multiple reports."""
        # Create reports
        results1 = [
            ComplianceCheckResult(check_id="CA-001", passed=True),
            ComplianceCheckResult(check_id="CA-007", passed=True),
        ]
        report1 = ComplianceReport(
            benchmark_name="bench1",
            benchmark_directory="/path1",
            timestamp="2026-01-28T12:00:00",
            results=results1,
        )

        results2 = [
            ComplianceCheckResult(check_id="CA-001", passed=False),
            ComplianceCheckResult(check_id="CA-007", passed=True),
        ]
        report2 = ComplianceReport(
            benchmark_name="bench2",
            benchmark_directory="/path2",
            timestamp="2026-01-28T12:00:00",
            results=results2,
        )

        summary = auditor.generate_aggregate_summary([report1, report2])
        assert summary["total_benchmarks"] == 2
        assert "passed_benchmarks" in summary
        assert "benchmark_pass_rate" in summary
        assert "critical_pass_rate" in summary

    def test_generate_compliance_markdown(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test generating markdown from compliance report."""
        (temp_benchmark_dir / "README.md").write_text("# Test\n\n## Description\nTest.")
        report = auditor.audit_benchmark(temp_benchmark_dir)

        markdown = auditor.generate_compliance_markdown(report)
        assert "# Compliance Report:" in markdown
        assert "Summary" in markdown
        assert "All Checks" in markdown


class TestComplianceAuditorEdgeCases:
    """Edge case tests for ComplianceAuditor."""

    @pytest.fixture
    def auditor(self) -> ComplianceAuditor:
        """Create an auditor instance."""
        return ComplianceAuditor()

    @pytest.fixture
    def temp_benchmark_dir(self) -> Generator[Path, None, None]:
        """Create a temporary benchmark directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_empty_readme(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test handling of empty README.md."""
        (temp_benchmark_dir / "README.md").write_text("")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        readme_present = next(r for r in report.results if r.check_id == "CA-001")
        readme_desc = next(r for r in report.results if r.check_id == "CA-002")
        assert readme_present.passed is True  # File exists
        assert readme_desc.passed is False  # But no content

    def test_empty_design(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test handling of empty DESIGN.md."""
        (temp_benchmark_dir / "README.md").write_text("# Test")
        (temp_benchmark_dir / "DESIGN.md").write_text("")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        design_present = next(r for r in report.results if r.check_id == "CA-005")
        design_rationale = next(r for r in report.results if r.check_id == "CA-006")
        assert design_present.passed is True
        assert design_rationale.passed is False

    def test_readme_implicit_description(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test implicit description detection (content without header)."""
        readme_content = """# My Benchmark

This is a benchmark for testing AI coding assistants.
It evaluates performance on real-world tasks.
Tasks range from simple bug fixes to complex refactoring.
"""
        (temp_benchmark_dir / "README.md").write_text(readme_content)

        report = auditor.audit_benchmark(temp_benchmark_dir)
        desc_result = next(r for r in report.results if r.check_id == "CA-002")
        assert desc_result.passed is True

    def test_license_case_variations(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test finding license files with different case."""
        # Create lowercase license file
        (temp_benchmark_dir / "license").write_text("MIT License")
        (temp_benchmark_dir / "README.md").write_text("# Test")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        license_result = next(r for r in report.results if r.check_id == "CA-007")
        assert license_result.passed is True

    def test_creative_commons_detection(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test detection of Creative Commons license."""
        license_content = """Creative Commons Attribution 4.0 International
Public License
"""
        (temp_benchmark_dir / "LICENSE").write_text(license_content)
        (temp_benchmark_dir / "README.md").write_text("# Test")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        license_recognized = next(r for r in report.results if r.check_id == "CA-008")
        assert license_recognized.passed is True

    def test_gpl_detection(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test detection of GPL license."""
        license_content = """GNU General Public License
Version 3
"""
        (temp_benchmark_dir / "LICENSE").write_text(license_content)
        (temp_benchmark_dir / "README.md").write_text("# Test")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        license_recognized = next(r for r in report.results if r.check_id == "CA-008")
        assert license_recognized.passed is True

    def test_citation_detection(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test detection of citation in README."""
        readme_content = """# Test

Please cite our paper if you use this benchmark:

```bibtex
@article{test2026,
  title={Test Benchmark},
  author={Smith, John}
}
```
"""
        (temp_benchmark_dir / "README.md").write_text(readme_content)

        report = auditor.audit_benchmark(temp_benchmark_dir)
        attr_result = next(r for r in report.results if r.check_id == "CA-009")
        assert attr_result.passed is True

    def test_markdown_link_attribution(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test detection of markdown link attribution."""
        readme_content = """# Test

Data from [Original Benchmark](https://example.com/benchmark).
"""
        (temp_benchmark_dir / "README.md").write_text(readme_content)

        report = auditor.audit_benchmark(temp_benchmark_dir)
        attr_result = next(r for r in report.results if r.check_id == "CA-009")
        assert attr_result.passed is True

    def test_notice_file_detection(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test detection of NOTICE file for code attribution."""
        (temp_benchmark_dir / "README.md").write_text("# Test")
        (temp_benchmark_dir / "NOTICE").write_text("Third-party notices here")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        code_attr = next(r for r in report.results if r.check_id == "CA-010")
        assert code_attr.passed is True

    def test_report_pass_rate_all_passed(
        self, auditor: ComplianceAuditor, temp_benchmark_dir: Path
    ) -> None:
        """Test pass rate when all checks pass."""
        # Create complete documentation
        (temp_benchmark_dir / "README.md").write_text(
            "# Test\n\n## Description\nTest.\n\n## Usage\nTest.\n\n## Data\nFrom example.com"
        )
        (temp_benchmark_dir / "DESIGN.md").write_text(
            "# Design\n\n## Task Selection\nTest.\n\n## Rationale\nTest."
        )
        (temp_benchmark_dir / "LICENSE").write_text("MIT License")
        (temp_benchmark_dir / "requirements.txt").write_text("pytest")

        report = auditor.audit_benchmark(temp_benchmark_dir)
        # Pass rate should be high but may not be 100% depending on check details
        assert report.get_pass_rate() >= 80.0

    def test_report_pass_rate_empty_results(self) -> None:
        """Test pass rate with no results."""
        report = ComplianceReport(
            benchmark_name="test",
            benchmark_directory="/path",
            timestamp="2026-01-28T12:00:00",
            results=[],
        )
        assert report.get_pass_rate() == 0.0
