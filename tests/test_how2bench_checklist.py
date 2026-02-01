"""
Unit tests for HOW2BENCH checklist module.

Tests the 55-criteria checklist data model, result dataclasses,
and audit report generation functionality.
"""

import pytest
from datetime import datetime

from src.quality.how2bench_checklist import (
    BenchmarkAuditReport,
    ChecklistCriterion,
    ChecklistResult,
    CriterionCategory,
    CriterionSeverity,
    HOW2BenchChecklist,
)


class TestCriterionCategory:
    """Tests for CriterionCategory enum."""

    def test_has_data_quality(self) -> None:
        """Test DATA_QUALITY category exists."""
        assert CriterionCategory.DATA_QUALITY.value == "data_quality"

    def test_has_reproducibility(self) -> None:
        """Test REPRODUCIBILITY category exists."""
        assert CriterionCategory.REPRODUCIBILITY.value == "reproducibility"

    def test_has_methodology(self) -> None:
        """Test METHODOLOGY category exists."""
        assert CriterionCategory.METHODOLOGY.value == "methodology"

    def test_all_categories(self) -> None:
        """Test all expected categories exist."""
        categories = list(CriterionCategory)
        assert len(categories) == 3


class TestCriterionSeverity:
    """Tests for CriterionSeverity enum."""

    def test_has_critical(self) -> None:
        """Test CRITICAL severity exists."""
        assert CriterionSeverity.CRITICAL.value == "critical"

    def test_has_important(self) -> None:
        """Test IMPORTANT severity exists."""
        assert CriterionSeverity.IMPORTANT.value == "important"

    def test_has_recommended(self) -> None:
        """Test RECOMMENDED severity exists."""
        assert CriterionSeverity.RECOMMENDED.value == "recommended"

    def test_all_severities(self) -> None:
        """Test all expected severities exist."""
        severities = list(CriterionSeverity)
        assert len(severities) == 3


class TestChecklistCriterion:
    """Tests for ChecklistCriterion dataclass."""

    def test_create_criterion(self) -> None:
        """Test creating a criterion."""
        criterion = ChecklistCriterion(
            id="DQ-001",
            category=CriterionCategory.DATA_QUALITY,
            description="Test description",
            severity=CriterionSeverity.CRITICAL,
            automated=True,
            verification_hint="Test hint",
        )
        assert criterion.id == "DQ-001"
        assert criterion.category == CriterionCategory.DATA_QUALITY
        assert criterion.description == "Test description"
        assert criterion.severity == CriterionSeverity.CRITICAL
        assert criterion.automated is True
        assert criterion.verification_hint == "Test hint"

    def test_criterion_default_hint(self) -> None:
        """Test criterion with default verification hint."""
        criterion = ChecklistCriterion(
            id="DQ-002",
            category=CriterionCategory.DATA_QUALITY,
            description="Test",
            severity=CriterionSeverity.IMPORTANT,
            automated=False,
        )
        assert criterion.verification_hint == ""

    def test_to_dict(self) -> None:
        """Test converting criterion to dictionary."""
        criterion = ChecklistCriterion(
            id="RP-001",
            category=CriterionCategory.REPRODUCIBILITY,
            description="Test reproducibility",
            severity=CriterionSeverity.CRITICAL,
            automated=True,
            verification_hint="Run twice",
        )
        data = criterion.to_dict()
        assert data["id"] == "RP-001"
        assert data["category"] == "reproducibility"
        assert data["description"] == "Test reproducibility"
        assert data["severity"] == "critical"
        assert data["automated"] is True
        assert data["verification_hint"] == "Run twice"

    def test_from_dict(self) -> None:
        """Test creating criterion from dictionary."""
        data = {
            "id": "MT-001",
            "category": "methodology",
            "description": "Test methodology",
            "severity": "important",
            "automated": False,
            "verification_hint": "Review metrics",
        }
        criterion = ChecklistCriterion.from_dict(data)
        assert criterion.id == "MT-001"
        assert criterion.category == CriterionCategory.METHODOLOGY
        assert criterion.description == "Test methodology"
        assert criterion.severity == CriterionSeverity.IMPORTANT
        assert criterion.automated is False
        assert criterion.verification_hint == "Review metrics"

    def test_from_dict_minimal(self) -> None:
        """Test creating criterion from minimal dictionary."""
        data = {
            "id": "DQ-003",
            "category": "data_quality",
            "description": "Minimal",
            "severity": "recommended",
        }
        criterion = ChecklistCriterion.from_dict(data)
        assert criterion.id == "DQ-003"
        assert criterion.automated is False
        assert criterion.verification_hint == ""


