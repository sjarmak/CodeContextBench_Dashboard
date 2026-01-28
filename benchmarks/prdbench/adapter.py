"""
PRDBench data model and loader.

PRDBench is a benchmark for evaluating LLM-powered coding agents on PRD-driven
development tasks. Each task contains:
- A Product Requirements Document (PRD) as the main instruction
- A detailed test plan with evaluation criteria
- Specific evaluation criteria for judging task completion

The loader reads tasks from the PRDBench directory structure:
    {task_id}/
    ├── src/
    │   └── PRD.md
    └── evaluation/
        └── detailed_test_plan.json

Each task is evaluated based on how well the agent implements the PRD.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json


@dataclass
class EvaluationCriterion:
    """
    A single evaluation criterion for a PRDBench task.

    Evaluation criteria define how to judge whether a requirement
    has been met. Each criterion has a weight contributing to
    the final score.

    Attributes:
        id: Unique criterion identifier (e.g., 'C1', 'C1.1')
        name: Human-readable criterion name
        description: Detailed description of what to evaluate
        weight: Weight of this criterion in the final score (0.0-1.0)
        category: Criterion category (functional, ui, performance, etc.)
        automated: Whether this can be evaluated automatically
    """

    id: str
    name: str
    description: str
    weight: float = 1.0
    category: str = "functional"
    automated: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "weight": self.weight,
            "category": self.category,
            "automated": self.automated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationCriterion":
        """Create an EvaluationCriterion from a dictionary."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            weight=data.get("weight", 1.0),
            category=data.get("category", "functional"),
            automated=data.get("automated", False),
        )


@dataclass
class EvaluationPlan:
    """
    A test plan for evaluating a PRDBench task.

    The test plan contains structured evaluation criteria
    and test cases for validating PRD implementation.

    Attributes:
        version: Test plan version
        task_id: ID of the associated task
        criteria: List of evaluation criteria
        test_cases: List of test case descriptions
        scoring: Scoring configuration (weights, thresholds)
        metadata: Additional test plan metadata
    """

    version: str
    task_id: str
    criteria: list[EvaluationCriterion] = field(default_factory=list)
    test_cases: list[dict[str, Any]] = field(default_factory=list)
    scoring: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "version": self.version,
            "task_id": self.task_id,
            "criteria": [c.to_dict() for c in self.criteria],
            "test_cases": self.test_cases,
            "scoring": self.scoring,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationPlan":
        """Create a EvaluationPlan from a dictionary."""
        # Parse criteria
        criteria_data = data.get("criteria", [])
        criteria = [
            EvaluationCriterion.from_dict(c) if isinstance(c, dict) else c
            for c in criteria_data
        ]

        return cls(
            version=data.get("version", "1.0"),
            task_id=data.get("task_id", ""),
            criteria=criteria,
            test_cases=data.get("test_cases", []),
            scoring=data.get("scoring", {}),
            metadata=data.get("metadata", {}),
        )

    def get_total_weight(self) -> float:
        """
        Get total weight of all criteria.

        Returns:
            Sum of all criterion weights.
        """
        return sum(c.weight for c in self.criteria)

    def get_criteria_by_category(self, category: str) -> list[EvaluationCriterion]:
        """
        Filter criteria by category.

        Args:
            category: Category to filter by.

        Returns:
            List of criteria matching the category.
        """
        return [c for c in self.criteria if c.category == category]

    def criterion_count(self) -> int:
        """
        Get number of evaluation criteria.

        Returns:
            Number of criteria in the test plan.
        """
        return len(self.criteria)


