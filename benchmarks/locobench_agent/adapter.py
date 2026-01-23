"""
LoCoBench-Agent Adapter for Harbor

Converts LoCoBench-Agent scenarios into Harbor task structure for benchmark execution.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class LoCoBenchTask:
    """Represents a single LoCoBench-Agent task scenario.

    Fields match the normalized JSONL output from extract_dataset.py plus
    additional fields from the raw scenario for complete task context.
    """

    id: str
    task_category: str
    difficulty: str
    title: str
    description: str
    context_files: List[str]
    context_length: int
    task_prompt: str
    ground_truth: Union[str, Dict[str, Any]]
    evaluation_criteria: List[str]
    language: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoCoBenchTask":
        """Create a LoCoBenchTask from a dictionary.

        Args:
            data: Dictionary containing task fields. Can be from either
                  the normalized JSONL or raw scenario JSON.

        Returns:
            LoCoBenchTask instance.
        """
        # Parse language from id if not provided
        language = data.get("language", "")
        if not language and data.get("id"):
            parts = data["id"].split("_")
            language = parts[0] if parts else "unknown"

        return cls(
            id=data.get("id", ""),
            task_category=data.get("task_category", ""),
            difficulty=data.get("difficulty", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            context_files=data.get("context_files", []),
            context_length=data.get("context_length", 0),
            task_prompt=data.get("task_prompt", ""),
            ground_truth=data.get("ground_truth", ""),
            evaluation_criteria=data.get("evaluation_criteria", []),
            language=language,
        )


class LoCoBenchLoader:
    """Loads LoCoBench-Agent tasks from dataset files.

    Supports loading from either:
    - Normalized JSONL files (from extract_dataset.py)
    - Raw scenario JSON files (from data/output/scenarios/)
    """

    def __init__(self, dataset_path: Optional[Path] = None):
        """Initialize the loader.

        Args:
            dataset_path: Path to JSONL dataset file. If None, tasks must be
                          loaded individually from raw JSON files.
        """
        self.dataset_path = dataset_path
        self._tasks: Dict[str, LoCoBenchTask] = {}

        if dataset_path and dataset_path.exists():
            self._load_dataset()

    def _load_dataset(self) -> None:
        """Load tasks from JSONL dataset file."""
        if not self.dataset_path:
            return

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                task = LoCoBenchTask.from_dict(data)
                self._tasks[task.id] = task

    def load(self, task_id: str) -> LoCoBenchTask:
        """Load a single task by ID.

        Args:
            task_id: The task/scenario ID.

        Returns:
            LoCoBenchTask instance.

        Raises:
            KeyError: If task is not found.
        """
        if task_id in self._tasks:
            return self._tasks[task_id]
        raise KeyError(f"Task not found: {task_id}")

    def all_ids(self) -> List[str]:
        """Return all task IDs.

        Returns:
            Sorted list of all loaded task IDs.
        """
        return sorted(self._tasks.keys())

    def filter_by_task_category(self, category: str) -> List[LoCoBenchTask]:
        """Filter tasks by task category.

        Args:
            category: Task category to filter by (e.g., 'architectural_understanding').

        Returns:
            List of tasks matching the category.
        """
        return [
            task for task in self._tasks.values()
            if task.task_category == category
        ]

    def filter_by_language(self, language: str) -> List[LoCoBenchTask]:
        """Filter tasks by programming language.

        Args:
            language: Programming language to filter by (e.g., 'python', 'rust').

        Returns:
            List of tasks matching the language.
        """
        return [
            task for task in self._tasks.values()
            if task.language == language
        ]

    def filter_by_difficulty(self, difficulty: str) -> List[LoCoBenchTask]:
        """Filter tasks by difficulty level.

        Args:
            difficulty: Difficulty level to filter by (e.g., 'expert', 'hard').

        Returns:
            List of tasks matching the difficulty.
        """
        return [
            task for task in self._tasks.values()
            if task.difficulty == difficulty
        ]

    def get_all_tasks(self) -> List[LoCoBenchTask]:
        """Return all loaded tasks.

        Returns:
            List of all LoCoBenchTask instances.
        """
        return list(self._tasks.values())
