"""
CodeContextBench Task Specification Schema

Canonical format for all benchmark tasks. Tasks must satisfy:
- Multi-file changes required for solution
- Ground-truth fix available (merged PR/closed issue)
- Deterministic verification (tests or reproducible checks)
- Codebase understanding necessary (not pattern-matchable)
"""

from typing import Literal, Optional, List
from enum import Enum
from dataclasses import dataclass, asdict
import json
import jsonschema


class TaskCategory(str, Enum):
    """Valid task categories"""
    CROSS_MODULE_BUG_FIX = "cross_module_bug_fix"
    FEATURE_IMPLEMENTATION = "feature_implementation"
    DEPENDENCY_UPGRADE = "dependency_upgrade"
    REFACTORING = "refactoring"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"


class Language(str, Enum):
    """Supported languages"""
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    GO = "go"
    RUST = "rust"
    CPP = "cpp"
    C = "c"
    JAVA = "java"
    CSHARP = "csharp"


class Difficulty(str, Enum):
    """Task difficulty levels"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class TaskSpecification:
    """
    Complete specification for a CodeContextBench task.
    
    All fields required unless marked Optional.
    """
    
    # Identifiers
    id: str  # e.g., "sgt-001", globally unique
    repo_key: str  # e.g., "firefox", "kubernetes", "pytorch"
    
    # Metadata
    title: str  # Task title (from GitHub issue)
    description: str  # Full task description / issue text
    category: TaskCategory  # Type of task
    language: Language  # Primary language of codebase
    difficulty: Difficulty  # Estimated difficulty
    
    # Task definition
    instructions: str  # Instructions for agent (combines issue + repro steps)
    success_criteria: str  # How to verify success (natural language)
    
    # Verification
    test_command: str  # Command to run tests (e.g., "pytest src/test.py")
    verification_type: Literal["test", "script", "diff", "manual"]  # How to verify
    
    # Repository context
    pre_fix_rev: str  # Git revision before fix (agent starts here)
    ground_truth_rev: str  # Git revision with fix (reference for correctness)
    source_issue_url: str  # Original issue/PR (for human reference)
    
    # Optional context
    reproduction_steps: Optional[str] = None  # Command to reproduce issue
    expected_behavior: Optional[str] = None  # What should happen
    failure_symptom: Optional[str] = None  # What happens without fix
    files_to_modify: Optional[List[str]] = None  # Files changed in ground-truth fix
    estimated_tokens: Optional[int] = None  # Rough context budget estimate
    time_limit_seconds: Optional[int] = None  # Suggested time budget
    tags: Optional[List[str]] = None  # e.g., ["security", "performance", "api-breaking"]
    
    def to_dict(self) -> dict:
        """Convert to dict, excluding None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    @classmethod
    def from_dict(cls, data: dict) -> "TaskSpecification":
        """Create from dict with validation"""
        # Convert enum strings to enums
        if isinstance(data.get("category"), str):
            data["category"] = TaskCategory(data["category"])
        if isinstance(data.get("language"), str):
            data["language"] = Language(data["language"])
        if isinstance(data.get("difficulty"), str):
            data["difficulty"] = Difficulty(data["difficulty"])
        
        return cls(**data)


