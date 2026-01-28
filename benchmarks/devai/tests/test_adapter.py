"""
Tests for DevAI data model and loader.
"""

import json
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from benchmarks.devai.adapter import (
    DEVAI_DOMAINS,
    DevAILoader,
    DevAITask,
    Preference,
    Requirement,
)


class TestRequirement:
    """Tests for the Requirement dataclass."""

    def test_requirement_creation(self) -> None:
        """Test creating a requirement with default values."""
        req = Requirement(
            id="R1",
            description="The application must handle user authentication",
        )
        assert req.id == "R1"
        assert req.description == "The application must handle user authentication"
        assert req.dependencies == []
        assert req.priority == 1
        assert req.category == "functional"

    def test_requirement_with_dependencies(self) -> None:
        """Test creating a requirement with dependencies."""
        req = Requirement(
            id="R1.1",
            description="Support OAuth2 authentication",
            dependencies=["R1"],
            priority=2,
            category="functional",
        )
        assert req.id == "R1.1"
        assert req.dependencies == ["R1"]
        assert req.priority == 2

    def test_requirement_to_dict(self) -> None:
        """Test converting requirement to dictionary."""
        req = Requirement(
            id="R2",
            description="API must return JSON",
            dependencies=["R1"],
            priority=1,
            category="non-functional",
        )
        result = req.to_dict()
        assert result["id"] == "R2"
        assert result["description"] == "API must return JSON"
        assert result["dependencies"] == ["R1"]
        assert result["priority"] == 1
        assert result["category"] == "non-functional"

    def test_requirement_from_dict(self) -> None:
        """Test creating requirement from dictionary."""
        data = {
            "id": "R3",
            "description": "Handle concurrent requests",
            "dependencies": ["R1", "R2"],
            "priority": 2,
            "category": "constraint",
        }
        req = Requirement.from_dict(data)
        assert req.id == "R3"
        assert req.description == "Handle concurrent requests"
        assert req.dependencies == ["R1", "R2"]
        assert req.priority == 2
        assert req.category == "constraint"

    def test_requirement_from_dict_with_defaults(self) -> None:
        """Test requirement from_dict uses defaults for missing fields."""
        data = {"id": "R4", "description": "Basic requirement"}
        req = Requirement.from_dict(data)
        assert req.id == "R4"
        assert req.dependencies == []
        assert req.priority == 1
        assert req.category == "functional"


class TestPreference:
    """Tests for the Preference dataclass."""

    def test_preference_creation(self) -> None:
        """Test creating a preference."""
        pref = Preference(
            name="language",
            value="Python",
            rationale="Team expertise",
        )
        assert pref.name == "language"
        assert pref.value == "Python"
        assert pref.rationale == "Team expertise"

    def test_preference_with_empty_rationale(self) -> None:
        """Test creating a preference without rationale."""
        pref = Preference(name="framework", value="FastAPI")
        assert pref.name == "framework"
        assert pref.value == "FastAPI"
        assert pref.rationale == ""

    def test_preference_to_dict(self) -> None:
        """Test converting preference to dictionary."""
        pref = Preference(
            name="database",
            value="PostgreSQL",
            rationale="ACID compliance",
        )
        result = pref.to_dict()
        assert result["name"] == "database"
        assert result["value"] == "PostgreSQL"
        assert result["rationale"] == "ACID compliance"

    def test_preference_from_dict(self) -> None:
        """Test creating preference from dictionary."""
        data = {
            "name": "testing",
            "value": "pytest",
            "rationale": "Standard library",
        }
        pref = Preference.from_dict(data)
        assert pref.name == "testing"
        assert pref.value == "pytest"
        assert pref.rationale == "Standard library"


