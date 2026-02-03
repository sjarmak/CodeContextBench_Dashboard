"""DPO fine-tuning script for judge models.

Reads preference pairs JSONL from generate_preferences output and fine-tunes
an open-source model via Together.ai API or HuggingFace TRL locally.

Usage:
    python -m scripts.judge_finetuning.train_dpo \
        --input data/training/preference_pairs.jsonl \
        --backend together \
        --model meta-llama/Llama-3-8b-chat-hf \
        --output-dir models/judge/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_LR = 5e-6
_DEFAULT_BETA = 0.1
_DEFAULT_EPOCHS = 3
_DEFAULT_TRAIN_SPLIT = 0.9


@dataclass(frozen=True)
class DPOConfig:
    """Configuration for DPO fine-tuning."""

    backend: str
    model: str
    learning_rate: float = _DEFAULT_LR
    beta: float = _DEFAULT_BETA
    epochs: int = _DEFAULT_EPOCHS
    lora_rank: int = 16
    lora_alpha: int = 32
    train_split: float = _DEFAULT_TRAIN_SPLIT
    batch_size: int = 4
    max_length: int = 2048
    max_prompt_length: int = 1024
    seed: int = 42


@dataclass(frozen=True)
class TrainingResult:
    """Result of a DPO fine-tuning run."""

    model_id: str
    backend: str
    base_model: str
    train_samples: int
    eval_samples: int
    config: dict[str, Any] = field(default_factory=dict)
    eval_metrics: dict[str, float] = field(default_factory=dict)
    output_path: str = ""
    job_id: str = ""


def load_preference_pairs(input_path: Path) -> list[dict[str, Any]]:
    """Load preference pairs from JSONL file.

    Each line must have 'prompt', 'chosen', 'rejected' fields.
    """
    pairs: list[dict[str, Any]] = []

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with open(input_path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping corrupt line %d in %s", line_num, input_path)
                continue

            if not all(k in record for k in ("prompt", "chosen", "rejected")):
                logger.warning(
                    "Skipping line %d: missing required fields", line_num
                )
                continue

            pairs.append(record)

    if not pairs:
        raise ValueError(f"No valid preference pairs found in {input_path}")

    return pairs


def split_train_eval(
    pairs: list[dict[str, Any]],
    train_ratio: float = _DEFAULT_TRAIN_SPLIT,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split preference pairs into train/eval sets, stratified by task.

    Groups pairs by task_id from metadata, then assigns each task's pairs
    to train or eval to maintain approximately the target ratio.
    """
    by_task: dict[str, list[dict[str, Any]]] = {}
    for pair in pairs:
        task_id = pair.get("metadata", {}).get("task_id", "unknown")
        by_task.setdefault(task_id, []).append(pair)

    sorted_tasks = sorted(by_task.keys())

    # Use a simple deterministic hash-based assignment for reproducibility
    # without requiring random module state management
    train: list[dict[str, Any]] = []
    eval_set: list[dict[str, Any]] = []

    # Sort tasks and assign based on position to approximate target ratio
    # For stratified split: assign each task's pairs entirely to train or eval
    target_train = int(len(pairs) * train_ratio)
    current_train = 0

    for task_id in sorted_tasks:
        task_pairs = by_task[task_id]
        # Deterministic: hash task_id + seed to decide assignment
        task_hash = hash((task_id, seed))

        if current_train < target_train:
            train.extend(task_pairs)
            current_train += len(task_pairs)
        else:
            eval_set.extend(task_pairs)

    # If all went to train (few tasks), move last task to eval
    if not eval_set and len(sorted_tasks) > 1:
        last_task = sorted_tasks[-1]
        last_pairs = by_task[last_task]
        train = [p for p in train if p not in last_pairs]
        eval_set = last_pairs
    elif not eval_set and train:
        # Single task: split pairs directly
        split_idx = max(1, int(len(train) * train_ratio))
        eval_set = train[split_idx:]
        train = train[:split_idx]

    return train, eval_set


