"""Tests for DAComp adapter."""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapter import DACompDAAdapter, DACompDEAdapter, DACompDELoader


@pytest.fixture
def da_dataset(tmp_path: Path):
    dataset_path = tmp_path / "dacomp-da.jsonl"
    instance = {
        "instance_id": "dacomp-001",
        "instruction": "Analyze the sample dataset.",
    }
    dataset_path.write_text(json.dumps(instance) + "\n")

    tasks_root = tmp_path / "tasks"
    instance_dir = tasks_root / "dacomp-001"
    instance_dir.mkdir(parents=True)
    (instance_dir / "dacomp-001.sqlite").write_text("")

    return dataset_path, tasks_root


@pytest.fixture
def de_tasks_root(tmp_path: Path) -> Path:
    tasks_root = tmp_path / "de-tasks"
    tasks_root.mkdir()

    impl_dir = tasks_root / "dacomp-de-impl-001"
    impl_dir.mkdir()
    (impl_dir / "run.py").write_text("print('ok')\n")
    (impl_dir / "config").mkdir()
    (impl_dir / "config" / "layer_dependencies.yaml").write_text("layers: []\n")
    (impl_dir / "docs").mkdir()
    (impl_dir / "docs" / "data_contract.yaml").write_text("version: '1.0'\n")
    (impl_dir / "raw_data").mkdir()
    (impl_dir / "sql").mkdir()
    (impl_dir / "sample_start.duckdb").write_text("")

    evol_dir = tasks_root / "dacomp-de-evol-001"
    evol_dir.mkdir()
    (evol_dir / "run.py").write_text("print('ok')\n")
    (evol_dir / "config").mkdir()
    (evol_dir / "config" / "layer_dependencies.yaml").write_text("layers: []\n")
    (evol_dir / "question.md").write_text("Update the pipeline.")
    (evol_dir / "raw_data").mkdir()
    (evol_dir / "sql").mkdir()
    (evol_dir / "sample_start.duckdb").write_text("")

    arch_dir = tasks_root / "dacomp-de-arch-001"
    arch_dir.mkdir()
    (arch_dir / "question.md").write_text("Design the architecture.")
    (arch_dir / "data_contract_raw.yaml").write_text("version: '1.0'\n")

    return tasks_root


def test_dacomp_da_adapter_generates_task(tmp_path: Path, da_dataset):
    dataset_path, tasks_root = da_dataset
    output_dir = tmp_path / "output"

    adapter = DACompDAAdapter(
        task_dir=output_dir,
        dataset_path=dataset_path,
        tasks_root=tasks_root,
    )

    adapter.generate_task("dacomp-001", "dacomp-001")

    task_path = output_dir / "dacomp-001"
    assert (task_path / "instruction.md").exists()
    assert (task_path / "task.toml").exists()
    assert (task_path / "environment" / "Dockerfile").exists()
    assert (task_path / "tests" / "test.sh").exists()
    assert (task_path / "environment" / "data" / "dacomp-001.sqlite").exists()


def test_dacomp_de_loader_detects_task_types(de_tasks_root: Path):
    loader = DACompDELoader(de_tasks_root)
    assert loader.load("dacomp-de-impl-001").task_type == "impl"
    assert loader.load("dacomp-de-evol-001").task_type == "evol"
    assert loader.load("dacomp-de-arch-001").task_type == "arch"


def test_dacomp_de_adapter_generates_tasks(tmp_path: Path, de_tasks_root: Path):
    output_dir = tmp_path / "output"
    adapter = DACompDEAdapter(
        task_dir=output_dir,
        tasks_root=de_tasks_root,
    )

    adapter.generate_task("dacomp-de-impl-001", "dacomp-de-impl-001")
    adapter.generate_task("dacomp-de-evol-001", "dacomp-de-evol-001")
    adapter.generate_task("dacomp-de-arch-001", "dacomp-de-arch-001")

    for task_id in ["dacomp-de-impl-001", "dacomp-de-evol-001", "dacomp-de-arch-001"]:
        task_path = output_dir / task_id
        assert (task_path / "instruction.md").exists()
        assert (task_path / "task.toml").exists()
        assert (task_path / "environment" / "Dockerfile").exists()
        assert (task_path / "tests" / "test.sh").exists()
        assert (task_path / "environment" / "task").exists()