class TestDevAITask:
    """Tests for the DevAITask dataclass."""

    def test_task_creation_minimal(self) -> None:
        """Test creating a task with minimal fields."""
        task = DevAITask(
            id="devai-001",
            user_query="Build a REST API for managing todos",
        )
        assert task.id == "devai-001"
        assert task.user_query == "Build a REST API for managing todos"
        assert task.requirements == []
        assert task.preferences == []
        assert task.domain == "general"

    def test_task_creation_full(self) -> None:
        """Test creating a task with all fields."""
        requirements = [
            Requirement(id="R1", description="Create endpoints"),
            Requirement(id="R1.1", description="GET /todos", dependencies=["R1"]),
        ]
        preferences = [
            Preference(name="framework", value="FastAPI"),
        ]

        task = DevAITask(
            id="devai-002",
            user_query="Build a web scraper",
            requirements=requirements,
            preferences=preferences,
            domain="automation",
            description="Extended description here",
            metadata={"difficulty": "medium"},
        )

        assert task.id == "devai-002"
        assert len(task.requirements) == 2
        assert len(task.preferences) == 1
        assert task.domain == "automation"
        assert task.metadata["difficulty"] == "medium"

    def test_task_domain_normalization(self) -> None:
        """Test that domain is normalized to lowercase."""
        task = DevAITask(
            id="devai-003",
            user_query="Test query",
            domain="WEB",
        )
        assert task.domain == "web"

    def test_task_to_dict(self) -> None:
        """Test converting task to dictionary."""
        task = DevAITask(
            id="devai-004",
            user_query="Create CLI tool",
            requirements=[Requirement(id="R1", description="Parse args")],
            preferences=[Preference(name="cli_lib", value="click")],
            domain="cli",
        )
        result = task.to_dict()

        assert result["id"] == "devai-004"
        assert result["user_query"] == "Create CLI tool"
        assert len(result["requirements"]) == 1
        assert result["requirements"][0]["id"] == "R1"
        assert len(result["preferences"]) == 1
        assert result["domain"] == "cli"

    def test_task_from_dict(self) -> None:
        """Test creating task from dictionary."""
        data = {
            "id": "devai-005",
            "user_query": "Build data pipeline",
            "requirements": [
                {"id": "R1", "description": "Read CSV files"},
                {"id": "R2", "description": "Transform data", "dependencies": ["R1"]},
            ],
            "preferences": [
                {"name": "library", "value": "pandas"},
            ],
            "domain": "data",
            "metadata": {"tags": ["etl", "csv"]},
        }
        task = DevAITask.from_dict(data)

        assert task.id == "devai-005"
        assert task.user_query == "Build data pipeline"
        assert len(task.requirements) == 2
        assert task.requirements[1].dependencies == ["R1"]
        assert len(task.preferences) == 1
        assert task.domain == "data"
        assert task.metadata["tags"] == ["etl", "csv"]

    def test_task_get_root_requirements(self) -> None:
        """Test getting root requirements (no dependencies)."""
        task = DevAITask(
            id="devai-006",
            user_query="Test task",
            requirements=[
                Requirement(id="R1", description="Root 1"),
                Requirement(id="R2", description="Root 2"),
                Requirement(id="R1.1", description="Child 1", dependencies=["R1"]),
                Requirement(id="R2.1", description="Child 2", dependencies=["R2"]),
            ],
        )
        roots = task.get_root_requirements()
        assert len(roots) == 2
        root_ids = [r.id for r in roots]
        assert "R1" in root_ids
        assert "R2" in root_ids

    def test_task_get_dependent_requirements(self) -> None:
        """Test getting requirements that depend on a given requirement."""
        task = DevAITask(
            id="devai-007",
            user_query="Test task",
            requirements=[
                Requirement(id="R1", description="Root"),
                Requirement(id="R1.1", description="Child 1", dependencies=["R1"]),
                Requirement(id="R1.2", description="Child 2", dependencies=["R1"]),
                Requirement(id="R2", description="Independent"),
            ],
        )
        dependents = task.get_dependent_requirements("R1")
        assert len(dependents) == 2
        dep_ids = [r.id for r in dependents]
        assert "R1.1" in dep_ids
        assert "R1.2" in dep_ids

    def test_task_get_requirement_count(self) -> None:
        """Test getting requirement count."""
        task = DevAITask(
            id="devai-008",
            user_query="Test task",
            requirements=[
                Requirement(id="R1", description="Req 1"),
                Requirement(id="R2", description="Req 2"),
                Requirement(id="R3", description="Req 3"),
            ],
        )
        assert task.get_requirement_count() == 3


