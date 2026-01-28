"""
AINativeBench data model and loader.

AINativeBench is a benchmark suite with 8 specialized benchmarks,
each having 4 variants for different evaluation modes.

Benchmarks:
- RepoBench: Repository-level code completion
- CrossCodeEval: Cross-file code evaluation
- RepoExec: Repository-level code execution
- SWE-bench: Software engineering problem solving
- DevBench: Developer benchmark tasks
- Cocomic: Code completion with context
- EvoCodeBench: Evolution-based code benchmark
- MdEval: Multi-document evaluation

Variants for each benchmark:
- easy: Basic difficulty tasks
- medium: Moderate difficulty tasks
- hard: Advanced difficulty tasks
- retrieval: Tasks requiring context retrieval
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json


# AINativeBench benchmark names
AINATIVEBENCH_BENCHMARKS = [
    "repobench",
    "crosscodeeval",
    "repoexec",
    "swe-bench",
    "devbench",
    "cocomic",
    "evocodebench",
    "mdeval",
]

# AINativeBench variants (4 per benchmark)
AINATIVEBENCH_VARIANTS = [
    "easy",
    "medium",
    "hard",
    "retrieval",
]


@dataclass
class ScoringMetrics:
    """Scoring metrics for an AINativeBench task."""

    primary_metric: str = "pass_rate"
    secondary_metrics: list[str] = field(default_factory=list)
    thresholds: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "primary_metric": self.primary_metric,
            "secondary_metrics": self.secondary_metrics,
            "thresholds": self.thresholds,
        }


@dataclass
class TestCase:
    """A test case for an AINativeBench task."""

    name: str
    input_data: dict[str, Any] = field(default_factory=dict)
    expected_output: dict[str, Any] = field(default_factory=dict)
    timeout_sec: int = 60

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "input_data": self.input_data,
            "expected_output": self.expected_output,
            "timeout_sec": self.timeout_sec,
        }


@dataclass
class AINativeBenchTask:
    """
    Data model for an AINativeBench task.

    Attributes:
        id: Unique task identifier (e.g., 'repobench-easy-001')
        benchmark_name: Name of the parent benchmark (e.g., 'repobench')
        variant: Task variant (e.g., 'easy', 'medium', 'hard', 'retrieval')
        test_cases: List of test cases for evaluation
        scoring_metrics: Metrics used for scoring
        description: Human-readable task description
        language: Primary programming language
        context_files: Files providing context for the task
        ground_truth: Ground truth solution or expected output
        metadata: Additional task metadata
    """

    id: str
    benchmark_name: str
    variant: str
    test_cases: list[TestCase] = field(default_factory=list)
    scoring_metrics: ScoringMetrics = field(default_factory=ScoringMetrics)
    description: str = ""
    language: str = "python"
    context_files: list[str] = field(default_factory=list)
    ground_truth: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate task fields."""
        if self.benchmark_name and self.benchmark_name.lower() not in AINATIVEBENCH_BENCHMARKS:
            # Allow unknown benchmarks but issue no error - flexibility for extensions
            pass
        if self.variant and self.variant.lower() not in AINATIVEBENCH_VARIANTS:
            # Allow unknown variants but issue no error - flexibility for extensions
            pass

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "benchmark_name": self.benchmark_name,
            "variant": self.variant,
            "test_cases": [tc.to_dict() for tc in self.test_cases],
            "scoring_metrics": self.scoring_metrics.to_dict(),
            "description": self.description,
            "language": self.language,
            "context_files": self.context_files,
            "ground_truth": self.ground_truth,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AINativeBenchTask":
        """Create an AINativeBenchTask from a dictionary."""
        # Parse test cases
        test_cases_data = data.get("test_cases", [])
        test_cases = [
            TestCase(
                name=tc.get("name", f"test_{i}"),
                input_data=tc.get("input_data", {}),
                expected_output=tc.get("expected_output", {}),
                timeout_sec=tc.get("timeout_sec", 60),
            )
            for i, tc in enumerate(test_cases_data)
        ]

        # Parse scoring metrics
        metrics_data = data.get("scoring_metrics", {})
        scoring_metrics = ScoringMetrics(
            primary_metric=metrics_data.get("primary_metric", "pass_rate"),
            secondary_metrics=metrics_data.get("secondary_metrics", []),
            thresholds=metrics_data.get("thresholds", {}),
        )

        return cls(
            id=data.get("id", ""),
            benchmark_name=data.get("benchmark_name", ""),
            variant=data.get("variant", ""),
            test_cases=test_cases,
            scoring_metrics=scoring_metrics,
            description=data.get("description", ""),
            language=data.get("language", "python"),
            context_files=data.get("context_files", []),
            ground_truth=data.get("ground_truth", {}),
            metadata=data.get("metadata", {}),
        )


