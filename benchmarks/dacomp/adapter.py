"""
DAComp Adapter for Harbor.

Converts DAComp-DA (analysis) and DAComp-DE (engineering) tasks into
Harbor task directories.
"""

import json
import os
import shutil
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Dict, List, Optional

import importlib.util


TEMPLATE_DIR = Path(__file__).parent / "templates"


def _resolve_harbor_src() -> Path:
    """Resolve the Harbor source path for direct file imports."""
    candidates = [
        Path(__file__).parent.parent.parent / "src",
    ]

    env_path = os.environ.get("HARBOR_SRC")
    if env_path:
        candidates.append(Path(env_path))

    candidates.append(Path.home() / "harbor" / "src")

    for path in candidates:
        if not path:
            continue
        config_path = path / "harbor" / "models" / "task" / "config.py"
        if config_path.exists():
            return path

    raise FileNotFoundError(
        "Could not locate Harbor source. Set HARBOR_SRC to the harbor/src path."
    )


src_path = _resolve_harbor_src()


def _import_module_from_file(module_name: str, file_path: Path):
    """Import a module from a file path without triggering package __init__."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Import Harbor models directly from source
_task_config_module = _import_module_from_file(
    "harbor.models.task.config",
    src_path / "harbor" / "models" / "task" / "config.py",
)
TaskConfig = _task_config_module.TaskConfig

_task_paths_module = _import_module_from_file(
    "harbor.models.task.paths",
    src_path / "harbor" / "models" / "task" / "paths.py",
)
TaskPaths = _task_paths_module.TaskPaths


class RequireNameMeta(type(ABC)):
    def __init__(cls, name, bases, dct):
        type.__init__(cls, name, bases, dct)
        if name != "BaseAdapter" and not hasattr(cls, "NAME"):
            raise TypeError(f"Class {name} must define a class property 'NAME'.")


class BaseAdapter(ABC, metaclass=RequireNameMeta):
    NAME: ClassVar[str]

    def __init__(self, **kwargs):
        super().__init__()

    @abstractmethod
    def generate_task(self, task_id: str, local_task_id: str) -> None:
        raise NotImplementedError("Adapter must implement this method.")


@dataclass
class DACompDAInstance:
    """Represents a DAComp-DA analysis instance."""

    instance_id: str
    instruction: str

    @classmethod
    def from_dict(cls, data: dict) -> "DACompDAInstance":
        return cls(
            instance_id=data["instance_id"],
            instruction=data.get("instruction", ""),
        )


@dataclass
class DACompDEInstance:
    """Represents a DAComp-DE engineering instance."""

    instance_id: str
    task_type: str
    source_dir: Path
    question_path: Optional[Path]
    data_contract_path: Optional[Path]
    start_db_name: Optional[str]
    output_db_name: Optional[str]


class DACompDALoader:
    """Loads DAComp-DA instances from JSONL."""

    def __init__(self, dataset_path: Optional[Path] = None):
        self.dataset_path = dataset_path
        self._instances: Dict[str, DACompDAInstance] = {}

        if dataset_path and dataset_path.exists():
            self._load_dataset()

    def _load_dataset(self) -> None:
        with open(self.dataset_path, "r") as handle:
            for line in handle:
                if not line.strip():
                    continue
                data = json.loads(line.strip())
                instance = DACompDAInstance.from_dict(data)
                self._instances[instance.instance_id] = instance

    def load(self, instance_id: str) -> DACompDAInstance:
        if instance_id in self._instances:
            return self._instances[instance_id]
        raise KeyError(f"Instance not found: {instance_id}")

    def all_ids(self) -> List[str]:
        return sorted(self._instances.keys())


class DACompDELoader:
    """Loads DAComp-DE instances from extracted task directories."""

    def __init__(self, tasks_root: Optional[Path] = None):
        self.tasks_root = tasks_root
        self._instances: Dict[str, DACompDEInstance] = {}

        if tasks_root and tasks_root.exists():
            self._load_tasks()

    def _infer_task_type(self, instance_id: str) -> str:
        if "-impl-" in instance_id:
            return "impl"
        if "-evol-" in instance_id:
            return "evol"
        if "-arch-" in instance_id:
            return "arch"
        raise ValueError(f"Unknown DAComp-DE task type: {instance_id}")

    def _find_db_names(self, task_dir: Path) -> tuple[Optional[str], Optional[str]]:
        start_db = None
        output_db = None
        start_candidates = sorted(task_dir.glob("*_start.duckdb"))
        if start_candidates:
            start_db = start_candidates[0].name
            output_db = start_db.replace("_start.duckdb", ".duckdb")
            return start_db, output_db

        duckdb_files = sorted(task_dir.glob("*.duckdb"))
        if duckdb_files:
            output_db = duckdb_files[0].name
        return None, output_db

    def _load_tasks(self) -> None:
        for task_dir in sorted(self.tasks_root.iterdir()):
            if not task_dir.is_dir():
                continue

            instance_id = task_dir.name
            task_type = self._infer_task_type(instance_id)

            question_path = task_dir / "question.md"
            if not question_path.exists():
                question_path = None

            data_contract_path = None
            if task_type == "arch":
                candidate = task_dir / "data_contract_raw.yaml"
                if candidate.exists():
                    data_contract_path = candidate
            elif task_type == "impl":
                candidate = task_dir / "docs" / "data_contract.yaml"
                if candidate.exists():
                    data_contract_path = candidate

            start_db, output_db = self._find_db_names(task_dir)

            instance = DACompDEInstance(
                instance_id=instance_id,
                task_type=task_type,
                source_dir=task_dir,
                question_path=question_path,
                data_contract_path=data_contract_path,
                start_db_name=start_db,
                output_db_name=output_db,
            )
            self._instances[instance_id] = instance

    def load(self, instance_id: str) -> DACompDEInstance:
        if instance_id in self._instances:
            return self._instances[instance_id]
        raise KeyError(f"Instance not found: {instance_id}")

    def all_ids(self) -> List[str]:
        return sorted(self._instances.keys())


class DACompDAAdapter(BaseAdapter):
    """Adapter that converts DAComp-DA tasks into Harbor task directories."""

    NAME = "dacomp-da"

    def __init__(
        self,
        task_dir: Path,
        dataset_path: Path,
        tasks_root: Path,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.task_dir = Path(task_dir)
        self.tasks_root = Path(tasks_root)
        self.loader = DACompDALoader(dataset_path)
        self.templates_dir = TEMPLATE_DIR

    def _render_template(self, template_path: Path, context: dict) -> str:
        content = template_path.read_text()
        for key, value in context.items():
            content = content.replace(f"{{{key}}}", str(value))
            content = content.replace(f"{{{{ {key} }}}}", str(value))
        return content

    def _find_sqlite_path(self, instance_id: str) -> Path:
        instance_dir = self.tasks_root / instance_id
        if not instance_dir.exists():
            raise FileNotFoundError(f"Task directory not found: {instance_dir}")

        candidate = instance_dir / f"{instance_id}.sqlite"
        if candidate.exists():
            return candidate

        sqlite_files = sorted(instance_dir.glob("*.sqlite"))
        if sqlite_files:
            return sqlite_files[0]

        raise FileNotFoundError(f"No sqlite file found in {instance_dir}")

    def _prepare_task_from_template(
        self,
        instance: DACompDAInstance,
        output_dir: Path,
    ) -> None:
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        task_paths = TaskPaths(task_dir=output_dir)
        task_paths.solution_dir.mkdir(parents=True, exist_ok=True)
        task_paths.tests_dir.mkdir(parents=True, exist_ok=True)
        task_paths.environment_dir.mkdir(parents=True, exist_ok=True)

        env_data_dir = task_paths.environment_dir / "data"
        env_task_dir = task_paths.environment_dir / "task"
        env_data_dir.mkdir(parents=True, exist_ok=True)
        env_task_dir.mkdir(parents=True, exist_ok=True)

        sqlite_path = self._find_sqlite_path(instance.instance_id)
        shutil.copy2(sqlite_path, env_data_dir / sqlite_path.name)

        instruction = self._render_template(
            self.templates_dir / "instruction_da.md",
            {
                "instance_id": instance.instance_id,
                "instruction": instance.instruction.strip(),
                "sqlite_path": f"/data/{sqlite_path.name}",
                "answer_path": "/app/answer.md",
            },
        )
        task_paths.instruction_path.write_text(instruction)

        task_toml_template = self.templates_dir / "task.toml"
        template_content = task_toml_template.read_text()
        task_config = TaskConfig.model_validate_toml(template_content)
        task_config.metadata["instance_id"] = instance.instance_id
        task_config.metadata["subset"] = "da"
        task_config.metadata["task_type"] = "analysis"
        task_config.metadata["tags"] = ["dacomp", "da", "analysis"]
        task_paths.config_path.write_text(task_config.model_dump_toml())

        dockerfile_path = self.templates_dir / "environment" / "Dockerfile"
        (task_paths.environment_dir / "Dockerfile").write_text(
            dockerfile_path.read_text()
        )

        solve_template = self.templates_dir / "solution" / "solve.sh"
        task_paths.solve_path.write_text(solve_template.read_text())
        task_paths.solve_path.chmod(0o755)

        test_template = self.templates_dir / "tests" / "test_da.sh"
        test_content = self._render_template(
            test_template,
            {"answer_path": "/app/answer.md"},
        )
        task_paths.test_path.write_text(test_content)
        task_paths.test_path.chmod(0o755)

    def generate_task(self, task_id: str, local_task_id: str) -> None:
        instance = self.loader.load(task_id)
        out_dir = self.task_dir / local_task_id
        out_dir.mkdir(parents=True, exist_ok=True)
        self._prepare_task_from_template(instance, out_dir)


class DACompDEAdapter(BaseAdapter):
    """Adapter that converts DAComp-DE tasks into Harbor task directories."""

    NAME = "dacomp-de"

    def __init__(
        self,
        task_dir: Path,
        tasks_root: Path,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.task_dir = Path(task_dir)
        self.tasks_root = Path(tasks_root)
        self.loader = DACompDELoader(tasks_root)
        self.templates_dir = TEMPLATE_DIR

    def _render_template(self, template_path: Path, context: dict) -> str:
        content = template_path.read_text()
        for key, value in context.items():
            content = content.replace(f"{{{key}}}", str(value))
            content = content.replace(f"{{{{ {key} }}}}", str(value))
        return content

    def _instruction_template(self, task_type: str) -> Path:
        if task_type == "impl":
            return self.templates_dir / "instruction_de_impl.md"
        if task_type == "evol":
            return self.templates_dir / "instruction_de_evol.md"
        if task_type == "arch":
            return self.templates_dir / "instruction_de_arch.md"
        raise ValueError(f"Unknown task type: {task_type}")

    def _test_template(self, task_type: str) -> Path:
        if task_type == "impl":
            return self.templates_dir / "tests" / "test_de_impl.sh"
        if task_type == "evol":
            return self.templates_dir / "tests" / "test_de_evol.sh"
        if task_type == "arch":
            return self.templates_dir / "tests" / "test_de_arch.sh"
        raise ValueError(f"Unknown task type: {task_type}")

    def _prepare_task_from_template(
        self,
        instance: DACompDEInstance,
        output_dir: Path,
    ) -> None:
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        task_paths = TaskPaths(task_dir=output_dir)
        task_paths.solution_dir.mkdir(parents=True, exist_ok=True)
        task_paths.tests_dir.mkdir(parents=True, exist_ok=True)
        task_paths.environment_dir.mkdir(parents=True, exist_ok=True)

        env_data_dir = task_paths.environment_dir / "data"
        env_task_dir = task_paths.environment_dir / "task"
        env_data_dir.mkdir(parents=True, exist_ok=True)
        env_task_dir.mkdir(parents=True, exist_ok=True)

        shutil.copytree(instance.source_dir, env_task_dir, dirs_exist_ok=True)

        question_path = None
        if instance.question_path:
            question_path = f"/app/task/{instance.question_path.name}"

        contract_path = None
        if instance.data_contract_path:
            contract_rel = instance.data_contract_path.relative_to(instance.source_dir)
            contract_path = f"/app/task/{contract_rel.as_posix()}"

        instruction = self._render_template(
            self._instruction_template(instance.task_type),
            {
                "instance_id": instance.instance_id,
                "task_type": instance.task_type,
                "task_dir": "/app/task",
                "question_path": question_path or "N/A",
                "contract_path": contract_path or "N/A",
                "output_db": instance.output_db_name or "output.duckdb",
                "answer_path": "/app/answer.md" if instance.task_type != "arch" else "/app/answer.yaml",
            },
        )
        task_paths.instruction_path.write_text(instruction)

        task_toml_template = self.templates_dir / "task.toml"
        template_content = task_toml_template.read_text()
        task_config = TaskConfig.model_validate_toml(template_content)
        task_config.metadata["instance_id"] = instance.instance_id
        task_config.metadata["subset"] = "de"
        task_config.metadata["task_type"] = instance.task_type
        task_config.metadata["tags"] = ["dacomp", "de", instance.task_type]
        task_paths.config_path.write_text(task_config.model_dump_toml())

        dockerfile_path = self.templates_dir / "environment" / "Dockerfile"
        (task_paths.environment_dir / "Dockerfile").write_text(
            dockerfile_path.read_text()
        )

        solve_template = self.templates_dir / "solution" / "solve.sh"
        task_paths.solve_path.write_text(solve_template.read_text())
        task_paths.solve_path.chmod(0o755)

        test_template = self._test_template(instance.task_type)
        test_context = {
            "answer_path": "/app/answer.md",
            "output_db": instance.output_db_name or "output.duckdb",
        }
        if instance.task_type == "arch":
            test_context = {"answer_path": "/app/answer.yaml"}

        test_content = self._render_template(test_template, test_context)
        task_paths.test_path.write_text(test_content)
        task_paths.test_path.chmod(0o755)

    def generate_task(self, task_id: str, local_task_id: str) -> None:
        instance = self.loader.load(task_id)
        out_dir = self.task_dir / local_task_id
        out_dir.mkdir(parents=True, exist_ok=True)
        self._prepare_task_from_template(instance, out_dir)
