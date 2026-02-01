"""Tests for checklist evaluation system."""

import pytest
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluation.checklist import (
    ChecklistItem,
    Checklist,
    ChecklistEvaluator,
    ItemEvaluation,
    ChecklistResult,
    Severity,
    EvaluationStatus,
)


class TestChecklistItem:
    """Tests for ChecklistItem."""

    def test_from_dict(self):
        """Test creating item from dictionary."""
        data = {
            "id": "SSA.C1",
            "category": "intro",
            "statement": "Explains SSA solves server-side declarative intent.",
            "severity": "must",
            "refs": ["R1", "R2"],
            "keywords": ["server-side apply", "field ownership"],
        }
        item = ChecklistItem.from_dict(data)

        assert item.id == "SSA.C1"
        assert item.category == "intro"
        assert item.severity == Severity.MUST
        assert len(item.refs) == 2
        assert "server-side apply" in item.keywords

    def test_severity_weights(self):
        """Test severity weight values."""
        assert Severity.MUST.weight == 1.0
        assert Severity.SHOULD.weight == 0.7
        assert Severity.NICE.weight == 0.3


class TestChecklist:
    """Tests for Checklist."""

    def test_from_yaml(self):
        """Test loading checklist from YAML."""
        yaml_content = """
checklist_id: test-v1
name: Test Checklist
ref_bundle_id: test-bundle

items:
  - id: T.1
    category: intro
    statement: First test item
    severity: must
    keywords: [test, first]

  - id: T.2
    category: concepts
    statement: Second test item
    severity: should
    keywords: [test, second]
"""
        checklist = Checklist.from_yaml(yaml_content)

        assert checklist.checklist_id == "test-v1"
        assert checklist.name == "Test Checklist"
        assert len(checklist.items) == 2
        assert set(checklist.categories) == {"intro", "concepts"}

    def test_get_items_by_category(self):
        """Test filtering items by category."""
        yaml_content = """
checklist_id: test-v1
name: Test
items:
  - id: T.1
    category: intro
    statement: Intro item
    severity: must
  - id: T.2
    category: concepts
    statement: Concept item
    severity: should
  - id: T.3
    category: intro
    statement: Another intro
    severity: nice
"""
        checklist = Checklist.from_yaml(yaml_content)
        intro_items = checklist.get_items_by_category("intro")

        assert len(intro_items) == 2
        assert all(item.category == "intro" for item in intro_items)


class TestChecklistEvaluator:
    """Tests for ChecklistEvaluator."""

    @pytest.fixture
    def simple_checklist(self):
        """Create a simple checklist for testing."""
        yaml_content = """
checklist_id: simple-v1
name: Simple Test Checklist
items:
  - id: S.1
    category: intro
    statement: Explains the main concept
    severity: must
    keywords: [main concept, overview]

  - id: S.2
    category: details
    statement: Describes implementation details
    severity: should
    keywords: [implementation, details, code]

  - id: S.3
    category: examples
    statement: Provides code examples
    severity: nice
    keywords: [example, code snippet, demo]
"""
        return Checklist.from_yaml(yaml_content)

    def test_tier_a_evaluation_covered(self, simple_checklist):
        """Test Tier A evaluation detects covered items."""
        document = """
# Main Concept Overview

This document provides an overview of the main concept.
It explains the key principles and design decisions.

## Implementation Details

The implementation uses a modular approach with clear separation
of concerns. The code follows best practices for maintainability.

## Conclusion

More information will be added later.
"""
        evaluator = ChecklistEvaluator(simple_checklist)
        result = evaluator.evaluate_tier_a(document)

        # S.1 and S.2 should be covered (keywords match)
        assert result.covered_count >= 2
        assert result.coverage_score > 0.5

    def test_tier_a_evaluation_not_covered(self, simple_checklist):
        """Test Tier A evaluation detects uncovered items."""
        document = """
# Unrelated Document

This document talks about completely different topics.
Nothing about concepts or implementation here.
"""
        evaluator = ChecklistEvaluator(simple_checklist)
        result = evaluator.evaluate_tier_a(document)

        # Most items should not be covered
        assert result.covered_count < len(simple_checklist.items)

    def test_weighted_score_calculation(self, simple_checklist):
        """Test weighted score calculation."""
        evaluator = ChecklistEvaluator(simple_checklist)

        # Create mock evaluations
        evaluations = [
            ItemEvaluation("S.1", EvaluationStatus.CORRECT, covered=True, correct=True),
            ItemEvaluation("S.2", EvaluationStatus.COVERED, covered=True, correct=None),
            ItemEvaluation("S.3", EvaluationStatus.NOT_EVALUATED, covered=False),
        ]

        result = evaluator._compute_result(evaluations)

        # Check score components
        assert result.covered_count == 2
        assert result.correct_count == 1
        assert result.coverage_score > 0  # Should have partial coverage
        assert result.weighted_score > 0

    def test_contradiction_penalty(self, simple_checklist):
        """Test that contradictions reduce the score."""
        evaluator = ChecklistEvaluator(simple_checklist)

        # Create evaluations with a contradiction
        eval_no_contradiction = [
            ItemEvaluation("S.1", EvaluationStatus.CORRECT, covered=True, correct=True),
            ItemEvaluation("S.2", EvaluationStatus.CORRECT, covered=True, correct=True),
            ItemEvaluation("S.3", EvaluationStatus.COVERED, covered=True),
        ]

        eval_with_contradiction = [
            ItemEvaluation("S.1", EvaluationStatus.CORRECT, covered=True, correct=True),
            ItemEvaluation("S.2", EvaluationStatus.CONTRADICTION, covered=True, correct=False),
            ItemEvaluation("S.3", EvaluationStatus.COVERED, covered=True),
        ]

        result_clean = evaluator._compute_result(eval_no_contradiction)
        result_contradiction = evaluator._compute_result(eval_with_contradiction)

        # Contradiction should lower the score
        assert result_contradiction.weighted_score < result_clean.weighted_score
        assert result_contradiction.contradiction_count == 1


