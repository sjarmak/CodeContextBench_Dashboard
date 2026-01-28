import json

from src.benchmark.provenance import build_provenance_section, load_profile_metadata


def test_build_provenance_section_includes_dataset_and_env():
    metadata = {
        "benchmarks": [
            {
                "id": "repoqa",
                "description": "RepoQA benchmark",
                "task_path": "/benchmarks/repoqa/tasks",
                "manifest_path": "/benchmarks/repoqa/MANIFEST.json",
                "manifest": {
                    "benchmark_id": "repoqa",
                    "description": "RepoQA benchmark",
                    "generated_at": "2025-01-01T00:00:00Z",
                    "datasets": [
                        {
                            "path": "/data/repoqa.jsonl",
                            "exists": True,
                            "sha256": "abc123",
                        }
                    ],
                    "validation": {
                        "steps": [
                            {
                                "name": "harbor-sanity",
                                "log_path": "/logs/repoqa-harbor.log",
                                "status": "success",
                            }
                        ]
                    },
                    "environment": {
                        "fingerprint": {
                            "combined_hash": "fingerprint",
                            "variables": [
                                {"name": "ANTHROPIC_API_KEY", "set": True, "sha256": "deadbeef"}
                            ],
                        },
                        "env_files": [
                            {
                                "path": "/repo/.env.local",
                                "exists": True,
                                "sha256": "feedface",
                            }
                        ],
                    },
                },
            }
        ]
    }

    lines = build_provenance_section(metadata)
    text = "\n".join(lines)
    assert "## Benchmark Provenance" in text
    assert "repoqa" in text
    assert "repoqa.jsonl" in text
    assert "fingerprint" in text
    assert "harbor-sanity" in text


def test_load_profile_metadata(tmp_path):
    metadata = {"profile_id": "demo"}
    manifest_path = tmp_path / "PROFILE_MANIFEST.json"
    manifest_path.write_text(json.dumps(metadata), encoding="utf-8")

    loaded = load_profile_metadata(tmp_path)
    assert loaded == metadata

    other_dir = tmp_path / "missing"
    other_dir.mkdir()
    assert load_profile_metadata(other_dir) == {}
