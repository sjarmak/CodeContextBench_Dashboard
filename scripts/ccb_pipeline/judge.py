"""
LLM judge pipeline step.

Runs LLM judge evaluation with a 3-model voting ensemble on trial outputs.
Reads experiment_metrics.json and augments it with judge_scores per trial.

Usage:
    python -m scripts.ccb_pipeline.judge --input experiment_metrics.json --runs-dir <path>
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_INITIAL_BACKOFF_SECONDS = 2.0
_MAX_SOLUTION_CHARS = 20_000
_MAX_TASK_DESC_CHARS = 2_000

# Default rubric templates keyed by benchmark type pattern
_DEFAULT_RUBRIC: dict[str, list[str]] = {
    "swe": ["correctness", "code_quality"],
    "locobench": ["correctness", "completeness", "code_quality"],
    "default": ["correctness", "completeness"],
}


# ---------------------------------------------------------------------------
# Data structures (frozen / immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JudgeVote:
    """Single vote from one judge model on one dimension."""

    model: str
    dimension: str
    score: float  # 0.0, 0.5, 1.0
    score_label: str  # "pass", "partial", "fail"
    reasoning: str


@dataclass(frozen=True)
class DimensionScore:
    """Aggregated score for a single dimension across judge votes."""

    dimension: str
    score: float
    score_label: str
    reasoning: str
    vote_distribution: tuple[tuple[str, int], ...]
    confidence: float
    num_rounds: int


@dataclass(frozen=True)
class TrialJudgeResult:
    """Judge evaluation result for a single trial."""

    trial_id: str
    task_name: str
    dimensions: tuple[DimensionScore, ...]
    mean_score: float
    overall_quality: str  # "pass", "partial", "fail"
    error: str | None = None


# ---------------------------------------------------------------------------
# Rubric selection
# ---------------------------------------------------------------------------


def _select_dimensions(benchmark: str, template_path: Path | None) -> list[str]:
    """Select evaluation dimensions based on benchmark type or custom template."""
    if template_path is not None and template_path.is_file():
        try:
            template_data = json.loads(template_path.read_text(encoding="utf-8"))
            dims = template_data.get("dimensions")
            if isinstance(dims, list) and len(dims) > 0:
                return [str(d) for d in dims]
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load judge template %s: %s", template_path, exc)

    benchmark_lower = benchmark.lower() if benchmark else ""
    for pattern, dims in _DEFAULT_RUBRIC.items():
        if pattern != "default" and pattern in benchmark_lower:
            return list(dims)
    return list(_DEFAULT_RUBRIC["default"])


# ---------------------------------------------------------------------------
# Trial data extraction helpers
# ---------------------------------------------------------------------------


def _load_solution_text(trial_dir: Path) -> str:
    """Load agent solution text from trial directory.

    Checks for:
    1. agent/solution.md
    2. agent/claude-code.txt (JSONL transcript - extract assistant messages)
    3. submission/diff.patch or any .patch file
    """
    # Try solution.md first
    solution_md = trial_dir / "agent" / "solution.md"
    if solution_md.is_file():
        text = solution_md.read_text(encoding="utf-8", errors="replace")
        return text[:_MAX_SOLUTION_CHARS]

    # Try claude-code.txt (JSONL) - extract assistant content
    transcript = trial_dir / "agent" / "claude-code.txt"
    if transcript.is_file():
        return _extract_assistant_content(transcript)

    # Try diff/patch files
    for pattern in ("submission/diff.patch", "submission/*.patch"):
        matches = list(trial_dir.glob(pattern))
        if matches:
            text = matches[0].read_text(encoding="utf-8", errors="replace")
            return text[:_MAX_SOLUTION_CHARS]

    return ""


def _extract_assistant_content(transcript_path: Path) -> str:
    """Extract assistant message content from claude-code.txt JSONL."""
    lines_out: list[str] = []
    char_count = 0
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                if char_count >= _MAX_SOLUTION_CHARS:
                    break
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                # Look for assistant messages with text content
                if event.get("type") == "assistant" or event.get("source") == "agent":
                    content = event.get("content")
                    if isinstance(content, str):
                        lines_out.append(content)
                        char_count += len(content)
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text = item.get("text", "")
                                lines_out.append(text)
                                char_count += len(text)
    except OSError as exc:
        logger.warning("Failed to read transcript %s: %s", transcript_path, exc)

    combined = "\n".join(lines_out)
    return combined[:_MAX_SOLUTION_CHARS]


def _load_task_description(trial_dir: Path) -> str:
    """Load task description from trial config or instruction files."""
    # Try config.json for task description
    config_json = trial_dir / "config.json"
    if config_json.is_file():
        try:
            config = json.loads(config_json.read_text(encoding="utf-8"))
            task_data = config.get("task") or {}
            desc = task_data.get("description", "")
            if desc:
                return str(desc)[:_MAX_TASK_DESC_CHARS]
        except (json.JSONDecodeError, OSError):
            pass

    # Try instruction files in task subdirectory
    for subdir in (trial_dir, trial_dir / "task"):
        if not subdir.is_dir():
            continue
        for filename in ("instruction.md", "TASK.md", "prompt.md", "task.md"):
            fpath = subdir / filename
            if fpath.is_file():
                text = fpath.read_text(encoding="utf-8", errors="replace")
                return text[:_MAX_TASK_DESC_CHARS]

    return "Task description not available"


# ---------------------------------------------------------------------------
# LLM judge invocation with retry
# ---------------------------------------------------------------------------


def _call_judge_llm(
    client: object,
    model: str,
    prompt: str,
    max_tokens: int = 2000,
) -> dict:
    """Call an Anthropic LLM and parse JSON response with retry + backoff.

    Returns parsed dict on success, or a fallback error dict.
    """
    backoff = _INITIAL_BACKOFF_SECONDS
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            response = client.messages.create(  # type: ignore[attr-defined]
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            text: str = response.content[0].text  # type: ignore[index]
            return _parse_json_response(text)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "Judge LLM call attempt %d/%d failed: %s",
                attempt + 1,
                _MAX_RETRIES,
                exc,
            )
            if attempt < _MAX_RETRIES - 1:
                time.sleep(backoff)
                backoff *= 2

    return {
        "score": "fail",
        "reasoning": f"All {_MAX_RETRIES} attempts failed: {last_exc}",
        "strengths": [],
        "weaknesses": ["Evaluation error - API call failed"],
    }


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences."""
    # Strip markdown code fences
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]

    try:
        return json.loads(text.strip())  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        pass

    # Fallback: try to find a JSON object in the text
    import re

    json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    return {
        "score": "fail",
        "reasoning": f"JSON parsing failed. Response preview: {text[:200]}",
        "strengths": [],
        "weaknesses": ["Evaluation error - malformed JSON response"],
    }


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_JUDGE_PROMPT = """You are an expert evaluator assessing an AI coding agent's output.

## Task Description
{task_description}

## Agent's Solution
{solution_text}

## Verifier Reward
{reward}

## Evaluation Dimension: {dimension}

{dimension_instructions}

Respond with valid JSON only (escape all quotes and special characters):
{{
    "score": "pass" | "partial" | "fail",
    "reasoning": "<2-3 sentences>",
    "strengths": ["<strength>"],
    "weaknesses": ["<weakness>"]
}}
"""

