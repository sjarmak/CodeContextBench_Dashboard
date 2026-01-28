"""
Test task regeneration from mining output.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from src.task_mining.regenerate_tasks import (
    load_mining_results,
    update_task_toml,
    update_dockerfile,
)


class TestTaskRegeneration:
    """Test regenerating task definitions with real commits"""
    
    def test_update_task_toml_adds_commits(self):
        """Test adding commit SHAs to task.toml"""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            
            # Create task.toml
            task_toml = task_dir / "task.toml"
            task_toml.write_text("""[task]
id = "sgt-001"
repo = "pytorch"
language = "cpp"
difficulty = "medium"
""")
            
            # Update with commit info
            task_data = {
                "pre_fix_rev": "abc123def456",
                "ground_truth_rev": "def456ghi789",
            }
            
            update_task_toml(task_dir, task_data)
            
            # Verify commits were added
            content = task_toml.read_text()
            assert "pre_fix_rev = \"abc123def456\"" in content
            assert "ground_truth_rev = \"def456ghi789\"" in content
    
    def test_update_dockerfile_checkout_commit(self):
        """Test updating Dockerfile to checkout pre_fix_rev"""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            env_dir = task_dir / "environment"
            env_dir.mkdir()
            
            # Create Dockerfile
            dockerfile = env_dir / "Dockerfile"
            dockerfile.write_text("""FROM gcc:13
WORKDIR /workspace
RUN git clone https://github.com/pytorch/pytorch.git /workspace && \\
    cd /workspace && \\
    git checkout main && \\
    git submodule update --init --recursive
""")
            
            # Update with commit info
            task_data = {
                "id": "sgt-001",
                "pre_fix_rev": "abc123def456",
            }
            repo_config = {
                "repo_url": "https://github.com/pytorch/pytorch",
            }
            
            update_dockerfile(task_dir, task_data, repo_config)
            
            # Verify checkout was updated
            content = dockerfile.read_text()
            assert "git checkout abc123def456" in content
            assert "git checkout main" not in content
    
    def test_load_mining_results(self):
        """Test loading mining results JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mining_file = Path(tmpdir) / "mining.json"
            
            mining_data = {
                "repositories": [
                    {
                        "repo_key": "pytorch",
                        "candidates": [
                            {
                                "id": "sgt-001",
                                "pre_fix_rev": "abc123",
                                "ground_truth_rev": "def456",
                            }
                        ]
                    }
                ]
            }
            
            mining_file.write_text(json.dumps(mining_data))
            
            results = load_mining_results(mining_file)
            
            assert results["repositories"][0]["repo_key"] == "pytorch"
            assert results["repositories"][0]["candidates"][0]["id"] == "sgt-001"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
