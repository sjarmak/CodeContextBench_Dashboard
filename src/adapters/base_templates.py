"""
Base templates for Harbor benchmark adapters.

Provides shared template utilities and base templates that support
verifier type selection (deterministic, agent_judge, hybrid).
"""

from enum import Enum
from typing import Any


class VerifierType(Enum):
    """Supported verifier types for Harbor tasks."""

    DETERMINISTIC = "deterministic"
    AGENT_JUDGE = "agent_judge"
    HYBRID = "hybrid"


def render_template(template: str, context: dict[str, Any]) -> str:
    """
    Render a template by replacing {key} placeholders with values.

    Args:
        template: Template string with {key} placeholders.
        context: Dictionary mapping keys to values.

    Returns:
        Rendered template string.
    """
    result = template
    for key, value in context.items():
        placeholder = f"{{{key}}}"
        result = result.replace(placeholder, str(value))
    return result


class BaseTaskTomlTemplate:
    """
    Base task.toml template with verifier_type support.

    This template provides a foundation that adapters can extend
    to support different verification modes.
    """

    # Template for task.toml with verifier_type support
    TEMPLATE = '''version = "1.0"

[metadata]
author_name = "{adapter_name}"
author_email = "unknown"
task_id = "{task_id}"
{extra_metadata}

[verifier]
timeout_sec = {verifier_timeout}
command = "bash /tests/test.sh"
verifier_type = "{verifier_type}"
{verifier_config}

[agent]
timeout_sec = {agent_timeout}
model_hint = "{model_hint}"

[environment]
build_timeout_sec = {build_timeout}
cpus = {cpus}
memory = "{memory}"
storage = "{storage}"
'''

    @classmethod
    def render(
        cls,
        task_id: str,
        adapter_name: str = "Base Adapter",
        verifier_type: VerifierType = VerifierType.DETERMINISTIC,
        verifier_timeout: float = 600.0,
        agent_timeout: float = 1800.0,
        build_timeout: float = 300.0,
        model_hint: str = "requires-mcp",
        cpus: int = 2,
        memory: str = "8G",
        storage: str = "20G",
        extra_metadata: str = "",
        verifier_config: str = "",
    ) -> str:
        """
        Render the task.toml template.

        Args:
            task_id: Unique task identifier.
            adapter_name: Name of the adapter.
            verifier_type: Type of verification to use.
            verifier_timeout: Verifier timeout in seconds.
            agent_timeout: Agent timeout in seconds.
            build_timeout: Build timeout in seconds.
            model_hint: Hint for model requirements.
            cpus: Number of CPUs to allocate.
            memory: Memory allocation (e.g., "8G").
            storage: Storage allocation (e.g., "20G").
            extra_metadata: Additional metadata fields.
            verifier_config: Additional verifier configuration.

        Returns:
            Rendered task.toml content.
        """
        context = {
            "task_id": task_id,
            "adapter_name": adapter_name,
            "verifier_type": verifier_type.value,
            "verifier_timeout": verifier_timeout,
            "agent_timeout": agent_timeout,
            "build_timeout": build_timeout,
            "model_hint": model_hint,
            "cpus": cpus,
            "memory": memory,
            "storage": storage,
            "extra_metadata": extra_metadata,
            "verifier_config": verifier_config,
        }
        return render_template(cls.TEMPLATE, context)