class AINativeBenchLoader:
    """
    Loader for AINativeBench tasks.

    Reads tasks from the AINativeBench dataset structure, which organizes
    tasks by benchmark and variant. Supports filtering by benchmark name
    and variant.

    Expected directory structure:
        data_dir/
        ├── repobench/
        │   ├── easy/
        │   │   ├── task_001.json
        │   │   └── task_002.json
        │   ├── medium/
        │   ├── hard/
        │   └── retrieval/
        ├── crosscodeeval/
        │   └── ...
        └── ...

    Alternative structure (flat with manifest):
        data_dir/
        ├── manifest.json
        └── tasks/
            ├── repobench-easy-001.json
            └── ...
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        """
        Initialize the loader.

        Args:
            data_dir: Path to the AINativeBench data directory.
                      If None, uses default path.
        """
        if data_dir is None:
            # Default to a data directory relative to this module
            self.data_dir = Path(__file__).parent / "data"
        else:
            self.data_dir = Path(data_dir)

        self._tasks: list[AINativeBenchTask] = []
        self._loaded = False

    def load(self) -> list[AINativeBenchTask]:
        """
        Load all tasks from the data directory.

        Returns:
            List of all AINativeBenchTask objects.

        Raises:
            FileNotFoundError: If data directory doesn't exist and no tasks found.
        """
        if self._loaded:
            return self._tasks

        self._tasks = []

        # Try to load from manifest first
        manifest_path = self.data_dir / "manifest.json"
        if manifest_path.exists():
            self._load_from_manifest(manifest_path)
        elif self.data_dir.exists():
            # Load from hierarchical directory structure
            self._load_from_directory()

        # If no tasks loaded but directory exists, create empty list (valid state)
        # If directory doesn't exist and no manifest, that's OK - empty benchmark
        self._loaded = True
        return self._tasks

    def _load_from_manifest(self, manifest_path: Path) -> None:
        """Load tasks from a manifest file."""
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

    def _load_from_directory(self) -> None:
        """Load tasks from hierarchical directory structure."""
        for benchmark in AINATIVEBENCH_BENCHMARKS:
            benchmark_dir = self.data_dir / benchmark
            if not benchmark_dir.exists():
                continue

            for variant in AINATIVEBENCH_VARIANTS:
                variant_dir = benchmark_dir / variant
                if not variant_dir.exists():
                    continue

                for task_file in variant_dir.glob("*.json"):
                    task = self._load_task_file(task_file, benchmark, variant)
                    if task:
                        self._tasks.append(task)

    def _load_task_file(
        self,
        task_path: Path,
        benchmark: str | None = None,
        variant: str | None = None,
    ) -> AINativeBenchTask | None:
        """Load a single task from a JSON file."""
        try:
            with open(task_path, encoding="utf-8") as f:
                data = json.load(f)

            # Override benchmark/variant if provided (from directory structure)
            if benchmark:
                data["benchmark_name"] = benchmark
            if variant:
                data["variant"] = variant

            # Generate ID if not present
            if not data.get("id"):
                stem = task_path.stem
                if benchmark and variant:
                    data["id"] = f"{benchmark}-{variant}-{stem}"
                else:
                    data["id"] = stem

            return AINativeBenchTask.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            # Log error but continue loading other tasks
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

    def filter_by_benchmark(self, benchmark_name: str) -> list[AINativeBenchTask]:
        """
        Filter tasks by benchmark name.

        Args:
            benchmark_name: Name of the benchmark to filter by.

        Returns:
            List of tasks belonging to the specified benchmark.
        """
        if not self._loaded:
            self.load()
        benchmark_lower = benchmark_name.lower()
        return [
            task for task in self._tasks
            if task.benchmark_name.lower() == benchmark_lower
        ]

    def filter_by_variant(self, variant: str) -> list[AINativeBenchTask]:
        """
        Filter tasks by variant.

        Args:
            variant: Variant to filter by (e.g., 'easy', 'hard').

        Returns:
            List of tasks matching the specified variant.
        """
        if not self._loaded:
            self.load()
        variant_lower = variant.lower()
        return [
            task for task in self._tasks
            if task.variant.lower() == variant_lower
        ]

    def filter_by_benchmark_and_variant(
        self,
        benchmark_name: str,
        variant: str,
    ) -> list[AINativeBenchTask]:
        """
        Filter tasks by both benchmark name and variant.

        Args:
            benchmark_name: Name of the benchmark.
            variant: Variant to filter by.

        Returns:
            List of tasks matching both criteria.
        """
        if not self._loaded:
            self.load()
        benchmark_lower = benchmark_name.lower()
        variant_lower = variant.lower()
        return [
            task for task in self._tasks
            if task.benchmark_name.lower() == benchmark_lower
            and task.variant.lower() == variant_lower
        ]

    def get_task(self, task_id: str) -> AINativeBenchTask | None:
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

    def get_benchmarks(self) -> list[str]:
        """
        Get list of available benchmark names.

        Returns:
            List of unique benchmark names in the loaded dataset.
        """
        if not self._loaded:
            self.load()
        return list(set(task.benchmark_name for task in self._tasks))

    def get_variants(self) -> list[str]:
        """
        Get list of available variants.

        Returns:
            List of unique variants in the loaded dataset.
        """
        if not self._loaded:
            self.load()
        return list(set(task.variant for task in self._tasks))

    def task_count(self) -> int:
        """
        Get total number of loaded tasks.

        Returns:
            Number of tasks loaded.
        """
        if not self._loaded:
            self.load()
        return len(self._tasks)
