"""
Quality assurance module for benchmark validation.

Provides tools for validating benchmarks against HOW2BENCH criteria,
pre-flight checks, compliance auditing, and task quality scoring.
"""

from src.quality.compliance_auditor import (
    ComplianceAuditor,
    ComplianceCategory,
    ComplianceCheck,
    ComplianceCheckResult,
    ComplianceReport,
    ComplianceSeverity,
)
from src.quality.how2bench_checklist import (
    BenchmarkAuditReport,
    ChecklistCriterion,
    ChecklistResult,
    CriterionCategory,
    CriterionSeverity,
    HOW2BenchChecklist,
)
from src.quality.preflight_validator import (
    CheckSeverity,
    CheckStatus,
    PreflightValidator,
    ValidationCheck,
    ValidationReport,
)

__all__ = [
    # Compliance auditor
    "ComplianceAuditor",
    "ComplianceCategory",
    "ComplianceCheck",
    "ComplianceCheckResult",
    "ComplianceReport",
    "ComplianceSeverity",
    # HOW2BENCH checklist
    "BenchmarkAuditReport",
    "ChecklistCriterion",
    "ChecklistResult",
    "CriterionCategory",
    "CriterionSeverity",
    "HOW2BenchChecklist",
    # Pre-flight validator
    "CheckSeverity",
    "CheckStatus",
    "PreflightValidator",
    "ValidationCheck",
    "ValidationReport",
]
