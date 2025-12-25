import json

from src.benchmark.lifecycle_pipeline import BenchmarkLifecyclePipeline


def test_pipeline_writes_manifest(tmp_path, monkeypatch):
    project_root = tmp_path
    env_file = project_root / ".env.test"
    env_file.write_text("SECRET=1", encoding="utf-8")

    dataset_path = project_root / "dataset.jsonl"
    dataset_path.write_text("{}", encoding="utf-8")

    config = {
        "pipeline_version": "test",
        "logs_root": "logs",
        "env_fingerprint_vars": ["CI_FAKE_ENV"],
        "env_files": [".env.test"],
        "benchmarks": {
            "dummy": {
                "description": "Unit test benchmark",
                "task_root": ".",
                "dataset_paths": ["${DATASET_PATH}"],
                "artifact_paths": ["generated"],
                "creation": {
                    "commands": [
                        {
                            "name": "write-artifact",
                            "run": "bash -lc 'mkdir -p generated && echo hi > generated/output.txt'",
                            "workdir": "${PROJECT_ROOT}",
                        }
                    ]
                },
                "validation": {
                    "commands": [
                        {
                            "name": "check-artifact",
                            "run": "bash -lc 'test -f generated/output.txt'",
                            "workdir": "${PROJECT_ROOT}",
                        }
                    ]
                },
                "manifest": {"path": "manifest/MANIFEST.json"},
            }
        },
    }

    monkeypatch.setenv("DATASET_PATH", str(dataset_path))
    monkeypatch.setenv("CI_FAKE_ENV", "test-value")

    pipeline = BenchmarkLifecyclePipeline(
        config=config,
        project_root=project_root,
    )

    manifests = pipeline.run(["dummy"])
    manifest_path = manifests["dummy"]
    assert manifest_path == project_root / "manifest" / "MANIFEST.json"
    assert manifest_path.exists()

    with manifest_path.open() as fh:
        manifest = json.load(fh)

    assert manifest["benchmark_id"] == "dummy"
    assert manifest["creation"]["steps"][0]["status"] == "success"
    assert manifest["validation"]["steps"][0]["exit_code"] == 0

    datasets = manifest.get("datasets")
    assert datasets is not None
    assert datasets[0]["exists"] is True

    artifacts = manifest.get("artifacts")
    assert artifacts is not None
    assert artifacts[0]["path"].endswith("generated")
    assert artifacts[0]["type"] == "directory"

    env_info = manifest["environment"]["fingerprint"]["variables"][0]
    assert env_info["name"] == "CI_FAKE_ENV"
    assert env_info["set"] is True
    assert env_info["sha256"] is not None

    env_files = manifest["environment"]["env_files"]
    assert env_files[0]["exists"] is True
    assert env_files[0]["sha256"] is not None