class TestChecklistResult:
    """Tests for ChecklistResult dataclass."""

    def test_create_result_passed(self) -> None:
        """Test creating a passed result."""
        result = ChecklistResult(
            criterion_id="DQ-001",
            passed=True,
            evidence="All tests pass",
            notes="Verified manually",
        )
        assert result.criterion_id == "DQ-001"
        assert result.passed is True
        assert result.evidence == "All tests pass"
        assert result.notes == "Verified manually"

    def test_create_result_failed(self) -> None:
        """Test creating a failed result."""
        result = ChecklistResult(
            criterion_id="DQ-002",
            passed=False,
            evidence="3 tests failed",
            notes="Need to fix edge cases",
        )
        assert result.passed is False

    def test_result_default_values(self) -> None:
        """Test result with default values."""
        result = ChecklistResult(criterion_id="DQ-003", passed=True)
        assert result.evidence == ""
        assert result.notes == ""

    def test_to_dict(self) -> None:
        """Test converting result to dictionary."""
        result = ChecklistResult(
            criterion_id="RP-001",
            passed=True,
            evidence="Ran 5 times",
            notes="Consistent results",
        )
        data = result.to_dict()
        assert data["criterion_id"] == "RP-001"
        assert data["passed"] is True
        assert data["evidence"] == "Ran 5 times"
        assert data["notes"] == "Consistent results"

    def test_from_dict(self) -> None:
        """Test creating result from dictionary."""
        data = {
            "criterion_id": "MT-001",
            "passed": False,
            "evidence": "Missing docs",
            "notes": "Need to add metric definitions",
        }
        result = ChecklistResult.from_dict(data)
        assert result.criterion_id == "MT-001"
        assert result.passed is False
        assert result.evidence == "Missing docs"
        assert result.notes == "Need to add metric definitions"


