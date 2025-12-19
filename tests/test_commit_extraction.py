"""
Test commit extraction from GitHub PR data.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.task_mining.github_client import GitHubClient, GitHubPullRequest
from src.task_mining.task_generator import TaskGenerator
from src.task_mining.repo_registry import RepositoryConfig, Language


class TestCommitExtraction:
    """Test commit SHA extraction from GitHub PRs"""
    
    def test_get_pr_commit_shas_with_parent(self):
        """Test extracting parent and first commit SHAs"""
        # Mock GitHub client
        client = GitHubClient.__new__(GitHubClient)
        client.session = Mock()
        
        # Mock PR commits response
        mock_commits = [
            {
                "sha": "first_commit_sha",
                "parents": [{"sha": "parent_commit_sha"}]
            },
            {
                "sha": "second_commit_sha",
                "parents": [{"sha": "first_commit_sha"}]
            }
        ]
        
        with patch.object(client, "get_pr_commits", return_value=mock_commits):
            parent, first = client.get_pr_commit_shas("org/repo", 123)
        
        assert parent == "parent_commit_sha"
        assert first == "first_commit_sha"
    
    def test_get_pr_commit_shas_no_parent(self):
        """Test when no parent is available (e.g., root commit)"""
        client = GitHubClient.__new__(GitHubClient)
        client.session = Mock()
        
        mock_commits = [
            {
                "sha": "first_commit_sha",
                "parents": []  # No parents (root commit)
            }
        ]
        
        with patch.object(client, "get_pr_commits", return_value=mock_commits):
            parent, first = client.get_pr_commit_shas("org/repo", 123)
        
        assert parent is None
        assert first == "first_commit_sha"
    
    def test_get_pr_commit_shas_empty(self):
        """Test when PR has no commits"""
        client = GitHubClient.__new__(GitHubClient)
        client.session = Mock()
        
        with patch.object(client, "get_pr_commits", return_value=[]):
            parent, first = client.get_pr_commit_shas("org/repo", 123)
        
        assert parent is None
        assert first is None


class TestTaskGenerationWithRealCommits:
    """Test that task generation accepts real commit values"""
    
    def test_task_generation_with_commit_shas(self):
        """Test TaskSpecification is created with real commit SHAs"""
        client = Mock()
        gen = TaskGenerator(client)
        
        pr = GitHubPullRequest(
            number=123,
            title="Fix memory leak",
            body="Fixes #456",
            state="merged",
            created_at="2025-01-01T00:00:00Z",
            merged_at="2025-01-02T00:00:00Z",
            merge_commit_sha="abc123def456",
            files_changed=3,
            additions=50,
            deletions=10,
            labels=["bug", "memory"],
            linked_issue_number=456
        )
        
        repo_config = RepositoryConfig(
            repo_key="pytorch",
            repo_url="https://github.com/pytorch/pytorch",
            gh_org="pytorch",
            gh_repo="pytorch",
            language=Language.CPP,
            description="PyTorch",
            sourcegraph_repo="github.com/pytorch/pytorch",
            sentinel_query="torch::nn"
        )
        
        # Generate task with real commit SHAs
        task = gen.from_pr(
            pr,
            repo_config,
            task_id="sgt-001",
            pre_fix_rev="def456ghi789",  # Parent commit
            ground_truth_rev="abc123def456"  # Merge commit
        )
        
        assert task is not None
        assert task.pre_fix_rev == "def456ghi789"
        assert task.ground_truth_rev == "abc123def456"
        assert task.id == "sgt-001"
        assert task.files_to_modify is None  # Optional field


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