_DIMENSION_INSTRUCTIONS: dict[str, str] = {
    "correctness": (
        "Does the solution correctly address the task requirements?\n"
        "- **pass**: Solution correctly addresses the core issue\n"
        "- **partial**: Solution addresses part of the issue but has gaps\n"
        "- **fail**: Solution does not address the issue or is incorrect"
    ),
    "completeness": (
        "Does the solution fully address all aspects of the task?\n"
        "- **pass**: All major aspects covered\n"
        "- **partial**: Some aspects covered but notable gaps remain\n"
        "- **fail**: Most aspects missing"
    ),
    "code_quality": (
        "Is the code clean, idiomatic, and well-structured?\n"
        "- **pass**: Code is clean, idiomatic, and well-structured\n"
        "- **partial**: Code works but has quality issues\n"
        "- **fail**: Code has significant quality problems"
    ),
    "retrieval": (
        "Did the agent effectively search for and find relevant code?\n"
        "- **pass**: Effective search strategy, found relevant code\n"
        "- **partial**: Found some relevant code but missed key areas\n"
        "- **fail**: Poor search strategy or found wrong code"
    ),
    "mcp_effectiveness": (
        "Did the agent effectively use MCP/Sourcegraph tools?\n"
        "- **pass**: Good use of MCP tools, efficient searches\n"
        "- **partial**: Some MCP tool use, but inefficient or incomplete\n"
        "- **fail**: No/poor MCP tool use"
    ),
}

