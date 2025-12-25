"""Manifest provenance helpers for CodeContextBench evaluation tooling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def load_profile_metadata(
    experiment_dir: Path, filename: str = "PROFILE_MANIFEST.json"
) -> Dict[str, Any]:
    """Load profile-level metadata produced by the profile runner."""

    metadata_path = experiment_dir / filename
    if not metadata_path.exists():
        return {}

    with metadata_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_provenance_section(metadata: Dict[str, Any]) -> List[str]:
    """Return markdown lines describing dataset/env provenance."""

    benchmarks = metadata.get("benchmarks") if metadata else None
    if not benchmarks:
        return []

    lines: List[str] = ["", "## Benchmark Provenance", ""]

    for bench in benchmarks:
        manifest = bench.get("manifest", {})
        bench_id = bench.get("id") or manifest.get("benchmark_id", "unknown-benchmark")
        description = manifest.get("description") or bench.get("description") or ""
        header = f"### {bench_id}"
        if description:
            header += f" – {description}"
        lines.append(header)

        manifest_path = bench.get("manifest_path")
        generated_at = manifest.get("generated_at")
        if manifest_path or generated_at:
            parts = []
            if manifest_path:
                parts.append(f"`{manifest_path}`")
            if generated_at:
                parts.append(f"generated {generated_at}")
            lines.append(f"- Manifest: {' / '.join(parts)}")

        task_path = bench.get("task_path")
        if task_path:
            lines.append(f"- Task path: `{task_path}`")

        datasets = manifest.get("datasets") or []
        if datasets:
            lines.append("- Datasets:")
            for dataset in datasets:
                dataset_path = dataset.get("path", "unknown-path")
                sha = dataset.get("sha256") or "missing"
                status = "present" if dataset.get("exists", False) else "missing"
                lines.append(f"  - `{dataset_path}` ({status}, sha256: {sha})")

        env = manifest.get("environment", {})
        fingerprint = env.get("fingerprint", {})
        combined_hash = fingerprint.get("combined_hash")
        if combined_hash:
            lines.append(f"- Env fingerprint: `{combined_hash}`")
        variables = fingerprint.get("variables") or []
        if variables:
            lines.append("  - Variables:")
            for entry in variables:
                name = entry.get("name", "UNKNOWN")
                status = "set" if entry.get("set") else "missing"
                sha = entry.get("sha256") or "n/a"
                lines.append(f"    - {name}: {status} (sha256: {sha})")

        env_files = env.get("env_files") or []
        if env_files:
            lines.append("- Env files:")
            for env_file in env_files:
                fpath = env_file.get("path", "UNKNOWN")
                status = "present" if env_file.get("exists") else "missing"
                sha = env_file.get("sha256") or "n/a"
                lines.append(f"  - `{fpath}` ({status}, sha256: {sha})")

        validation = manifest.get("validation", {})
        validation_steps = validation.get("steps") or []
        if validation_steps:
            lines.append("- Validation logs:")
            for step in validation_steps:
                step_name = step.get("name", "validate")
                log_path = step.get("log_path", "unknown-log")
                status = step.get("status") or "unknown"
                lines.append(f"  - {step_name}: `{log_path}` (status: {status})")

        lines.append("")

    return lines


__all__ = ["build_provenance_section", "load_profile_metadata"]