class TestDevAILoader:
    """Tests for the DevAILoader class."""

    @pytest.fixture
    def temp_data_dir(self) -> Generator[Path, None, None]:
        """Create a temporary data directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_loader_initialization_default(self) -> None:
        """Test loader initializes with default data directory."""
        loader = DevAILoader()
        assert loader.data_dir == Path(__file__).parent.parent / "data"
        assert not loader._loaded

    def test_loader_initialization_custom_path(self, temp_data_dir: Path) -> None:
        """Test loader initializes with custom data directory."""
        loader = DevAILoader(data_dir=temp_data_dir)
        assert loader.data_dir == temp_data_dir

    def test_loader_load_empty_directory(self, temp_data_dir: Path) -> None:
        """Test loader returns empty list for empty directory."""
        loader = DevAILoader(data_dir=temp_data_dir)
        tasks = loader.load()
        assert tasks == []
        assert loader._loaded

    def test_loader_load_individual_files(self, temp_data_dir: Path) -> None:
        """Test loading tasks from individual JSON files."""
        # Create test task files
        task1 = {
            "id": "devai-001",
            "user_query": "Build a CLI",
            "domain": "cli",
            "requirements": [{"id": "R1", "description": "Parse args"}],
        }
        task2 = {
            "id": "devai-002",
            "user_query": "Create API",
            "domain": "web",
            "requirements": [{"id": "R1", "description": "Handle requests"}],
        }

        (temp_data_dir / "devai-001.json").write_text(json.dumps(task1))
        (temp_data_dir / "devai-002.json").write_text(json.dumps(task2))

        loader = DevAILoader(data_dir=temp_data_dir)
        tasks = loader.load()

        assert len(tasks) == 2
        task_ids = [t.id for t in tasks]
        assert "devai-001" in task_ids
        assert "devai-002" in task_ids

    def test_loader_load_combined_file(self, temp_data_dir: Path) -> None:
        """Test loading tasks from combined tasks.json file."""
        tasks_data = [
            {"id": "devai-001", "user_query": "Task 1", "domain": "web"},
            {"id": "devai-002", "user_query": "Task 2", "domain": "cli"},
            {"id": "devai-003", "user_query": "Task 3", "domain": "data"},
        ]

        (temp_data_dir / "tasks.json").write_text(json.dumps(tasks_data))

        loader = DevAILoader(data_dir=temp_data_dir)
        tasks = loader.load()

        assert len(tasks) == 3

    def test_loader_load_combined_file_with_tasks_key(self, temp_data_dir: Path) -> None:
        """Test loading from combined file with 'tasks' key."""
        data = {
            "version": "1.0",
            "tasks": [
                {"id": "devai-001", "user_query": "Task 1", "domain": "web"},
                {"id": "devai-002", "user_query": "Task 2", "domain": "cli"},
            ],
        }

        (temp_data_dir / "tasks.json").write_text(json.dumps(data))

        loader = DevAILoader(data_dir=temp_data_dir)
        tasks = loader.load()

        assert len(tasks) == 2

    def test_loader_load_from_manifest(self, temp_data_dir: Path) -> None:
        """Test loading tasks from manifest file."""
        tasks_subdir = temp_data_dir / "tasks"
        tasks_subdir.mkdir()

        # Create task files
        task1 = {"id": "devai-001", "user_query": "Task 1", "domain": "web"}
        task2 = {"id": "devai-002", "user_query": "Task 2", "domain": "api"}
        (tasks_subdir / "devai-001.json").write_text(json.dumps(task1))
        (tasks_subdir / "devai-002.json").write_text(json.dumps(task2))

        # Create manifest
        manifest = {"tasks": ["devai-001.json", "devai-002.json"]}
        (temp_data_dir / "manifest.json").write_text(json.dumps(manifest))

        loader = DevAILoader(data_dir=temp_data_dir)
        tasks = loader.load()

        assert len(tasks) == 2

    def test_loader_all_ids(self, temp_data_dir: Path) -> None:
        """Test getting all task IDs."""
        tasks_data = [
            {"id": "devai-001", "user_query": "Task 1"},
            {"id": "devai-002", "user_query": "Task 2"},
        ]
        (temp_data_dir / "tasks.json").write_text(json.dumps(tasks_data))

        loader = DevAILoader(data_dir=temp_data_dir)
        ids = loader.all_ids()

        assert len(ids) == 2
        assert "devai-001" in ids
        assert "devai-002" in ids

    def test_loader_filter_by_domain(self, temp_data_dir: Path) -> None:
        """Test filtering tasks by domain."""
        tasks_data = [
            {"id": "devai-001", "user_query": "Task 1", "domain": "web"},
            {"id": "devai-002", "user_query": "Task 2", "domain": "web"},
            {"id": "devai-003", "user_query": "Task 3", "domain": "cli"},
            {"id": "devai-004", "user_query": "Task 4", "domain": "data"},
        ]
        (temp_data_dir / "tasks.json").write_text(json.dumps(tasks_data))

        loader = DevAILoader(data_dir=temp_data_dir)
        web_tasks = loader.filter_by_domain("web")

        assert len(web_tasks) == 2
        for task in web_tasks:
            assert task.domain == "web"

    def test_loader_filter_by_domain_case_insensitive(self, temp_data_dir: Path) -> None:
        """Test that domain filtering is case-insensitive."""
        tasks_data = [
            {"id": "devai-001", "user_query": "Task 1", "domain": "WEB"},
            {"id": "devai-002", "user_query": "Task 2", "domain": "web"},
        ]
        (temp_data_dir / "tasks.json").write_text(json.dumps(tasks_data))

        loader = DevAILoader(data_dir=temp_data_dir)
        # Both should be normalized to lowercase
        web_tasks = loader.filter_by_domain("WEB")

        assert len(web_tasks) == 2

    def test_loader_get_task(self, temp_data_dir: Path) -> None:
        """Test getting a specific task by ID."""
        tasks_data = [
            {"id": "devai-001", "user_query": "Task 1", "domain": "web"},
            {"id": "devai-002", "user_query": "Task 2", "domain": "cli"},
        ]
        (temp_data_dir / "tasks.json").write_text(json.dumps(tasks_data))

        loader = DevAILoader(data_dir=temp_data_dir)
        task = loader.get_task("devai-002")

        assert task is not None
        assert task.id == "devai-002"
        assert task.domain == "cli"

    def test_loader_get_task_not_found(self, temp_data_dir: Path) -> None:
        """Test getting a non-existent task returns None."""
        tasks_data = [{"id": "devai-001", "user_query": "Task 1"}]
        (temp_data_dir / "tasks.json").write_text(json.dumps(tasks_data))

        loader = DevAILoader(data_dir=temp_data_dir)
        task = loader.get_task("devai-999")

        assert task is None

    def test_loader_get_domains(self, temp_data_dir: Path) -> None:
        """Test getting list of unique domains."""
        tasks_data = [
            {"id": "devai-001", "user_query": "Task 1", "domain": "web"},
            {"id": "devai-002", "user_query": "Task 2", "domain": "cli"},
            {"id": "devai-003", "user_query": "Task 3", "domain": "web"},
            {"id": "devai-004", "user_query": "Task 4", "domain": "data"},
        ]
        (temp_data_dir / "tasks.json").write_text(json.dumps(tasks_data))

        loader = DevAILoader(data_dir=temp_data_dir)
        domains = loader.get_domains()

        assert len(domains) == 3
        assert "web" in domains
        assert "cli" in domains
        assert "data" in domains

    def test_loader_task_count(self, temp_data_dir: Path) -> None:
        """Test getting total task count."""
        tasks_data = [
            {"id": "devai-001", "user_query": "Task 1"},
            {"id": "devai-002", "user_query": "Task 2"},
            {"id": "devai-003", "user_query": "Task 3"},
        ]
        (temp_data_dir / "tasks.json").write_text(json.dumps(tasks_data))

        loader = DevAILoader(data_dir=temp_data_dir)
        assert loader.task_count() == 3

    def test_loader_total_requirement_count(self, temp_data_dir: Path) -> None:
        """Test getting total requirement count across all tasks."""
        tasks_data = [
            {
                "id": "devai-001",
                "user_query": "Task 1",
                "requirements": [
                    {"id": "R1", "description": "Req 1"},
                    {"id": "R2", "description": "Req 2"},
                ],
            },
            {
                "id": "devai-002",
                "user_query": "Task 2",
                "requirements": [
                    {"id": "R1", "description": "Req 1"},
                    {"id": "R2", "description": "Req 2"},
                    {"id": "R3", "description": "Req 3"},
                ],
            },
        ]
        (temp_data_dir / "tasks.json").write_text(json.dumps(tasks_data))

        loader = DevAILoader(data_dir=temp_data_dir)
        total_reqs = loader.total_requirement_count()

        assert total_reqs == 5

    def test_loader_filter_by_requirement_count(self, temp_data_dir: Path) -> None:
        """Test filtering tasks by requirement count."""
        tasks_data = [
            {
                "id": "devai-001",
                "user_query": "Task 1",
                "requirements": [{"id": "R1", "description": "Req 1"}],
            },
            {
                "id": "devai-002",
                "user_query": "Task 2",
                "requirements": [
                    {"id": "R1", "description": "Req 1"},
                    {"id": "R2", "description": "Req 2"},
                    {"id": "R3", "description": "Req 3"},
                ],
            },
            {
                "id": "devai-003",
                "user_query": "Task 3",
                "requirements": [
                    {"id": "R1", "description": "Req 1"},
                    {"id": "R2", "description": "Req 2"},
                ],
            },
        ]
        (temp_data_dir / "tasks.json").write_text(json.dumps(tasks_data))

        loader = DevAILoader(data_dir=temp_data_dir)

        # Filter for tasks with at least 2 requirements
        filtered = loader.filter_by_requirement_count(min_requirements=2)
        assert len(filtered) == 2

        # Filter for tasks with at most 2 requirements
        filtered = loader.filter_by_requirement_count(max_requirements=2)
        assert len(filtered) == 2

        # Filter for tasks with exactly 2-3 requirements
        filtered = loader.filter_by_requirement_count(min_requirements=2, max_requirements=3)
        assert len(filtered) == 2

    def test_loader_caches_loaded_tasks(self, temp_data_dir: Path) -> None:
        """Test that loader caches tasks and doesn't reload."""
        tasks_data = [{"id": "devai-001", "user_query": "Task 1"}]
        (temp_data_dir / "tasks.json").write_text(json.dumps(tasks_data))

        loader = DevAILoader(data_dir=temp_data_dir)
        tasks1 = loader.load()
        tasks2 = loader.load()

        # Should be the same list object (cached)
        assert tasks1 is tasks2

    def test_loader_handles_malformed_json(self, temp_data_dir: Path) -> None:
        """Test that loader handles malformed JSON gracefully."""
        # Write valid tasks.json
        tasks_data = [{"id": "devai-001", "user_query": "Task 1"}]
        (temp_data_dir / "tasks.json").write_text(json.dumps(tasks_data))

        # Write malformed individual file (shouldn't crash loading)
        (temp_data_dir / "bad.json").write_text("{invalid json")

        loader = DevAILoader(data_dir=temp_data_dir)
        tasks = loader.load()

        # Should load the valid task from tasks.json
        assert len(tasks) == 1

    def test_loader_generates_id_from_filename(self, temp_data_dir: Path) -> None:
        """Test that loader generates task ID from filename when not in data."""
        task_data = {"user_query": "Task without ID"}
        (temp_data_dir / "my-task.json").write_text(json.dumps(task_data))

        loader = DevAILoader(data_dir=temp_data_dir)
        tasks = loader.load()

        assert len(tasks) == 1
        assert tasks[0].id == "my-task"


class TestDevAIDomains:
    """Tests for DevAI domain constants."""

    def test_domains_defined(self) -> None:
        """Test that expected domains are defined."""
        assert "web" in DEVAI_DOMAINS
        assert "cli" in DEVAI_DOMAINS
        assert "data" in DEVAI_DOMAINS
        assert "automation" in DEVAI_DOMAINS
        assert "api" in DEVAI_DOMAINS

    def test_domains_are_lowercase(self) -> None:
        """Test that all domains are lowercase."""
        for domain in DEVAI_DOMAINS:
            assert domain == domain.lower()