# JSON Schema for validation
TASK_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CodeContextBench Task Specification",
    "type": "object",
    "required": [
        "id",
        "repo_key",
        "title",
        "description",
        "category",
        "language",
        "difficulty",
        "instructions",
        "success_criteria",
        "test_command",
        "verification_type",
        "pre_fix_rev",
        "ground_truth_rev",
        "source_issue_url",
    ],
    "properties": {
        "id": {
            "type": "string",
            "pattern": "^sgt-[0-9]{3,}$",
            "description": "Task ID (e.g., sgt-001)"
        },
        "repo_key": {
            "type": "string",
            "enum": ["firefox", "kubernetes", "pytorch", "vscode", "ffmpeg", "tensorrt", "servo"],
            "description": "Repository identifier"
        },
        "title": {
            "type": "string",
            "minLength": 10,
            "maxLength": 200
        },
        "description": {
            "type": "string",
            "minLength": 50,
            "description": "Full issue description (from GitHub)"
        },
        "category": {
            "type": "string",
            "enum": [
                "cross_module_bug_fix",
                "feature_implementation",
                "dependency_upgrade",
                "refactoring",
                "performance_optimization"
            ]
        },
        "language": {
            "type": "string",
            "enum": ["python", "typescript", "javascript", "go", "rust", "cpp", "c", "java", "csharp"]
        },
        "difficulty": {
            "type": "string",
            "enum": ["easy", "medium", "hard"]
        },
        "instructions": {
            "type": "string",
            "minLength": 30,
            "description": "Step-by-step instructions for agent"
        },
        "success_criteria": {
            "type": "string",
            "minLength": 20,
            "description": "How to determine if task is solved"
        },
        "test_command": {
            "type": "string",
            "minLength": 5,
            "description": "Command to run verification (e.g., pytest, go test)"
        },
        "verification_type": {
            "type": "string",
            "enum": ["test", "script", "diff", "manual"]
        },
        "pre_fix_rev": {
            "type": "string",
            "minLength": 6,
            "description": "Git SHA or ref before fix (agent starts here)"
        },
        "ground_truth_rev": {
            "type": "string",
            "minLength": 6,
            "description": "Git SHA or ref with fix (reference solution)"
        },
        "source_issue_url": {
            "type": "string",
            "format": "uri",
            "description": "Link to original issue/PR on GitHub"
        },
        "reproduction_steps": {
            "type": ["string", "null"],
            "description": "Optional: how to reproduce the issue"
        },
        "expected_behavior": {
            "type": ["string", "null"]
        },
        "failure_symptom": {
            "type": ["string", "null"]
        },
        "files_to_modify": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "description": "List of files that should be modified in solution"
        },
        "estimated_tokens": {
            "type": ["integer", "null"],
            "minimum": 100,
            "description": "Rough context size estimate"
        },
        "time_limit_seconds": {
            "type": ["integer", "null"],
            "minimum": 60,
            "description": "Suggested time budget for agent"
        },
        "tags": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "description": "Metadata tags (e.g., security, performance)"
        }
    },
    "additionalProperties": False
}


class TaskValidator:
    """Validate task specifications against schema"""
    
    @staticmethod
    def validate(data: dict) -> tuple[bool, Optional[str]]:
        """
        Validate task data against schema.
        
        Returns:
            (is_valid, error_message)
        """
        try:
            jsonschema.validate(instance=data, schema=TASK_SCHEMA)
            return True, None
        except jsonschema.ValidationError as e:
            return False, str(e)
    
    @staticmethod
    def validate_file(filepath: str) -> tuple[bool, Optional[str]]:
        """Load and validate a task file"""
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            return TaskValidator.validate(data)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"
        except FileNotFoundError:
            return False, f"File not found: {filepath}"
    
    @staticmethod
    def validate_directory(dirpath: str) -> dict:
        """Validate all .json files in directory, return report"""
        import os
        from pathlib import Path
        
        results = {
            "total": 0,
            "valid": 0,
            "invalid": 0,
            "errors": []
        }
        
        for filepath in Path(dirpath).glob("*.json"):
            results["total"] += 1
            is_valid, error = TaskValidator.validate_file(str(filepath))
            
            if is_valid:
                results["valid"] += 1
            else:
                results["invalid"] += 1
                results["errors"].append({
                    "file": filepath.name,
                    "error": error
                })
        
        return results


if __name__ == "__main__":
    # Example task
    example_task = {
        "id": "sgt-001",
        "repo_key": "firefox",
        "title": "Fix memory leak in JavaScript GC",
        "description": "The garbage collector in SpiderMonkey leaks memory when handling cyclic references in WeakMaps. This causes long-running processes to OOM.",
        "category": "cross_module_bug_fix",
        "language": "cpp",
        "difficulty": "hard",
        "instructions": "1. Review the failing test in js/src/gc/test_weakmap.cpp\n2. Understand the issue in js/src/gc/GC.cpp\n3. Fix the cyclic reference handling\n4. Verify with test suite",
        "success_criteria": "All GC tests pass, memory usage stable on long-running benchmark",
        "test_command": "cd js && ./configure && make && ./mach test js/src/gc/",
        "verification_type": "test",
        "pre_fix_rev": "abc123def456",
        "ground_truth_rev": "def456ghi789",
        "source_issue_url": "https://bugzilla.mozilla.org/show_bug.cgi?id=12345",
        "reproduction_steps": "node test_gc_leak.js (waits 30s, checks memory)",
        "failure_symptom": "Memory grows unbounded, OOM after ~5 minutes",
        "files_to_modify": ["js/src/gc/GC.cpp", "js/src/gc/test_weakmap.cpp"],
        "estimated_tokens": 8000,
        "time_limit_seconds": 300,
        "tags": ["memory-leak", "gc", "stability"]
    }
    
    # Validate
    is_valid, error = TaskValidator.validate(example_task)
    print(f"Valid: {is_valid}")
    if error:
        print(f"Error: {error}")
    else:
        print("\nExample task specification:")
        print(json.dumps(example_task, indent=2))
