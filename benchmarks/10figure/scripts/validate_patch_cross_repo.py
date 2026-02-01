#!/usr/bin/env python3
"""
Cross-repo patch validation with per-repo weighted scoring.

Extends the base validate_patch.py with --weights support for cross-repo tasks.
When --weights is provided, scoring is computed per-repo and combined:
  reward = sum(repo_reward * weight)

When --weights is omitted, behavior delegates to the base validator unchanged.

Usage:
  # Single-repo (passthrough to base validator)
  python3 validate_patch_cross_repo.py patch.diff --output result.json

  # Cross-repo with weights
  python3 validate_patch_cross_repo.py patch.diff --output result.json \
    --weights '{"kubernetes": 0.6, "envoy": 0.4}'
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def validate_weights(weights: Dict[str, float]) -> None:
    """Validate that weights sum to 1.0."""
    weight_sum = sum(weights.values())
    if abs(weight_sum - 1.0) > 0.01:
        logger.error(f"Weights sum to {weight_sum}, expected 1.0")
        sys.exit(1)

    for name, w in weights.items():
        if w < 0.0 or w > 1.0:
            logger.error(f"Weight for '{name}' is {w}, must be between 0.0 and 1.0")
            sys.exit(1)


def split_patch_by_repo(
    patch_file: str, repo_names: list[str]
) -> Dict[str, str]:
    """Split a combined patch into per-repo patch files.

    Returns mapping of repo_name -> temp patch file path.
    """
    with open(patch_file) as f:
        patch_content = f.read()

    repo_patches: Dict[str, list[str]] = {name: [] for name in repo_names}
    current_lines: list[str] = []
    current_repo: Optional[str] = None

    for line in patch_content.splitlines(True):
        if line.startswith("diff --git"):
            if current_repo and current_lines:
                repo_patches[current_repo].extend(current_lines)
            current_lines = [line]
            current_repo = None
            for repo_name in repo_names:
                if f"/{repo_name}/" in line or f" {repo_name}/" in line:
                    current_repo = repo_name
                    break
        else:
            current_lines.append(line)

    if current_repo and current_lines:
        repo_patches[current_repo].extend(current_lines)

    result = {}
    for name, lines in repo_patches.items():
        if lines:
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=f"_{name}.patch", delete=False
            )
            tmp.writelines(lines)
            tmp.close()
            result[name] = tmp.name
            logger.info(f"Repo {name}: {len(lines)} lines in patch")
        else:
            logger.info(f"Repo {name}: no changes in patch")

    return result


def run_base_validator(
    patch_file: str,
    output_file: str,
    cwd: str,
    timeout: int = 30,
    validator_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the base validate_patch.py and return its results."""
    if validator_path is None:
        validator_path = os.environ.get(
            "VALIDATOR_PATH", "/10figure/scripts/validate_patch.py"
        )

    cmd = ["python3", validator_path, patch_file, "--output", output_file]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout * 60,
        )

        if result.returncode == 0 and os.path.exists(output_file):
            with open(output_file) as f:
                return json.load(f)
        else:
            logger.error(f"Validator failed (rc={result.returncode}): {result.stderr[:500]}")
            return {"overall_score": 0.0, "error": result.stderr[:500]}

    except subprocess.TimeoutExpired:
        logger.error(f"Validator timed out after {timeout} minutes")
        return {"overall_score": 0.0, "error": "timeout"}
    except Exception as e:
        logger.error(f"Error running validator: {e}")
        return {"overall_score": 0.0, "error": str(e)}


def validate_cross_repo(
    patch_file: str,
    weights: Dict[str, float],
    output_file: str,
    corpus_root: str,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Validate a cross-repo patch with per-repo weighted scoring."""
    validate_weights(weights)

    repo_names = list(weights.keys())
    repo_patch_files = split_patch_by_repo(patch_file, repo_names)

    per_repo_scores: Dict[str, Dict[str, Any]] = {}
    overall_score = 0.0
    temp_files = []

    try:
        for repo_name, weight in weights.items():
            logger.info(f"--- Validating {repo_name} (weight={weight}) ---")

            repo_patch = repo_patch_files.get(repo_name)
            if repo_patch is None:
                logger.info(f"No changes for {repo_name} - score 0.0")
                per_repo_scores[repo_name] = {
                    "score": 0.0,
                    "weight": weight,
                    "weighted_score": 0.0,
                    "error": "no changes for this repo",
                }
                continue

            temp_files.append(repo_patch)
            repo_result_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=f"_{repo_name}_result.json", delete=False
            ).name
            temp_files.append(repo_result_file)

            repo_dir = os.path.join(corpus_root, "src", repo_name)
            if not os.path.isdir(repo_dir):
                repo_dir = corpus_root

            repo_result = run_base_validator(
                repo_patch, repo_result_file, repo_dir, timeout
            )

            score = float(repo_result.get("overall_score") or 0.0)
            weighted = score * weight
            overall_score += weighted

            per_repo_scores[repo_name] = {
                "score": score,
                "weight": weight,
                "weighted_score": round(weighted, 4),
                "details": repo_result.get("task_results", []),
            }
            logger.info(f"  Score: {score}, Weighted: {weighted}")

    finally:
        for tmp in temp_files:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    overall_score = round(overall_score, 4)

    result = {
        "overall_score": overall_score,
        "per_repo_scores": per_repo_scores,
        "weights": weights,
        "patch_file": patch_file,
        "status": "success",
    }

    if output_file:
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Results saved to {output_file}")

    logger.info(f"Overall weighted score: {overall_score}")
    for name, info in per_repo_scores.items():
        logger.info(
            f"  {name}: {info['score']} * {info['weight']} = {info['weighted_score']}"
        )

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate patches with optional per-repo weighted scoring"
    )
    parser.add_argument("patch_file", help="Path to the patch file to validate")
    parser.add_argument("--output", "-o", help="Output file for results (JSON)")
    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=30,
        help="Timeout in minutes (default: 30)",
    )
    parser.add_argument(
        "--weights",
        help='JSON mapping repo name to weight, e.g., \'{"kubernetes": 0.6, "envoy": 0.4}\'',
    )
    parser.add_argument(
        "--corpus-root",
        default=os.environ.get("CORPUS_ROOT", "/10figure"),
        help="Path to corpus root (default: /10figure or $CORPUS_ROOT)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.patch_file):
        logger.error(f"Patch file not found: {args.patch_file}")
        sys.exit(1)

    if args.weights:
        try:
            weights = json.loads(args.weights)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in --weights: {e}")
            sys.exit(1)

        result = validate_cross_repo(
            args.patch_file,
            weights,
            args.output or "/dev/null",
            args.corpus_root,
            args.timeout,
        )
    else:
        # No weights - delegate to base validator (single-repo mode)
        logger.info("No --weights provided, delegating to base validator")
        cwd = args.corpus_root
        if not os.path.exists(os.path.join(cwd, "tasks")):
            cwd = os.getcwd()

        result = run_base_validator(
            args.patch_file,
            args.output or "/dev/stdout",
            cwd,
            args.timeout,
        )

    if "overall_score" in result:
        print(f"\nOverall Score: {result['overall_score']:.4f}")
        if "per_repo_scores" in result:
            print("Per-repo breakdown:")
            for name, info in result["per_repo_scores"].items():
                print(
                    f"  {name}: {info['score']} * {info['weight']} = {info['weighted_score']}"
                )


if __name__ == "__main__":
    main()
