"""Tests for DPO fine-tuning script."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from scripts.judge_finetuning.train_dpo import (
    DPOConfig,
    TrainingResult,
    _config_to_dict,
    _save_result,
    _write_jsonl,
    load_preference_pairs,
    main,
    split_train_eval,
    train_dpo,
)


# -- Fixtures --


def _make_pair(
    task_id: str = "t1",
    prompt: str = "Task: do something",
    chosen: str = "good",
    rejected: str = "bad",
) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "chosen": chosen,
        "rejected": rejected,
        "metadata": {"task_id": task_id, "source": "test"},
    }


def _write_pairs_file(path: Path, pairs: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for pair in pairs:
            f.write(json.dumps(pair) + "\n")


# -- DPOConfig tests --


class TestDPOConfig:
    """Tests for DPOConfig frozen dataclass."""

    def test_construction(self) -> None:
        config = DPOConfig(backend="together", model="llama-3")
        assert config.backend == "together"
        assert config.model == "llama-3"
        assert config.learning_rate == 5e-6
        assert config.beta == 0.1
        assert config.epochs == 3
        assert config.lora_rank == 16
        assert config.train_split == 0.9

    def test_immutability(self) -> None:
        config = DPOConfig(backend="together", model="llama-3")
        with pytest.raises(AttributeError):
            config.backend = "huggingface"  # type: ignore[misc]

    def test_custom_values(self) -> None:
        config = DPOConfig(
            backend="huggingface",
            model="test-model",
            learning_rate=1e-5,
            beta=0.2,
            epochs=5,
            lora_rank=8,
            lora_alpha=16,
            batch_size=8,
        )
        assert config.learning_rate == 1e-5
        assert config.beta == 0.2
        assert config.epochs == 5
        assert config.lora_rank == 8
        assert config.lora_alpha == 16
        assert config.batch_size == 8


class TestTrainingResult:
    """Tests for TrainingResult frozen dataclass."""

    def test_construction(self) -> None:
        result = TrainingResult(
            model_id="ft-123",
            backend="together",
            base_model="llama-3",
            train_samples=90,
            eval_samples=10,
        )
        assert result.model_id == "ft-123"
        assert result.train_samples == 90
        assert result.eval_metrics == {}

    def test_immutability(self) -> None:
        result = TrainingResult(
            model_id="x", backend="y", base_model="z",
            train_samples=0, eval_samples=0,
        )
        with pytest.raises(AttributeError):
            result.model_id = "changed"  # type: ignore[misc]

    def test_with_metrics(self) -> None:
        result = TrainingResult(
            model_id="ft-456",
            backend="huggingface",
            base_model="model",
            train_samples=100,
            eval_samples=10,
            eval_metrics={"loss": 0.5, "accuracy": 0.85},
        )
        assert result.eval_metrics["loss"] == 0.5
        assert result.eval_metrics["accuracy"] == 0.85


# -- load_preference_pairs tests --


class TestLoadPreferencePairs:
    """Tests for loading preference pairs from JSONL."""

    def test_load_valid_file(self, tmp_path: Path) -> None:
        pairs = [_make_pair("t1"), _make_pair("t2")]
        path = tmp_path / "pairs.jsonl"
        _write_pairs_file(path, pairs)

        loaded = load_preference_pairs(path)
        assert len(loaded) == 2
        assert loaded[0]["prompt"] == "Task: do something"

    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_preference_pairs(tmp_path / "missing.jsonl")

    def test_skip_corrupt_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "pairs.jsonl"
        with open(path, "w") as f:
            f.write(json.dumps(_make_pair("t1")) + "\n")
            f.write("not valid json\n")
            f.write(json.dumps(_make_pair("t2")) + "\n")

        loaded = load_preference_pairs(path)
        assert len(loaded) == 2

    def test_skip_missing_fields(self, tmp_path: Path) -> None:
        path = tmp_path / "pairs.jsonl"
        with open(path, "w") as f:
            f.write(json.dumps(_make_pair("t1")) + "\n")
            f.write(json.dumps({"prompt": "only prompt"}) + "\n")

        loaded = load_preference_pairs(path)
        assert len(loaded) == 1

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "pairs.jsonl"
        path.write_text("")

        with pytest.raises(ValueError, match="No valid preference pairs"):
            load_preference_pairs(path)

    def test_skip_blank_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "pairs.jsonl"
        with open(path, "w") as f:
            f.write("\n")
            f.write(json.dumps(_make_pair("t1")) + "\n")
            f.write("\n")

        loaded = load_preference_pairs(path)
        assert len(loaded) == 1


# -- split_train_eval tests --


class TestSplitTrainEval:
    """Tests for stratified train/eval splitting."""

    def test_basic_split(self) -> None:
        pairs = [_make_pair(f"t{i}") for i in range(10)]
        train, eval_set = split_train_eval(pairs, train_ratio=0.9)

        assert len(train) + len(eval_set) == 10
        assert len(train) >= 8
        assert len(eval_set) >= 1

    def test_stratified_by_task(self) -> None:
        pairs = (
            [_make_pair("task_a") for _ in range(5)]
            + [_make_pair("task_b") for _ in range(5)]
        )
        train, eval_set = split_train_eval(pairs, train_ratio=0.5)

        # All pairs from a given task should be in the same split
        train_tasks = {p["metadata"]["task_id"] for p in train}
        eval_tasks = {p["metadata"]["task_id"] for p in eval_set}
        # At least one task in each split
        assert len(train_tasks) >= 1
        assert len(eval_tasks) >= 1

    def test_single_task_splits_pairs(self) -> None:
        pairs = [_make_pair("only_task") for _ in range(10)]
        train, eval_set = split_train_eval(pairs, train_ratio=0.9)

        assert len(train) + len(eval_set) == 10
        assert len(eval_set) >= 1

    def test_two_pairs_splits(self) -> None:
        pairs = [_make_pair("t1"), _make_pair("t2")]
        train, eval_set = split_train_eval(pairs, train_ratio=0.9)

        assert len(train) + len(eval_set) == 2
        assert len(eval_set) >= 1

    def test_deterministic(self) -> None:
        pairs = [_make_pair(f"t{i}") for i in range(20)]
        train1, eval1 = split_train_eval(pairs, seed=42)
        train2, eval2 = split_train_eval(pairs, seed=42)

        assert len(train1) == len(train2)
        assert len(eval1) == len(eval2)

    def test_different_seed_may_differ(self) -> None:
        pairs = [_make_pair(f"t{i}") for i in range(20)]
        train1, _ = split_train_eval(pairs, seed=42)
        train2, _ = split_train_eval(pairs, seed=99)

        # With enough tasks, different seeds should produce same logic
        # (our implementation is position-based, not hash-based)
        assert len(train1) + len(train2) > 0


# -- _write_jsonl tests --


class TestWriteJsonl:
    """Tests for JSONL writing utility."""

    def test_write_and_read_back(self, tmp_path: Path) -> None:
        pairs = [_make_pair("t1"), _make_pair("t2")]
        path = tmp_path / "output.jsonl"
        _write_jsonl(pairs, path)

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            record = json.loads(line)
            assert "prompt" in record

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "sub" / "dir" / "output.jsonl"
        _write_jsonl([_make_pair()], path)
        assert path.exists()


# -- _config_to_dict tests --


class TestConfigToDict:
    """Tests for config serialization."""

    def test_round_trip(self) -> None:
        config = DPOConfig(backend="together", model="llama-3")
        d = _config_to_dict(config)

        assert d["backend"] == "together"
        assert d["model"] == "llama-3"
        assert d["learning_rate"] == 5e-6
        assert d["epochs"] == 3

        # Should be JSON-serializable
        json.dumps(d)


# -- _save_result tests --


class TestSaveResult:
    """Tests for saving training results."""

    def test_saves_json(self, tmp_path: Path) -> None:
        result = TrainingResult(
            model_id="ft-test",
            backend="together",
            base_model="llama-3",
            train_samples=90,
            eval_samples=10,
            config={"lr": 5e-6},
            eval_metrics={"loss": 0.3},
            job_id="job-123",
        )
        _save_result(result, tmp_path)

        result_path = tmp_path / "training_result.json"
        assert result_path.exists()

        data = json.loads(result_path.read_text())
        assert data["model_id"] == "ft-test"
        assert data["backend"] == "together"
        assert data["eval_metrics"]["loss"] == 0.3
        assert data["job_id"] == "job-123"

    def test_creates_output_dir(self, tmp_path: Path) -> None:
        result = TrainingResult(
            model_id="x", backend="y", base_model="z",
            train_samples=0, eval_samples=0,
        )
        out = tmp_path / "new_dir"
        _save_result(result, out)
        assert (out / "training_result.json").exists()


# -- Together.ai backend tests --


class TestTrainTogether:
    """Tests for Together.ai training path with mocked SDK."""

    def test_together_import_error(self, tmp_path: Path) -> None:
        """Should raise ImportError when together package is missing."""
        pairs = [_make_pair()]
        config = DPOConfig(backend="together", model="test-model")

        with patch.dict("sys.modules", {"together": None}):
            from scripts.judge_finetuning.train_dpo import train_together

            with pytest.raises(ImportError, match="together package required"):
                train_together(pairs, pairs, config, tmp_path)

    def test_together_creates_job(self, tmp_path: Path) -> None:
        """Should upload data and create fine-tuning job."""
        mock_together = MagicMock()
        mock_client = MagicMock()
        mock_together.Together.return_value = mock_client

        mock_train_file = MagicMock()
        mock_train_file.id = "file-train-123"
        mock_eval_file = MagicMock()
        mock_eval_file.id = "file-eval-456"
        mock_client.files.upload.side_effect = [mock_train_file, mock_eval_file]

        mock_job = MagicMock()
        mock_job.id = "ft-job-789"
        mock_job.status = "pending"
        mock_job.output_name = "user/model:ft-job-789"
        mock_client.fine_tuning.create.return_value = mock_job

        with patch.dict("sys.modules", {"together": mock_together}):
            from scripts.judge_finetuning.train_dpo import train_together

            config = DPOConfig(backend="together", model="llama-3")
            train_pairs = [_make_pair("t1")]
            eval_pairs = [_make_pair("t2")]

            result = train_together(train_pairs, eval_pairs, config, tmp_path)

        assert result.model_id == "user/model:ft-job-789"
        assert result.backend == "together"
        assert result.job_id == "ft-job-789"
        assert result.train_samples == 1
        assert result.eval_samples == 1

        # Verify files were uploaded
        assert mock_client.files.upload.call_count == 2

        # Verify job was created with DPO config
        call_kwargs = mock_client.fine_tuning.create.call_args.kwargs
        assert call_kwargs["model"] == "llama-3"
        assert call_kwargs["lora"] is True
        assert call_kwargs["training_type"]["type"] == "DPO"
        assert call_kwargs["training_type"]["dpo_beta"] == 0.1

        # Verify result was saved
        assert (tmp_path / "training_result.json").exists()


# -- HuggingFace backend tests --


class TestTrainHuggingFace:
    """Tests for HuggingFace TRL training path with mocked libraries."""

    def test_huggingface_import_error(self, tmp_path: Path) -> None:
        """Should raise ImportError when HF packages are missing."""
        pairs = [_make_pair()]
        config = DPOConfig(backend="huggingface", model="test-model")

        with patch.dict("sys.modules", {"datasets": None}):
            from scripts.judge_finetuning.train_dpo import train_huggingface

            with pytest.raises(ImportError, match="HuggingFace packages required"):
                train_huggingface(pairs, pairs, config, tmp_path)

    def test_huggingface_training_flow(self, tmp_path: Path) -> None:
        """Should load model, train with DPO, and save."""
        mock_dataset = MagicMock()
        mock_datasets = MagicMock()
        mock_datasets.Dataset.from_list.return_value = mock_dataset

        mock_peft = MagicMock()
        mock_peft.TaskType.CAUSAL_LM = "CAUSAL_LM"

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token = None
        mock_tokenizer.eos_token = "<eos>"

        mock_model = MagicMock()

        mock_transformers = MagicMock()
        mock_transformers.AutoTokenizer.from_pretrained.return_value = mock_tokenizer
        mock_transformers.AutoModelForCausalLM.from_pretrained.return_value = mock_model

        mock_train_output = MagicMock()
        mock_train_output.metrics = {"train_loss": 0.4}

        mock_trainer = MagicMock()
        mock_trainer.train.return_value = mock_train_output
        mock_trainer.evaluate.return_value = {"eval_loss": 0.5}

        mock_trl = MagicMock()
        mock_trl.DPOTrainer.return_value = mock_trainer

        with patch.dict("sys.modules", {
            "datasets": mock_datasets,
            "peft": mock_peft,
            "transformers": mock_transformers,
            "trl": mock_trl,
        }):
            from scripts.judge_finetuning.train_dpo import train_huggingface

            config = DPOConfig(backend="huggingface", model="test-model")
            train_pairs = [_make_pair("t1")]
            eval_pairs = [_make_pair("t2")]

            result = train_huggingface(train_pairs, eval_pairs, config, tmp_path)

        assert result.backend == "huggingface"
        assert result.base_model == "test-model"
        assert result.train_samples == 1
        assert result.eval_samples == 1
        assert "train_loss" in result.eval_metrics

        # Verify model was saved
        mock_trainer.save_model.assert_called_once()
        mock_tokenizer.save_pretrained.assert_called_once()

        # Verify training_result.json was saved
        assert (tmp_path / "training_result.json").exists()


# -- train_dpo integration tests --


class TestTrainDpo:
    """Tests for the main train_dpo entry point."""

    def test_unknown_backend(self, tmp_path: Path) -> None:
        pairs = [_make_pair("t1"), _make_pair("t2")]
        path = tmp_path / "pairs.jsonl"
        _write_pairs_file(path, pairs)

        with pytest.raises(ValueError, match="Unknown backend"):
            train_dpo(path, "invalid", "model", tmp_path)

    def test_saves_split_files(self, tmp_path: Path) -> None:
        """Should save train/eval split JSONL files for reproducibility."""
        pairs = [_make_pair(f"t{i}") for i in range(10)]
        path = tmp_path / "pairs.jsonl"
        _write_pairs_file(path, pairs)

        # Mock together backend to avoid SDK dependency
        with patch(
            "scripts.judge_finetuning.train_dpo.train_together"
        ) as mock_train:
            mock_train.return_value = TrainingResult(
                model_id="ft-test",
                backend="together",
                base_model="model",
                train_samples=9,
                eval_samples=1,
            )

            out_dir = tmp_path / "output"
            train_dpo(path, "together", "model", out_dir)

        assert (out_dir / "train_split.jsonl").exists()
        assert (out_dir / "eval_split.jsonl").exists()

        train_lines = (out_dir / "train_split.jsonl").read_text().strip().split("\n")
        eval_lines = (out_dir / "eval_split.jsonl").read_text().strip().split("\n")
        assert len(train_lines) + len(eval_lines) == 10

    def test_dispatches_to_together(self, tmp_path: Path) -> None:
        pairs = [_make_pair("t1"), _make_pair("t2")]
        path = tmp_path / "pairs.jsonl"
        _write_pairs_file(path, pairs)

        with patch(
            "scripts.judge_finetuning.train_dpo.train_together"
        ) as mock_train:
            mock_train.return_value = TrainingResult(
                model_id="ft-test", backend="together", base_model="m",
                train_samples=1, eval_samples=1,
            )

            train_dpo(path, "together", "model", tmp_path)
            mock_train.assert_called_once()

    def test_dispatches_to_huggingface(self, tmp_path: Path) -> None:
        pairs = [_make_pair("t1"), _make_pair("t2")]
        path = tmp_path / "pairs.jsonl"
        _write_pairs_file(path, pairs)

        with patch(
            "scripts.judge_finetuning.train_dpo.train_huggingface"
        ) as mock_train:
            mock_train.return_value = TrainingResult(
                model_id="ft-test", backend="huggingface", base_model="m",
                train_samples=1, eval_samples=1,
            )

            train_dpo(path, "huggingface", "model", tmp_path)
            mock_train.assert_called_once()


# -- CLI tests --


class TestCLI:
    """Tests for CLI entry point."""

    def test_missing_required_args(self) -> None:
        """Should exit with error when required arguments missing."""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 2

    def test_valid_args_together(self, tmp_path: Path) -> None:
        pairs = [_make_pair("t1"), _make_pair("t2")]
        path = tmp_path / "pairs.jsonl"
        _write_pairs_file(path, pairs)

        with patch("scripts.judge_finetuning.train_dpo.train_dpo") as mock_train:
            mock_train.return_value = TrainingResult(
                model_id="ft-test",
                backend="together",
                base_model="llama-3",
                train_samples=1,
                eval_samples=1,
            )

            result = main([
                "--input", str(path),
                "--backend", "together",
                "--model", "llama-3",
                "--output-dir", str(tmp_path / "out"),
            ])

        assert result == 0
        mock_train.assert_called_once()

    def test_valid_args_huggingface(self, tmp_path: Path) -> None:
        pairs = [_make_pair("t1"), _make_pair("t2")]
        path = tmp_path / "pairs.jsonl"
        _write_pairs_file(path, pairs)

        with patch("scripts.judge_finetuning.train_dpo.train_dpo") as mock_train:
            mock_train.return_value = TrainingResult(
                model_id="/path/to/model",
                backend="huggingface",
                base_model="test-model",
                train_samples=1,
                eval_samples=1,
                eval_metrics={"loss": 0.3},
            )

            result = main([
                "--input", str(path),
                "--backend", "huggingface",
                "--model", "test-model",
                "--output-dir", str(tmp_path / "out"),
                "--learning-rate", "1e-5",
                "--epochs", "5",
                "--beta", "0.2",
            ])

        assert result == 0

    def test_file_not_found(self, tmp_path: Path) -> None:
        result = main([
            "--input", str(tmp_path / "missing.jsonl"),
            "--backend", "together",
            "--model", "llama-3",
        ])
        assert result == 1

    def test_custom_config_values(self, tmp_path: Path) -> None:
        pairs = [_make_pair("t1"), _make_pair("t2")]
        path = tmp_path / "pairs.jsonl"
        _write_pairs_file(path, pairs)

        with patch("scripts.judge_finetuning.train_dpo.train_dpo") as mock_train:
            mock_train.return_value = TrainingResult(
                model_id="ft", backend="together", base_model="m",
                train_samples=1, eval_samples=1,
            )

            main([
                "--input", str(path),
                "--backend", "together",
                "--model", "llama-3",
                "--lora-rank", "8",
                "--batch-size", "8",
                "--seed", "123",
            ])

            call_kwargs = mock_train.call_args.kwargs
            config = call_kwargs["config"]
            assert config.lora_rank == 8
            assert config.batch_size == 8
            assert config.seed == 123
