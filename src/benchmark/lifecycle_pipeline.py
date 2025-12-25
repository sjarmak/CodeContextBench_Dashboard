"""Benchmark lifecycle pipeline orchestration for CodeContextBench.

This module powers CodeContextBench-cu8 by chaining benchmark creation,
adapter refresh, Harbor validation, and manifest emission into a single
repeatable workflow that can run from scripts/benchmark_lifecycle.py.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:  # Optional dependency used by the CLI entrypoint
    import yaml
except ImportError:  # pragma: no cover - handled in load_pipeline_config
    yaml = None


@dataclasses.dataclass
class StepResult:
    """Result information for a single pipeline command."""

    name: str
    command: str
    status: str
    log_path: str
    duration_seconds: float
    exit_code: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "status": self.status,
            "log_path": self.log_path,
            "duration_seconds": round(self.duration_seconds, 2),
            "exit_code": self.exit_code,
        }


class PipelineConfigError(Exception):
    """Raised when the lifecycle pipeline configuration is invalid."""


def load_pipeline_config(config_path: Path) -> Dict[str, Any]:
    """Load YAML configuration for the benchmark lifecycle pipeline."""

    if yaml is None:  # pragma: no cover - dependency guard
        raise PipelineConfigError(
            "PyYAML not installed. Install pyyaml to load pipeline configs."
        )

    with config_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    if not isinstance(config, dict) or "benchmarks" not in config:
        raise PipelineConfigError(
            f"Invalid pipeline config: expected mapping with 'benchmarks' in {config_path}"
        )
    return config


class BenchmarkLifecyclePipeline:
    """Drive the CodeContextBench benchmark lifecycle end-to-end."""

    def __init__(
        self,
        config: Dict[str, Any],
        project_root: Optional[Path] = None,
        logs_root: Optional[Path] = None,
        dry_run: bool = False,
    ) -> None:
        self.config = config
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.logs_root = self._resolve_path(
            logs_root or config.get("logs_root", "artifacts/benchmark_pipeline"),
            base=self.project_root,
        )
        self.logs_root.mkdir(parents=True, exist_ok=True)
        self.dry_run = dry_run
        self._placeholders = {"PROJECT_ROOT": str(self.project_root)}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, benchmark_ids: Optional[Iterable[str]] = None) -> Dict[str, Path]:
        """Run the pipeline for each requested benchmark."""

        available = self.config.get("benchmarks", {})
        selected = benchmark_ids or available.keys()
        manifests: Dict[str, Path] = {}

        for bench in selected:
            if bench not in available:
                raise PipelineConfigError(f"Benchmark '{bench}' not found in config")
            manifests[bench] = self._run_single(bench, available[bench])

        return manifests

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _run_single(self, benchmark_id: str, spec: Dict[str, Any]) -> Path:
        benchmark_logs = self.logs_root / benchmark_id
        (benchmark_logs / "creation").mkdir(parents=True, exist_ok=True)
        (benchmark_logs / "validation").mkdir(parents=True, exist_ok=True)

        creation_results = self._run_section(
            spec.get("creation", {}).get("commands", []),
            benchmark_logs / "creation",
        )
        validation_results = self._run_section(
            spec.get("validation", {}).get("commands", []),
            benchmark_logs / "validation",
        )

        manifest = self._build_manifest(
            benchmark_id=benchmark_id,
            spec=spec,
            creation_results=creation_results,
            validation_results=validation_results,
        )

        manifest_path = self._resolve_path(
            spec.get("manifest", {}).get("path")
            or Path(spec.get("task_root", ".")) / "MANIFEST.json",
            base=self.project_root,
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_manifest(manifest_path, manifest)
        return manifest_path

    def _run_section(
        self,
        commands: List[Dict[str, Any]],
        log_dir: Path,
    ) -> List[StepResult]:
        results: List[StepResult] = []
        if not commands:
            return results

        for command_spec in commands:
            results.append(self._execute_command(command_spec, log_dir))
        return results

    def _execute_command(self, spec: Dict[str, Any], log_dir: Path) -> StepResult:
        name = spec.get("name")
        if not name:
            raise PipelineConfigError("Each command must include a 'name' field")

        command_raw = spec.get("run")
        if not command_raw:
            raise PipelineConfigError(f"Command '{name}' missing 'run' value")

        command = self._resolve_value(command_raw)
        workdir = self._resolve_path(
            spec.get("workdir") or self.project_root,
            base=self.project_root,
        )
        env_overrides = {
            key: self._resolve_value(value)
            for key, value in (spec.get("env") or {}).items()
        }
        env = os.environ.copy()
        env.update(env_overrides)

        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{self._slugify(name)}.log"

        if self.dry_run:
            log_path.write_text(f"[dry-run] {command}\n", encoding="utf-8")
            return StepResult(
                name=name,
                command=command,
                status="skipped",
                log_path=str(log_path),
                duration_seconds=0.0,
                exit_code=None,
            )

        start = time.monotonic()
        with log_path.open("w", encoding="utf-8") as log_file:
            process = subprocess.run(  # noqa: S603 - command controlled by config
                command,
                shell=True,
                cwd=workdir,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                check=False,
            )
        duration = time.monotonic() - start
        status = "success" if process.returncode == 0 else "failed"
        return StepResult(
            name=name,
            command=command,
            status=status,
            log_path=str(log_path),
            duration_seconds=duration,
            exit_code=process.returncode,
        )

    def _build_manifest(
        self,
        benchmark_id: str,
        spec: Dict[str, Any],
        creation_results: List[StepResult],
        validation_results: List[StepResult],
    ) -> Dict[str, Any]:
        timestamp = (
            dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        )
        pipeline_version = self.config.get("pipeline_version", "0.0.0")
        env_fingerprint = self._env_fingerprint()
        env_files = self._hash_files(self.config.get("env_files", []))
        datasets = self._hash_files(spec.get("dataset_paths", []))
        artifacts = self._describe_paths(spec.get("artifact_paths", []))

        manifest = {
            "benchmark_id": benchmark_id,
            "description": spec.get("description"),
            "generated_at": timestamp,
            "task_root": str(
                self._resolve_path(spec.get("task_root", "."), base=self.project_root)
            ),
            "pipeline": {
                "name": "benchmark_lifecycle",
                "version": pipeline_version,
            },
            "repo_commit": self._git_commit(),
            "creation": {
                "steps": [step.to_dict() for step in creation_results],
            },
            "validation": {
                "steps": [step.to_dict() for step in validation_results],
            },
            "environment": {
                "python": self._python_version(),
                "harbor": self._harbor_version(),
                "fingerprint": env_fingerprint,
                "env_files": env_files,
            },
        }

        if datasets:
            manifest["datasets"] = datasets
        if artifacts:
            manifest["artifacts"] = artifacts
        return manifest

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------
    def _resolve_value(self, raw: Any) -> Any:
        if isinstance(raw, str):
            pattern = re.compile(r"\$\{([A-Z0-9_]+)\}")

            def replace(match: re.Match[str]) -> str:
                key = match.group(1)
                if key in self._placeholders:
                    return self._placeholders[key]
                if key in os.environ:
                    return os.environ[key]
                raise PipelineConfigError(
                    f"Missing environment value for placeholder '{key}'"
                )

            return pattern.sub(replace, raw)
        return raw

    def _resolve_path(self, raw: Any, base: Optional[Path] = None) -> Path:
        resolved = Path(str(self._resolve_value(raw)))
        if not resolved.is_absolute():
            resolved = (base or self.project_root) / resolved
        return resolved

    def _env_fingerprint(self) -> Dict[str, Any]:
        names = self.config.get("env_fingerprint_vars", [])
        entries = []
        digest_input = []
        for name in names:
            value = os.environ.get(name)
            if value:
                hashed = hashlib.sha256(value.encode("utf-8")).hexdigest()
                digest_input.append(hashed)
                entries.append({"name": name, "set": True, "sha256": hashed})
            else:
                digest_input.append(f"{name}:missing")
                entries.append({"name": name, "set": False, "sha256": None})
        combined = (
            hashlib.sha256("|".join(digest_input).encode("utf-8")).hexdigest()
            if digest_input
            else None
        )
        return {
            "variables": entries,
            "combined_hash": combined,
        }

    def _hash_files(self, relative_paths: Iterable[str]) -> List[Dict[str, Any]]:
        results = []
        for path in relative_paths or []:
            resolved = self._resolve_path(path, base=self.project_root)
            if not resolved.exists():
                results.append({"path": str(resolved), "exists": False})
                continue
            results.append(
                {
                    "path": str(resolved),
                    "exists": True,
                    "sha256": self._sha256_file(resolved),
                }
            )
        return results

    def _describe_paths(self, relative_paths: Iterable[str]) -> List[Dict[str, Any]]:
        descriptions = []
        for path in relative_paths or []:
            resolved = self._resolve_path(path, base=self.project_root)
            descriptions.append(
                {
                    "path": str(resolved),
                    "exists": resolved.exists(),
                    "type": self._path_type(resolved),
                }
            )
        return descriptions

    def _path_type(self, path: Path) -> str:
        if path.is_dir():
            return "directory"
        if path.is_file():
            return "file"
        return "missing"

    def _sha256_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _git_commit(self) -> Optional[str]:
        try:
            output = subprocess.check_output(
                ["git", "-C", str(self.project_root), "rev-parse", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            return output.decode("utf-8").strip()
        except Exception:  # pragma: no cover - depends on calling environment
            return None

    def _python_version(self) -> str:
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def _harbor_version(self) -> Optional[str]:
        try:
            output = subprocess.check_output(
                ["harbor", "--version"],
                stderr=subprocess.STDOUT,
            )
            return output.decode("utf-8").strip()
        except Exception:  # pragma: no cover - not always installed
            return None

    def _write_manifest(self, path: Path, manifest: Dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
            fh.write("\n")

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
        return slug or "step"


__all__ = [
    "BenchmarkLifecyclePipeline",
    "PipelineConfigError",
    "StepResult",
    "load_pipeline_config",
]
