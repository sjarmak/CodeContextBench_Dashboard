import json
from pathlib import Path

from src.benchmark.profile_runner import BenchmarkProfileRunner


def test_profile_runner_writes_profile_manifest(tmp_path):
    project_root = tmp_path

    # Prepare benchmark directories + manifest
    tasks_dir = project_root / "benchmarks" / "repoqa" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = project_root / "datasets" / "repoqa.jsonl"
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text("{}", encoding="utf-8")

    manifest_path = project_root / "benchmarks" / "repoqa" / "MANIFEST.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_contents = {
        "benchmark_id": "repoqa",
        "description": "RepoQA test benchmark",
        "generated_at": "2025-01-01T00:00:00Z",
        "task_root": str(tasks_dir.parent),
        "pipeline": {"name": "benchmark_lifecycle", "version": "0.1.0"},
        "repo_commit": "deadbeef",
        "creation": {"steps": [{"name": "adapter", "log_path": "artifacts/adapter.log"}]},
        "validation": {"steps": [{"name": "validate", "log_path": "artifacts/validate.log"}]},
        "datasets": [
            {"path": str(dataset_path), "exists": True, "sha256": "abc123"}
        ],
        "artifacts": [
            {"path": str(tasks_dir), "type": "directory", "exists": True}
        ],
        "environment": {
            "python": "3.11.0",
            "harbor": "harbor 0.9.2",
            "fingerprint": {"combined_hash": "hash", "variables": []},
            "env_files": [],
        },
    }
    manifest_path.write_text(json.dumps(manifest_contents), encoding="utf-8")

    pipeline_config = {
        "pipeline_version": "0.1.0",
        "benchmarks": {
            "repoqa": {
                "description": "RepoQA test benchmark",
                "task_root": "benchmarks/repoqa",
                "artifact_paths": ["benchmarks/repoqa/tasks"],
                "manifest": {"path": "benchmarks/repoqa/MANIFEST.json"},
            }
        },
    }

    profile_config = {
        "defaults": {
            "model": "anthropic/claude-haiku-4-5-20251001",
            "jobs_root": "runs/benchmark_profiles",
            "harbor": {"n_tasks": 1, "timeout_multiplier": 1.5},
        },
        "profiles": {
            "repoqa_smoke": {
                "description": "RepoQA smoke test",
                "benchmarks": [
                    {
                        "id": "repoqa",
                        "jobs_subdir": "repoqa",
                        "task_names": ["sr-qa-requests-001"],
                    }
                ],
                "agents": [
                    {
                        "name": "baseline",
                        "agent_import_path": "agents.claude_baseline_agent:BaselineClaudeCodeAgent",
                    }
                ],
            }
        },
    }

    runner = BenchmarkProfileRunner(
        pipeline_config=pipeline_config,
        profile_config=profile_config,
        project_root=project_root,
        dry_run=True,
        run_id="test-run",
    )

    outputs = runner.run(["repoqa_smoke"])
    run_dir = outputs["repoqa_smoke"]
    expected_dir = project_root / "jobs" / "benchmark_profiles" / "repoqa_smoke" / "test-run"
    assert run_dir == expected_dir
    assert run_dir.exists()

    profile_manifest_path = run_dir / "PROFILE_MANIFEST.json"
    assert profile_manifest_path.exists()

    with profile_manifest_path.open() as fh:
        profile_manifest = json.load(fh)

    assert profile_manifest["profile_id"] == "repoqa_smoke"
    assert profile_manifest["benchmarks"][0]["manifest"]["benchmark_id"] == "repoqa"

    runs = profile_manifest["runs"]
    assert len(runs) == 1
    assert runs[0]["status"] == "skipped"
    assert runs[0]["task_name"] == "sr-qa-requests-001"

    log_path = Path(runs[0]["log_path"])
    assert log_path.exists()
    assert "dry-run" in log_path.read_text()