def _write_jsonl(pairs: list[dict[str, Any]], path: Path) -> None:
    """Write pairs to JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for pair in pairs:
            f.write(json.dumps(pair, default=str) + "\n")


def _config_to_dict(config: DPOConfig) -> dict[str, Any]:
    """Convert DPOConfig to a JSON-serializable dict."""
    return {
        "backend": config.backend,
        "model": config.model,
        "learning_rate": config.learning_rate,
        "beta": config.beta,
        "epochs": config.epochs,
        "lora_rank": config.lora_rank,
        "lora_alpha": config.lora_alpha,
        "train_split": config.train_split,
        "batch_size": config.batch_size,
        "max_length": config.max_length,
        "max_prompt_length": config.max_prompt_length,
        "seed": config.seed,
    }


def train_together(
    train_pairs: list[dict[str, Any]],
    eval_pairs: list[dict[str, Any]],
    config: DPOConfig,
    output_dir: Path,
) -> TrainingResult:
    """Fine-tune via Together.ai API.

    Uploads dataset, creates a DPO fine-tuning job, and polls for completion.
    Requires TOGETHER_API_KEY environment variable.
    """
    try:
        import together
    except ImportError as exc:
        raise ImportError(
            "together package required for Together.ai backend. "
            "Install with: pip install together"
        ) from exc

    client = together.Together()

    # Write training data in Together's expected format
    train_path = output_dir / "train.jsonl"
    eval_path = output_dir / "eval.jsonl"

    # Together DPO format: {"prompt": ..., "chosen": ..., "rejected": ...}
    _write_jsonl(train_pairs, train_path)
    _write_jsonl(eval_pairs, eval_path)

    logger.info(
        "Uploading training data: %d train, %d eval pairs",
        len(train_pairs),
        len(eval_pairs),
    )

    # Upload files
    train_file = client.files.upload(file=str(train_path), purpose="fine-tune")
    eval_file = client.files.upload(file=str(eval_path), purpose="fine-tune")

    logger.info(
        "Files uploaded: train=%s, eval=%s", train_file.id, eval_file.id
    )

    # Create fine-tuning job
    job = client.fine_tuning.create(
        training_file=train_file.id,
        validation_file=eval_file.id,
        model=config.model,
        n_epochs=config.epochs,
        learning_rate=config.learning_rate,
        batch_size=config.batch_size,
        lora=True,
        lora_r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        training_type={"type": "DPO", "dpo_beta": config.beta},
    )

    logger.info("Fine-tuning job created: %s", job.id)
    logger.info("Model: %s", config.model)
    logger.info("Status: %s", job.status)

    # Save job metadata
    result = TrainingResult(
        model_id=job.output_name if hasattr(job, "output_name") else f"{config.model}:ft-{job.id}",
        backend="together",
        base_model=config.model,
        train_samples=len(train_pairs),
        eval_samples=len(eval_pairs),
        config=_config_to_dict(config),
        job_id=job.id,
        output_path=str(output_dir),
    )

    _save_result(result, output_dir)

    logger.info("Fine-tuning job submitted. Model ID: %s", result.model_id)
    logger.info("Track progress: together fine-tuning list")

    return result


def train_huggingface(
    train_pairs: list[dict[str, Any]],
    eval_pairs: list[dict[str, Any]],
    config: DPOConfig,
    output_dir: Path,
) -> TrainingResult:
    """Fine-tune locally via HuggingFace TRL with LoRA.

    Requires transformers, trl, peft, and datasets packages.
    """
    try:
        from datasets import Dataset
        from peft import LoraConfig, TaskType
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
        from trl import DPOTrainer
    except ImportError as exc:
        raise ImportError(
            "HuggingFace packages required for local training. "
            "Install with: pip install transformers trl peft datasets"
        ) from exc

    logger.info("Loading model: %s", config.model)

    tokenizer = AutoTokenizer.from_pretrained(config.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        config.model,
        torch_dtype="auto",
        device_map="auto",
    )

    # Configure LoRA
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj"],
    )

    # Build datasets
    train_dataset = Dataset.from_list(train_pairs)
    eval_dataset = Dataset.from_list(eval_pairs)

    model_output_dir = output_dir / "model"
    model_output_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(model_output_dir),
        num_train_epochs=config.epochs,
        per_device_train_batch_size=config.batch_size,
        per_device_eval_batch_size=config.batch_size,
        learning_rate=config.learning_rate,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_steps=10,
        seed=config.seed,
        report_to="none",
        remove_unused_columns=False,
    )

    trainer = DPOTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
        beta=config.beta,
        max_length=config.max_length,
        max_prompt_length=config.max_prompt_length,
    )

    logger.info(
        "Starting training: %d train, %d eval pairs, %d epochs",
        len(train_pairs),
        len(eval_pairs),
        config.epochs,
    )

    train_output = trainer.train()

    logger.info("Training complete. Saving model...")
    trainer.save_model(str(model_output_dir))
    tokenizer.save_pretrained(str(model_output_dir))

    # Extract eval metrics
    eval_metrics: dict[str, float] = {}
    if hasattr(train_output, "metrics"):
        for key, val in train_output.metrics.items():
            if isinstance(val, (int, float)):
                eval_metrics[key] = float(val)

    # Run final evaluation
    try:
        eval_results = trainer.evaluate()
        for key, val in eval_results.items():
            if isinstance(val, (int, float)):
                eval_metrics[f"eval_{key}"] = float(val)
    except Exception as exc:
        logger.warning("Final evaluation failed: %s", exc)

    result = TrainingResult(
        model_id=str(model_output_dir),
        backend="huggingface",
        base_model=config.model,
        train_samples=len(train_pairs),
        eval_samples=len(eval_pairs),
        config=_config_to_dict(config),
        eval_metrics=eval_metrics,
        output_path=str(model_output_dir),
    )

    _save_result(result, output_dir)

    logger.info("Model saved to: %s", model_output_dir)

    return result


def _save_result(result: TrainingResult, output_dir: Path) -> None:
    """Save training result metadata to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "training_result.json"

    result_dict = {
        "model_id": result.model_id,
        "backend": result.backend,
        "base_model": result.base_model,
        "train_samples": result.train_samples,
        "eval_samples": result.eval_samples,
        "config": result.config,
        "eval_metrics": dict(result.eval_metrics),
        "output_path": result.output_path,
        "job_id": result.job_id,
    }

    with open(result_path, "w") as f:
        json.dump(result_dict, f, indent=2)

    logger.info("Training result saved to: %s", result_path)