_SCORE_MAP: dict[str, tuple[float, str]] = {
    "pass": (1.0, "pass"),
    "full": (1.0, "pass"),
    "effective": (1.0, "pass"),
    "1": (1.0, "pass"),
    "1.0": (1.0, "pass"),
    "partial": (0.5, "partial"),
    "partially": (0.5, "partial"),
    "partially_effective": (0.5, "partial"),
    "0.5": (0.5, "partial"),
    "fail": (0.0, "fail"),
    "ineffective": (0.0, "fail"),
    "0": (0.0, "fail"),
    "0.0": (0.0, "fail"),
}


def _normalize_score(raw: str) -> tuple[float, str]:
    """Normalize a raw score string to (numeric, label)."""
    key = raw.lower().strip()
    return _SCORE_MAP.get(key, (0.0, "fail"))


def _build_prompt(
    task_description: str,
    solution_text: str,
    reward: float | None,
    dimension: str,
) -> str:
    """Build evaluation prompt for a single dimension."""
    dim_instructions = _DIMENSION_INSTRUCTIONS.get(
        dimension,
        _DIMENSION_INSTRUCTIONS["correctness"],
    )
    return _JUDGE_PROMPT.format(
        task_description=task_description[:_MAX_TASK_DESC_CHARS],
        solution_text=solution_text[:_MAX_SOLUTION_CHARS],
        reward=reward if reward is not None else "N/A",
        dimension=dimension,
        dimension_instructions=dim_instructions,
    )


# ---------------------------------------------------------------------------
# Core judge evaluation
# ---------------------------------------------------------------------------


def _evaluate_dimension(
    client: object,
    models: tuple[str, ...],
    task_description: str,
    solution_text: str,
    reward: float | None,
    dimension: str,
    rounds_per_model: int,
) -> DimensionScore:
    """Evaluate a single dimension using multi-model voting ensemble.

    Each model in *models* is called *rounds_per_model* times.
    Majority vote determines the final score.
    """
    prompt = _build_prompt(task_description, solution_text, reward, dimension)

    votes: list[JudgeVote] = []
    for model in models:
        for _ in range(rounds_per_model):
            result = _call_judge_llm(client, model, prompt)
            score_raw = result.get("score", "fail")
            score_val, score_label = _normalize_score(str(score_raw))
            votes.append(
                JudgeVote(
                    model=model,
                    dimension=dimension,
                    score=score_val,
                    score_label=score_label,
                    reasoning=result.get("reasoning", ""),
                )
            )

    # Majority vote
    score_counts: dict[float, int] = {}
    for v in votes:
        score_counts[v.score] = score_counts.get(v.score, 0) + 1

    final_score = max(score_counts, key=lambda s: score_counts[s])
    final_label = {1.0: "pass", 0.5: "partial", 0.0: "fail"}.get(
        final_score, "fail"
    )
    confidence = score_counts[final_score] / len(votes) if votes else 0.0

    # Pick the longest reasoning from the majority
    majority_reasoning = [v.reasoning for v in votes if v.score == final_score]
    best_reasoning = max(majority_reasoning, key=len) if majority_reasoning else ""

    vote_dist = tuple(sorted(
        ((f"{s:.1f}", c) for s, c in score_counts.items()),
        key=lambda x: x[0],
    ))

    return DimensionScore(
        dimension=dimension,
        score=final_score,
        score_label=final_label,
        reasoning=best_reasoning,
        vote_distribution=vote_dist,
        confidence=confidence,
        num_rounds=len(votes),
    )


