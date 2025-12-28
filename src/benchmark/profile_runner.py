"""Benchmark profile runner (CodeContextBench-fft).

Loads `configs/benchmark_profiles.yaml` plus the lifecycle config and
associated benchmark manifests to launch Harbor job matrices with full
provenance tracking.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:  # Optional dependency for YAML configs
    import yaml
except ImportError:  # pragma: no cover - handled by loader
    yaml = None


class ProfileConfigError(Exception):
    """Raised when the benchmark profile configuration is invalid."""


@dataclasses.dataclass
class HarborRunResult:
    """Execution metadata for a single Harbor invocation."""

    profile_id: str
    benchmark_id: str
    agent_name: str
    command: str
    log_path: str
    job_dir: str
    status: str
    duration_seconds: float
    task_name: Optional[str] = None
    task_filter: Optional[str] = None
    exit_code: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "benchmark_id": self.benchmark_id,
            "agent_name": self.agent_name,
            "command": self.command,
            "log_path": self.log_path,
            "job_dir": self.job_dir,
            "status": self.status,
            "duration_seconds": round(self.duration_seconds, 2),
            "task_name": self.task_name,
            "task_filter": self.task_filter,
            "exit_code": self.exit_code,
        }


def load_profile_config(config_path: Path) -> Dict[str, Any]:
    """Load YAML configuration describing benchmark profiles."""

    if yaml is None:  # pragma: no cover - dependency guard
        raise ProfileConfigError(
            "PyYAML not installed. Install pyyaml to load profile configs."
        )

    with config_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    if not isinstance(config, dict) or "profiles" not in config:
        raise ProfileConfigError(
            f"Invalid profile config: expected mapping with 'profiles' in {config_path}"
        )
    return config


class BenchmarkProfileRunner:
    """Launch Harbor job matrices defined in benchmark profile configs."""

    def __init__(
        self,
        pipeline_config: Dict[str, Any],
        profile_config: Dict[str, Any],
        project_root: Optional[Path] = None,
        dry_run: bool = False,
        run_id: Optional[str] = None,
    ) -> None:
        self.pipeline_config = pipeline_config
        self.profile_config = profile_config
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.dry_run = dry_run
        self.run_id = run_id or dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self._placeholders = {"PROJECT_ROOT": str(self.project_root)}

        if "benchmarks" not in self.pipeline_config:
            raise ProfileConfigError("Pipeline config missing 'benchmarks' section")
        if "profiles" not in self.profile_config:
            raise ProfileConfigError("Profile config missing 'profiles' section")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, profile_ids: Optional[Iterable[str]] = None) -> Dict[str, Path]:
        """Run each requested profile, returning output directories."""
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] BenchmarkProfileRunner started. Run ID: {self.run_id}", flush=True)

        available_profiles = self.profile_config.get("profiles", {})
        selected_ids = list(profile_ids) if profile_ids else list(available_profiles.keys())
        results: Dict[str, Path] = {}

        for profile_id in selected_ids:
            if profile_id not in available_profiles:
                raise ProfileConfigError(f"Profile '{profile_id}' not found in config")
            results[profile_id] = self._run_single(profile_id, available_profiles[profile_id])

        return results

    # ------------------------------------------------------------------
    # Profile execution
    # ------------------------------------------------------------------
    def _run_single(self, profile_id: str, spec: Dict[str, Any]) -> Path:
        jobs_root = self._resolve_path(
            spec.get("jobs_root")
            or self.profile_config.get("defaults", {}).get("jobs_root")
            or "jobs/benchmark_profiles",
            base=self.project_root,
        )
        run_dir = jobs_root / profile_id / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        agents = spec.get("agents") or []
        if not agents:
            raise ProfileConfigError(f"Profile '{profile_id}' must define at least one agent")

        benchmarks = spec.get("benchmarks")
        if not benchmarks and spec.get("benchmark"):
            benchmarks = [{"id": spec["benchmark"]}]
        if not benchmarks:
            raise ProfileConfigError(
                f"Profile '{profile_id}' must define one or more benchmarks"
            )

        harbor_defaults = self._merge_dicts(
            self.profile_config.get("defaults", {}).get("harbor", {}),
            spec.get("harbor", {}),
        )

        benchmark_metadata = []
        run_results: List[HarborRunResult] = []

        for bench_entry in benchmarks:
            bench_context = self._prepare_benchmark_context(bench_entry)
            benchmark_metadata.append(bench_context["metadata"])

            run_results.extend(
                self._run_agents_for_benchmark(
                    profile_id=profile_id,
                    run_dir=run_dir,
                    agents=agents,
                    bench_context=bench_context,
                    harbor_defaults=harbor_defaults,
                )
            )

        manifest_path = run_dir / "PROFILE_MANIFEST.json"
        profile_manifest = {
            "profile_id": profile_id,
            "description": spec.get("description"),
            "generated_at": dt.datetime.now(dt.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "run_id": self.run_id,
            "run_dir": str(run_dir),
            "jobs_root": str(jobs_root),
            "dry_run": self.dry_run,
            "pipeline_version": self.pipeline_config.get("pipeline_version", "0.0.0"),
            "benchmarks": benchmark_metadata,
            "agents": [
                {
                    "name": agent.get("name"),
                    "display_name": agent.get("display_name"),
                    "agent_import_path": agent.get("agent_import_path"),
                    "model": agent.get("model")
                    or spec.get("model")
                    or self.profile_config.get("defaults", {}).get("model"),
                }
                for agent in agents
            ],
            "runs": [result.to_dict() for result in run_results],
        }
        with manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(profile_manifest, fh, indent=2)
            fh.write("\n")

        return run_dir

    def _prepare_benchmark_context(self, bench_entry: Dict[str, Any]) -> Dict[str, Any]:
        bench_id = bench_entry.get("id")
        if not bench_id:
            raise ProfileConfigError("Each benchmark entry must include an 'id'")

        pipeline_bench = self.pipeline_config["benchmarks"].get(bench_id)
        if not pipeline_bench:
            raise ProfileConfigError(f"Benchmark '{bench_id}' not found in pipeline config")

        manifest_rel = (
            bench_entry.get("manifest_path")
            or pipeline_bench.get("manifest", {}).get("path")
            or Path(pipeline_bench.get("task_root", ".")) / "MANIFEST.json"
        )
        manifest_path = self._resolve_path(manifest_rel)
        if not manifest_path.exists():
            raise ProfileConfigError(
                f"Benchmark manifest not found for '{bench_id}' at {manifest_path}."
                " Run scripts/benchmark_lifecycle.py first."
            )
        with manifest_path.open("r", encoding="utf-8") as fh:
            manifest = json.load(fh)

        task_path = self._determine_task_path(
            bench_entry=bench_entry,
            pipeline_bench=pipeline_bench,
            manifest=manifest,
        )

        task_names = bench_entry.get("task_names") or []
        task_filter = bench_entry.get("task_filter")
        harbor_overrides = bench_entry.get("harbor", {})
        jobs_subdir = bench_entry.get("jobs_subdir") or bench_id

        metadata = {
            "id": bench_id,
            "description": pipeline_bench.get("description"),
            "task_path": str(task_path),
            "jobs_subdir": jobs_subdir,
            "manifest_path": str(manifest_path),
            "manifest": manifest,
            "task_selection": {
                "task_names": task_names,
                "task_filter": task_filter,
                "n_tasks": harbor_overrides.get("n_tasks"),
            },
        }

        return {
            "id": bench_id,
            "task_path": task_path,
            "jobs_subdir": jobs_subdir,
            "task_names": task_names,
            "task_filter": task_filter,
            "manifest": manifest,
            "harbor_overrides": harbor_overrides,
            "metadata": metadata,
        }

    def _run_agents_for_benchmark(
        self,
        profile_id: str,
        run_dir: Path,
        agents: List[Dict[str, Any]],
        bench_context: Dict[str, Any],
        harbor_defaults: Dict[str, Any],
    ) -> List[HarborRunResult]:
        results: List[HarborRunResult] = []
        bench_dir = run_dir / bench_context["jobs_subdir"]

        for agent in agents:
            agent_name = agent.get("name")
            if not agent_name:
                raise ProfileConfigError("Each agent entry must include a 'name'")
            import_path = agent.get("agent_import_path")
            if not import_path:
                raise ProfileConfigError(
                    f"Agent '{agent_name}' missing 'agent_import_path' setting"
                )

            agent_dir = bench_dir / agent_name
            logs_dir = agent_dir / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)

            harbor_opts = self._merge_dicts(
                harbor_defaults,
                bench_context.get("harbor_overrides") or {},
                agent.get("harbor", {}),
            )

            if bench_context["task_names"]:
                for task_name in bench_context["task_names"]:
                    results.append(
                        self._invoke_harbor(
                            profile_id=profile_id,
                            bench_id=bench_context["id"],
                            agent=agent,
                            agent_dir=agent_dir,
                            logs_dir=logs_dir,
                            task_path=bench_context["task_path"],
                            task_name=task_name,
                            task_filter=None,
                            harbor_opts=harbor_opts,
                            import_path=import_path,
                        )
                    )
            else:
                results.append(
                    self._invoke_harbor(
                        profile_id=profile_id,
                        bench_id=bench_context["id"],
                        agent=agent,
                        agent_dir=agent_dir,
                        logs_dir=logs_dir,
                        task_path=bench_context["task_path"],
                        task_name=None,
                        task_filter=bench_context.get("task_filter"),
                        harbor_opts=harbor_opts,
                        import_path=import_path,
                    )
                )

        return results

    def _invoke_harbor(
        self,
        profile_id: str,
        bench_id: str,
        agent: Dict[str, Any],
        agent_dir: Path,
        logs_dir: Path,
        task_path: Path,
        harbor_opts: Dict[str, Any],
        import_path: str,
        task_name: Optional[str],
        task_filter: Optional[str],
    ) -> HarborRunResult:
        agent_name = agent.get("name")
        model = (
            agent.get("model")
            or harbor_opts.get("model")
            or self.profile_config.get("defaults", {}).get("model")
            or "anthropic/claude-haiku-4-5-20251001"
        )
        n_tasks = 1 if task_name else int(harbor_opts.get("n_tasks", 1))
        n_concurrent = harbor_opts.get("n_concurrent")
        timeout_multiplier = harbor_opts.get("timeout_multiplier")

        job_name_parts = [agent_name, bench_id, self.run_id]
        if task_name:
            job_name_parts.append(self._slugify(task_name))
        job_name = "-".join(part for part in job_name_parts if part)

        cmd = [
            "harbor",
            "run",
            "--registry-url", "file:///Users/sjarmak/CodeContextBench/configs/harbor/registry.json", "--registry-path",
            "configs/harbor/registry.json",
            "--path",
            str(task_path),
            "--agent-import-path",
            import_path,
            "--model",
            str(model),
            "--jobs-dir",
            str(agent_dir),
            "--job-name",
            job_name,
            "-n",
            str(n_tasks),
        ]
        if n_concurrent:
            cmd.extend(["--n-concurrent", str(n_concurrent)])
        if timeout_multiplier:
            cmd.extend(["--timeout-multiplier", str(timeout_multiplier)])
        if task_filter and not task_name:
            cmd.extend(["--task-filter", str(task_filter)])
        if task_name:
            cmd.extend(["--task-name", task_name])

        log_name_parts = [agent_name, bench_id]
        if task_name:
            log_name_parts.append(self._slugify(task_name))
        log_path = logs_dir / f"{'-'.join(filter(None, log_name_parts))}.log"

        env = os.environ.copy()
        agent_env = agent.get("env") or {}
        env.update({k: str(self._resolve_value(v)) for k, v in agent_env.items()})

        # CRITICAL: Clean the cmd list of any accidental stale URL flags
        if "--registry-url" in cmd:
            idx = cmd.index("--registry-url")
            cmd.pop(idx) # --registry-url
            if idx < len(cmd):
                cmd.pop(idx) # the value

        command_str = " ".join(shlex.quote(part) for part in cmd)
        if self.dry_run:
            log_path.write_text(f"[dry-run] {command_str}\n", encoding="utf-8")
            return HarborRunResult(
                profile_id=profile_id,
                benchmark_id=bench_id,
                agent_name=agent_name,
                command=command_str,
                log_path=str(log_path),
                job_dir=str(agent_dir),
                status="skipped",
                duration_seconds=0.0,
                task_name=task_name,
                task_filter=task_filter,
            )

        # Print status for dashboard monitoring
        task_label = task_name or task_filter or "all tasks"
        timestamp = dt.datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] Starting agent: {agent_name} on task: {task_label}", flush=True)
        print(f"[{timestamp}] Command: {command_str}", flush=True)
        print(f"[{timestamp}] Log: {log_path}", flush=True)

        start = time.monotonic()
        # Open with line buffering for real-time logging
        log_file = log_path.open("w", encoding="utf-8", buffering=1)
        try:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
                text=True,
            )
            process.wait()
        except KeyboardInterrupt:
            process.terminate()
            raise
        finally:
            log_file.close()

        duration = time.monotonic() - start
        status = "success" if process.returncode == 0 else "failed"
        
        timestamp = dt.datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] Agent {agent_name} finished task {task_label} with status: {status}", flush=True)
        
        return HarborRunResult(
            profile_id=profile_id,
            benchmark_id=bench_id,
            agent_name=agent_name,
            command=command_str,
            log_path=str(log_path),
            job_dir=str(agent_dir),
            status=status,
            duration_seconds=duration,
            task_name=task_name,
            task_filter=task_filter,
            exit_code=process.returncode,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _determine_task_path(
        self,
        bench_entry: Dict[str, Any],
        pipeline_bench: Dict[str, Any],
        manifest: Dict[str, Any],
    ) -> Path:
        if bench_entry.get("task_path"):
            return self._resolve_path(bench_entry["task_path"])

        artifact_paths = bench_entry.get("artifact_paths") or pipeline_bench.get(
            "artifact_paths", []
        )
        candidates: List[str] = []
        for artifact in manifest.get("artifacts", []) or []:
            if artifact.get("type") == "directory" and artifact.get("path"):
                candidates.append(artifact["path"])
        candidates.extend(artifact_paths)
        if pipeline_bench.get("task_root"):
            candidates.append(
                str(self._resolve_path(pipeline_bench.get("task_root")))
            )

        for candidate in candidates:
            resolved = self._resolve_path(candidate)
            if resolved.exists():
                return resolved

        raise ProfileConfigError(
            f"Unable to determine task path for benchmark '{bench_entry.get('id')}'. "
            "Ensure artifact_paths exist."
        )

    def _merge_dicts(self, *mappings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        for mapping in mappings:
            if mapping:
                merged.update(mapping)
        return merged

    def _resolve_value(self, raw: Any) -> Any:
        if isinstance(raw, str):
            pattern = re.compile(r"\$\{([A-Z0-9_]+)\}")

            def replace(match: re.Match[str]) -> str:
                key = match.group(1)
                if key in self._placeholders:
                    return self._placeholders[key]
                if key in os.environ:
                    return os.environ[key]
                raise ProfileConfigError(
                    f"Missing environment value for placeholder '{key}'"
                )

            return pattern.sub(replace, raw)
        return raw

    def _resolve_path(self, raw: Any, base: Optional[Path] = None) -> Path:
        resolved = Path(str(self._resolve_value(raw)))
        if not resolved.is_absolute():
            resolved = (base or self.project_root) / resolved
        return resolved

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
        return slug or "run"


__all__ = [
    "BenchmarkProfileRunner",
    "HarborRunResult",
    "ProfileConfigError",
    "load_profile_config",
]