class TestBenchmarkAuditReport:
    """Tests for BenchmarkAuditReport dataclass."""

    @pytest.fixture
    def sample_results(self) -> list[ChecklistResult]:
        """Create sample results for testing."""
        return [
            ChecklistResult(criterion_id="DQ-001", passed=True),
            ChecklistResult(criterion_id="DQ-002", passed=True),
            ChecklistResult(criterion_id="DQ-003", passed=False),
            ChecklistResult(criterion_id="RP-001", passed=True),
            ChecklistResult(criterion_id="RP-005", passed=False),
            ChecklistResult(criterion_id="MT-001", passed=True),
            ChecklistResult(criterion_id="MT-003", passed=True),
        ]

    def test_create_report(self, sample_results: list[ChecklistResult]) -> None:
        """Test creating an audit report."""
        report = BenchmarkAuditReport(
            benchmark_name="TestBench",
            timestamp="2026-01-28T10:00:00",
            results=sample_results,
        )
        assert report.benchmark_name == "TestBench"
        assert report.timestamp == "2026-01-28T10:00:00"
        assert len(report.results) == 7

    def test_auto_compute_statistics(self, sample_results: list[ChecklistResult]) -> None:
        """Test that statistics are auto-computed."""
        report = BenchmarkAuditReport(
            benchmark_name="TestBench",
            timestamp="2026-01-28T10:00:00",
            results=sample_results,
        )
        # DQ-001, DQ-002, DQ-003 are DATA_QUALITY (DQ-001, DQ-002 critical, DQ-003 critical)
        # RP-001, RP-005 are REPRODUCIBILITY (RP-001, RP-005 critical)
        # MT-001, MT-003 are METHODOLOGY (MT-001, MT-003 critical)
        # Critical: DQ-001(pass), DQ-002(pass), DQ-003(fail), RP-001(pass), RP-005(fail), MT-001(pass), MT-003(pass)
        assert report.critical_total > 0

    def test_overall_passed_all_critical(self) -> None:
        """Test overall_passed when all critical pass."""
        results = [
            ChecklistResult(criterion_id="DQ-001", passed=True),
            ChecklistResult(criterion_id="DQ-002", passed=True),
            ChecklistResult(criterion_id="DQ-003", passed=True),
            ChecklistResult(criterion_id="RP-001", passed=True),
            ChecklistResult(criterion_id="RP-005", passed=True),
            ChecklistResult(criterion_id="MT-001", passed=True),
            ChecklistResult(criterion_id="MT-003", passed=True),
        ]
        report = BenchmarkAuditReport(
            benchmark_name="TestBench",
            timestamp="2026-01-28T10:00:00",
            results=results,
        )
        assert report.overall_passed is True

    def test_overall_failed_missing_critical(self) -> None:
        """Test overall_passed when a critical fails."""
        results = [
            ChecklistResult(criterion_id="DQ-001", passed=False),  # Critical
        ]
        report = BenchmarkAuditReport(
            benchmark_name="TestBench",
            timestamp="2026-01-28T10:00:00",
            results=results,
        )
        assert report.overall_passed is False

    def test_get_pass_rate(self, sample_results: list[ChecklistResult]) -> None:
        """Test calculating pass rate."""
        report = BenchmarkAuditReport(
            benchmark_name="TestBench",
            timestamp="2026-01-28T10:00:00",
            results=sample_results,
        )
        rate = report.get_pass_rate()
        assert 0 <= rate <= 100

    def test_get_failed_critical(self) -> None:
        """Test getting failed critical criteria."""
        results = [
            ChecklistResult(criterion_id="DQ-001", passed=True),
            ChecklistResult(criterion_id="DQ-002", passed=False, notes="Ground truth invalid"),
            ChecklistResult(criterion_id="RP-001", passed=False, notes="Non-deterministic"),
        ]
        report = BenchmarkAuditReport(
            benchmark_name="TestBench",
            timestamp="2026-01-28T10:00:00",
            results=results,
        )
        failed = report.get_failed_critical()
        # DQ-002 and RP-001 are both critical
        assert len(failed) == 2
        ids = [f.criterion_id for f in failed]
        assert "DQ-002" in ids
        assert "RP-001" in ids

    def test_to_dict(self, sample_results: list[ChecklistResult]) -> None:
        """Test converting report to dictionary."""
        report = BenchmarkAuditReport(
            benchmark_name="TestBench",
            timestamp="2026-01-28T10:00:00",
            results=sample_results,
            metadata={"version": "1.0"},
        )
        data = report.to_dict()
        assert data["benchmark_name"] == "TestBench"
        assert data["timestamp"] == "2026-01-28T10:00:00"
        assert len(data["results"]) == 7
        assert "overall_passed" in data
        assert "pass_rate" in data
        assert data["metadata"]["version"] == "1.0"

    def test_from_dict(self) -> None:
        """Test creating report from dictionary."""
        data = {
            "benchmark_name": "FromDict",
            "timestamp": "2026-01-28T12:00:00",
            "results": [
                {"criterion_id": "DQ-001", "passed": True, "evidence": "", "notes": ""},
            ],
            "overall_passed": True,
            "critical_passed": 1,
            "critical_total": 1,
            "important_passed": 0,
            "important_total": 0,
            "recommended_passed": 0,
            "recommended_total": 0,
            "metadata": {"source": "test"},
        }
        report = BenchmarkAuditReport.from_dict(data)
        assert report.benchmark_name == "FromDict"
        assert len(report.results) == 1
        assert report.overall_passed is True

    def test_to_markdown(self, sample_results: list[ChecklistResult]) -> None:
        """Test generating markdown report."""
        report = BenchmarkAuditReport(
            benchmark_name="TestBench",
            timestamp="2026-01-28T10:00:00",
            results=sample_results,
        )
        markdown = report.to_markdown()
        assert "# Benchmark Audit Report: TestBench" in markdown
        assert "**Timestamp:**" in markdown
        assert "**Overall Status:**" in markdown
        assert "| Severity | Passed | Total | Rate |" in markdown