class TestSSAChecklist:
    """Tests for the SSA documentation checklist."""

    @pytest.fixture
    def ssa_checklist(self):
        """Load the SSA checklist."""
        checklist_path = Path(__file__).parent.parent / "configs" / "checklists" / "ssa-doc-v1.yaml"
        return Checklist.from_file(checklist_path)

    def test_ssa_checklist_loads(self, ssa_checklist):
        """Test SSA checklist loads correctly."""
        assert ssa_checklist.checklist_id == "ssa-doc-v1"
        assert len(ssa_checklist.items) == 56  # 7+11+12+10+8+4+4 = 56 (we have one extra)

    def test_ssa_checklist_categories(self, ssa_checklist):
        """Test SSA checklist has expected categories."""
        expected_categories = {
            "intro", "ownership", "merge", "conflicts",
            "api", "migration", "controllers"
        }
        assert expected_categories.issubset(set(ssa_checklist.categories))

    def test_ssa_checklist_severity_distribution(self, ssa_checklist):
        """Test SSA checklist has reasonable severity distribution."""
        must_items = ssa_checklist.get_items_by_severity(Severity.MUST)
        should_items = ssa_checklist.get_items_by_severity(Severity.SHOULD)
        nice_items = ssa_checklist.get_items_by_severity(Severity.NICE)

        # Should have items in each severity level
        assert len(must_items) > 0
        assert len(should_items) > 0
        assert len(nice_items) > 0

        # Must items should be significant portion
        assert len(must_items) >= 15  # At least 15 "must" items

    def test_ssa_evaluation_sample_doc(self, ssa_checklist):
        """Test SSA evaluation on a sample document."""
        sample_doc = """
# Kubernetes Server-Side Apply Guide

## Introduction

Server-Side Apply (SSA) is a feature that allows the Kubernetes API server
to perform declarative configuration management server-side, with built-in
field ownership tracking.

### SSA vs Client-Side Apply

Unlike client-side apply which relies on the `last-applied-configuration`
annotation, SSA tracks field ownership using `managedFields` metadata.

## Field Managers

A field manager is an identity that claims ownership of specific fields.
Each manager should have a unique name to avoid conflicts.

To view managed fields:
```bash
kubectl get deployment my-app --show-managed-fields -o yaml
```

## Merge Semantics

SSA uses OpenAPI schema extensions to determine merge behavior:
- `x-kubernetes-list-type`: Defines list merge strategy (atomic, map, set)
- `x-kubernetes-map-type`: Defines map merge strategy (atomic, granular)

### Merge Strategy Reference

| Type | Behavior |
|------|----------|
| atomic | Replace entire value |
| map | Merge by key |
| set | Unique elements |
| granular | Per-field ownership |

## Conflicts

A conflict occurs when trying to change a field owned by another manager.
Use `--force-conflicts` to override, but use carefully.

## kubectl Usage

```bash
kubectl apply --server-side --field-manager=my-controller -f manifest.yaml
kubectl apply --server-side --force-conflicts -f manifest.yaml
```
"""
        evaluator = ChecklistEvaluator(ssa_checklist)
        result = evaluator.evaluate_tier_a(sample_doc)

        # Should cover a reasonable number of items
        assert result.covered_count >= 10
        assert result.coverage_score > 0.2  # At least 20% coverage
        print(f"Coverage: {result.coverage_score:.1%} ({result.covered_count}/{result.total_items})")


class TestItemEvaluation:
    """Tests for ItemEvaluation."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        eval_item = ItemEvaluation(
            item_id="T.1",
            status=EvaluationStatus.CORRECT,
            covered=True,
            correct=True,
            evidence="Some evidence text",
            reasoning="Matched keywords",
            cited_excerpts=["E1", "E2"],
            confidence=0.85,
        )

        result = eval_item.to_dict()

        assert result["item_id"] == "T.1"
        assert result["status"] == "correct"
        assert result["covered"] is True
        assert result["confidence"] == 0.85


class TestChecklistResult:
    """Tests for ChecklistResult."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ChecklistResult(
            checklist_id="test-v1",
            total_items=10,
            covered_count=7,
            correct_count=5,
            incorrect_count=1,
            unsupported_count=1,
            contradiction_count=0,
            coverage_score=0.7,
            accuracy_score=0.71,
            weighted_score=0.706,
            item_evaluations=[],
        )

        data = result.to_dict()

        assert data["checklist_id"] == "test-v1"
        assert data["covered_count"] == 7
        assert data["weighted_score"] == 0.706


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
