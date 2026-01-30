#!/usr/bin/env python3
"""
Master orchestration script for LoCoBench data integrity fixes.

This script runs all fixes in the correct dependency order:
1. Adapter fix (already applied manually)
2. Regenerate task environments
3. Initialize git repositories
4. Push to GitHub

Usage:
    ./orchestrate_fixes.py --all
    ./orchestrate_fixes.py --steps regenerate,git,push
    ./orchestrate_fixes.py --dry-run --steps regenerate
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent
CCBENCH_ROOT = Path("/home/stephanie_jarmak/CodeContextBench/benchmarks/locobench_agent")

# Step names
STEP_ADAPTER = "adapter"
STEP_REGENERATE = "regenerate"
STEP_GIT = "git"
STEP_PUSH = "push"

ALL_STEPS = [STEP_ADAPTER, STEP_REGENERATE, STEP_GIT, STEP_PUSH]

# Broken project prefixes from audit
BROKEN_PROJECT_PREFIXES = [
    "cpp_system_security_expert_064",
    "csharp_ml_training_expert_087",
    "python_data_streaming_expert_085",
    "typescript_system_monitoring_expert_061",
    "c_api_microservice_expert_080",
    "rust_ml_computer_vision_expert_054",
    "cpp_web_blog_expert_040",
    "go_ml_nlp_expert_053",
    "javascript_ml_nlp_expert_053",
    "csharp_web_blog_expert_076",
    "rust_data_streaming_expert_013",
    "rust_api_microservice_expert_008",
    "csharp_data_warehouse_expert_012",
    "rust_web_social_expert_073",
    "python_desktop_development_expert_021",
]


class OrchestrationReport:
    """Track execution status and results."""

    def __init__(self):
        self.start_time = datetime.now()
        self.steps_completed: List[str] = []
        self.steps_failed: List[str] = []
        self.step_results: Dict[str, Dict] = {}

    def record_step(self, step: str, success: bool, message: str, details: Optional[Dict] = None):
        """Record the result of a step."""
        if success:
            self.steps_completed.append(step)
        else:
            self.steps_failed.append(step)

        self.step_results[step] = {
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
        }

    def get_summary(self) -> Dict:
        """Get final report summary."""
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "step_results": self.step_results,
        }

    def print_summary(self):
        """Print human-readable summary."""
        logger.info("")
        logger.info("=" * 80)
        logger.info("ORCHESTRATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Start time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {(datetime.now() - self.start_time).total_seconds():.1f}s")
        logger.info("")
        logger.info(f"✓ Steps completed: {len(self.steps_completed)}")
        for step in self.steps_completed:
            logger.info(f"  ✓ {step}: {self.step_results[step]['message']}")
        logger.info("")
        if self.steps_failed:
            logger.info(f"✗ Steps failed: {len(self.steps_failed)}")
            for step in self.steps_failed:
                logger.info(f"  ✗ {step}: {self.step_results[step]['message']}")
        logger.info("=" * 80)


def run_command(
    cmd: List[str],
    cwd: Optional[Path] = None,
    check: bool = True,
    capture_output: bool = True,
) -> Tuple[bool, str, str]:
    """
    Run a shell command and return result.

    Args:
        cmd: Command arguments
        cwd: Working directory
        check: If True, raise exception on non-zero exit
        capture_output: If True, capture stdout/stderr

    Returns:
        Tuple of (success, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=check,
            capture_output=capture_output,
            text=True,
        )
        return True, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        if check:
            raise
        return False, e.stdout or "", e.stderr or ""


def step_check_adapter_fix(dry_run: bool = False) -> Tuple[bool, str, Dict]:
    """
    Step 1: Verify adapter.py fix has been applied.

    The adapter fix was applied manually in US-001, so we just verify it exists.
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 1: Verify Adapter Fix")
    logger.info("=" * 80)

    adapter_path = CCBENCH_ROOT / "adapter.py"

    if not adapter_path.exists():
        return False, f"Adapter not found: {adapter_path}", {}

    # Check for the heuristic-based copy logic added in US-001
    with open(adapter_path, "r") as f:
        content = f.read()

    if "heuristic-based copy logic" in content or "standard dirs" in content:
        msg = "Adapter fix verified (heuristic-based copy logic present)"
        logger.info(f"✓ {msg}")
        return True, msg, {"adapter_path": str(adapter_path)}
    else:
        msg = "Warning: Adapter fix markers not found (may have been applied differently)"
        logger.warning(f"⚠ {msg}")
        return True, msg, {"adapter_path": str(adapter_path)}


def step_regenerate_tasks(
    tasks_dir: Path,
    dry_run: bool = False
) -> Tuple[bool, str, Dict]:
    """
    Step 2: Regenerate task environments using fixed adapter.
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 2: Regenerate Task Environments")
    logger.info("=" * 80)

    regenerate_script = CCBENCH_ROOT / "regenerate_tasks.py"

    if not regenerate_script.exists():
        return False, f"Regenerate script not found: {regenerate_script}", {}

    cmd = [
        sys.executable,
        str(regenerate_script),
        "--tasks_dir", str(tasks_dir),
    ]

    if dry_run:
        cmd.append("--dry-run")

    logger.info(f"Running: {' '.join(cmd)}")

    try:
        success, stdout, stderr = run_command(cmd, check=False)

        # Parse the regeneration report
        report_path = tasks_dir.parent / "regeneration_report.json"
        details = {}
        if report_path.exists() and not dry_run:
            with open(report_path, "r") as f:
                details = json.load(f)

        if success:
            msg = f"Task regeneration completed"
            if details:
                msg += f": {details.get('files_added', 0)} files added"
            logger.info(f"✓ {msg}")
            return True, msg, details
        else:
            msg = f"Task regeneration failed: {stderr}"
            logger.error(f"✗ {msg}")
            return False, msg, {}

    except Exception as e:
        msg = f"Task regeneration error: {str(e)}"
        logger.error(f"✗ {msg}")
        return False, msg, {}


