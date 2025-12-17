"""Task schema and parsing for CodeContextBench.

Handles task manifest format (TOML) from sg_benchmark/sourcegraph-benchmarks:
- task metadata (title, description, repository)
- environment setup (repo path, dependencies)
- success criteria (test file, expected output)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any

import toml


@dataclass
class TaskEnvironment:
    """Environment configuration for a task."""
    
    repo_path: str
    repo_commit: str
    setup_commands: Optional[List[str]] = None
    build_commands: Optional[List[str]] = None
    
    def to_dict(self) -> dict:
        return {
            "repo_path": self.repo_path,
            "repo_commit": self.repo_commit,
            "setup_commands": self.setup_commands or [],
            "build_commands": self.build_commands or [],
        }


@dataclass
class SuccessCriteria:
    """Definition of task success."""
    
    test_file: Optional[str] = None
    test_command: Optional[str] = None
    expected_files_modified: Optional[List[str]] = None
    expected_files_created: Optional[List[str]] = None
    
    def to_dict(self) -> dict:
        return {
            "test_file": self.test_file,
            "test_command": self.test_command,
            "expected_files_modified": self.expected_files_modified,
            "expected_files_created": self.expected_files_created,
        }


@dataclass
class Task:
    """A CodeContextBench task definition."""
    
    id: str
    title: str
    description: str
    category: str  # "bug_fix", "feature", "refactor", "dependency_upgrade"
    environment: TaskEnvironment
    instruction: str
    success_criteria: SuccessCriteria
    difficulty: Optional[str] = "medium"  # easy, medium, hard
    estimated_time_minutes: Optional[int] = None
    tags: Optional[List[str]] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "environment": self.environment.to_dict(),
            "instruction": self.instruction,
            "success_criteria": self.success_criteria.to_dict(),
            "difficulty": self.difficulty,
            "estimated_time_minutes": self.estimated_time_minutes,
            "tags": self.tags or [],
        }


def load_task_from_toml(toml_path: Path) -> Task:
    """Load a task from a TOML file.
    
    Args:
        toml_path: Path to task.toml file
        
    Returns:
        Parsed Task object
        
    Raises:
        FileNotFoundError: If TOML file not found
        ValueError: If TOML structure is invalid
    """
    if not toml_path.exists():
        raise FileNotFoundError(f"Task TOML not found: {toml_path}")
    
    data = toml.load(toml_path)
    
    # Extract sections
    task_meta = data.get("task", {})
    env_meta = data.get("environment", {})
    success_meta = data.get("success_criteria", {})
    
    # Build objects
    environment = TaskEnvironment(
        repo_path=env_meta.get("repo_path", ""),
        repo_commit=env_meta.get("repo_commit", ""),
        setup_commands=env_meta.get("setup_commands"),
        build_commands=env_meta.get("build_commands"),
    )
    
    success_criteria = SuccessCriteria(
        test_file=success_meta.get("test_file"),
        test_command=success_meta.get("test_command"),
        expected_files_modified=success_meta.get("expected_files_modified"),
        expected_files_created=success_meta.get("expected_files_created"),
    )
    
    task = Task(
        id=task_meta.get("id", "unknown"),
        title=task_meta.get("title", ""),
        description=task_meta.get("description", ""),
        category=task_meta.get("category", "bug_fix"),
        environment=environment,
        instruction=task_meta.get("instruction", ""),
        success_criteria=success_criteria,
        difficulty=task_meta.get("difficulty", "medium"),
        estimated_time_minutes=task_meta.get("estimated_time_minutes"),
        tags=task_meta.get("tags", []),
    )
    
    return task
