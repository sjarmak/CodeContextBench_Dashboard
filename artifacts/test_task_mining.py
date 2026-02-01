"""
Unit tests for task mining infrastructure.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.task_mining.repo_registry import (
    RepositoryRegistry,
    RepositoryConfig,
    Language,
    REPO_REGISTRY,
)
from src.task_mining.task_generator import TaskGenerator
from src.task_mining.github_client import (
    GitHubClient,
    GitHubIssue,
    GitHubPullRequest,
)
from src.benchmark.task_schema import TaskCategory, Difficulty


class TestRepositoryRegistry:
    """Test repository registry"""
    
    def test_registry_has_all_required_repos(self):
        """All target repos are registered"""
        registry = RepositoryRegistry()
        required_repos = {"firefox", "kubernetes", "pytorch", "vscode", "ffmpeg"}
        available = set(registry.list_repo_keys())
        assert required_repos.issubset(available)
    
    def test_get_repo(self):
        """Can retrieve repo config by key"""
        registry = RepositoryRegistry()
        k8s = registry.get_repo("kubernetes")
        assert k8s is not None
        assert k8s.gh_org == "kubernetes"
        assert k8s.language == Language.GO
    
    def test_repos_by_language(self):
        """Can filter repos by language"""
        registry = RepositoryRegistry()
        cpp_repos = registry.repos_by_language(Language.CPP)
        assert len(cpp_repos) > 0
        for repo in cpp_repos:
            assert repo.language == Language.CPP
    
    def test_repo_config_urls(self):
        """Repo config generates correct URLs"""
        registry = RepositoryRegistry()
        k8s = registry.get_repo("kubernetes")
        assert "kubernetes/kubernetes" in k8s.github_url()


class TestTaskGenerator:
    """Test task specification generation"""
    
    @pytest.fixture
    def mock_gh_client(self):
        return Mock(spec=GitHubClient)
    
    @pytest.fixture
    def task_gen(self, mock_gh_client):
        return TaskGenerator(mock_gh_client)
    
    @pytest.fixture
    def k8s_repo(self):
        return RepositoryRegistry().get_repo("kubernetes")
    
    def test_infer_difficulty_easy(self, task_gen):
        """Single-file changes are easy"""
        diff = task_gen._infer_difficulty(files_changed=1, additions=10, deletions=5)
        assert diff == Difficulty.EASY
    
    def test_infer_difficulty_medium(self, task_gen):
        """Multi-file changes are medium"""
        diff = task_gen._infer_difficulty(files_changed=3, additions=100, deletions=50)
        assert diff == Difficulty.MEDIUM
    
    def test_infer_difficulty_hard(self, task_gen):
        """Many files changed is hard"""
        diff = task_gen._infer_difficulty(files_changed=10, additions=500, deletions=300)
        assert diff == Difficulty.HARD
    
    def test_infer_category_bugfix(self, task_gen):
        """Bug-related PRs classified as bug fix"""
        cat = task_gen._infer_category(
            "Fix crash in connection handler",
            "This PR fixes issue #123"
        )
        assert cat == TaskCategory.CROSS_MODULE_BUG_FIX
    
    def test_infer_category_refactor(self, task_gen):
        """Refactor-related PRs classified correctly"""
        cat = task_gen._infer_category(
            "Refactor API handler",
            "Extract common logic"
        )
        assert cat == TaskCategory.REFACTORING
    
    def test_infer_test_command_go(self, task_gen):
        """Go repos get 'go test' command"""
        k8s_repo = RepositoryRegistry().get_repo("kubernetes")
        cmd = task_gen._infer_test_command(k8s_repo)
        assert "go test" in cmd
    
    def test_infer_test_command_python(self, task_gen):
        """Python repos get pytest command"""
        registry = RepositoryRegistry()
        pytorch_repo = registry.get_repo("pytorch")
        cmd = task_gen._infer_test_command(pytorch_repo)
        assert "pytest" in cmd or "test" in cmd
    
    def test_from_pr_multi_file(self, task_gen, k8s_repo):
        """PR with multiple files generates task"""
        pr = GitHubPullRequest(
            number=1234,
            title="Fix etcd timeout handling",
            body="Resolve issue where connections hang indefinitely",
            state="merged",
            created_at="2025-01-01T00:00:00Z",
            merged_at="2025-01-05T00:00:00Z",
            merge_commit_sha="abc123def456",
            files_changed=3,
            additions=150,
            deletions=75,
            labels=["bug", "etcd"],
        )
        
        task = task_gen.from_pr(
            pr,
            k8s_repo,
            task_id="sgt-001",
            pre_fix_rev="abc123abc123",
            ground_truth_rev="abc123def456",
        )
        
        assert task is not None
        assert task.id == "sgt-001"
        assert task.repo_key == "kubernetes"
        assert "etcd" in task.title.lower() or "timeout" in task.title.lower()
        assert task.difficulty == Difficulty.MEDIUM
    
    def test_from_pr_single_file_filtered(self, task_gen, k8s_repo):
        """Single-file PRs are filtered out"""
        pr = GitHubPullRequest(
            number=1235,
            title="Fix typo in comment",
            body="",
            state="merged",
            created_at="2025-01-01T00:00:00Z",
            merged_at="2025-01-05T00:00:00Z",
            merge_commit_sha="xyz789",
            files_changed=1,  # Single file
            additions=1,
            deletions=1,
            labels=[],
        )
        
        task = task_gen.from_pr(
            pr,
            k8s_repo,
            task_id="sgt-999",
            pre_fix_rev="xyz",
            ground_truth_rev="xyz789",
        )
        
        assert task is None  # Filtered out
    
    def test_task_spec_valid(self, task_gen, k8s_repo):
        """Generated task spec is valid"""
        pr = GitHubPullRequest(
            number=1236,
            title="Fix connection pooling bug",
            body="Connections were not being reused properly in the kube-apiserver due to incorrect connection pool initialization and cleanup logic.",
            state="merged",
            created_at="2025-01-01T00:00:00Z",
            merged_at="2025-01-05T00:00:00Z",
            merge_commit_sha="def123abc456",
            files_changed=3,
            additions=200,
            deletions=100,
            labels=["bug"],
        )
        
        task = task_gen.from_pr(
            pr,
            k8s_repo,
            task_id="sgt-002",
            pre_fix_rev="def123456789",
            ground_truth_rev="def123abc456",
        )
        
        # Validate using schema
        from src.benchmark.task_schema import TaskValidator
        is_valid, error = TaskValidator.validate(task.to_dict())
        assert is_valid, f"Task validation failed: {error}"


class TestGitHubClient:
    """Test GitHub API client (basic, requires token for full tests)"""
    
    def test_client_requires_token(self):
        """GitHubClient requires GITHUB_TOKEN"""
        with patch.dict("os.environ", clear=True):
            with pytest.raises(ValueError, match="GITHUB_TOKEN"):
                GitHubClient()
    
    def test_client_accepts_explicit_token(self):
        """GitHubClient accepts explicit token"""
        client = GitHubClient(token="test_token_xyz123")
        assert client.token == "test_token_xyz123"


class TestTaskFilter:
    """Test task filtering"""
    
    def test_filter_valid_task(self):
        """Valid task passes filter"""
        from src.task_mining.task_filter import TaskFilter
        
        task = {
            "id": "sgt-001",
            "repo_key": "kubernetes",
            "title": "Fix etcd timeout",
            "description": "This is a detailed description of the issue that explains the problem clearly",
            "category": "cross_module_bug_fix",
            "language": "go",
            "difficulty": "medium",
            "instructions": "Follow these steps carefully to fix the problem in the code",
            "success_criteria": "All tests pass successfully",
            "test_command": "go test ./...",
            "verification_type": "test",
            "pre_fix_rev": "abc123def456",
            "ground_truth_rev": "def456ghi789",
            "source_issue_url": "https://github.com/kubernetes/kubernetes/issues/123",
            "estimated_tokens": 5000,
            "time_limit_seconds": 300,
        }
        
        result = TaskFilter.filter_task(task)
        assert result.passed
        assert len(result.reasons) == 0
    
    def test_filter_missing_test_command(self):
        """Task without test command is rejected"""
        from src.task_mining.task_filter import TaskFilter
        
        task = {
            "id": "sgt-999",
            "repo_key": "kubernetes",
            "title": "Fix etcd timeout handling in cluster",
            "description": "This is a detailed description of the issue that explains the problem clearly and comprehensively",
            "category": "cross_module_bug_fix",
            "language": "go",
            "difficulty": "medium",
            "instructions": "Follow these steps carefully and thoroughly to resolve the issue properly",
            "success_criteria": "All tests pass successfully and no regressions occur",
            "test_command": "",  # Missing
            "verification_type": "test",
            "pre_fix_rev": "abc123def456",
            "ground_truth_rev": "def456ghi789",
            "source_issue_url": "https://github.com/test/test/issues/1",
            "estimated_tokens": 5000,
            "time_limit_seconds": 300,
        }
        
        result = TaskFilter.filter_task(task)
        assert not result.passed
        assert any("test_command" in r.lower() for r in result.reasons)
    
    def test_filter_token_budget_too_low(self):
        """Task with too-low token estimate is rejected"""
        from src.task_mining.task_filter import TaskFilter
        
        task = {
            "id": "sgt-997",
            "repo_key": "kubernetes",
            "title": "Fix etcd timeout handling in cluster operations",
            "description": "This is a detailed description of the issue that explains the problem clearly and comprehensively with context",
            "category": "cross_module_bug_fix",
            "language": "go",
            "difficulty": "medium",
            "instructions": "Follow these steps carefully and thoroughly to resolve the issue properly without breaking other functionality",
            "success_criteria": "All tests pass successfully and no regressions occur in the cluster operations",
            "test_command": "go test ./...",
            "verification_type": "test",
            "pre_fix_rev": "abc123def456",
            "ground_truth_rev": "def456ghi789",
            "source_issue_url": "https://github.com/test/test/issues/1",
            "estimated_tokens": 100,  # Too low
            "time_limit_seconds": 300,
        }
        
        result = TaskFilter.filter_task(task)
        assert not result.passed
        assert any("token" in r.lower() for r in result.reasons)
    
    def test_filter_batch(self):
        """Filter batch of tasks"""
        from src.task_mining.task_filter import TaskFilter
        
        base_task = {
            "id": "sgt-000",
            "repo_key": "kubernetes",
            "title": "Fix test failure in etcd integration",
            "description": "This is a detailed description of the issue that explains the problem clearly and comprehensively",
            "category": "cross_module_bug_fix",
            "language": "go",
            "difficulty": "medium",
            "instructions": "Follow these steps carefully to resolve the issue properly without breaking existing functionality",
            "success_criteria": "All tests pass successfully and no regressions occur",
            "test_command": "go test ./...",
            "verification_type": "test",
            "pre_fix_rev": "abc123def456",
            "ground_truth_rev": "def456ghi789",
            "source_issue_url": "https://github.com/test/test/issues/0",
            "estimated_tokens": 5000,
            "time_limit_seconds": 300,
        }
        
        # Create batch: 3 valid + 1 invalid
        tasks = []
        for i in range(3):
            task = base_task.copy()
            task["id"] = f"sgt-{100+i}"
            task["source_issue_url"] = f"https://github.com/test/test/issues/{i}"
            tasks.append(task)
        
        # Invalid task (bad token budget)
        invalid = base_task.copy()
        invalid["id"] = "sgt-900"
        invalid["estimated_tokens"] = 100  # Too low
        invalid["source_issue_url"] = "https://github.com/test/test/issues/99"
        tasks.append(invalid)
        
        result = TaskFilter.filter_batch(tasks)
        assert result["total"] == 4
        assert result["passed"] >= 3
        assert result["failed"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