def evaluate_trial(
    client: object,
    models: tuple[str, ...],
    trial: dict,
    runs_dir: Path | None,
    dimensions: list[str],
    rounds_per_model: int,
) -> TrialJudgeResult:
    """Evaluate a single trial with the judge ensemble.

    Returns a TrialJudgeResult with scores per dimension.
    """
    trial_id = trial.get("trial_id", "unknown")
    task_name = trial.get("task_name", "unknown")
    reward = trial.get("reward")

    # Load solution text
    solution_text = ""
    if runs_dir is not None:
        trial_dir = _find_trial_dir(runs_dir, trial_id)
        if trial_dir is not None:
            solution_text = _load_solution_text(trial_dir)
            if not solution_text:
                task_desc = _load_task_description(trial_dir)
            else:
                task_desc = _load_task_description(trial_dir)
        else:
            task_desc = task_name
    else:
        task_desc = task_name

    if not task_desc:
        task_desc = task_name

    if not solution_text:
        return TrialJudgeResult(
            trial_id=trial_id,
            task_name=task_name,
            dimensions=(),
            mean_score=0.0,
            overall_quality="fail",
            error="No solution text found for trial",
        )

    # Evaluate each dimension
    dim_scores: list[DimensionScore] = []
    for dim in dimensions:
        try:
            dim_score = _evaluate_dimension(
                client=client,
                models=models,
                task_description=task_desc,
                solution_text=solution_text,
                reward=reward,
                dimension=dim,
                rounds_per_model=rounds_per_model,
            )
            dim_scores.append(dim_score)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to evaluate dimension %s for trial %s: %s",
                dim,
                trial_id,
                exc,
            )

    # Compute summary
    if dim_scores:
        mean_score = sum(d.score for d in dim_scores) / len(dim_scores)
        if mean_score >= 0.75:
            overall = "pass"
        elif mean_score >= 0.25:
            overall = "partial"
        else:
            overall = "fail"
    else:
        mean_score = 0.0
        overall = "fail"

    return TrialJudgeResult(
        trial_id=trial_id,
        task_name=task_name,
        dimensions=tuple(dim_scores),
        mean_score=mean_score,
        overall_quality=overall,
    )


def _find_trial_dir(runs_dir: Path, trial_id: str) -> Path | None:
    """Search for a trial directory by its ID under runs_dir."""
    # Trial ID is typically the directory name
    for candidate in runs_dir.rglob(trial_id):
        if candidate.is_dir() and (candidate / "result.json").is_file():
            return candidate

    # Fallback: search for directories containing result.json with matching name
    for result_json in runs_dir.rglob("result.json"):
        if result_json.parent.name == trial_id:
            return result_json.parent

    return None


# ---------------------------------------------------------------------------
# Flatten / augment helpers
# ---------------------------------------------------------------------------


def _flatten_trials(categories: list[dict]) -> list[dict]:
    """Flatten nested categories/experiments/trials into flat list."""
    trials: list[dict] = []
    for category in categories:
        for experiment in category.get("experiments", []):
            for trial in experiment.get("trials", []):
                trials.append(trial)
    return trials


def _augment_metrics(
    categories: list[dict],
    judge_results: dict[str, TrialJudgeResult],
) -> list[dict]:
    """Return a new categories list with judge_scores added to each trial.

    Does NOT mutate the input; builds new dicts following immutability rules.
    """
    new_categories: list[dict] = []
    for category in categories:
        new_experiments: list[dict] = []
        for experiment in category.get("experiments", []):
            new_trials: list[dict] = []
            for trial in experiment.get("trials", []):
                tid = trial.get("trial_id", "")
                result = judge_results.get(tid)
                if result is not None:
                    judge_scores = {
                        "mean_score": result.mean_score,
                        "overall_quality": result.overall_quality,
                        "dimensions": [asdict(d) for d in result.dimensions],
                        "error": result.error,
                    }
                    new_trial = {**trial, "judge_scores": judge_scores}
                else:
                    new_trial = {**trial}
                new_trials.append(new_trial)
            new_experiments.append({**experiment, "trials": new_trials})
        new_categories.append({**category, "experiments": new_experiments})
    return new_categories


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------


