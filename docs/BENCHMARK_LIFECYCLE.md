# Benchmark Lifecycle Pipeline

*Bead: CodeContextBench-cu8*

This document explains the unified workflow for creating, refreshing, validating, and documenting CodeContextBench benchmark suites. The lifecycle pipeline removes ad-hoc shell scripts by encoding each benchmark's adapter refresh commands, Harbor validation runbooks, and manifest emission requirements in a single config-driven tool.

## Goals

1. **Deterministic setup** – Every benchmark run documents the exact git commit, dataset hashes, env fingerprints, and validation logs.
2. **Adapter refresh hygiene** – RepoQA, DIBench, and other adapter-backed suites always regenerate tasks through the same entrypoint.
3. **Harbor sanity by default** – Every lifecycle execution includes at least one Harbor smoke test plus structural validation.
4. **Manifest contract** – Each suite emits `MANIFEST.json` with reproducible metadata for downstream profile runners (CodeContextBench-fft) and post-run evaluation (CodeContextBench-0za/mpg/jzv).

## Components

| Component | Path | Purpose |
|-----------|------|---------|
| Config template | `configs/benchmark_pipeline.yaml` | Declaratively lists dataset inputs, adapter commands, validation steps, and manifest destinations per benchmark. |
| Orchestrator module | `src/benchmark/lifecycle_pipeline.py` | Executes commands, collects logs, hashes datasets/env files, and writes manifests. |
| CLI runner | `scripts/benchmark_lifecycle.py` | User-facing entrypoint with `--benchmarks`, `--dry-run`, and `--logs-root` flags. |
| Unit tests | `tests/test_benchmark_lifecycle.py` | Ensures manifests are written and metadata fields populated when commands succeed. |
| Profile registry | `configs/benchmark_profiles.yaml` | Defines CodeContextBench-fft benchmark slices and agent matrices that consume lifecycle manifests. |
| Profile runner | `scripts/benchmark_profile_runner.py` | Launches Harbor jobs per profile and emits `PROFILE_MANIFEST.json` with provenance details. |

## Running the Pipeline

```bash
# 1. Export dataset pointers + Harbor credentials
eexport REPOQA_DATASET_PATH=/path/to/repoqa.jsonl
export DIBENCH_DATASET_PATH=/path/to/dibench.jsonl
source .env.local && export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

# 2. Dry-run to inspect commands
python scripts/benchmark_lifecycle.py --dry-run

# 3. Execute full lifecycle for all benchmarks
python scripts/benchmark_lifecycle.py

# 4. Execute a subset (e.g., RepoQA only) and override log directory
python scripts/benchmark_lifecycle.py --benchmarks repoqa --logs-root artifacts/pipeline-runs/repoqa
```

Each command listed in `configs/benchmark_pipeline.yaml` runs inside `bash -lc` under the repo root (or an override per command). Outputs are recorded in `artifacts/benchmark_pipeline/<benchmark>/<section>/<step>.log`.

### Launching Benchmark Profiles (CodeContextBench-fft)

`configs/benchmark_profiles.yaml` enumerates reusable benchmark profiles (e.g., RepoQA smoke, DIBench sanity) with their agent matrices. The new runner wires those profiles to the lifecycle manifests so Harbor runs always cite dataset/env provenance:

```bash
# Preview a subset of profiles with dry-run output
python scripts/benchmark_profile_runner.py --profiles repoqa_smoke dibench_smoke --dry-run

# Execute all profiles defined in configs/benchmark_profiles.yaml
python scripts/benchmark_profile_runner.py
```

Every execution writes `PROFILE_MANIFEST.json` under `jobs/benchmark_profiles/<profile>/<run-id>/`. That manifest mirrors the benchmark `MANIFEST.json` (datasets, env fingerprints, validation logs) plus every Harbor command that launched. Evaluation tooling (CodeContextBench-0za/mpg/jzv) now ingests this metadata so reports automatically reference dataset/env fingerprints and validation breadcrumbs.

### Configuration Conventions

- `${PROJECT_ROOT}` is automatically substituted with repo root.
- `${ENV_VAR}` placeholders must exist in the shell environment or the pipeline aborts with a helpful error.
- `dataset_paths` entries are hashed (SHA-256) inside the manifest so downstream tools can verify dataset provenance.
- `artifact_paths` describe generated directories (e.g., `benchmarks/repoqa/tasks`) and are listed in the manifest for quick existence checks.
- `env_fingerprint_vars` (default: `ANTHROPIC_API_KEY`, `SOURCEGRAPH_ACCESS_TOKEN`, `SOURCEGRAPH_URL`) are hashed—not stored in plaintext—to give reproducibility guarantees without leaking secrets.

## Manifest Schema (per benchmark)

Every lifecycle run writes `MANIFEST.json` inside the benchmark directory (customizable via config). The structure is intentionally machine-readable:

```json
{
  "benchmark_id": "repoqa",
  "description": "RepoQA adapter refresh and Harbor sanity validation",
  "generated_at": "2025-12-24T18:30:02.112Z",
  "task_root": "/Users/.../benchmarks/repoqa",
  "pipeline": {"name": "benchmark_lifecycle", "version": "0.1.0"},
  "repo_commit": "4c6ff6b...",
  "datasets": [
    {"path": "/data/repoqa.jsonl", "exists": true, "sha256": "..."}
  ],
  "artifacts": [
    {"path": "/Users/.../benchmarks/repoqa/tasks", "type": "directory", "exists": true}
  ],
  "creation": {
    "steps": [
      {
        "name": "repoqa-adapter-refresh",
        "command": "python benchmarks/repoqa/run_adapter.py ...",
        "status": "success",
        "log_path": "artifacts/benchmark_pipeline/repoqa/creation/repoqa-adapter-refresh.log",
        "exit_code": 0
      }
    ]
  },
  "validation": {
    "steps": [
      {
        "name": "repoqa-harbor-sanity",
        "status": "success",
        "log_path": "artifacts/benchmark_pipeline/repoqa/validation/repoqa-harbor-sanity.log"
      }
    ]
  },
  "environment": {
    "python": "3.11.8",
    "harbor": "harbor version 0.9.2",
    "fingerprint": {
      "combined_hash": "...",
      "variables": [
        {"name": "ANTHROPIC_API_KEY", "set": true, "sha256": "..."}
      ]
    },
    "env_files": [
      {"path": "/Users/.../.env.local", "exists": true, "sha256": "..."}
    ]
  }
}
```

Validation log paths listed above double as breadcrumbs for investigating adapter failures or Harbor regressions (e.g., when CodeContextBench-fft consumes this manifest before launching comparison matrices).

## Relationship to Upcoming Work

- **Profile runner (CodeContextBench-fft):** The runner can now look up benchmark manifests to determine which task directories exist, which artifacts to mount, and which job directories to reuse. It no longer has to guess whether adapters were refreshed.
- **Post-run evaluation (CodeContextBench-0za) + Streamlit dashboard (CodeContextBench-mpg) + documentation (CodeContextBench-jzv):** Evaluation tooling will ingest manifest metadata (dataset hashes, env fingerprints, validation logs) alongside Harbor result JSON to build trustworthy reports.

Future enhancements (tracked separately) include automatic Harbor sample selection per benchmark, per-agent validation matrices, and integrating ds/Deep Search health checks prior to manifest emission.
