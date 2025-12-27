"""
Checklist evaluation system for documentation tasks.

Provides structured evaluation of generated documentation against
versioned checklists with coverage and accuracy scoring.

Scoring formula:
  weighted_score = 0.6 * accuracy + 0.4 * coverage - contradiction_penalty

Where:
  coverage = covered / total (optionally weighted by severity)
  accuracy = correct / covered
  contradiction_penalty = 0.1 * contradiction_count
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import re
import yaml
from pathlib import Path


class Severity(Enum):
    """Checklist item severity levels."""
    MUST = "must"      # Required - higher weight
    SHOULD = "should"  # Recommended
    NICE = "nice"      # Nice to have - lower weight

    @property
    def weight(self) -> float:
        """Get severity weight for scoring."""
        return {
            Severity.MUST: 1.0,
            Severity.SHOULD: 0.7,
            Severity.NICE: 0.3,
        }[self]


class EvaluationStatus(Enum):
    """Evaluation status for a checklist item."""
    NOT_EVALUATED = "not_evaluated"
    COVERED = "covered"           # Item is addressed in doc
    CORRECT = "correct"           # Covered and factually correct
    INCORRECT = "incorrect"       # Covered but factually wrong
    UNSUPPORTED = "unsupported"   # Claim not backed by references
    CONTRADICTION = "contradiction"  # Contradicts reference material


@dataclass
class ChecklistItem:
    """A single checklist item for evaluation."""
    id: str                           # e.g., "SSA.C1"
    category: str                     # e.g., "intro", "concepts", "ownership"
    statement: str                    # What the doc should explain
    severity: Severity                # must/should/nice
    refs: List[str] = field(default_factory=list)  # Reference IDs (R1, R2, etc.)
    keywords: List[str] = field(default_factory=list)  # Keywords for heuristic detection
    supports_excerpts: List[str] = field(default_factory=list)  # Excerpt IDs that support this

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChecklistItem":
        """Create from dictionary (YAML parsing)."""
        severity = Severity(data.get("severity", "should"))
        return cls(
            id=data["id"],
            category=data.get("category", "general"),
            statement=data["statement"],
            severity=severity,
            refs=data.get("refs", []),
            keywords=data.get("keywords", []),
            supports_excerpts=data.get("supports", []),
        )


@dataclass
class ItemEvaluation:
    """Evaluation result for a single checklist item."""
    item_id: str
    status: EvaluationStatus
    covered: bool = False
    correct: Optional[bool] = None
    evidence: str = ""                # Text snippet that covers this item
    reasoning: str = ""               # Why this status was assigned
    cited_excerpts: List[str] = field(default_factory=list)  # Excerpt IDs cited
    confidence: float = 0.0           # 0-1 confidence in this evaluation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_id": self.item_id,
            "status": self.status.value,
            "covered": self.covered,
            "correct": self.correct,
            "evidence": self.evidence,
            "reasoning": self.reasoning,
            "cited_excerpts": self.cited_excerpts,
            "confidence": self.confidence,
        }


@dataclass
class ChecklistResult:
    """Overall result of checklist evaluation."""
    checklist_id: str
    total_items: int
    covered_count: int
    correct_count: int
    incorrect_count: int
    unsupported_count: int
    contradiction_count: int
    coverage_score: float          # covered / total (weighted)
    accuracy_score: float          # correct / covered
    weighted_score: float          # Final combined score
    item_evaluations: List[ItemEvaluation] = field(default_factory=list)
    evaluation_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "checklist_id": self.checklist_id,
            "total_items": self.total_items,
            "covered_count": self.covered_count,
            "correct_count": self.correct_count,
            "incorrect_count": self.incorrect_count,
            "unsupported_count": self.unsupported_count,
            "contradiction_count": self.contradiction_count,
            "coverage_score": self.coverage_score,
            "accuracy_score": self.accuracy_score,
            "weighted_score": self.weighted_score,
            "item_evaluations": [e.to_dict() for e in self.item_evaluations],
            "evaluation_details": self.evaluation_details,
        }


@dataclass
class Checklist:
    """A versioned checklist for evaluation."""
    checklist_id: str              # e.g., "ssa-doc-v1"
    name: str
    ref_bundle_id: Optional[str]   # Associated reference bundle
    items: List[ChecklistItem] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "Checklist":
        """Parse checklist from YAML content."""
        data = yaml.safe_load(yaml_content)
        items = [ChecklistItem.from_dict(item) for item in data.get("items", [])]
        categories = list(set(item.category for item in items))

        return cls(
            checklist_id=data.get("checklist_id", "unknown"),
            name=data.get("name", "Unnamed Checklist"),
            ref_bundle_id=data.get("ref_bundle_id"),
            items=items,
            categories=sorted(categories),
        )

    @classmethod
    def from_file(cls, path: Path) -> "Checklist":
        """Load checklist from YAML file."""
        with open(path) as f:
            return cls.from_yaml(f.read())

    def get_items_by_category(self, category: str) -> List[ChecklistItem]:
        """Get items for a specific category."""
        return [item for item in self.items if item.category == category]

    def get_items_by_severity(self, severity: Severity) -> List[ChecklistItem]:
        """Get items for a specific severity level."""
        return [item for item in self.items if item.severity == severity]


class ChecklistEvaluator:
    """
    Evaluates documentation against a checklist.

    Two-tier evaluation:
    - Tier A (fast): Keyword/regex heuristics for coverage detection
    - Tier B (accurate): LLM judge for correctness verification
    """

    # Weights for final score calculation
    ACCURACY_WEIGHT = 0.6
    COVERAGE_WEIGHT = 0.4
    CONTRADICTION_PENALTY = 0.1

    def __init__(self, checklist: Checklist, ref_excerpts: Optional[List[Dict]] = None):
        """
        Initialize evaluator.

        Args:
            checklist: The checklist to evaluate against
            ref_excerpts: Optional list of reference excerpts for grounded evaluation
        """
        self.checklist = checklist
        self.ref_excerpts = ref_excerpts or []
        self._excerpt_map = {e.get("id"): e for e in self.ref_excerpts}

    def evaluate_tier_a(self, document: str) -> ChecklistResult:
        """
        Tier A evaluation: Fast heuristic-based coverage detection.

        Uses keyword matching and regex patterns to detect which
        checklist items are likely covered in the document.
        """
        document_lower = document.lower()
        item_evaluations = []

        for item in self.checklist.items:
            evaluation = self._evaluate_item_heuristic(item, document, document_lower)
            item_evaluations.append(evaluation)

        return self._compute_result(item_evaluations)

    def evaluate_tier_b(
        self,
        document: str,
        tier_a_result: Optional[ChecklistResult] = None,
        judge_fn: Optional[callable] = None
    ) -> ChecklistResult:
        """
        Tier B evaluation: LLM judge for correctness verification.

        Only evaluates items that were marked as covered in Tier A.
        Uses the judge function to verify factual correctness against
        reference excerpts.

        Args:
            document: The document to evaluate
            tier_a_result: Optional Tier A result to build on
            judge_fn: Function(item, evidence, excerpts) -> (correct, reasoning)
        """
        if tier_a_result is None:
            tier_a_result = self.evaluate_tier_a(document)

        if judge_fn is None:
            # No judge provided, return Tier A result
            return tier_a_result

        item_evaluations = []

        for eval_a in tier_a_result.item_evaluations:
            if not eval_a.covered:
                # Not covered, keep as-is
                item_evaluations.append(eval_a)
                continue

            # Get the checklist item
            item = next((i for i in self.checklist.items if i.id == eval_a.item_id), None)
            if item is None:
                item_evaluations.append(eval_a)
                continue

            # Get relevant excerpts for this item
            relevant_excerpts = self._get_relevant_excerpts(item)

            # Call judge function
            try:
                correct, reasoning, cited = judge_fn(item, eval_a.evidence, relevant_excerpts)

                if correct is True:
                    status = EvaluationStatus.CORRECT
                elif correct is False:
                    # Check if it's a contradiction or just incorrect
                    if "contradict" in reasoning.lower():
                        status = EvaluationStatus.CONTRADICTION
                    else:
                        status = EvaluationStatus.INCORRECT
                else:
                    status = EvaluationStatus.UNSUPPORTED

                item_evaluations.append(ItemEvaluation(
                    item_id=eval_a.item_id,
                    status=status,
                    covered=True,
                    correct=correct,
                    evidence=eval_a.evidence,
                    reasoning=reasoning,
                    cited_excerpts=cited or [],
                    confidence=0.8,  # Judge confidence
                ))

            except Exception as e:
                # Judge failed, keep Tier A result
                item_evaluations.append(ItemEvaluation(
                    item_id=eval_a.item_id,
                    status=eval_a.status,
                    covered=eval_a.covered,
                    correct=None,
                    evidence=eval_a.evidence,
                    reasoning=f"Judge error: {e}",
                    confidence=eval_a.confidence,
                ))

        return self._compute_result(item_evaluations)

    def _evaluate_item_heuristic(
        self,
        item: ChecklistItem,
        document: str,
        document_lower: str
    ) -> ItemEvaluation:
        """Evaluate a single item using heuristics."""
        # Check keywords from item definition
        keywords_found = []
        for keyword in item.keywords:
            if keyword.lower() in document_lower:
                keywords_found.append(keyword)

        # Check for key terms derived from the statement
        statement_terms = self._extract_key_terms(item.statement)
        terms_found = sum(1 for term in statement_terms if term.lower() in document_lower)
        term_coverage = terms_found / len(statement_terms) if statement_terms else 0

        # Determine if covered
        covered = len(keywords_found) > 0 or term_coverage > 0.5

        # Extract evidence (first paragraph containing keywords)
        evidence = ""
        if covered:
            evidence = self._extract_evidence(document, keywords_found or statement_terms[:3])

        status = EvaluationStatus.COVERED if covered else EvaluationStatus.NOT_EVALUATED

        return ItemEvaluation(
            item_id=item.id,
            status=status,
            covered=covered,
            correct=None,  # Unknown until Tier B
            evidence=evidence[:500],  # Limit evidence length
            reasoning=f"Keywords found: {keywords_found}" if keywords_found else f"Term coverage: {term_coverage:.0%}",
            confidence=0.6 if covered else 0.3,
        )

    def _extract_key_terms(self, statement: str) -> List[str]:
        """Extract key terms from a statement for matching."""
        # Remove common words and extract meaningful terms
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "can", "and", "or", "but", "if",
            "then", "else", "when", "where", "why", "how", "what", "which", "who",
            "this", "that", "these", "those", "it", "its", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "as", "into", "through", "during",
            "before", "after", "above", "below", "between", "under", "again",
            "explains", "describes", "mentions", "shows", "defines", "provides",
        }

        # Tokenize and filter
        words = re.findall(r'\b[a-zA-Z][a-zA-Z-]+\b', statement.lower())
        terms = [w for w in words if w not in stop_words and len(w) > 2]

        return terms[:10]  # Limit to top 10 terms

    def _extract_evidence(self, document: str, terms: List[str]) -> str:
        """Extract a paragraph containing the key terms."""
        paragraphs = document.split('\n\n')

        for para in paragraphs:
            para_lower = para.lower()
            matches = sum(1 for t in terms if t.lower() in para_lower)
            if matches >= min(2, len(terms)):
                return para.strip()

        # Fallback: first paragraph with any match
        for para in paragraphs:
            para_lower = para.lower()
            if any(t.lower() in para_lower for t in terms):
                return para.strip()

        return ""

    def _get_relevant_excerpts(self, item: ChecklistItem) -> List[Dict]:
        """Get reference excerpts relevant to a checklist item."""
        excerpts = []

        # First, check explicit supports
        for excerpt_id in item.supports_excerpts:
            if excerpt_id in self._excerpt_map:
                excerpts.append(self._excerpt_map[excerpt_id])

        # If no explicit supports, get excerpts by ref
        if not excerpts:
            for ref in item.refs:
                for excerpt in self.ref_excerpts:
                    if excerpt.get("ref") == ref:
                        excerpts.append(excerpt)

        return excerpts[:5]  # Limit to 5 excerpts

    def _compute_result(self, item_evaluations: List[ItemEvaluation]) -> ChecklistResult:
        """Compute the final result from item evaluations."""
        total_items = len(item_evaluations)
        if total_items == 0:
            return ChecklistResult(
                checklist_id=self.checklist.checklist_id,
                total_items=0,
                covered_count=0,
                correct_count=0,
                incorrect_count=0,
                unsupported_count=0,
                contradiction_count=0,
                coverage_score=0.0,
                accuracy_score=0.0,
                weighted_score=0.0,
                item_evaluations=item_evaluations,
            )

        # Count statuses
        covered_count = sum(1 for e in item_evaluations if e.covered)
        correct_count = sum(1 for e in item_evaluations if e.status == EvaluationStatus.CORRECT)
        incorrect_count = sum(1 for e in item_evaluations if e.status == EvaluationStatus.INCORRECT)
        unsupported_count = sum(1 for e in item_evaluations if e.status == EvaluationStatus.UNSUPPORTED)
        contradiction_count = sum(1 for e in item_evaluations if e.status == EvaluationStatus.CONTRADICTION)

        # Calculate weighted coverage (by severity)
        total_weight = sum(
            next((i.severity.weight for i in self.checklist.items if i.id == e.item_id), 1.0)
            for e in item_evaluations
        )
        covered_weight = sum(
            next((i.severity.weight for i in self.checklist.items if i.id == e.item_id), 1.0)
            for e in item_evaluations if e.covered
        )
        coverage_score = covered_weight / total_weight if total_weight > 0 else 0.0

        # Calculate accuracy (correct / covered that were judged)
        judged_covered = [e for e in item_evaluations if e.covered and e.correct is not None]
        if judged_covered:
            accuracy_score = sum(1 for e in judged_covered if e.correct) / len(judged_covered)
        else:
            # If no items were judged, use coverage as proxy
            accuracy_score = coverage_score

        # Calculate weighted score
        contradiction_penalty = self.CONTRADICTION_PENALTY * contradiction_count
        weighted_score = max(0.0, min(1.0,
            self.ACCURACY_WEIGHT * accuracy_score +
            self.COVERAGE_WEIGHT * coverage_score -
            contradiction_penalty
        ))

        return ChecklistResult(
            checklist_id=self.checklist.checklist_id,
            total_items=total_items,
            covered_count=covered_count,
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            unsupported_count=unsupported_count,
            contradiction_count=contradiction_count,
            coverage_score=round(coverage_score, 4),
            accuracy_score=round(accuracy_score, 4),
            weighted_score=round(weighted_score, 4),
            item_evaluations=item_evaluations,
            evaluation_details={
                "accuracy_weight": self.ACCURACY_WEIGHT,
                "coverage_weight": self.COVERAGE_WEIGHT,
                "contradiction_penalty_rate": self.CONTRADICTION_PENALTY,
            },
        )

    def get_uncovered_items(self, result: ChecklistResult) -> List[ChecklistItem]:
        """Get checklist items that were not covered."""
        covered_ids = {e.item_id for e in result.item_evaluations if e.covered}
        return [item for item in self.checklist.items if item.id not in covered_ids]

    def get_items_by_status(
        self,
        result: ChecklistResult,
        status: EvaluationStatus
    ) -> List[tuple[ChecklistItem, ItemEvaluation]]:
        """Get items with a specific evaluation status."""
        items = []
        for eval_item in result.item_evaluations:
            if eval_item.status == status:
                item = next((i for i in self.checklist.items if i.id == eval_item.item_id), None)
                if item:
                    items.append((item, eval_item))
        return items
