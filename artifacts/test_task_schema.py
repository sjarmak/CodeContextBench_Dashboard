"""Tests for task schema and validation."""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.benchmark.task_schema import (
    TaskSpecification,
    TaskCategory,
    Language,
    Difficulty,
    TaskValidator,
    TASK_SCHEMA,
)


class TestTaskSpecification:
    """Tests for TaskSpecification dataclass."""
    
    @pytest.fixture
    def valid_task_dict(self):
        """A valid task specification dictionary."""
        return {
            "id": "sgt-001",
            "repo_key": "firefox",
            "title": "Fix memory leak in JavaScript GC",
            "description": "The garbage collector in SpiderMonkey leaks memory when handling cyclic references in WeakMaps. This causes long-running processes to OOM.",
            "category": "cross_module_bug_fix",
            "language": "cpp",
            "difficulty": "hard",
            "instructions": "1. Review the failing test\n2. Fix the cyclic reference handling\n3. Verify with test suite",
            "success_criteria": "All GC tests pass, memory usage stable",
            "test_command": "cd js && ./mach test js/src/gc/",
            "verification_type": "test",
            "pre_fix_rev": "abc123def456",
            "ground_truth_rev": "def456ghi789",
            "source_issue_url": "https://bugzilla.mozilla.org/show_bug.cgi?id=12345",
        }
    
    def test_create_from_dict(self, valid_task_dict):
        """Test creating TaskSpecification from dict."""
        task = TaskSpecification.from_dict(valid_task_dict)
        
        assert task.id == "sgt-001"
        assert task.repo_key == "firefox"
        assert task.category == TaskCategory.CROSS_MODULE_BUG_FIX
        assert task.language == Language.CPP
        assert task.difficulty == Difficulty.HARD
    
    def test_to_dict(self, valid_task_dict):
        """Test converting TaskSpecification to dict."""
        task = TaskSpecification.from_dict(valid_task_dict)
        result = task.to_dict()
        
        assert result["id"] == "sgt-001"
        assert result["category"] == "cross_module_bug_fix"
        assert result["language"] == "cpp"
        assert result["difficulty"] == "hard"
    
    def test_to_json(self, valid_task_dict):
        """Test converting TaskSpecification to JSON."""
        task = TaskSpecification.from_dict(valid_task_dict)
        json_str = task.to_json()
        
        parsed = json.loads(json_str)
        assert parsed["id"] == "sgt-001"
        assert parsed["category"] == "cross_module_bug_fix"
    
    def test_optional_fields(self, valid_task_dict):
        """Test that optional fields are handled correctly."""
        task = TaskSpecification.from_dict(valid_task_dict)
        
        # Optional fields should be None
        assert task.reproduction_steps is None
        assert task.expected_behavior is None
        assert task.tags is None
    
    def test_with_optional_fields(self, valid_task_dict):
        """Test with optional fields populated."""
        valid_task_dict.update({
            "reproduction_steps": "node test.js",
            "failure_symptom": "OOM after 5 minutes",
            "tags": ["memory-leak", "gc"]
        })
        
        task = TaskSpecification.from_dict(valid_task_dict)
        
        assert task.reproduction_steps == "node test.js"
        assert task.failure_symptom == "OOM after 5 minutes"
        assert task.tags == ["memory-leak", "gc"]


class TestTaskCategory:
    """Tests for TaskCategory enum."""
    
    def test_all_categories_exist(self):
        """Test that all expected categories are defined."""
        assert TaskCategory.CROSS_MODULE_BUG_FIX.value == "cross_module_bug_fix"
        assert TaskCategory.FEATURE_IMPLEMENTATION.value == "feature_implementation"
        assert TaskCategory.DEPENDENCY_UPGRADE.value == "dependency_upgrade"
        assert TaskCategory.REFACTORING.value == "refactoring"
        assert TaskCategory.PERFORMANCE_OPTIMIZATION.value == "performance_optimization"
    
    def test_create_from_string(self):
        """Test creating enum from string."""
        cat = TaskCategory("cross_module_bug_fix")
        assert cat == TaskCategory.CROSS_MODULE_BUG_FIX


class TestLanguage:
    """Tests for Language enum."""
    
    def test_supported_languages(self):
        """Test that expected languages are supported."""
        assert Language.PYTHON.value == "python"
        assert Language.TYPESCRIPT.value == "typescript"
        assert Language.GO.value == "go"
        assert Language.RUST.value == "rust"
        assert Language.CPP.value == "cpp"


class TestDifficulty:
    """Tests for Difficulty enum."""
    
    def test_difficulty_levels(self):
        """Test difficulty levels."""
        assert Difficulty.EASY.value == "easy"
        assert Difficulty.MEDIUM.value == "medium"
        assert Difficulty.HARD.value == "hard"