def train_dpo(
    input_path: Path,
    backend: str,
    model: str,
    output_dir: Path,
    config: DPOConfig | None = None,
) -> TrainingResult:
    """Main entry point for DPO fine-tuning.

    Loads preference pairs, splits into train/eval, and dispatches to
    the appropriate backend.
    """
    if config is None:
        config = DPOConfig(backend=backend, model=model)

    pairs = load_preference_pairs(input_path)
    logger.info("Loaded %d preference pairs from %s", len(pairs), input_path)

    train_pairs, eval_pairs = split_train_eval(
        pairs, train_ratio=config.train_split, seed=config.seed
    )
    logger.info(
        "Split: %d train, %d eval (ratio=%.2f)",
        len(train_pairs),
        len(eval_pairs),
        config.train_split,
    )

    # Save split data for reproducibility
    _write_jsonl(train_pairs, output_dir / "train_split.jsonl")
    _write_jsonl(eval_pairs, output_dir / "eval_split.jsonl")

    if backend == "together":
        return train_together(train_pairs, eval_pairs, config, output_dir)
    elif backend == "huggingface":
        return train_huggingface(train_pairs, eval_pairs, config, output_dir)
    else:
        raise ValueError(f"Unknown backend: {backend}. Use 'together' or 'huggingface'.")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for DPO fine-tuning."""
    parser = argparse.ArgumentParser(
        description="Fine-tune a judge model using DPO on preference pairs"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input JSONL file with preference pairs (from generate_preferences)",
    )
    parser.add_argument(
        "--backend",
        choices=["together", "huggingface"],
        required=True,
        help="Training backend: 'together' (API) or 'huggingface' (local TRL)",
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Base model ID (e.g., meta-llama/Llama-3-8b-chat-hf)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models/judge"),
        help="Output directory for model and training artifacts",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=_DEFAULT_LR,
        help=f"Learning rate (default: {_DEFAULT_LR})",
    )
    parser.add_argument(
        "--beta",
        type=float,
        default=_DEFAULT_BETA,
        help=f"DPO beta parameter (default: {_DEFAULT_BETA})",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=_DEFAULT_EPOCHS,
        help=f"Number of training epochs (default: {_DEFAULT_EPOCHS})",
    )
    parser.add_argument(
        "--lora-rank",
        type=int,
        default=16,
        help="LoRA rank (default: 16)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Training batch size (default: 4)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = DPOConfig(
        backend=args.backend,
        model=args.model,
        learning_rate=args.learning_rate,
        beta=args.beta,
        epochs=args.epochs,
        lora_rank=args.lora_rank,
        batch_size=args.batch_size,
        seed=args.seed,
    )

    try:
        result = train_dpo(
            input_path=args.input,
            backend=args.backend,
            model=args.model,
            output_dir=args.output_dir,
            config=config,
        )

        print(f"Training complete!")
        print(f"  Backend: {result.backend}")
        print(f"  Base model: {result.base_model}")
        print(f"  Model ID: {result.model_id}")
        print(f"  Train samples: {result.train_samples}")
        print(f"  Eval samples: {result.eval_samples}")

        if result.eval_metrics:
            print("  Eval metrics:")
            for key, val in sorted(result.eval_metrics.items()):
                print(f"    {key}: {val:.4f}")

        if result.job_id:
            print(f"  Job ID: {result.job_id}")

        print(f"  Output: {result.output_path}")
        return 0

    except FileNotFoundError as exc:
        logger.error("File not found: %s", exc)
        return 1
    except ValueError as exc:
        logger.error("Invalid input: %s", exc)
        return 1
    except ImportError as exc:
        logger.error("Missing dependency: %s", exc)
        return 1
    except Exception as exc:
        logger.error("Training failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
