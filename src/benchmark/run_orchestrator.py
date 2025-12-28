"""
Run Orchestrator

Manages Harbor evaluation runs with:
- Background execution
- Pause/resume functionality
- Progress tracking
- Log streaming

Runs are executed as background processes and can be paused/resumed.
"""

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
import json
import signal

from .database import RunManager, TaskManager, BenchmarkRegistry


class EvaluationOrchestrator:
    """Orchestrate Harbor evaluation runs."""

    def __init__(self, run_id: str):
        """
        Initialize orchestrator for a run.

        Args:
            run_id: Unique run identifier
        """
        self.run_id = run_id
        self.run_data = RunManager.get(run_id)

        if not self.run_data:
            raise ValueError(f"Run not found: {run_id}")

        self.should_pause = threading.Event()
        self.is_paused = threading.Event()
        self.is_running = False
        self.current_process = None
        self.log_file = None

    def start(self, progress_callback: Optional[Callable] = None):
        """
        Start the evaluation run.

        Args:
            progress_callback: Optional callback for progress updates
        """
        if self.is_running:
            raise RuntimeError("Run is already running")

        self.is_running = True
        RunManager.update_status(self.run_id, "running")

        # Start execution in background thread
        thread = threading.Thread(target=self._run_evaluation, args=(progress_callback,))
        thread.daemon = True
        thread.start()

    def pause(self):
        """Request pause after current task completes."""
        self.should_pause.set()

    def resume(self):
        """Resume paused run."""
        if not self.is_paused.is_set():
            return

        self.should_pause.clear()
        self.is_paused.clear()
        RunManager.update_status(self.run_id, "running")

        # Restart execution
        thread = threading.Thread(target=self._run_evaluation, args=(None,))
        thread.daemon = True
        thread.start()

    def stop(self):
        """Stop the run immediately."""
        self.should_pause.set()

        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=5)
            except:
                self.current_process.kill()

        RunManager.update_status(self.run_id, "stopped")
        self.is_running = False

    def _run_evaluation(self, progress_callback: Optional[Callable] = None):
        """Execute the evaluation (runs in background thread)."""
        try:
            # Get benchmark info
            benchmark = BenchmarkRegistry.get(self.run_data["benchmark_id"])
            if not benchmark:
                raise ValueError("Benchmark not found")

            benchmark_path = Path("benchmarks") / benchmark["folder_name"]

            # Get tasks to run
            tasks = self._get_tasks_to_run(benchmark_path)

            if not tasks:
                RunManager.update_status(self.run_id, "completed")
                self.is_running = False
                return

            # Get agents
            agents = self.run_data["agents"]
            concurrency = self.run_data.get("concurrency", 1)

            # Create task records
            for task_name in tasks:
                for agent in agents:
                    TaskManager.create(self.run_id, task_name, agent)

            # Execute tasks
            total = len(tasks) * len(agents)
            completed = 0

            for task_name in tasks:
                for agent in agents:
                    # Check if we should pause
                    if self.should_pause.is_set():
                        self.is_paused.set()
                        RunManager.update_status(self.run_id, "paused")
                        self.is_running = False
                        return

                    # Check if already completed (for resume)
                    task_data = TaskManager.get_tasks(self.run_id)
                    task_status = next(
                        (t for t in task_data if t["task_name"] == task_name and t["agent_name"] == agent),
                        None
                    )

                    if task_status and task_status["status"] in ("completed", "failed"):
                        completed += 1
                        continue

                    # Run task
                    self._run_single_task(benchmark_path, task_name, agent)

                    completed += 1

                    if progress_callback:
                        progress_callback(completed, total, task_name, agent)

            # Mark run as completed
            RunManager.update_status(self.run_id, "completed")

        except Exception as e:
            RunManager.update_status(self.run_id, "failed", error=str(e))

        finally:
            self.is_running = False

    def _get_tasks_to_run(self, benchmark_path: Path) -> List[str]:
        """Get list of tasks to run based on selection."""
        # Get benchmark info
        benchmark = BenchmarkRegistry.get(self.run_data["benchmark_id"])
        is_harbor_dataset = benchmark.get("adapter_type") == "harbor_dataset"

        task_selection = self.run_data.get("task_selection")

        if task_selection:
            return task_selection

        # For Harbor datasets, we need explicit instance selection
        # (can't enumerate tasks from filesystem)
        if is_harbor_dataset:
            return []  # Must specify instances explicitly

        # Get all tasks from benchmark directory
        tasks = []
        for task_dir in benchmark_path.iterdir():
            if task_dir.is_dir() and (task_dir / "task.toml").exists():
                tasks.append(task_dir.name)

        return sorted(tasks)

    def _run_single_task(self, benchmark_path: Path, task_name: str, agent: str):
        """Run a single task with an agent."""
        # Get benchmark info to check if it's a Harbor dataset
        benchmark = BenchmarkRegistry.get(self.run_data["benchmark_id"])
        is_harbor_dataset = benchmark.get("adapter_type") == "harbor_dataset"

        # Update task status
        TaskManager.update_status(self.run_id, task_name, agent, "running")

        # Prepare output directory
        output_dir = Path(self.run_data.get("output_dir", f"jobs/{self.run_id}"))
        output_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize agent name for filesystem/Docker (replace : with __)
        safe_agent_name = agent.replace(":", "__").replace("/", "_")
        task_output_dir = output_dir / f"{task_name}_{safe_agent_name}"

        # Build Harbor command
        # Use absolute path for local registry
        project_root = Path.cwd().resolve()
        registry_path = str(project_root / "configs/harbor/registry.json")
        
        if is_harbor_dataset:
            # Use Harbor dataset command
            cmd = [
                "harbor", "run",
                "--dataset", benchmark["folder_name"],  # e.g., "swebench_verified"
                "--task-name", task_name,               # Specific task to run from dataset
                "--agent-import-path", agent,
                "--model", "anthropic/claude-haiku-4-5-20251001",
                "--jobs-dir", str(task_output_dir),
                "-n", "1",
            ]
        else:
            # Use local benchmark path
            cmd = [
                "harbor", "run",
                "--path", str(benchmark_path),  # Point to benchmark directory, not task
                "--task-name", task_name,       # Specify which task to run
                "--agent-import-path", agent,
                "--model", "anthropic/claude-haiku-4-5-20251001",
                "--jobs-dir", str(task_output_dir),
                "-n", "1",
            ]

        # Prepare environment variables
        env = os.environ.copy()
        
        # Force Harbor to use our local fixed registry
        env["HARBOR_REGISTRY_PATH"] = registry_path

        # Add any custom environment variables from config
        if "env" in self.run_data.get("config", {}):
            env.update(self.run_data["config"]["env"])

        # CRITICAL: Clean the cmd list of any accidental stale URL/path flags
        # Harbor environment variables take precedence or work better than conflicting flags
        for flag in ["--registry-url", "--registry-path"]:
            while flag in cmd:
                idx = cmd.index(flag)
                cmd.pop(idx) # flag
                if idx < len(cmd):
                    cmd.pop(idx) # value

            # Run from project root so relative paths work correctly
            project_root = Path.cwd()

            # Save Harbor output for debugging (Live streaming)
            log_file = output_dir / f"{task_name}_{safe_agent_name}_harbor.log"
            
            with open(log_file, "w", buffering=1) as log_fd:
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=log_fd,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=str(project_root),  # Run from project root
                    env=env
                )

                # Wait for completion without communicate (which buffers)
                self.current_process.wait()

            # Read stdout for error parsing if it failed
            stdout = log_file.read_text()

            # Check result
            if self.current_process.returncode == 0:
                # Find result.json
                result_files = list(task_output_dir.rglob("result.json"))

                if result_files:
                    with open(result_files[0]) as f:
                        result_data = json.load(f)

                    # Extract reward from Harbor's result structure
                    reward = 0.0

                    # Try new Harbor format: stats.evals[agent_key].metrics[0].mean
                    stats = result_data.get("stats", {})
                    evals = stats.get("evals", {})

                    # Get the first eval (there should only be one)
                    if evals:
                        first_eval = next(iter(evals.values()))
                        metrics = first_eval.get("metrics", [])
                        if metrics and len(metrics) > 0:
                            reward = metrics[0].get("mean", 0.0)

                    # Fallback to old format
                    if reward == 0.0:
                        verifier_result = result_data.get("verifier_result", {})
                        rewards = verifier_result.get("rewards", {})
                        reward = rewards.get("reward", 0.0)

                    trajectory_files = list(task_output_dir.rglob("trajectory.json"))

                    TaskManager.update_status(
                        self.run_id, task_name, agent, "completed",
                        result_path=str(result_files[0]),
                        trajectory_path=str(trajectory_files[0]) if trajectory_files else None,
                        reward=reward
                    )
                else:
                    TaskManager.update_status(
                        self.run_id, task_name, agent, "completed"
                    )
            else:
                # Extract key error info from stdout
                # capture the last 100 lines to get the traceback (especially if rich formatting is used)
                output_lines = stdout.split('\n')
                tail = '\n'.join(output_lines[-100:])
                
                error_lines = [line for line in output_lines if 'error' in line.lower() or 'failed' in line.lower()]
                error_summary = '\n'.join(error_lines[:3]) if error_lines else "See log for details"

                error_message = (
                    f"Harbor exited with code {self.current_process.returncode}.\n"
                    f"Log: {log_file}\n"
                    f"Summary: {error_summary}\n"
                    f"Tail:\n{tail}"
                )

                TaskManager.update_status(
                    self.run_id, task_name, agent, "failed",
                    error_message=error_message
                )

        except Exception as e:
            TaskManager.update_status(
                self.run_id, task_name, agent, "failed",
                error_message=str(e)
            )

        finally:
            self.current_process = None

    def get_progress(self) -> Dict[str, Any]:
        """Get current run progress."""
        tasks = TaskManager.get_tasks(self.run_id)

        total = len(tasks)
        completed = len([t for t in tasks if t["status"] in ("completed", "failed")])
        running = len([t for t in tasks if t["status"] == "running"])
        pending = len([t for t in tasks if t["status"] == "pending"])

        return {
            "run_id": self.run_id,
            "status": self.run_data["status"],
            "total_tasks": total,
            "completed": completed,
            "running": running,
            "pending": pending,
            "progress_pct": (completed / total * 100) if total > 0 else 0,
            "is_paused": self.is_paused.is_set(),
            "can_resume": self.is_paused.is_set(),
        }


