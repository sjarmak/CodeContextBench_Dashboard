"""
DevAI data model and loader.

DevAI is a benchmark suite featuring 55 tasks with 365 hierarchical requirements.
Tasks span multiple domains including web development, data science, and automation.

Each task has:
- A user query describing what to build
- Hierarchical requirements with dependencies
- Preferences for how the task should be completed
- A domain classification

Requirements can depend on other requirements, creating a hierarchy that
reflects real-world software development where features often build on each other.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json


# DevAI domain categories
DEVAI_DOMAINS = [
    "web",          # Web application development
    "cli",          # Command-line tool development
    "data",         # Data processing and analysis
    "automation",   # Task automation scripts
    "api",          # API development
    "ml",           # Machine learning
    "testing",      # Testing tools and frameworks
    "devops",       # DevOps and deployment
]


@dataclass
class Requirement:
    """
    A requirement for a DevAI task.

    Requirements can have dependencies on other requirements,
    creating a hierarchical structure.

    Attributes:
        id: Unique requirement identifier within the task (e.g., 'R1', 'R1.1')
        description: Human-readable description of the requirement
        dependencies: List of requirement IDs this requirement depends on
        priority: Requirement priority (1=must-have, 2=should-have, 3=nice-to-have)
        category: Requirement category (functional, non-functional, constraint)
    """

    id: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    priority: int = 1
    category: str = "functional"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "description": self.description,
            "dependencies": self.dependencies,
            "priority": self.priority,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Requirement":
        """Create a Requirement from a dictionary."""
        return cls(
            id=data.get("id", ""),
            description=data.get("description", ""),
            dependencies=data.get("dependencies", []),
            priority=data.get("priority", 1),
            category=data.get("category", "functional"),
        )


@dataclass
class Preference:
    """
    A preference for how a DevAI task should be completed.

    Preferences are softer constraints than requirements, indicating
    preferred approaches or technologies.

    Attributes:
        name: Preference name/identifier
        value: Preferred value or approach
        rationale: Reason for the preference
    """

    name: str
    value: str
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "value": self.value,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Preference":
        """Create a Preference from a dictionary."""
        return cls(
            name=data.get("name", ""),
            value=data.get("value", ""),
            rationale=data.get("rationale", ""),
        )


@dataclass
class DevAITask:
    """
    Data model for a DevAI task.

    Attributes:
        id: Unique task identifier (e.g., 'devai-001')
        user_query: The user's request describing what to build
        requirements: Hierarchical list of requirements with dependencies
        preferences: List of preferences for how to complete the task
        domain: Task domain category (e.g., 'web', 'cli', 'data')
        description: Extended task description (optional)
        metadata: Additional task metadata
    """

    id: str
    user_query: str
    requirements: list[Requirement] = field(default_factory=list)
    preferences: list[Preference] = field(default_factory=list)
    domain: str = "general"
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate task fields after initialization."""
        # Normalize domain to lowercase
        if self.domain:
            self.domain = self.domain.lower()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "user_query": self.user_query,
            "requirements": [r.to_dict() for r in self.requirements],
            "preferences": [p.to_dict() for p in self.preferences],
            "domain": self.domain,
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DevAITask":
        """Create a DevAITask from a dictionary."""
        # Parse requirements
        requirements_data = data.get("requirements", [])
        requirements = [
            Requirement.from_dict(r) if isinstance(r, dict) else r
            for r in requirements_data
        ]

        # Parse preferences
        preferences_data = data.get("preferences", [])
        preferences = [
            Preference.from_dict(p) if isinstance(p, dict) else p
            for p in preferences_data
        ]

        return cls(
            id=data.get("id", ""),
            user_query=data.get("user_query", ""),
            requirements=requirements,
            preferences=preferences,
            domain=data.get("domain", "general"),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
        )

    def get_root_requirements(self) -> list[Requirement]:
        """
        Get requirements with no dependencies (root of hierarchy).

        Returns:
            List of requirements that don't depend on other requirements.
        """
        return [r for r in self.requirements if not r.dependencies]

    def get_dependent_requirements(self, requirement_id: str) -> list[Requirement]:
        """
        Get requirements that depend on a given requirement.

        Args:
            requirement_id: The requirement ID to find dependents for.

        Returns:
            List of requirements that depend on the given requirement.
        """
        return [
            r for r in self.requirements
            if requirement_id in r.dependencies
        ]

    def get_requirement_count(self) -> int:
        """
        Get total number of requirements.

        Returns:
            Number of requirements in this task.
        """
        return len(self.requirements)