@dataclass
class PRDBenchTask:
    """
    Data model for a PRDBench task.

    Attributes:
        id: Unique task identifier (e.g., 'prdbench-001')
        prd_content: The Product Requirements Document content (markdown)
        test_plan: Structured test plan for evaluation
        evaluation_criteria: List of evaluation criteria (convenience accessor)
        title: Task title extracted from PRD
        description: Brief task description
        difficulty: Task difficulty (easy, medium, hard)
        metadata: Additional task metadata
    """

    id: str
    prd_content: str
    test_plan: EvaluationPlan | None = None
    evaluation_criteria: list[EvaluationCriterion] = field(default_factory=list)
    title: str = ""
    description: str = ""
    difficulty: str = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize evaluation_criteria from test_plan if not provided."""
        # If we have a test_plan but no evaluation_criteria, populate from test_plan
        if self.test_plan and not self.evaluation_criteria:
            self.evaluation_criteria = list(self.test_plan.criteria)
        # If we have evaluation_criteria but no test_plan, create a basic test_plan
        elif self.evaluation_criteria and not self.test_plan:
            self.test_plan = EvaluationPlan(
                version="1.0",
                task_id=self.id,
                criteria=self.evaluation_criteria,
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "prd_content": self.prd_content,
            "test_plan": self.test_plan.to_dict() if self.test_plan else None,
            "evaluation_criteria": [c.to_dict() for c in self.evaluation_criteria],
            "title": self.title,
            "description": self.description,
            "difficulty": self.difficulty,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PRDBenchTask":
        """Create a PRDBenchTask from a dictionary."""
        # Parse test_plan
        test_plan_data = data.get("test_plan")
        test_plan = None
        if test_plan_data and isinstance(test_plan_data, dict):
            test_plan = EvaluationPlan.from_dict(test_plan_data)

        # Parse evaluation_criteria
        criteria_data = data.get("evaluation_criteria", [])
        evaluation_criteria = [
            EvaluationCriterion.from_dict(c) if isinstance(c, dict) else c
            for c in criteria_data
        ]

        return cls(
            id=data.get("id", ""),
            prd_content=data.get("prd_content", ""),
            test_plan=test_plan,
            evaluation_criteria=evaluation_criteria,
            title=data.get("title", ""),
            description=data.get("description", ""),
            difficulty=data.get("difficulty", "medium"),
            metadata=data.get("metadata", {}),
        )

    def get_criterion_count(self) -> int:
        """
        Get total number of evaluation criteria.

        Returns:
            Number of evaluation criteria.
        """
        return len(self.evaluation_criteria)

    def get_prd_sections(self) -> list[str]:
        """
        Extract section headers from the PRD content.

        Returns:
            List of section headers found in the PRD.
        """
        sections = []
        for line in self.prd_content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("#"):
                # Remove '#' characters and whitespace
                section = stripped.lstrip("#").strip()
                if section:
                    sections.append(section)
        return sections

    def extract_title_from_prd(self) -> str:
        """
        Extract title from the first heading in the PRD.

        Returns:
            Title extracted from PRD, or empty string if not found.
        """
        for line in self.prd_content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        return ""


class PRDBenchLoader:
    """
    Loader for PRDBench tasks.

    Reads tasks from the PRDBench dataset structure. Supports loading from
    individual task directories or a manifest/combined file.

    Expected directory structure (individual directories):
        data_dir/
        ├── task-001/
        │   ├── src/
        │   │   └── PRD.md
        │   └── evaluation/
        │       └── detailed_test_plan.json
        ├── task-002/
        │   ├── src/
        │   │   └── PRD.md
        │   └── evaluation/
        │       └── detailed_test_plan.json
        └── ...

    Alternative structure (manifest):
        data_dir/
        ├── manifest.json
        └── tasks/
            └── ...

    Alternative structure (combined):
        data_dir/
        └── tasks.json  (array of all tasks)
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        """
        Initialize the loader.

        Args:
            data_dir: Path to the PRDBench data directory.
                      If None, uses default path relative to this module.
        """
        if data_dir is None:
            # Default to a data directory relative to this module
            self.data_dir = Path(__file__).parent / "data"
        else:
            self.data_dir = Path(data_dir)

        self._tasks: list[PRDBenchTask] = []
        self._loaded = False

    def load(self) -> list[PRDBenchTask]:
        """
        Load all tasks from the data directory.

        Attempts to load from:
        1. tasks.json (combined file)
        2. manifest.json (manifest-based loading)
        3. Individual task directories with {task_id}/src/PRD.md structure

        Returns:
            List of all PRDBenchTask objects.
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
        # Load from individual task directories
        elif self.data_dir.exists():
            self._load_from_directories()

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
                    task = PRDBenchTask.from_dict(task_data)
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

            tasks_list = manifest.get("tasks", [])

            for task_entry in tasks_list:
                # Handle both string (task_id) and dict (full task data)
                if isinstance(task_entry, str):
                    task = self._load_task_directory(self.data_dir / task_entry)
                elif isinstance(task_entry, dict):
                    task_id = task_entry.get("id", task_entry.get("task_id"))
                    if task_id:
                        task = self._load_task_directory(self.data_dir / task_id)
                    else:
                        continue
                else:
                    continue

                if task:
                    self._tasks.append(task)

        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load manifest: {e}")

    def _load_from_directories(self) -> None:
        """Load tasks from individual task directories."""
        # Look for directories containing src/PRD.md
        for item in self.data_dir.iterdir():
            if item.is_dir():
                prd_path = item / "src" / "PRD.md"
                if prd_path.exists():
                    task = self._load_task_directory(item)
                    if task:
                        self._tasks.append(task)

    def _load_task_directory(self, task_dir: Path) -> PRDBenchTask | None:
        """
        Load a single task from a directory.

        Expected structure:
            task_dir/
            ├── src/
            │   └── PRD.md
            └── evaluation/
                └── detailed_test_plan.json

        Args:
            task_dir: Path to the task directory.

        Returns:
            PRDBenchTask if successful, None otherwise.
        """
        task_id = task_dir.name
        prd_path = task_dir / "src" / "PRD.md"
        test_plan_path = task_dir / "evaluation" / "detailed_test_plan.json"

        # Read PRD content (required)
        if not prd_path.exists():
            print(f"Warning: PRD.md not found in {task_dir}")
            return None

        try:
            prd_content = prd_path.read_text(encoding="utf-8")
        except IOError as e:
            print(f"Warning: Failed to read PRD.md from {task_dir}: {e}")
            return None

        # Read test plan (optional)
        test_plan = None
        evaluation_criteria: list[EvaluationCriterion] = []

        if test_plan_path.exists():
            try:
                with open(test_plan_path, encoding="utf-8") as f:
                    test_plan_data = json.load(f)

                # Set task_id in test plan data
                test_plan_data["task_id"] = task_id
                test_plan = EvaluationPlan.from_dict(test_plan_data)
                evaluation_criteria = list(test_plan.criteria)

            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load test plan from {task_dir}: {e}")

        # Extract title from PRD
        title = ""
        for line in prd_content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
                break

        # Check for additional metadata
        metadata_path = task_dir / "metadata.json"
        metadata: dict[str, Any] = {}
        if metadata_path.exists():
            try:
                with open(metadata_path, encoding="utf-8") as f:
                    metadata = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        return PRDBenchTask(
            id=task_id,
            prd_content=prd_content,
            test_plan=test_plan,
            evaluation_criteria=evaluation_criteria,
            title=title,
            difficulty=metadata.get("difficulty", "medium"),
            metadata=metadata,
        )

    def all_ids(self) -> list[str]:
        """
        Get all task IDs.

        Returns:
            List of all task IDs in the loaded dataset.
        """
        if not self._loaded:
            self.load()
        return [task.id for task in self._tasks]

    def get_task(self, task_id: str) -> PRDBenchTask | None:
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

    def task_count(self) -> int:
        """
        Get total number of loaded tasks.

        Returns:
            Number of tasks loaded.
        """
        if not self._loaded:
            self.load()
        return len(self._tasks)

    def filter_by_difficulty(self, difficulty: str) -> list[PRDBenchTask]:
        """
        Filter tasks by difficulty level.

        Args:
            difficulty: Difficulty level (easy, medium, hard).

        Returns:
            List of tasks matching the difficulty.
        """
        if not self._loaded:
            self.load()
        difficulty_lower = difficulty.lower()
        return [
            task for task in self._tasks
            if task.difficulty.lower() == difficulty_lower
        ]

    def filter_by_criteria_count(
        self,
        min_criteria: int | None = None,
        max_criteria: int | None = None,
    ) -> list[PRDBenchTask]:
        """
        Filter tasks by number of evaluation criteria.

        Args:
            min_criteria: Minimum number of criteria (inclusive).
            max_criteria: Maximum number of criteria (inclusive).

        Returns:
            List of tasks matching the criteria count range.
        """
        if not self._loaded:
            self.load()

        result = []
        for task in self._tasks:
            count = task.get_criterion_count()
            if min_criteria is not None and count < min_criteria:
                continue
            if max_criteria is not None and count > max_criteria:
                continue
            result.append(task)

        return result

    def total_criteria_count(self) -> int:
        """
        Get total number of evaluation criteria across all tasks.

        Returns:
            Total count of evaluation criteria.
        """
        if not self._loaded:
            self.load()
        return sum(task.get_criterion_count() for task in self._tasks)
