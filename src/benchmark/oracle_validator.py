"""
Oracle Validator

Runs Harbor validation using the oracle/solution provided with tasks.
This validates that the task and validator work correctly.

See: https://harborframework.com/docs/adapters#24-running-harbor-harness
"""

import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import json


def run_oracle_validation(
    task_path: Path,
    timeout_sec: int = 300
) -> Dict[str, Any]:
    """
    Run oracle validation for a task using Harbor.

    Args:
        task_path: Path to task directory
        timeout_sec: Timeout in seconds

    Returns:
        Dictionary with validation results
    """
    result = {
        "task_path": str(task_path),
        "validated_at": datetime.utcnow().isoformat() + "Z",
        "status": "unknown",
        "reward": None,
        "error": None,
        "output": "",
    }

    if not task_path.exists():
        result["status"] = "error"
        result["error"] = f"Task path does not exist: {task_path}"
        return result

    # Check for task.toml
    task_toml = task_path / "task.toml"
    if not task_toml.exists():
        result["status"] = "error"
        result["error"] = "No task.toml found"
        return result

    # Run Harbor with oracle agent
    # harbor run --path <task-path> --agent oracle -n 1
    cmd = [
        "harbor",
        "run",
        "--path", str(task_path),
        "--agent", "oracle",
        "-n", "1",  # Run once
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec + 30,  # Add buffer to subprocess timeout
            cwd=str(task_path.parent.parent)  # Run from benchmarks root
        )

        result["output"] = proc.stdout + "\n" + proc.stderr
        result["exit_code"] = proc.returncode

        if proc.returncode == 0:
            result["status"] = "passed"
            result["reward"] = 1.0

            # Try to parse result.json if available
            # Harbor oracle runs may output results
            result_json_pattern = task_path.parent.parent / "jobs" / "*" / "result.json"
            import glob
            result_files = sorted(glob.glob(str(result_json_pattern)), key=lambda x: Path(x).stat().st_mtime, reverse=True)

            if result_files:
                try:
                    with open(result_files[0]) as f:
                        harbor_result = json.load(f)
                        verifier_result = harbor_result.get("verifier_result", {})
                        rewards = verifier_result.get("rewards", {})
                        result["reward"] = rewards.get("reward", 1.0)
                except Exception:
                    pass  # Ignore parsing errors

        else:
            result["status"] = "failed"
            result["reward"] = 0.0
            result["error"] = f"Oracle validation failed with exit code {proc.returncode}"

    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
        result["error"] = f"Oracle validation timed out after {timeout_sec}s"

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


def validate_task_structure(task_path: Path) -> Dict[str, Any]:
    """
    Validate task structure without running.

    Checks for required files and structure.

    Returns:
        Dictionary with validation results
    """
    result = {
        "task_path": str(task_path),
        "valid": False,
        "errors": [],
        "warnings": [],
    }

    if not task_path.exists():
        result["errors"].append("Task directory does not exist")
        return result

    # Check for required files
    required_files = ["task.toml"]
    for filename in required_files:
        if not (task_path / filename).exists():
            result["errors"].append(f"Missing required file: {filename}")

    # Check for common instruction files
    instruction_files = ["instruction.md", "TASK.md", "prompt.md", "README.md"]
    has_instruction = any((task_path / f).exists() for f in instruction_files)

    if not has_instruction:
        result["warnings"].append("No instruction file found (instruction.md, TASK.md, etc.)")

    # Check for environment
    if (task_path / "environment").exists():
        result["has_environment"] = True
    else:
        result["warnings"].append("No environment directory found")

    # If no errors, it's valid
    result["valid"] = len(result["errors"]) == 0

    return result