def _extract_agent_short_name(agent_path: str) -> str:
    """Extract a short name from agent import path.

    Examples:
        'agents.mcp_variants:StrategicDeepSearchAgent' -> 'StrategicDeepSearch'
        'agents.claude_baseline_agent:BaselineClaudeCodeAgent' -> 'Baseline'
        'agents.mcp_variants:DeepSearchFocusedAgent' -> 'DeepSearchFocused'
    """
    # Extract class name from path like 'module:ClassName'
    if ':' in agent_path:
        class_name = agent_path.split(':')[-1]
    else:
        class_name = agent_path.split('.')[-1]

    # Remove common suffixes
    for suffix in ['ClaudeCodeAgent', 'Agent', 'Claude']:
        if class_name.endswith(suffix):
            class_name = class_name[:-len(suffix)]
            break

    return class_name or 'Unknown'


def create_evaluation_run(
    benchmark_name: str,
    agents: List[str],
    task_selection: Optional[List[str]] = None,
    concurrency: int = 1,
    config: Optional[Dict] = None
) -> str:
    """
    Create a new evaluation run.

    Args:
        benchmark_name: Benchmark name
        agents: List of agent import paths
        task_selection: Optional list of specific tasks
        concurrency: Number of concurrent tasks
        config: Optional run configuration

    Returns:
        run_id for the created run
    """
    # Get benchmark
    benchmark = BenchmarkRegistry.get_by_name(benchmark_name)
    if not benchmark:
        raise ValueError(f"Benchmark not found: {benchmark_name}")

    # Extract agent short names for run_id
    agent_names = [_extract_agent_short_name(a) for a in agents]
    # Use first agent name if single, otherwise 'multi'
    agent_suffix = agent_names[0] if len(agent_names) == 1 else f"multi_{len(agent_names)}"

    # Generate run_id with agent config
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_id = f"{benchmark_name}_{agent_suffix}_{timestamp}"

    # Create output directory
    output_dir = f"jobs/{run_id}"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Create run record
    RunManager.create(
        run_id=run_id,
        benchmark_id=benchmark["id"],
        run_type="evaluation",
        agents=agents,
        task_selection=task_selection,
        concurrency=concurrency,
        config=config,
        output_dir=output_dir
    )

    return run_id


def get_orchestrator(run_id: str) -> EvaluationOrchestrator:
    """Get orchestrator for a run."""
    return EvaluationOrchestrator(run_id)