class BaseVerifyPyTemplate:
    """
    Base verify.py template with agent-as-a-judge support.

    This template provides a verification script that can:
    1. Run deterministic checks (test-based)
    2. Use agent-as-a-judge for LLM evaluation
    3. Combine both in hybrid mode
    """

    # Template for verify.py with verifier_type support
    TEMPLATE = '''#!/usr/bin/env python3
"""
{adapter_name} Verifier

Supports multiple verification modes:
- deterministic: Traditional test-based verification
- agent_judge: LLM-based judgment using evaluation criteria
- hybrid: Combines deterministic and agent-judge scoring
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_ground_truth(path: Path) -> dict[str, Any]:
    """Load ground truth JSON file."""
    if not path.exists():
        return {{"error": f"Ground truth not found: {{path}}"}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_deterministic_verification(
    agent_output_dir: Path,
    ground_truth: dict[str, Any],
) -> dict[str, Any]:
    """
    Run deterministic (test-based) verification.

    Override this function in adapter-specific verify.py.
    """
    # Default implementation - subclasses should override
    return {{
        "score": 0.0,
        "metrics": {{}},
        "error": "Deterministic verification not implemented",
    }}


def run_agent_judge_verification(
    agent_output_dir: Path,
    ground_truth: dict[str, Any],
    instruction_path: Path | None = None,
) -> dict[str, Any]:
    """
    Run agent-as-a-judge verification.
    """
    try:
        # Try to import the verifier
        from src.evaluation.agent_judge_verifier import run_verifier
        from pathlib import Path

        # Create temporary output path
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_output = Path(f.name)

        ground_truth_path = agent_output_dir.parent / "tests" / "ground_truth.json"
        if not ground_truth_path.exists():
            # Try alternative location
            ground_truth_path = agent_output_dir / "ground_truth.json"

        result = run_verifier(
            agent_output_path=agent_output_dir,
            ground_truth_path=ground_truth_path,
            output_path=temp_output,
            instruction_path=instruction_path,
            verifier_type="agent_judge",
        )

        return result.to_reward_json()

    except ImportError:
        return {{
            "score": 0.0,
            "metrics": {{}},
            "error": "agent_judge_verifier module not available",
        }}
    except Exception as e:
        return {{
            "score": 0.0,
            "metrics": {{}},
            "error": f"Agent judge verification failed: {{e}}",
        }}


def run_hybrid_verification(
    agent_output_dir: Path,
    ground_truth: dict[str, Any],
    instruction_path: Path | None = None,
    deterministic_weight: float = 0.5,
    judge_weight: float = 0.5,
) -> dict[str, Any]:
    """
    Run hybrid verification combining deterministic and agent-judge.
    """
    det_result = run_deterministic_verification(agent_output_dir, ground_truth)
    judge_result = run_agent_judge_verification(
        agent_output_dir, ground_truth, instruction_path
    )

    det_score = det_result.get("score", 0.0)
    judge_score = judge_result.get("score", 0.0)

    # Normalize weights
    total_weight = deterministic_weight + judge_weight
    if total_weight > 0:
        det_weight_norm = deterministic_weight / total_weight
        judge_weight_norm = judge_weight / total_weight
    else:
        det_weight_norm = 0.5
        judge_weight_norm = 0.5

    combined_score = (det_weight_norm * det_score) + (judge_weight_norm * judge_score)

    return {{
        "score": round(combined_score, 4),
        "metrics": {{
            "hybrid_mode": True,
            "deterministic_score": det_score,
            "deterministic_weight": det_weight_norm,
            "agent_judge_score": judge_score,
            "agent_judge_weight": judge_weight_norm,
        }},
    }}


def main() -> None:
    parser = argparse.ArgumentParser(description="{adapter_name} Verifier")
    parser.add_argument(
        "--agent-output",
        required=True,
        help="Path to agent output directory",
    )
    parser.add_argument(
        "--ground-truth",
        required=True,
        help="Path to ground truth JSON",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output reward JSON",
    )
    parser.add_argument(
        "--instruction",
        help="Path to instruction.md (optional)",
    )
    parser.add_argument(
        "--verifier-type",
        choices=["deterministic", "agent_judge", "hybrid"],
        default="deterministic",
        help="Type of verification to perform",
    )
    args = parser.parse_args()

    agent_output_dir = Path(args.agent_output)
    ground_truth_path = Path(args.ground_truth)
    output_path = Path(args.output)
    instruction_path = Path(args.instruction) if args.instruction else None

    ground_truth = load_ground_truth(ground_truth_path)
    if "error" in ground_truth:
        result = {{"score": 0.0, "error": ground_truth["error"]}}
        output_path.write_text(json.dumps(result, indent=2))
        print(f"Error: {{ground_truth['error']}}")
        return

    verifier_type = args.verifier_type
    if verifier_type == "agent_judge":
        result = run_agent_judge_verification(
            agent_output_dir, ground_truth, instruction_path
        )
    elif verifier_type == "hybrid":
        result = run_hybrid_verification(
            agent_output_dir, ground_truth, instruction_path
        )
    else:
        result = run_deterministic_verification(agent_output_dir, ground_truth)

    output_path.write_text(json.dumps(result, indent=2))

    print(f"Verification complete:")
    print(f"  Score: {{result.get('score', 0.0)}}")
    if "error" in result:
        print(f"  Error: {{result['error']}}")


if __name__ == "__main__":
    main()
'''

    @classmethod
    def render(cls, adapter_name: str = "Base Adapter") -> str:
        """
        Render the verify.py template.

        Args:
            adapter_name: Name of the adapter.

        Returns:
            Rendered verify.py content.
        """
        return render_template(cls.TEMPLATE, {"adapter_name": adapter_name})


# Verifier type configuration snippets for task.toml
VERIFIER_TYPE_CONFIGS = {
    VerifierType.DETERMINISTIC: "",  # No extra config needed
    VerifierType.AGENT_JUDGE: """# Agent-as-a-judge configuration
model = "claude-sonnet-4-20250514"
min_confidence_threshold = 0.3""",
    VerifierType.HYBRID: """# Hybrid verification configuration
model = "claude-sonnet-4-20250514"
deterministic_weight = 0.5
judge_weight = 0.5""",
}


def get_verifier_config(verifier_type: VerifierType) -> str:
    """
    Get verifier configuration snippet for task.toml.

    Args:
        verifier_type: Type of verification.

    Returns:
        Configuration snippet as string.
    """
    return VERIFIER_TYPE_CONFIGS.get(verifier_type, "")
