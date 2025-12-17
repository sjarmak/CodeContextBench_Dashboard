"""
Repository registry for CodeContextBench mining.

Defines target repositories, language classifications, and sentinel queries
for validating Sourcegraph integration.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Literal
from enum import Enum


class Language(str, Enum):
    """Supported languages in CodeContextBench"""
    C = "c"
    CPP = "cpp"
    GO = "go"
    PYTHON = "python"
    RUST = "rust"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"


@dataclass
class RepositoryConfig:
    """Configuration for a target repository"""
    
    repo_key: str  # e.g., "firefox", "kubernetes"
    repo_url: str  # e.g., "https://github.com/mozilla/firefox"
    gh_org: str    # GitHub org
    gh_repo: str   # GitHub repo name
    language: Language
    description: str
    
    # Sourcegraph validation
    sourcegraph_repo: str  # e.g., "github.com/mozilla/firefox"
    sentinel_query: str    # Query to validate Sourcegraph indexing
    
    # Mining parameters
    min_stars: int = 1000  # Minimum GitHub stars (quality gate)
    max_results: int = 500  # Max candidates per repo
    
    def github_url(self) -> str:
        """Full GitHub URL"""
        return f"https://github.com/{self.gh_org}/{self.gh_repo}"
    
    def github_graphql_query_repo(self) -> str:
        """GraphQL fragment for repository"""
        return f"{self.gh_org}/{self.gh_repo}"


# Target repositories for Phase 0.5
REPO_REGISTRY: Dict[str, RepositoryConfig] = {
    "firefox": RepositoryConfig(
        repo_key="firefox",
        repo_url="https://github.com/mozilla/firefox",
        gh_org="mozilla",
        gh_repo="mozilla-central",  # Note: actual repo is different
        language=Language.CPP,
        description="Firefox browser engine (SpiderMonkey, Gecko)",
        sourcegraph_repo="github.com/mozilla/mozilla-central",
        sentinel_query="const GC",
        min_stars=5000,
    ),
    "kubernetes": RepositoryConfig(
        repo_key="kubernetes",
        repo_url="https://github.com/kubernetes/kubernetes",
        gh_org="kubernetes",
        gh_repo="kubernetes",
        language=Language.GO,
        description="Kubernetes container orchestration",
        sourcegraph_repo="github.com/kubernetes/kubernetes",
        sentinel_query="func NewKubeClient",
        min_stars=5000,
    ),
    "pytorch": RepositoryConfig(
        repo_key="pytorch",
        repo_url="https://github.com/pytorch/pytorch",
        gh_org="pytorch",
        gh_repo="pytorch",
        language=Language.CPP,
        description="PyTorch ML framework (C++/Python)",
        sourcegraph_repo="github.com/pytorch/pytorch",
        sentinel_query="torch::nn::Module",
        min_stars=5000,
    ),
    "vscode": RepositoryConfig(
        repo_key="vscode",
        repo_url="https://github.com/microsoft/vscode",
        gh_org="microsoft",
        gh_repo="vscode",
        language=Language.TYPESCRIPT,
        description="Visual Studio Code editor",
        sourcegraph_repo="github.com/microsoft/vscode",
        sentinel_query="export class Editor",
        min_stars=5000,
    ),
    "ffmpeg": RepositoryConfig(
        repo_key="ffmpeg",
        repo_url="https://github.com/ffmpeg/ffmpeg",
        gh_org="ffmpeg",
        gh_repo="ffmpeg",
        language=Language.C,
        description="FFmpeg multimedia library",
        sourcegraph_repo="github.com/ffmpeg/ffmpeg",
        sentinel_query="avcodec_decode_video2",
        min_stars=2000,
    ),
    "tensorrt_llm": RepositoryConfig(
        repo_key="tensorrt_llm",
        repo_url="https://github.com/NVIDIA/TensorRT-LLM",
        gh_org="NVIDIA",
        gh_repo="TensorRT-LLM",
        language=Language.CPP,
        description="NVIDIA TensorRT-LLM inference engine",
        sourcegraph_repo="github.com/NVIDIA/TensorRT-LLM",
        sentinel_query="class LLMModel",
        min_stars=1000,
    ),
    "servo": RepositoryConfig(
        repo_key="servo",
        repo_url="https://github.com/servo/servo",
        gh_org="servo",
        gh_repo="servo",
        language=Language.RUST,
        description="Servo browser engine (Rust)",
        sourcegraph_repo="github.com/servo/servo",
        sentinel_query="impl Document",
        min_stars=1000,
    ),
}


class RepositoryRegistry:
    """Registry of target repositories with validation helpers"""
    
    def __init__(self, registry: Optional[Dict[str, RepositoryConfig]] = None):
        self.registry = registry or REPO_REGISTRY
    
    def get_repo(self, repo_key: str) -> Optional[RepositoryConfig]:
        """Get repository by key"""
        return self.registry.get(repo_key)
    
    def list_repos(self) -> List[RepositoryConfig]:
        """List all repositories"""
        return list(self.registry.values())
    
    def list_repo_keys(self) -> List[str]:
        """List all repository keys"""
        return list(self.registry.keys())
    
    def repos_by_language(self, language: Language) -> List[RepositoryConfig]:
        """Filter repos by language"""
        return [r for r in self.registry.values() if r.language == language]
