"""
Task mining infrastructure for CodeContextBench.

Mines real OSS repositories for tasks matching CodeContextBench criteria:
- Multi-file changes required
- Ground-truth fix available (merged PR / closed issue)
- Deterministically verifiable (tests or reproducible checks)
- Requires codebase understanding (not pattern-matchable)
"""

from .github_client import GitHubClient, GitHubIssue, GitHubPullRequest
from .task_generator import TaskGenerator
from .task_filter import TaskFilter, FilterResult
from .repo_registry import RepositoryRegistry, RepositoryConfig, Language

__all__ = [
    "GitHubClient",
    "GitHubIssue",
    "GitHubPullRequest",
    "TaskGenerator",
    "TaskFilter",
    "FilterResult",
    "RepositoryRegistry",
    "RepositoryConfig",
    "Language",
]