class TestHOW2BenchChecklist:
    """Tests for HOW2BenchChecklist class."""

    @pytest.fixture
    def checklist(self) -> HOW2BenchChecklist:
        """Create checklist instance."""
        return HOW2BenchChecklist()

    def test_has_55_criteria(self, checklist: HOW2BenchChecklist) -> None:
        """Test that checklist has exactly 55 criteria."""
        criteria = checklist.get_all_criteria()
        assert len(criteria) == 55

    def test_all_criteria_have_ids(self, checklist: HOW2BenchChecklist) -> None:
        """Test all criteria have unique IDs."""
        criteria = checklist.get_all_criteria()
        ids = [c.id for c in criteria]
        assert len(ids) == len(set(ids)), "Duplicate IDs found"

    def test_all_criteria_have_descriptions(self, checklist: HOW2BenchChecklist) -> None:
        """Test all criteria have non-empty descriptions."""
        criteria = checklist.get_all_criteria()
        for criterion in criteria:
            assert criterion.description, f"Criterion {criterion.id} has empty description"

    def test_get_by_id_exists(self, checklist: HOW2BenchChecklist) -> None:
        """Test getting criterion by existing ID."""
        criterion = checklist.get_by_id("DQ-001")
        assert criterion is not None
        assert criterion.id == "DQ-001"

    def test_get_by_id_not_exists(self, checklist: HOW2BenchChecklist) -> None:
        """Test getting criterion by non-existing ID."""
        criterion = checklist.get_by_id("XX-999")
        assert criterion is None

    def test_get_by_category_data_quality(self, checklist: HOW2BenchChecklist) -> None:
        """Test getting data quality criteria."""
        criteria = checklist.get_by_category(CriterionCategory.DATA_QUALITY)
        assert len(criteria) == 20
        for criterion in criteria:
            assert criterion.category == CriterionCategory.DATA_QUALITY
            assert criterion.id.startswith("DQ-")

    def test_get_by_category_reproducibility(self, checklist: HOW2BenchChecklist) -> None:
        """Test getting reproducibility criteria."""
        criteria = checklist.get_by_category(CriterionCategory.REPRODUCIBILITY)
        assert len(criteria) == 18
        for criterion in criteria:
            assert criterion.category == CriterionCategory.REPRODUCIBILITY
            assert criterion.id.startswith("RP-")

    def test_get_by_category_methodology(self, checklist: HOW2BenchChecklist) -> None:
        """Test getting methodology criteria."""
        criteria = checklist.get_by_category(CriterionCategory.METHODOLOGY)
        assert len(criteria) == 17
        for criterion in criteria:
            assert criterion.category == CriterionCategory.METHODOLOGY
            assert criterion.id.startswith("MT-")

    def test_get_by_severity_critical(self, checklist: HOW2BenchChecklist) -> None:
        """Test getting critical criteria."""
        criteria = checklist.get_by_severity(CriterionSeverity.CRITICAL)
        assert len(criteria) > 0
        for criterion in criteria:
            assert criterion.severity == CriterionSeverity.CRITICAL

    def test_get_by_severity_important(self, checklist: HOW2BenchChecklist) -> None:
        """Test getting important criteria."""
        criteria = checklist.get_by_severity(CriterionSeverity.IMPORTANT)
        assert len(criteria) > 0
        for criterion in criteria:
            assert criterion.severity == CriterionSeverity.IMPORTANT

    def test_get_by_severity_recommended(self, checklist: HOW2BenchChecklist) -> None:
        """Test getting recommended criteria."""
        criteria = checklist.get_by_severity(CriterionSeverity.RECOMMENDED)
        assert len(criteria) > 0
        for criterion in criteria:
            assert criterion.severity == CriterionSeverity.RECOMMENDED

    def test_get_automated(self, checklist: HOW2BenchChecklist) -> None:
        """Test getting automated criteria."""
        criteria = checklist.get_automated()
        assert len(criteria) > 0
        for criterion in criteria:
            assert criterion.automated is True

    def test_get_manual(self, checklist: HOW2BenchChecklist) -> None:
        """Test getting manual criteria."""
        criteria = checklist.get_manual()
        assert len(criteria) > 0
        for criterion in criteria:
            assert criterion.automated is False

    def test_automated_plus_manual_equals_total(self, checklist: HOW2BenchChecklist) -> None:
        """Test automated + manual = total criteria."""
        automated = checklist.get_automated()
        manual = checklist.get_manual()
        total = checklist.get_all_criteria()
        assert len(automated) + len(manual) == len(total)

    def test_count_by_category(self, checklist: HOW2BenchChecklist) -> None:
        """Test counting by category."""
        counts = checklist.count_by_category()
        assert counts["data_quality"] == 20
        assert counts["reproducibility"] == 18
        assert counts["methodology"] == 17
        assert sum(counts.values()) == 55

    def test_count_by_severity(self, checklist: HOW2BenchChecklist) -> None:
        """Test counting by severity."""
        counts = checklist.count_by_severity()
        assert "critical" in counts
        assert "important" in counts
        assert "recommended" in counts
        assert sum(counts.values()) == 55

    def test_create_audit_report(self, checklist: HOW2BenchChecklist) -> None:
        """Test creating an audit report."""
        results = [
            ChecklistResult(criterion_id="DQ-001", passed=True, evidence="Clear descriptions"),
            ChecklistResult(criterion_id="DQ-002", passed=True, evidence="Verified ground truth"),
        ]
        report = checklist.create_audit_report(
            benchmark_name="MyBenchmark",
            results=results,
            metadata={"auditor": "test"},
        )
        assert report.benchmark_name == "MyBenchmark"
        assert len(report.results) == 2
        assert report.metadata["auditor"] == "test"
        # Timestamp should be set
        assert report.timestamp

    def test_criteria_ids_follow_pattern(self, checklist: HOW2BenchChecklist) -> None:
        """Test all criteria IDs follow expected patterns."""
        criteria = checklist.get_all_criteria()
        for criterion in criteria:
            parts = criterion.id.split("-")
            assert len(parts) == 2, f"Invalid ID format: {criterion.id}"
            prefix, number = parts
            assert prefix in ["DQ", "RP", "MT"], f"Invalid prefix: {prefix}"
            assert number.isdigit(), f"Invalid number: {number}"
            assert len(number) == 3, f"Number should be 3 digits: {number}"