class DevAILoader:
    """
    Loader for DevAI tasks.

    Reads tasks from the DevAI dataset structure. Supports loading from
    individual JSON files or a combined manifest file.

    Expected directory structure (individual files):
        data_dir/
        ├── devai-001.json
        ├── devai-002.json
        └── ...

    Alternative structure (manifest):
        data_dir/
        ├── manifest.json
        └── tasks/
            ├── devai-001.json
            └── ...

    Alternative structure (combined):
        data_dir/
        └── tasks.json  (array of all tasks)
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        """
        Initialize the loader.

        Args:
            data_dir: Path to the DevAI data directory.
                      If None, uses default path relative to this module.
        """
        if data_dir is None:
            # Default to a data directory relative to this module
            self.data_dir = Path(__file__).parent / "data"
        else:
            self.data_dir = Path(data_dir)

        self._tasks: list[DevAITask] = []
        self._loaded = False

    def load(self) -> list[DevAITask]:
        """
        Load all tasks from the data directory.

        Attempts to load from:
        1. tasks.json (combined file)
        2. manifest.json (manifest-based loading)
        3. Individual .json files in directory

        Returns:
            List of all DevAITask objects.
        """
        if self._loaded:
            return self._tasks

        self._tasks = []

        # Try loading from combined tasks.json
        tasks_file = self.data_dir / "tasks.json"
        if tasks_file.exists():
            self._load_from_combined_file(tasks_file)
        # Try loading from manifest
        elif (self.data_dir / "manifest.json").exists():
            self._load_from_manifest(self.data_dir / "manifest.json")
        # Load from individual files
        elif self.data_dir.exists():
            self._load_from_directory()

        self._loaded = True
        return self._tasks

    def _load_from_combined_file(self, tasks_file: Path) -> None:
        """Load tasks from a single combined JSON file."""
        try:
            with open(tasks_file, encoding="utf-8") as f:
                data = json.load(f)

            # Handle both array of tasks and object with 'tasks' key
            if isinstance(data, list):
                tasks_data = data
            elif isinstance(data, dict):
                tasks_data = data.get("tasks", [])
            else:
                return

            for task_data in tasks_data:
                try:
                    task = DevAITask.from_dict(task_data)
                    self._tasks.append(task)
                except (KeyError, TypeError) as e:
                    print(f"Warning: Failed to parse task: {e}")

        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load tasks.json: {e}")

    def _load_from_manifest(self, manifest_path: Path) -> None:
        """Load tasks from a manifest file."""
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)

            tasks_dir = self.data_dir / "tasks"
            task_files = manifest.get("tasks", [])

            for task_file in task_files:
                task_path = tasks_dir / task_file
                if task_path.exists():
                    task = self._load_task_file(task_path)
                    if task:
                        self._tasks.append(task)

        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load manifest: {e}")

    def _load_from_directory(self) -> None:
        """Load tasks from individual JSON files in the data directory."""
        # Also check tasks/ subdirectory
        search_dirs = [self.data_dir]
        tasks_subdir = self.data_dir / "tasks"
        if tasks_subdir.exists():
            search_dirs.append(tasks_subdir)

        for search_dir in search_dirs:
            for task_file in search_dir.glob("*.json"):
                # Skip manifest.json
                if task_file.name == "manifest.json":
                    continue
                # Skip combined tasks.json (handled separately)
                if task_file.name == "tasks.json":
                    continue

                task = self._load_task_file(task_file)
                if task:
                    self._tasks.append(task)

    def _load_task_file(self, task_path: Path) -> DevAITask | None:
        """Load a single task from a JSON file."""
        try:
            with open(task_path, encoding="utf-8") as f:
                data = json.load(f)

            # Generate ID from filename if not present
            if not data.get("id"):
                data["id"] = task_path.stem

            return DevAITask.from_dict(data)

        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load task from {task_path}: {e}")
            return None

    def all_ids(self) -> list[str]:
        """
        Get all task IDs.

        Returns:
            List of all task IDs in the loaded dataset.
        """
        if not self._loaded:
            self.load()
        return [task.id for task in self._tasks]

    def filter_by_domain(self, domain: str) -> list[DevAITask]:
        """
        Filter tasks by domain.

        Args:
            domain: Domain to filter by (e.g., 'web', 'cli').

        Returns:
            List of tasks matching the specified domain.
        """
        if not self._loaded:
            self.load()
        domain_lower = domain.lower()
        return [
            task for task in self._tasks
            if task.domain.lower() == domain_lower
        ]

    def get_task(self, task_id: str) -> DevAITask | None:
        """
        Get a specific task by ID.

        Args:
            task_id: The task ID to look up.

        Returns:
            The task if found, None otherwise.
        """
        if not self._loaded:
            self.load()
        for task in self._tasks:
            if task.id == task_id:
                return task
        return None

    def get_domains(self) -> list[str]:
        """
        Get list of available domains.

        Returns:
            List of unique domains in the loaded dataset.
        """
        if not self._loaded:
            self.load()
        return list(set(task.domain for task in self._tasks))

    def task_count(self) -> int:
        """
        Get total number of loaded tasks.

        Returns:
            Number of tasks loaded.
        """
        if not self._loaded:
            self.load()
        return len(self._tasks)

    def total_requirement_count(self) -> int:
        """
        Get total number of requirements across all tasks.

        DevAI has 365 hierarchical requirements across 55 tasks.

        Returns:
            Total count of requirements.
        """
        if not self._loaded:
            self.load()
        return sum(task.get_requirement_count() for task in self._tasks)

    def filter_by_requirement_count(
        self,
        min_requirements: int | None = None,
        max_requirements: int | None = None,
    ) -> list[DevAITask]:
        """
        Filter tasks by number of requirements.

        Args:
            min_requirements: Minimum number of requirements (inclusive).
            max_requirements: Maximum number of requirements (inclusive).

        Returns:
            List of tasks matching the requirement count criteria.
        """
        if not self._loaded:
            self.load()

        result = []
        for task in self._tasks:
            count = task.get_requirement_count()
            if min_requirements is not None and count < min_requirements:
                continue
            if max_requirements is not None and count > max_requirements:
                continue
            result.append(task)

        return result
