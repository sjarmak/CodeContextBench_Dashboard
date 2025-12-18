"""
Task specification generator for CodeContextBench.

Converts GitHub issues/PRs + code analysis into TaskSpecification objects.
"""

import re
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from src.benchmark.task_schema import (
    TaskSpecification,
    TaskCategory,
    Language as TaskLanguage,
    Difficulty,
)
from .github_client import GitHubIssue, GitHubPullRequest, GitHubClient
from .repo_registry import RepositoryConfig, Language as RegLanguage


class TaskGenerator:
    """
    Generates TaskSpecification from GitHub issues and PRs.
    
    Applies CodeContextBench task eligibility criteria:
    - Multi-file changes (min 2 files modified)
    - Deterministic verifiers (test commands)
    - Requires codebase understanding (not pattern-matchable)
    """
    
    def __init__(self, gh_client: GitHubClient):
        self.gh_client = gh_client
    
    @staticmethod
    def _infer_difficulty(
        files_changed: int,
        additions: int,
        deletions: int,
    ) -> Difficulty:
        """Heuristic difficulty estimation"""
        # Multi-file changes are inherently harder
        if files_changed >= 10:
            return Difficulty.HARD
        elif files_changed >= 5:
            return Difficulty.HARD
        elif files_changed >= 3:
            return Difficulty.MEDIUM
        else:
            return Difficulty.EASY
    
    @staticmethod
    def _infer_category(
        pr_title: str,
        pr_body: str,
    ) -> TaskCategory:
        """Heuristic category inference from PR/issue content"""
        combined = (pr_title + " " + pr_body).lower()
        
        if any(kw in combined for kw in ["fix", "bug", "issue", "error"]):
            return TaskCategory.CROSS_MODULE_BUG_FIX
        elif any(kw in combined for kw in ["refactor", "rename", "extract", "cleanup"]):
            return TaskCategory.REFACTORING
        elif any(kw in combined for kw in ["feature", "add", "implement", "new"]):
            return TaskCategory.FEATURE_IMPLEMENTATION
        elif any(kw in combined for kw in ["perf", "optimize", "speed", "fast"]):
            return TaskCategory.PERFORMANCE_OPTIMIZATION
        elif any(kw in combined for kw in ["upgrade", "update", "version", "deprecat"]):
            return TaskCategory.DEPENDENCY_UPGRADE
        else:
            return TaskCategory.CROSS_MODULE_BUG_FIX  # Default
    
    @staticmethod
    def _infer_test_command(repo_config: RepositoryConfig) -> str:
        """Infer test command based on repository language"""
        lang = repo_config.language
        
        if lang == RegLanguage.PYTHON:
            return "python -m pytest tests/ -xvs"
        elif lang == RegLanguage.GO:
            return "go test ./..."
        elif lang == RegLanguage.TYPESCRIPT or lang == RegLanguage.JAVASCRIPT:
            return "npm test"
        elif lang == RegLanguage.RUST:
            return "cargo test"
        elif lang == RegLanguage.CPP or lang == RegLanguage.C:
            return "make test"  # Repo-specific, may vary
        else:
            return "make test"
    
    @staticmethod
    def _map_language(reg_lang: RegLanguage) -> TaskLanguage:
        """Map registry language to task schema language"""
        mapping = {
            RegLanguage.PYTHON: TaskLanguage.PYTHON,
            RegLanguage.GO: TaskLanguage.GO,
            RegLanguage.TYPESCRIPT: TaskLanguage.TYPESCRIPT,
            RegLanguage.JAVASCRIPT: TaskLanguage.JAVASCRIPT,
            RegLanguage.RUST: TaskLanguage.RUST,
            RegLanguage.CPP: TaskLanguage.CPP,
            RegLanguage.C: TaskLanguage.C,
        }
        return mapping.get(reg_lang, TaskLanguage.PYTHON)
    
    def from_pr(
        self,
        pr: GitHubPullRequest,
        repo_config: RepositoryConfig,
        task_id: str,
        pre_fix_rev: str,
        ground_truth_rev: str,
    ) -> Optional[TaskSpecification]:
        """
        Generate TaskSpecification from merged PR.
        
        Args:
            pr: GitHub PR
            repo_config: Repository configuration
            task_id: Task ID (e.g., "sgt-001")
            pre_fix_rev: Git revision before fix
            ground_truth_rev: Git revision with fix (PR merge commit)
        
        Returns:
            TaskSpecification or None if ineligible
        """
        # Filter: multi-file requirement
        if pr.files_changed < 2:
            return None
        
        # Infer task properties
        category = self._infer_category(pr.title, pr.body)
        difficulty = self._infer_difficulty(pr.files_changed, pr.additions, pr.deletions)
        test_command = self._infer_test_command(repo_config)
        language = self._map_language(repo_config.language)
        
        # Construct instructions from PR title/body
        instructions = f"""
Review the PR: {pr.title}

Description: {pr.body[:500]}

Changes:
- {pr.files_changed} files modified
- {pr.additions} additions, {pr.deletions} deletions

Tasks:
1. Understand the issue being fixed
2. Review the solution in the merged PR
3. Implement the fix to pass all tests
4. Verify: run "{test_command}" successfully
""".strip()
        
        # Success criteria
        success_criteria = f"""
All tests pass: run "{test_command}" successfully.
Code follows repository conventions.
No regressions in existing functionality.
All {pr.files_changed} modified files updated correctly.
""".strip()
        
        # Tags from PR labels
        tags = pr.labels[:5] if pr.labels else None
        
        return TaskSpecification(
            id=task_id,
            repo_key=repo_config.repo_key,
            title=pr.title,
            description=(pr.body[:500] if pr.body else "") or f"Task: {pr.title}\n\nThis PR implements the following changes:\n- Files changed: {pr.files_changed}\n- Additions: {pr.additions}\n- Deletions: {pr.deletions}",
            category=category,
            language=language,
            difficulty=difficulty,
            instructions=instructions,
            success_criteria=success_criteria,
            test_command=test_command,
            verification_type="test",
            pre_fix_rev=pre_fix_rev,
            ground_truth_rev=ground_truth_rev,
            source_issue_url=f"{repo_config.github_url()}/pull/{pr.number}",
            files_to_modify=None,  # Could extract from PR files
            estimated_tokens=8000,  # Conservative estimate
            time_limit_seconds=600,
            tags=tags,
        )
    
    def from_issue(
        self,
        issue: GitHubIssue,
        repo_config: RepositoryConfig,
        task_id: str,
        pre_fix_rev: str,
        ground_truth_rev: str,
    ) -> Optional[TaskSpecification]:
        """
        Generate TaskSpecification from closed issue with linked PR.
        
        Args:
            issue: GitHub issue
            repo_config: Repository configuration
            task_id: Task ID
            pre_fix_rev: Git revision before fix
            ground_truth_rev: Git revision with fix
        
        Returns:
            TaskSpecification or None if ineligible
        """
        if not issue.linked_pr_number:
            return None
        
        # Get PR details for multi-file check
        try:
            pr_data = self.gh_client._get(
                f"/repos/{repo_config.github_url().replace('https://github.com/', '')}"
                f"/pulls/{issue.linked_pr_number}"
            )
            files_changed = pr_data.get("changed_files", 0)
        except:
            return None
        
        # Filter: multi-file requirement
        if files_changed < 2:
            return None
        
        # Infer task properties
        category = self._infer_category(issue.title, issue.body)
        difficulty = self._infer_difficulty(files_changed, 0, 0)
        test_command = self._infer_test_command(repo_config)
        language = self._map_language(repo_config.language)
        
        # Construct instructions
        instructions = f"""
Resolve issue: {issue.title}

Issue description: {issue.body[:400]}

Requirements:
1. Understand the issue described above
2. Implement a fix across relevant files
3. Ensure all tests pass
4. Run: {test_command}
""".strip()
        
        success_criteria = f"""
Issue is resolved: all related tests pass.
No regressions introduced.
All code follows repository style guidelines.
Run "{test_command}" successfully.
""".strip()
        
        return TaskSpecification(
            id=task_id,
            repo_key=repo_config.repo_key,
            title=issue.title,
            description=(issue.body[:500] if issue.body else "") or f"Task: {issue.title}",
            category=category,
            language=language,
            difficulty=difficulty,
            instructions=instructions,
            success_criteria=success_criteria,
            test_command=test_command,
            verification_type="test",
            pre_fix_rev=pre_fix_rev,
            ground_truth_rev=ground_truth_rev,
            source_issue_url=f"{repo_config.github_url()}/issues/{issue.number}",
            files_to_modify=None,
            estimated_tokens=8000,
            time_limit_seconds=600,
            tags=issue.labels[:5] if issue.labels else None,
        )
