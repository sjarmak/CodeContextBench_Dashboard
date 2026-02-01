#!/usr/bin/env python3
"""
Agent-as-a-Judge Verifier for Harbor tasks.

Provides an LLM-based verifier option for Harbor benchmark adapters,
using the AgentJudge to evaluate agent outputs against criteria defined
in ground_truth.json or a dedicated criteria file.

Verifier types:
- deterministic: Traditional test-based verification
- agent_judge: LLM-based judgment using configured criteria
- hybrid: Combines deterministic checks with agent judgment

Usage:
    python agent_judge_verifier.py \
        --agent-output /workspace/output \
        --ground-truth /tests/ground_truth.json \
        --output /tests/reward.json
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class VerifierType(Enum):
    """Supported verifier types for Harbor tasks."""

    DETERMINISTIC = "deterministic"
    AGENT_JUDGE = "agent_judge"
    HYBRID = "hybrid"


@dataclass
class VerifierConfig:
    """Configuration for the agent-as-a-judge verifier."""

    model: str = "claude-sonnet-4-20250514"
    max_output_length: int = 50000
    timeout_seconds: int = 300
    hybrid_deterministic_weight: float = 0.5
    hybrid_judge_weight: float = 0.5
    min_confidence_threshold: float = 0.3

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VerifierConfig":
        """Create from dictionary representation."""
        return cls(
            model=data.get("model", cls.model),
            max_output_length=data.get("max_output_length", cls.max_output_length),
            timeout_seconds=data.get("timeout_seconds", cls.timeout_seconds),
            hybrid_deterministic_weight=data.get(
                "hybrid_deterministic_weight", cls.hybrid_deterministic_weight
            ),
            hybrid_judge_weight=data.get(
                "hybrid_judge_weight", cls.hybrid_judge_weight
            ),
            min_confidence_threshold=data.get(
                "min_confidence_threshold", cls.min_confidence_threshold
            ),
        )


@dataclass
class VerifierResult:
    """
    Result from the agent-as-a-judge verifier.

    Attributes:
        score: Overall score from 0.0 to 1.0
        metrics: Dictionary of evaluation metrics
        judgment: Detailed judgment information (if agent_judge used)
        error: Error message if verification failed
    """

    score: float
    metrics: dict[str, Any] = field(default_factory=dict)
    judgment: dict[str, Any] | None = None
    error: str | None = None

    def to_reward_json(self) -> dict[str, Any]:
        """Convert to Harbor reward.json format."""
        result: dict[str, Any] = {
            "score": round(self.score, 4),
            "metrics": self.metrics,
        }

        if self.judgment:
            result["judgment"] = self.judgment

        if self.error:
            result["error"] = self.error

        return result


def load_ground_truth(ground_truth_path: Path) -> dict[str, Any]:
    """
    Load ground truth file.

    Args:
        ground_truth_path: Path to ground_truth.json.

    Returns:
        Ground truth dictionary.

    Raises:
        FileNotFoundError: If file doesn't exist.
        json.JSONDecodeError: If file is invalid JSON.
    """
    if not ground_truth_path.exists():
        raise FileNotFoundError(f"Ground truth not found: {ground_truth_path}")

    with open(ground_truth_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_criteria(
    ground_truth: dict[str, Any],
    criteria_file: Path | None = None,
) -> list[str]:
    """
    Load evaluation criteria from ground truth or dedicated file.

    Criteria can be specified in multiple formats:
    - ground_truth["evaluation_criteria"]: list of criterion strings
    - ground_truth["criteria"]: list of criterion strings
    - ground_truth["requirements"]: list of dicts with "description" field
    - Dedicated criteria file with "criteria" key

    Args:
        ground_truth: Ground truth dictionary.
        criteria_file: Optional path to dedicated criteria file.

    Returns:
        List of criterion description strings.
    """
    # Check for dedicated criteria file
    if criteria_file and criteria_file.exists():
        with open(criteria_file, "r", encoding="utf-8") as f:
            criteria_data = json.load(f)
            if "criteria" in criteria_data:
                return criteria_data["criteria"]

    # Check ground truth for criteria
    if "evaluation_criteria" in ground_truth:
        return ground_truth["evaluation_criteria"]

    if "criteria" in ground_truth:
        return ground_truth["criteria"]

    # Extract from requirements
    if "requirements" in ground_truth:
        criteria = []
        for req in ground_truth["requirements"]:
            if isinstance(req, dict) and "description" in req:
                criteria.append(req["description"])
            elif isinstance(req, str):
                criteria.append(req)
        if criteria:
            return criteria

    # Default criterion if none specified
    return ["The agent successfully completed the task as described"]


def load_agent_output(
    agent_output_path: Path,
    max_length: int = 50000,
) -> str:
    """
    Load agent output from file or directory.

    Supports:
    - Single file: reads file content
    - Directory: concatenates relevant files (trajectory.json, output.txt, etc.)

    Args:
        agent_output_path: Path to agent output file or directory.
        max_length: Maximum output length to include.

    Returns:
        Agent output as string.
    """
    if not agent_output_path.exists():
        return ""

    output_parts: list[str] = []

    if agent_output_path.is_file():
        content = agent_output_path.read_text(encoding="utf-8", errors="replace")
        return content[:max_length]

    # Directory - look for common output files
    priority_files = [
        "trajectory.json",
        "output.json",
        "output.txt",
        "result.json",
        "agent_output.txt",
        "response.txt",
    ]

    # First check priority files
    for filename in priority_files:
        file_path = agent_output_path / filename
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8", errors="replace")
            output_parts.append(f"=== {filename} ===\n{content}")

    # Then look for any JSON or text files
    if not output_parts:
        for ext in ["*.json", "*.txt", "*.md"]:
            for file_path in agent_output_path.glob(ext):
                if file_path.name not in priority_files:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    output_parts.append(f"=== {file_path.name} ===\n{content}")

    combined = "\n\n".join(output_parts)
    return combined[:max_length]


def load_task_description(
    instruction_path: Path | None = None,
    ground_truth: dict[str, Any] | None = None,
) -> str:
    """
    Load task description from instruction.md or ground truth.

    Args:
        instruction_path: Path to instruction.md file.
        ground_truth: Ground truth dictionary with optional description.

    Returns:
        Task description string.
    """
    # Try instruction.md first
    if instruction_path and instruction_path.exists():
        return instruction_path.read_text(encoding="utf-8", errors="replace")

    # Fall back to ground truth description
    if ground_truth:
        if "task_description" in ground_truth:
            return ground_truth["task_description"]
        if "description" in ground_truth:
            return ground_truth["description"]
        if "instruction" in ground_truth:
            return ground_truth["instruction"]

    return "Complete the assigned task."


class AgentJudgeVerifier:
    """
    Harbor verifier implementation using agent-as-a-judge.

    This verifier uses an LLM to evaluate agent outputs against
    specified criteria, supporting deterministic, agent_judge,
    and hybrid verification modes.
    """

    def __init__(
        self,
        verifier_type: VerifierType = VerifierType.AGENT_JUDGE,
        config: VerifierConfig | None = None,
    ) -> None:
        """
        Initialize the verifier.

        Args:
            verifier_type: Type of verification to perform.
            config: Optional configuration overrides.
        """
        self.verifier_type = verifier_type
        self.config = config or VerifierConfig()
        self._judge: Any = None

    def _get_judge(self) -> Any:
        """Get or create the AgentJudge instance."""
        if self._judge is not None:
            return self._judge

        # Import here to avoid circular dependencies
        from src.evaluation.agent_judge import AgentJudge, HarborResult

        self._judge = AgentJudge(model=self.config.model)
        return self._judge

    def verify(
        self,
        agent_output: str,
        task_description: str,
        criteria: list[str],
        ground_truth: dict[str, Any] | None = None,
        deterministic_result: dict[str, Any] | None = None,
    ) -> VerifierResult:
        """
        Verify agent output against criteria.

        Args:
            agent_output: The agent's output to evaluate.
            task_description: Description of the task.
            criteria: List of evaluation criteria.
            ground_truth: Optional ground truth for reference.
            deterministic_result: Optional result from deterministic verifier.

        Returns:
            VerifierResult with score and details.
        """
        if self.verifier_type == VerifierType.DETERMINISTIC:
            return self._verify_deterministic(deterministic_result)
        elif self.verifier_type == VerifierType.HYBRID:
            return self._verify_hybrid(
                agent_output,
                task_description,
                criteria,
                ground_truth,
                deterministic_result,
            )
        else:
            return self._verify_agent_judge(
                agent_output,
                task_description,
                criteria,
                ground_truth,
            )

    def _verify_deterministic(
        self,
        deterministic_result: dict[str, Any] | None,
    ) -> VerifierResult:
        """Handle deterministic verification (pass-through)."""
        if deterministic_result is None:
            return VerifierResult(
                score=0.0,
                error="No deterministic result provided for deterministic verifier",
            )

        score = deterministic_result.get("score", 0.0)
        return VerifierResult(
            score=float(score),
            metrics=deterministic_result.get("metrics", {}),
        )

    def _verify_agent_judge(
        self,
        agent_output: str,
        task_description: str,
        criteria: list[str],
        ground_truth: dict[str, Any] | None,
    ) -> VerifierResult:
        """Perform agent-as-a-judge verification."""
        if not criteria:
            return VerifierResult(
                score=0.0,
                error="No evaluation criteria provided",
            )

        if not agent_output.strip():
            return VerifierResult(
                score=0.0,
                metrics={"criteria_count": len(criteria)},
                error="No agent output to evaluate",
            )

        try:
            # Import here to avoid circular dependencies
            from src.evaluation.agent_judge import HarborResult

            judge = self._get_judge()

            harbor_result = HarborResult(
                task_id="verification_task",
                task_description=task_description,
                agent_output=agent_output,
                ground_truth=json.dumps(ground_truth) if ground_truth else None,
            )

            judgment = judge.evaluate_result(harbor_result, criteria)

            # Check confidence threshold
            if judgment.confidence < self.config.min_confidence_threshold:
                return VerifierResult(
                    score=judgment.overall_score,
                    metrics={
                        "criteria_count": len(criteria),
                        "confidence": judgment.confidence,
                        "low_confidence": True,
                    },
                    judgment=judgment.to_dict(),
                    error=f"Low confidence judgment ({judgment.confidence:.2f})",
                )

            # Build metrics from judgment
            metrics: dict[str, Any] = {
                "criteria_count": len(criteria),
                "confidence": judgment.confidence,
                "criteria_satisfied": sum(
                    1
                    for rs in judgment.requirement_scores.values()
                    if rs.satisfied
                ),
                "criteria_scores": {
                    k: v.score for k, v in judgment.requirement_scores.items()
                },
            }

            return VerifierResult(
                score=judgment.overall_score,
                metrics=metrics,
                judgment=judgment.to_dict(),
            )

        except ImportError as e:
            return VerifierResult(
                score=0.0,
                error=f"Failed to import agent_judge module: {e}",
            )
        except ValueError as e:
            return VerifierResult(
                score=0.0,
                error=f"Validation error: {e}",
            )
        except RuntimeError as e:
            return VerifierResult(
                score=0.0,
                error=f"LLM evaluation failed: {e}",
            )

    def _verify_hybrid(
        self,
        agent_output: str,
        task_description: str,
        criteria: list[str],
        ground_truth: dict[str, Any] | None,
        deterministic_result: dict[str, Any] | None,
    ) -> VerifierResult:
        """Perform hybrid verification combining deterministic and agent-judge."""
        # Get deterministic score
        det_score = 0.0
        det_metrics: dict[str, Any] = {}
        if deterministic_result:
            det_score = float(deterministic_result.get("score", 0.0))
            det_metrics = deterministic_result.get("metrics", {})

        # Get agent-judge result
        judge_result = self._verify_agent_judge(
            agent_output,
            task_description,
            criteria,
            ground_truth,
        )

        # Compute weighted score
        det_weight = self.config.hybrid_deterministic_weight
        judge_weight = self.config.hybrid_judge_weight

        # Normalize weights
        total_weight = det_weight + judge_weight
        if total_weight > 0:
            det_weight /= total_weight
            judge_weight /= total_weight

        combined_score = (det_weight * det_score) + (judge_weight * judge_result.score)

        # Merge metrics
        metrics: dict[str, Any] = {
            "hybrid_mode": True,
            "deterministic_score": det_score,
            "deterministic_weight": det_weight,
            "agent_judge_score": judge_result.score,
            "agent_judge_weight": judge_weight,
            "deterministic_metrics": det_metrics,
            "agent_judge_metrics": judge_result.metrics,
        }

        return VerifierResult(
            score=combined_score,
            metrics=metrics,
            judgment=judge_result.judgment,
            error=judge_result.error,
        )


def run_verifier(
    agent_output_path: Path,
    ground_truth_path: Path,
    output_path: Path,
    instruction_path: Path | None = None,
    criteria_file: Path | None = None,
    verifier_type: str = "agent_judge",
    deterministic_result_path: Path | None = None,
    model: str | None = None,
) -> VerifierResult:
    """
    Run the agent-as-a-judge verifier.

    Args:
        agent_output_path: Path to agent output file or directory.
        ground_truth_path: Path to ground_truth.json.
        output_path: Path to write reward.json output.
        instruction_path: Optional path to instruction.md.
        criteria_file: Optional path to criteria file.
        verifier_type: Type of verification (deterministic, agent_judge, hybrid).
        deterministic_result_path: Optional path to deterministic verifier result.
        model: Optional LLM model override.

    Returns:
        VerifierResult with score and details.
    """
    # Load ground truth
    try:
        ground_truth = load_ground_truth(ground_truth_path)
    except FileNotFoundError as e:
        result = VerifierResult(score=0.0, error=str(e))
        output_path.write_text(json.dumps(result.to_reward_json(), indent=2))
        return result
    except json.JSONDecodeError as e:
        result = VerifierResult(score=0.0, error=f"Invalid ground truth JSON: {e}")
        output_path.write_text(json.dumps(result.to_reward_json(), indent=2))
        return result

    # Load criteria
    criteria = load_criteria(ground_truth, criteria_file)

    # Load agent output
    config = VerifierConfig()
    if model:
        config.model = model

    agent_output = load_agent_output(agent_output_path, config.max_output_length)

    # Load task description
    task_description = load_task_description(instruction_path, ground_truth)

    # Load deterministic result if provided
    deterministic_result: dict[str, Any] | None = None
    if deterministic_result_path and deterministic_result_path.exists():
        with open(deterministic_result_path, "r", encoding="utf-8") as f:
            deterministic_result = json.load(f)

    # Get verifier configuration from ground truth
    verifier_config = ground_truth.get("verifier_config", {})
    config = VerifierConfig.from_dict(verifier_config)
    if model:
        config.model = model

    # Create and run verifier
    try:
        vtype = VerifierType(verifier_type)
    except ValueError:
        vtype = VerifierType.AGENT_JUDGE

    verifier = AgentJudgeVerifier(verifier_type=vtype, config=config)

    result = verifier.verify(
        agent_output=agent_output,
        task_description=task_description,
        criteria=criteria,
        ground_truth=ground_truth,
        deterministic_result=deterministic_result,
    )

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result.to_reward_json(), indent=2))

    return result


def main() -> None:
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="Agent-as-a-Judge Verifier for Harbor tasks"
    )
    parser.add_argument(
        "--agent-output",
        required=True,
        help="Path to agent output file or directory",
    )
    parser.add_argument(
        "--ground-truth",
        required=True,
        help="Path to ground_truth.json",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output reward.json",
    )
    parser.add_argument(
        "--instruction",
        help="Path to instruction.md (optional)",
    )
    parser.add_argument(
        "--criteria-file",
        help="Path to dedicated criteria file (optional)",
    )
    parser.add_argument(
        "--verifier-type",
        choices=["deterministic", "agent_judge", "hybrid"],
        default="agent_judge",
        help="Type of verification to perform",
    )
    parser.add_argument(
        "--deterministic-result",
        help="Path to deterministic verifier result (for hybrid mode)",
    )
    parser.add_argument(
        "--model",
        help="LLM model to use (default: claude-sonnet-4-20250514)",
    )

    args = parser.parse_args()

    agent_output_path = Path(args.agent_output)
    ground_truth_path = Path(args.ground_truth)
    output_path = Path(args.output)
    instruction_path = Path(args.instruction) if args.instruction else None
    criteria_file = Path(args.criteria_file) if args.criteria_file else None
    deterministic_result_path = (
        Path(args.deterministic_result) if args.deterministic_result else None
    )

    result = run_verifier(
        agent_output_path=agent_output_path,
        ground_truth_path=ground_truth_path,
        output_path=output_path,
        instruction_path=instruction_path,
        criteria_file=criteria_file,
        verifier_type=args.verifier_type,
        deterministic_result_path=deterministic_result_path,
        model=args.model,
    )

    print(f"Verification complete:")
    print(f"  Score: {result.score:.4f}")
    if result.metrics:
        if "confidence" in result.metrics:
            print(f"  Confidence: {result.metrics['confidence']:.2f}")
        if "criteria_count" in result.metrics:
            print(f"  Criteria count: {result.metrics['criteria_count']}")
        if "criteria_satisfied" in result.metrics:
            print(
                f"  Criteria satisfied: {result.metrics['criteria_satisfied']}/{result.metrics['criteria_count']}"
            )
    if result.error:
        print(f"  Error: {result.error}")


if __name__ == "__main__":
    main()