def step_init_git_repos(
    tasks_dir: Path,
    dry_run: bool = False
) -> Tuple[bool, str, Dict]:
    """
    Step 3: Initialize git repositories in task environments.
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 3: Initialize Git Repositories")
    logger.info("=" * 80)

    init_script = SCRIPT_DIR / "init_git_repos.py"

    if not init_script.exists():
        return False, f"Git init script not found: {init_script}", {}

    # Find all task directories
    task_dirs = [d for d in tasks_dir.iterdir() if d.is_dir()]
    logger.info(f"Found {len(task_dirs)} task directories")

    success_count = 0
    failed_count = 0
    failed_tasks = []

    for i, task_dir in enumerate(task_dirs, 1):
        logger.info(f"[{i}/{len(task_dirs)}] Initializing git in {task_dir.name}")

        cmd = [sys.executable, str(init_script), str(task_dir)]
        if dry_run:
            cmd.append("--dry-run")

        try:
            success, stdout, stderr = run_command(cmd, check=False)
            if success:
                success_count += 1
                logger.info(f"  ✓ {stdout.strip()}")
            else:
                failed_count += 1
                failed_tasks.append(task_dir.name)
                logger.error(f"  ✗ {stderr.strip()}")
        except Exception as e:
            failed_count += 1
            failed_tasks.append(task_dir.name)
            logger.error(f"  ✗ Error: {str(e)}")

    details = {
        "total_tasks": len(task_dirs),
        "success_count": success_count,
        "failed_count": failed_count,
        "failed_tasks": failed_tasks,
    }

    if failed_count > 0:
        msg = f"Git initialization partially succeeded: {success_count}/{len(task_dirs)} tasks"
        logger.warning(f"⚠ {msg}")
        return False, msg, details
    else:
        msg = f"Git initialization completed: {success_count}/{len(task_dirs)} tasks"
        logger.info(f"✓ {msg}")
        return True, msg, details


def step_push_to_github(
    tasks_dir: Path,
    project_prefixes: List[str],
    dry_run: bool = False
) -> Tuple[bool, str, Dict]:
    """
    Step 4: Push project trees to GitHub sg-benchmarks organization.
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 4: Push to GitHub")
    logger.info("=" * 80)

    push_script = SCRIPT_DIR / "push_to_github.py"

    if not push_script.exists():
        return False, f"Push script not found: {push_script}", {}

    # Check gh auth
    try:
        run_command(["gh", "auth", "status"], check=True)
    except Exception:
        return False, "gh CLI not authenticated. Run: gh auth login", {}

    success_count = 0
    failed_count = 0
    failed_pushes = []

    # Task variants
    task_variants = [
        "architectural_understanding_expert_01",
        "cross_file_refactoring_expert_01",
        "bug_investigation_expert_01",
    ]

    # Find task directories for each project prefix
    tasks_to_push = []
    for prefix in project_prefixes:
        for variant in task_variants:
            task_id = f"{prefix}_{variant}"
            task_dir = tasks_dir / task_id
            if task_dir.exists():
                project_path = task_dir / "environment" / "project"
                if project_path.exists():
                    tasks_to_push.append((prefix, project_path))
                    break  # Only need to push once per prefix

    logger.info(f"Found {len(tasks_to_push)} projects to push")

    for i, (prefix, project_path) in enumerate(tasks_to_push, 1):
        logger.info(f"[{i}/{len(tasks_to_push)}] Pushing {prefix}")

        cmd = [
            sys.executable,
            str(push_script),
            prefix,
            str(project_path),
        ]
        if dry_run:
            cmd.append("--dry-run")

        try:
            success, stdout, stderr = run_command(cmd, check=False, capture_output=True)
            if success:
                success_count += 1
                logger.info(f"  ✓ {stdout.strip().split(chr(10))[-1]}")
            else:
                failed_count += 1
                failed_pushes.append(prefix)
                logger.error(f"  ✗ {stderr.strip()}")
        except Exception as e:
            failed_count += 1
            failed_pushes.append(prefix)
            logger.error(f"  ✗ Error: {str(e)}")

    details = {
        "total_projects": len(tasks_to_push),
        "success_count": success_count,
        "failed_count": failed_count,
        "failed_pushes": failed_pushes,
    }

    if failed_count > 0:
        msg = f"GitHub push partially succeeded: {success_count}/{len(tasks_to_push)} projects"
        logger.warning(f"⚠ {msg}")
        return False, msg, details
    else:
        msg = f"GitHub push completed: {success_count}/{len(tasks_to_push)} projects"
        logger.info(f"✓ {msg}")
        return True, msg, details


