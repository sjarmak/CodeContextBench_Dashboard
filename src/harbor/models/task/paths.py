"""Task paths model for Harbor benchmark framework."""

from pathlib import Path


class TaskPaths:
    """Defines the directory structure for a Harbor task."""

    def __init__(self, task_dir: Path):
        """Initialize task paths.

        Args:
            task_dir: Root directory for the task.
        """
        self.task_dir = Path(task_dir)

    @property
    def tests_dir(self) -> Path:
        """Directory containing test files."""
        return self.task_dir / "tests"

    @property
    def environment_dir(self) -> Path:
        """Directory containing environment/Docker setup."""
        return self.task_dir / "environment"

    @property
    def instruction_path(self) -> Path:
        """Path to instruction.md file."""
        return self.task_dir / "instruction.md"

    @property
    def config_path(self) -> Path:
        """Path to task.toml configuration file."""
        return self.task_dir / "task.toml"

    @property
    def test_path(self) -> Path:
        """Path to main test script."""
        return self.tests_dir / "test.sh"
