"""
Task filtering and validation for CodeContextBench mining results.

Applies CodeContextBench eligibility criteria:
- Multi-file changes (minimum 2 files)
- Task properties (difficulty, category, language)
- Test command feasibility (can we verify the task?)
- Estimated token budget (within reasonable context limits)
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json
import logging

from src.benchmark.task_schema import TaskSpecification, TaskValidator

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Result of filtering a single task"""
    task_id: str
    passed: bool
    reasons: List[str]  # Reasons for rejection
    metadata: Dict[str, Any]  # Additional info


class TaskFilter:
    """
    Filters task candidates by CodeContextBench eligibility criteria.
    """
    
    # Eligibility thresholds
    MIN_FILES_CHANGED = 2
    MAX_FILES_CHANGED = 100
    MIN_DESCRIPTION_LENGTH = 50
    MIN_INSTRUCTIONS_LENGTH = 30
    MIN_SUCCESS_CRITERIA_LENGTH = 20
    MAX_ESTIMATED_TOKENS = 20000
    MIN_ESTIMATED_TOKENS = 1000
    
    @staticmethod
    def filter_task(task_dict: Dict[str, Any]) -> FilterResult:
        """
        Filter a single task against all eligibility criteria.
        
        Returns:
            FilterResult with passed/rejected status and reasons
        """
        task_id = task_dict.get("id", "unknown")
        reasons = []
        
        # 1. Schema validation
        is_valid, error = TaskValidator.validate(task_dict)
        if not is_valid:
            return FilterResult(
                task_id=task_id,
                passed=False,
                reasons=[f"Schema validation failed: {error}"],
                metadata={},
            )
        
        # 2. Test command feasibility
        test_command = task_dict.get("test_command", "")
        if not test_command or len(test_command) < 5:
            reasons.append(f"Test command missing or too short: '{test_command}'")
        
        # 3. Difficulty is set
        if not task_dict.get("difficulty"):
            reasons.append("Difficulty not set")
        
        # 4. Category is set
        if not task_dict.get("category"):
            reasons.append("Category not set")
        
        # 5. Language is supported
        supported_languages = {
            "python", "typescript", "javascript", "go", "rust",
            "cpp", "c", "java", "csharp"
        }
        language = task_dict.get("language", "")
        if language not in supported_languages:
            reasons.append(f"Language not supported: {language}")
        
        # 6. Token budget
        estimated_tokens = task_dict.get("estimated_tokens", 0)
        if estimated_tokens < TaskFilter.MIN_ESTIMATED_TOKENS:
            reasons.append(
                f"Token estimate too low: {estimated_tokens} "
                f"(min: {TaskFilter.MIN_ESTIMATED_TOKENS})"
            )
        if estimated_tokens > TaskFilter.MAX_ESTIMATED_TOKENS:
            reasons.append(
                f"Token estimate too high: {estimated_tokens} "
                f"(max: {TaskFilter.MAX_ESTIMATED_TOKENS})"
            )
        
        # 7. Time budget is reasonable
        time_limit = task_dict.get("time_limit_seconds", 0)
        if time_limit < 60:
            reasons.append(f"Time limit too low: {time_limit}s (min: 60s)")
        if time_limit > 3600:
            reasons.append(f"Time limit too high: {time_limit}s (max: 3600s)")
        
        # 8. Source issue URL
        if not task_dict.get("source_issue_url"):
            reasons.append("source_issue_url missing")
        
        # 9. Pre-fix and ground-truth revisions
        if not task_dict.get("pre_fix_rev") or len(task_dict.get("pre_fix_rev", "")) < 6:
            reasons.append(f"pre_fix_rev invalid: {task_dict.get('pre_fix_rev')}")
        
        if not task_dict.get("ground_truth_rev") or len(task_dict.get("ground_truth_rev", "")) < 6:
            reasons.append(f"ground_truth_rev invalid: {task_dict.get('ground_truth_rev')}")
        
        # Passed if no rejection reasons
        passed = len(reasons) == 0
        
        return FilterResult(
            task_id=task_id,
            passed=passed,
            reasons=reasons,
            metadata={
                "category": task_dict.get("category"),
                "difficulty": task_dict.get("difficulty"),
                "language": task_dict.get("language"),
                "test_command": test_command,
                "estimated_tokens": estimated_tokens,
            },
        )
    
    @staticmethod
    def filter_batch(
        tasks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Filter a batch of tasks.
        
        Args:
            tasks: List of task dicts
        
        Returns:
            {
                "total": 100,
                "passed": 42,
                "failed": 58,
                "passed_tasks": [...],
                "failed_tasks": [
                    {"task_id": "sgt-001", "reasons": [...]}
                ]
            }
        """
        passed_tasks = []
        failed_tasks = []
        
        for task_dict in tasks:
            result = TaskFilter.filter_task(task_dict)
            
            if result.passed:
                passed_tasks.append(task_dict)
            else:
                failed_tasks.append({
                    "task_id": result.task_id,
                    "reasons": result.reasons,
                    "metadata": result.metadata,
                })
        
        return {
            "total": len(tasks),
            "passed": len(passed_tasks),
            "failed": len(failed_tasks),
            "pass_rate": len(passed_tasks) / max(1, len(tasks)),
            "passed_tasks": passed_tasks,
            "failed_tasks": failed_tasks,
        }