def run_judge(
    categories: list[dict],
    runs_dir: Path | None,
    models: tuple[str, ...] = ("anthropic/claude-haiku-4-5-20251001",),
    rounds_per_model: int = 3,
    template_path: Path | None = None,
) -> list[dict]:
    """Run the LLM judge pipeline on experiment_metrics categories.

    Returns a new categories list with judge_scores field added to each trial.
    """
    try:
        import anthropic as _anthropic
    except ImportError as exc:
        raise ImportError(
            "anthropic package required for judge pipeline. Run: pip install anthropic"
        ) from exc

    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is required for the judge pipeline"
        )

    client = _anthropic.Anthropic(api_key=api_key)

    all_trials = _flatten_trials(categories)
    total = len(all_trials)
    logger.info("Running judge evaluation on %d trials", total)

    judge_results: dict[str, TrialJudgeResult] = {}
    for idx, trial in enumerate(all_trials, 1):
        trial_id = trial.get("trial_id", f"unknown_{idx}")
        benchmark = trial.get("benchmark", "")
        dimensions = _select_dimensions(benchmark, template_path)

        logger.info(
            "Judging trial %d/%d: %s [%s]",
            idx,
            total,
            trial_id,
            ", ".join(dimensions),
        )

        try:
            result = evaluate_trial(
                client=client,
                models=models,
                trial=trial,
                runs_dir=runs_dir,
                dimensions=dimensions,
                rounds_per_model=rounds_per_model,
            )
            judge_results[trial_id] = result

            if result.error:
                logger.warning("Trial %s judge error: %s", trial_id, result.error)
            else:
                logger.info(
                    "Trial %s: mean_score=%.2f quality=%s",
                    trial_id,
                    result.mean_score,
                    result.overall_quality,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Judge failed for trial %s, continuing: %s", trial_id, exc
            )
            judge_results[trial_id] = TrialJudgeResult(
                trial_id=trial_id,
                task_name=trial.get("task_name", "unknown"),
                dimensions=(),
                mean_score=0.0,
                overall_quality="fail",
                error=str(exc),
            )

    return _augment_metrics(categories, judge_results)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the judge pipeline."""
    parser = argparse.ArgumentParser(
        description="Run LLM judge evaluation on experiment metrics.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to experiment_metrics.json from the extract step",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=None,
        help="Path to runs directory for loading trial solution files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path (default: overwrites --input in place)",
    )
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="Skip judge evaluation (copy input to output unchanged)",
    )
    parser.add_argument(
        "--judge-template",
        type=Path,
        default=None,
        help="Path to custom judge template JSON (overrides default rubric)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="Number of voting rounds per model (default: 3)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    input_path: Path = args.input
    output_path: Path = args.output if args.output else input_path

    if not input_path.is_file():
        logger.error("Input file does not exist: %s", input_path)
        return 1

    try:
        categories = json.loads(input_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read input: %s", exc)
        return 1

    if args.skip_judge:
        logger.info("Judge evaluation skipped (--skip-judge)")
        if output_path != input_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(categories, indent=2, default=str),
                encoding="utf-8",
            )
        return 0

    # Default models for the 3-model voting ensemble
    # The PRD says GPT-5.2, Claude Sonnet, Gemini but we only have Anthropic
    # client available. Use 3 rounds of a single model as the ensemble.
    models = ("anthropic/claude-haiku-4-5-20251001",)

    try:
        augmented = run_judge(
            categories=categories,
            runs_dir=args.runs_dir,
            models=models,
            rounds_per_model=args.rounds,
            template_path=args.judge_template,
        )
    except (ImportError, ValueError) as exc:
        logger.error("Judge pipeline failed: %s", exc)
        return 1

    # Count results
    total_judged = 0
    total_errors = 0
    for cat in augmented:
        for exp in cat.get("experiments", []):
            for trial in exp.get("trials", []):
                js = trial.get("judge_scores")
                if js is not None:
                    total_judged += 1
                    if js.get("error"):
                        total_errors += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(augmented, indent=2, default=str),
        encoding="utf-8",
    )

    logger.info(
        "Judge complete: %d trials judged (%d errors) -> %s",
        total_judged,
        total_errors,
        output_path,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
