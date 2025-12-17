"""
GitHub API client for mining CodeContextBench tasks.

Queries for:
1. Closed issues with linked PRs (ground-truth fix)
2. Merged PRs that fix issues
3. Filtered by multi-file changes, test coverage, etc.
"""

import os
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import requests
from urllib.parse import urlencode


@dataclass
class GitHubIssue:
    """GitHub issue candidate for mining"""
    number: int
    title: str
    body: str
    state: str  # "open" | "closed"
    created_at: str
    updated_at: str
    closed_at: Optional[str]
    labels: List[str]
    linked_pr_number: Optional[int] = None
    linked_pr_merged: bool = False
    linked_pr_merge_commit: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class GitHubPullRequest:
    """GitHub PR candidate for mining"""
    number: int
    title: str
    body: str
    state: str
    created_at: str
    merged_at: Optional[str]
    merge_commit_sha: Optional[str]
    files_changed: int
    additions: int
    deletions: int
    labels: List[str]
    linked_issue_number: Optional[int] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


class GitHubClient:
    """
    GitHub API client for mining tasks.
    
    Uses GitHub REST API v3 (or GraphQL for complex queries).
    Requires GITHUB_TOKEN environment variable.
    """
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN environment variable required")
        
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        })
    
    def _get(self, path: str, params: Optional[Dict] = None) -> Dict:
        """Make authenticated GET request"""
        url = f"{self.BASE_URL}{path}"
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()
    
    def search_issues(
        self,
        repo: str,  # "org/repo"
        filters: Optional[Dict[str, Any]] = None,
        sort: str = "updated",
        order: str = "desc",
        per_page: int = 100,
    ) -> List[Dict]:
        """
        Search GitHub issues with optional filters.
        
        Args:
            repo: "org/repo"
            filters: Query filters (e.g., {"is": "closed", "has": "linked_pr"})
            sort: "created", "updated", "comments"
            order: "asc", "desc"
            per_page: Results per page (max 100)
        
        Returns:
            List of issue dicts
        """
        query_parts = [f"repo:{repo}"]
        
        if filters:
            for key, val in filters.items():
                if isinstance(val, list):
                    query_parts.extend([f"{key}:{v}" for v in val])
                else:
                    query_parts.append(f"{key}:{val}")
        
        query = " ".join(query_parts)
        
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": per_page,
        }
        
        result = self._get("/search/issues", params=params)
        return result.get("items", [])
    
    def get_issue_with_prs(self, repo: str, issue_number: int) -> Optional[Dict]:
        """
        Get issue details and linked PRs.
        
        Args:
            repo: "org/repo"
            issue_number: Issue number
        
        Returns:
            Issue dict with linked PRs (if any)
        """
        issue = self._get(f"/repos/{repo}/issues/{issue_number}")
        
        # Look for linked PRs in timeline
        timeline = self._get(
            f"/repos/{repo}/issues/{issue_number}/timeline",
            params={"per_page": 100}
        )
        
        linked_prs = []
        for event in timeline:
            if event.get("event") == "cross-referenced":
                source = event.get("source", {})
                if source.get("type") == "PullRequest":
                    linked_prs.append(source.get("number"))
        
        issue["linked_prs"] = linked_prs
        return issue
    
    def get_pr_files(self, repo: str, pr_number: int) -> List[Dict]:
        """
        Get files changed in a PR.
        
        Args:
            repo: "org/repo"
            pr_number: PR number
        
        Returns:
            List of file dicts with filename, status, additions, deletions
        """
        files = []
        page = 1
        per_page = 100
        
        while True:
            result = self._get(
                f"/repos/{repo}/pulls/{pr_number}/files",
                params={"page": page, "per_page": per_page}
            )
            
            if not result:
                break
            
            files.extend(result)
            
            if len(result) < per_page:
                break
            
            page += 1
        
        return files
    
    def get_pr_commits(self, repo: str, pr_number: int) -> List[Dict]:
        """
        Get commits in a PR.
        
        Args:
            repo: "org/repo"
            pr_number: PR number
        
        Returns:
            List of commit dicts
        """
        commits = []
        page = 1
        per_page = 100
        
        while True:
            result = self._get(
                f"/repos/{repo}/pulls/{pr_number}/commits",
                params={"page": page, "per_page": per_page}
            )
            
            if not result:
                break
            
            commits.extend(result)
            
            if len(result) < per_page:
                break
            
            page += 1
        
        return commits
    
    def get_repo_info(self, repo: str) -> Dict:
        """Get repository metadata"""
        return self._get(f"/repos/{repo}")
    
    def closed_issues_with_linked_prs(
        self,
        repo: str,
        days_back: int = 365,
        min_labels: Optional[List[str]] = None,
        exclude_labels: Optional[List[str]] = None,
    ) -> List[GitHubIssue]:
        """
        Mine closed issues that have linked merged PRs.
        
        Args:
            repo: "org/repo"
            days_back: Only issues closed in last N days
            min_labels: Filter to issues with any of these labels
            exclude_labels: Exclude issues with these labels
        
        Returns:
            List of GitHubIssue candidates
        """
        since_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        
        filters = {
            "is": "closed",
            "closed": f">={since_date}",
        }
        
        if min_labels:
            filters["label"] = min_labels
        
        if exclude_labels:
            filters["-label"] = exclude_labels
        
        issues = []
        for item in self.search_issues(repo, filters=filters, per_page=100):
            # Check for linked PRs
            full_issue = self.get_issue_with_prs(repo, item["number"])
            linked_prs = full_issue.get("linked_prs", [])
            
            if linked_prs:
                issues.append(GitHubIssue(
                    number=item["number"],
                    title=item["title"],
                    body=item.get("body", ""),
                    state=item["state"],
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    closed_at=item.get("closed_at"),
                    labels=[label["name"] for label in item.get("labels", [])],
                    linked_pr_number=linked_prs[0] if linked_prs else None,
                ))
        
        return issues
    
    def merged_prs_with_tests(
        self,
        repo: str,
        days_back: int = 365,
        min_files_changed: int = 2,
    ) -> List[GitHubPullRequest]:
        """
        Mine merged PRs that modified multiple files.
        
        Args:
            repo: "org/repo"
            days_back: Only PRs merged in last N days
            min_files_changed: Minimum files modified
        
        Returns:
            List of GitHubPullRequest candidates
        """
        since_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        
        filters = {
            "is": "merged",
            "merged": f">={since_date}",
        }
        
        prs = []
        for item in self.search_issues(repo, filters=filters, per_page=100):
            # Get full PR details
            pr_data = self._get(f"/repos/{repo}/pulls/{item['number']}")
            
            # Filter by file count
            if pr_data.get("changed_files", 0) < min_files_changed:
                continue
            
            # Get linked issue
            linked_issue = None
            if pr_data.get("body"):
                # Simple heuristic: look for issue references in PR body
                # More sophisticated parsing could extract issue numbers
                pass
            
            prs.append(GitHubPullRequest(
                number=item["number"],
                title=item["title"],
                body=item.get("body", ""),
                state=item["state"],
                created_at=item["created_at"],
                merged_at=pr_data.get("merged_at"),
                merge_commit_sha=pr_data.get("merge_commit_sha"),
                files_changed=pr_data.get("changed_files", 0),
                additions=pr_data.get("additions", 0),
                deletions=pr_data.get("deletions", 0),
                labels=[label["name"] for label in item.get("labels", [])],
                linked_issue_number=linked_issue,
            ))
        
        return prs
