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
        task_selection = self.run_data.get("task_selection")

        if task_selection:
            return task_selection

        # Get all tasks from benchmark directory
        tasks = []
        for task_dir in benchmark_path.iterdir():
            if task_dir.is_dir() and (task_dir / "task.toml").exists():
                tasks.append(task_dir.name)

        return sorted(tasks)

    def _run_single_task(self, benchmark_path: Path, task_name: str, agent: str):
        """Run a single task with an agent."""
        task_path = benchmark_path / task_name

        # Update task status
        TaskManager.update_status(self.run_id, task_name, agent, "running")

        # Prepare output directory
        output_dir = Path(self.run_data.get("output_dir", f"jobs/{self.run_id}"))
        output_dir.mkdir(parents=True, exist_ok=True)

        task_output_dir = output_dir / f"{task_name}_{agent}"

        # Build Harbor command
        cmd = [
            "harbor", "run",
            "--path", str(benchmark_path),  # Point to benchmark directory, not task
            "--task-name", task_name,       # Specify which task to run
            "--agent-import-path", agent,
            "--model", "anthropic/claude-haiku-4-5-20251001",  # Default model
            "--jobs-dir", str(task_output_dir),
            "-n", "1",  # Run once
        ]

        # Add timeout multiplier if configured
        if "timeout" in self.run_data.get("config", {}):
            # Harbor uses timeout-multiplier, not timeout
            # Convert seconds to multiplier (Harbor's default timeout varies by task)
            timeout_sec = self.run_data["config"]["timeout"]
            # Use timeout-multiplier of 1.0 and let Harbor respect task's time_limit_sec
            # For now, we'll skip this and let Harbor use task defaults
            pass

        # Prepare environment variables
        env = os.environ.copy()

        # Add any custom environment variables from config
        if "env" in self.run_data.get("config", {}):
            env.update(self.run_data["config"]["env"])

        # Run Harbor
        try:
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(benchmark_path.parent),
                env=env
            )

            # Wait for completion
            stdout, _ = self.current_process.communicate()

            # Save Harbor output for debugging
            log_file = output_dir / f"{task_name}_{agent.replace(':', '_')}_harbor.log"
            log_file.write_text(stdout)

            # Check result
            if self.current_process.returncode == 0:
                # Find result.json
                result_files = list(task_output_dir.rglob("result.json"))

                if result_files:
                    with open(result_files[0]) as f:
                        result_data = json.load(f)

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
                error_lines = [line for line in stdout.split('\n') if 'error' in line.lower() or 'failed' in line.lower()]
                error_snippet = '\n'.join(error_lines[:3]) if error_lines else stdout[:200]

                TaskManager.update_status(
                    self.run_id, task_name, agent, "failed",
                    error_message=f"Harbor exited with code {self.current_process.returncode}. Log: {log_file}. Error: {error_snippet}"
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

    # Generate run_id
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_id = f"{benchmark_name}_{timestamp}"

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