def main(
    tasks_dir: Path,
    steps: List[str],
    dry_run: bool = False,
) -> int:
    """
    Main orchestration logic.

    Args:
        tasks_dir: Directory containing task subdirectories
        steps: List of steps to run
        dry_run: If True, run in dry-run mode

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger.info("=" * 80)
    logger.info("LoCoBench Data Integrity Fixes - Master Orchestration")
    logger.info("=" * 80)
    logger.info(f"Steps to run: {', '.join(steps)}")
    if dry_run:
        logger.info("DRY RUN MODE - No permanent changes will be made")

    report = OrchestrationReport()

    # Execute requested steps in dependency order
    try:
        if STEP_ADAPTER in steps:
            success, message, details = step_check_adapter_fix(dry_run)
            report.record_step(STEP_ADAPTER, success, message, details)
            if not success and not dry_run:
                logger.error(f"Step {STEP_ADAPTER} failed, stopping execution")
                report.print_summary()
                return 1

        if STEP_REGENERATE in steps:
            success, message, details = step_regenerate_tasks(tasks_dir, dry_run)
            report.record_step(STEP_REGENERATE, success, message, details)
            if not success and not dry_run:
                logger.error(f"Step {STEP_REGENERATE} failed, stopping execution")
                report.print_summary()
                return 1

        if STEP_GIT in steps:
            success, message, details = step_init_git_repos(tasks_dir, dry_run)
            report.record_step(STEP_GIT, success, message, details)
            if not success and not dry_run:
                logger.error(f"Step {STEP_GIT} failed, stopping execution")
                report.print_summary()
                return 1

        if STEP_PUSH in steps:
            success, message, details = step_push_to_github(
                tasks_dir, BROKEN_PROJECT_PREFIXES, dry_run
            )
            report.record_step(STEP_PUSH, success, message, details)
            if not success and not dry_run:
                logger.error(f"Step {STEP_PUSH} failed, stopping execution")
                report.print_summary()
                return 1

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        report.print_summary()
        return 1

    # Print summary and save report
    report.print_summary()

    if not dry_run:
        report_path = REPO_ROOT / "orchestration_report.json"
        with open(report_path, "w") as f:
            json.dump(report.get_summary(), f, indent=2)
        logger.info(f"\nDetailed report saved to: {report_path}")

    # Return 0 if all steps succeeded, 1 otherwise
    return 0 if not report.steps_failed else 1


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Master orchestration script for LoCoBench data integrity fixes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all steps
  ./orchestrate_fixes.py --all

  # Run specific steps
  ./orchestrate_fixes.py --steps regenerate,git,push

  # Dry run to see what would happen
  ./orchestrate_fixes.py --all --dry-run

  # Run only git initialization
  ./orchestrate_fixes.py --steps git
        """,
    )

    parser.add_argument(
        "--tasks_dir",
        type=Path,
        default=Path("/home/stephanie_jarmak/CodeContextBench/benchmarks/locobench_agent/tasks"),
        help="Directory containing task subdirectories (default: CCBench tasks dir)",
    )

    step_group = parser.add_mutually_exclusive_group(required=True)
    step_group.add_argument(
        "--all",
        action="store_true",
        help="Run all steps in order",
    )
    step_group.add_argument(
        "--steps",
        type=str,
        help=f"Comma-separated list of steps to run: {','.join(ALL_STEPS)}",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no permanent changes)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Determine which steps to run
    if args.all:
        steps = ALL_STEPS
    else:
        steps = [s.strip() for s in args.steps.split(",")]
        # Validate step names
        invalid_steps = [s for s in steps if s not in ALL_STEPS]
        if invalid_steps:
            print(f"Error: Invalid steps: {', '.join(invalid_steps)}", file=sys.stderr)
            print(f"Valid steps: {', '.join(ALL_STEPS)}", file=sys.stderr)
            sys.exit(1)

    exit_code = main(
        tasks_dir=args.tasks_dir,
        steps=steps,
        dry_run=args.dry_run,
    )

    sys.exit(exit_code)