class TestTaskValidator:
    """Tests for TaskValidator."""
    
    @pytest.fixture
    def valid_task_dict(self):
        """A valid task specification."""
        return {
            "id": "sgt-001",
            "repo_key": "firefox",
            "title": "Fix memory leak in JavaScript GC",
            "description": "The garbage collector in SpiderMonkey leaks memory when handling cyclic references in WeakMaps. This causes long-running processes to OOM.",
            "category": "cross_module_bug_fix",
            "language": "cpp",
            "difficulty": "hard",
            "instructions": "1. Review the failing test\n2. Fix the cyclic reference\n3. Verify",
            "success_criteria": "All GC tests pass, memory stable",
            "test_command": "cd js && ./mach test",
            "verification_type": "test",
            "pre_fix_rev": "abc123def456",
            "ground_truth_rev": "def456ghi789",
            "source_issue_url": "https://bugzilla.mozilla.org/show_bug.cgi?id=12345",
        }
    
    def test_valid_task(self, valid_task_dict):
        """Test validation of a valid task."""
        is_valid, error = TaskValidator.validate(valid_task_dict)
        
        assert is_valid is True
        assert error is None
    
    def test_missing_required_field(self, valid_task_dict):
        """Test validation fails with missing required field."""
        del valid_task_dict["id"]
        
        is_valid, error = TaskValidator.validate(valid_task_dict)
        
        assert is_valid is False
        assert error is not None
        assert "id" in error
    
    def test_invalid_id_format(self, valid_task_dict):
        """Test validation fails with invalid ID format."""
        valid_task_dict["id"] = "invalid-id"
        
        is_valid, error = TaskValidator.validate(valid_task_dict)
        
        assert is_valid is False
        assert error is not None
    
    def test_invalid_repo_key(self, valid_task_dict):
        """Test validation fails with unsupported repo_key."""
        valid_task_dict["repo_key"] = "unsupported_repo"
        
        is_valid, error = TaskValidator.validate(valid_task_dict)
        
        assert is_valid is False
        assert error is not None
    
    def test_invalid_category(self, valid_task_dict):
        """Test validation fails with invalid category."""
        valid_task_dict["category"] = "invalid_category"
        
        is_valid, error = TaskValidator.validate(valid_task_dict)
        
        assert is_valid is False
    
    def test_invalid_language(self, valid_task_dict):
        """Test validation fails with invalid language."""
        valid_task_dict["language"] = "cobol"
        
        is_valid, error = TaskValidator.validate(valid_task_dict)
        
        assert is_valid is False
    
    def test_invalid_difficulty(self, valid_task_dict):
        """Test validation fails with invalid difficulty."""
        valid_task_dict["difficulty"] = "impossible"
        
        is_valid, error = TaskValidator.validate(valid_task_dict)
        
        assert is_valid is False
    
    def test_invalid_verification_type(self, valid_task_dict):
        """Test validation fails with invalid verification_type."""
        valid_task_dict["verification_type"] = "magic"
        
        is_valid, error = TaskValidator.validate(valid_task_dict)
        
        assert is_valid is False
    
    def test_short_title(self, valid_task_dict):
        """Test validation fails with title too short."""
        valid_task_dict["title"] = "Short"
        
        is_valid, error = TaskValidator.validate(valid_task_dict)
        
        assert is_valid is False
    
    def test_short_description(self, valid_task_dict):
        """Test validation fails with description too short."""
        valid_task_dict["description"] = "Too short"
        
        is_valid, error = TaskValidator.validate(valid_task_dict)
        
        assert is_valid is False
    
    def test_optional_fields_allowed(self, valid_task_dict):
        """Test that optional fields are allowed."""
        valid_task_dict["reproduction_steps"] = "npm test"
        valid_task_dict["tags"] = ["bug", "performance"]
        
        is_valid, error = TaskValidator.validate(valid_task_dict)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_file(self, valid_task_dict):
        """Test validating a task from file."""
        with TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "task.json"
            filepath.write_text(json.dumps(valid_task_dict))
            
            is_valid, error = TaskValidator.validate_file(str(filepath))
            
            assert is_valid is True
            assert error is None
    
    def test_validate_file_not_found(self):
        """Test validation fails for missing file."""
        is_valid, error = TaskValidator.validate_file("/nonexistent/path.json")
        
        assert is_valid is False
        assert "not found" in error.lower()
    
    def test_validate_file_invalid_json(self):
        """Test validation fails for invalid JSON."""
        with TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "task.json"
            filepath.write_text("{ invalid json")
            
            is_valid, error = TaskValidator.validate_file(str(filepath))
            
            assert is_valid is False
            assert "JSON" in error
    
    def test_validate_directory(self, valid_task_dict):
        """Test validating all tasks in a directory."""
        with TemporaryDirectory() as tmpdir:
            # Write valid task
            valid_file = Path(tmpdir) / "valid.json"
            valid_file.write_text(json.dumps(valid_task_dict))
            
            # Write invalid task
            invalid_dict = valid_task_dict.copy()
            del invalid_dict["id"]
            invalid_file = Path(tmpdir) / "invalid.json"
            invalid_file.write_text(json.dumps(invalid_dict))
            
            results = TaskValidator.validate_directory(tmpdir)
            
            assert results["total"] == 2
            assert results["valid"] == 1
            assert results["invalid"] == 1
            assert len(results["errors"]) == 1