class TestSpecificCriteria:
    """Tests for specific important criteria."""

    @pytest.fixture
    def checklist(self) -> HOW2BenchChecklist:
        """Create checklist instance."""
        return HOW2BenchChecklist()

    def test_dq001_task_descriptions_clear(self, checklist: HOW2BenchChecklist) -> None:
        """Test DQ-001 exists and is critical."""
        criterion = checklist.get_by_id("DQ-001")
        assert criterion is not None
        assert criterion.severity == CriterionSeverity.CRITICAL
        assert "clear" in criterion.description.lower()

    def test_dq002_ground_truth_verified(self, checklist: HOW2BenchChecklist) -> None:
        """Test DQ-002 exists and is critical."""
        criterion = checklist.get_by_id("DQ-002")
        assert criterion is not None
        assert criterion.severity == CriterionSeverity.CRITICAL
        assert "ground truth" in criterion.description.lower()

    def test_dq011_no_hardcoded_secrets(self, checklist: HOW2BenchChecklist) -> None:
        """Test DQ-011 exists and is critical."""
        criterion = checklist.get_by_id("DQ-011")
        assert criterion is not None
        assert criterion.severity == CriterionSeverity.CRITICAL
        assert "secret" in criterion.description.lower() or "credential" in criterion.description.lower()

    def test_rp001_deterministic_results(self, checklist: HOW2BenchChecklist) -> None:
        """Test RP-001 exists and is critical."""
        criterion = checklist.get_by_id("RP-001")
        assert criterion is not None
        assert criterion.severity == CriterionSeverity.CRITICAL
        assert "deterministic" in criterion.description.lower()

    def test_rp003_docker_provided(self, checklist: HOW2BenchChecklist) -> None:
        """Test RP-003 exists and relates to Docker."""
        criterion = checklist.get_by_id("RP-003")
        assert criterion is not None
        assert "docker" in criterion.description.lower() or "container" in criterion.description.lower()

    def test_mt001_metrics_defined(self, checklist: HOW2BenchChecklist) -> None:
        """Test MT-001 exists and is critical."""
        criterion = checklist.get_by_id("MT-001")
        assert criterion is not None
        assert criterion.severity == CriterionSeverity.CRITICAL
        assert "metric" in criterion.description.lower()

    def test_mt003_scoring_rubric(self, checklist: HOW2BenchChecklist) -> None:
        """Test MT-003 exists and is critical."""
        criterion = checklist.get_by_id("MT-003")
        assert criterion is not None
        assert criterion.severity == CriterionSeverity.CRITICAL
        assert "scoring" in criterion.description.lower() or "rubric" in criterion.description.lower()
