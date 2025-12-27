"""
Evaluation module for CodeContextBench.

Contains:
- Checklist evaluation system for doc tasks
- Grounding anchor validation
- Hard verifiers
"""

from .checklist import (
    ChecklistItem,
    Checklist,
    ChecklistEvaluator,
    ItemEvaluation,
    ChecklistResult,
)

__all__ = [
    "ChecklistItem",
    "Checklist",
    "ChecklistEvaluator",
    "ItemEvaluation",
    "ChecklistResult",
]
