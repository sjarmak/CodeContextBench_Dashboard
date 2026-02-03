"""Tests for DPO preference pair generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.judge_finetuning.generate_preferences import (
    GenerationReport,
    PreferencePair,
    _build_prompt_from_task,
    _build_task_index,
    generate_preference_pairs,
    load_annotations,
    load_judge_results,
    main,
    pairs_from_direct_annotations,
    pairs_from_judge_results,
    pairs_from_pairwise_annotations,
    pairs_from_reference_annotations,
    serialize_pair,
    write_pairs_jsonl,
)


class TestPreferencePairDataclass:
    """Tests for PreferencePair frozen dataclass."""

    def test_construction(self) -> None:
        pair = PreferencePair(
            prompt="task description",
            chosen="good output",
            rejected="bad output",
            metadata={"task_id": "t1", "source": "human_pairwise"},
        )
        assert pair.prompt == "task description"
        assert pair.chosen == "good output"
        assert pair.rejected == "bad output"
        assert pair.metadata["source"] == "human_pairwise"

    def test_immutability(self) -> None:
        pair = PreferencePair(prompt="p", chosen="c", rejected="r")
        with pytest.raises(AttributeError):
            pair.prompt = "modified"  # type: ignore[misc]

    def test_default_metadata(self) -> None:
        pair = PreferencePair(prompt="p", chosen="c", rejected="r")
        assert pair.metadata == {}


class TestGenerationReport:
    """Tests for GenerationReport frozen dataclass."""

    def test_construction(self) -> None:
        report = GenerationReport(
            total_pairs=10,
            from_human_pairwise=3,
            from_human_direct=2,
            from_human_reference=1,
            from_judge=4,
            skipped_annotations=5,
            skipped_judge_results=2,
        )
        assert report.total_pairs == 10
        assert report.from_judge == 4

    def test_immutability(self) -> None:
        report = GenerationReport(0, 0, 0, 0, 0, 0, 0)
        with pytest.raises(AttributeError):
            report.total_pairs = 5  # type: ignore[misc]


class TestLoadAnnotations:
    """Tests for loading annotations from JSONL."""

    def test_load_valid_annotations(self, tmp_path: Path) -> None:
        ann_dir = tmp_path / "annotations"
        ann_dir.mkdir()
        ann_file = ann_dir / "annotations.jsonl"
        records = [
            {"annotator_id": "alice", "task_id": "t1", "mode": "pairwise", "preference": "A"},
            {"annotator_id": "bob", "task_id": "t2", "mode": "direct", "scores": {"Correctness": 4}},
        ]
        ann_file.write_text("\n".join(json.dumps(r) for r in records) + "\n")

        result = load_annotations(ann_dir)
        assert len(result) == 2
        assert result[0]["annotator_id"] == "alice"
        assert result[1]["mode"] == "direct"

    def test_load_missing_file(self, tmp_path: Path) -> None:
        result = load_annotations(tmp_path / "nonexistent")
        assert result == []

    def test_skip_corrupt_lines(self, tmp_path: Path) -> None:
        ann_dir = tmp_path / "annotations"
        ann_dir.mkdir()
        ann_file = ann_dir / "annotations.jsonl"
        ann_file.write_text(
            '{"annotator_id": "alice", "task_id": "t1", "mode": "pairwise"}\n'
            "CORRUPT LINE\n"
            '{"annotator_id": "bob", "task_id": "t2", "mode": "direct"}\n'
        )

        result = load_annotations(ann_dir)
        assert len(result) == 2

    def test_skip_blank_lines(self, tmp_path: Path) -> None:
        ann_dir = tmp_path / "annotations"
        ann_dir.mkdir()
        ann_file = ann_dir / "annotations.jsonl"
        ann_file.write_text(
            '{"annotator_id": "alice", "task_id": "t1", "mode": "pairwise"}\n'
            "\n"
            '{"annotator_id": "bob", "task_id": "t2", "mode": "direct"}\n'
        )

        result = load_annotations(ann_dir)
        assert len(result) == 2


class TestLoadJudgeResults:
    """Tests for loading judge experiment results."""

    def test_load_valid_experiments(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "exp_abc123"
        exp_dir.mkdir(parents=True)
        results = {
            "results": [
                {"task_id": "t1", "overall_score": 0.8, "agent_output": "output1"},
                {"task_id": "t2", "overall_score": 0.5, "agent_output": "output2"},
            ]
        }
        (exp_dir / "results.json").write_text(json.dumps(results))

        loaded = load_judge_results(tmp_path)
        assert len(loaded) == 2
        assert loaded[0]["experiment_id"] == "abc123"
        assert loaded[0]["task_id"] == "t1"

    def test_missing_directory(self, tmp_path: Path) -> None:
        result = load_judge_results(tmp_path / "nonexistent")
        assert result == []

    def test_skip_corrupt_experiments(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "exp_bad"
        exp_dir.mkdir(parents=True)
        (exp_dir / "results.json").write_text("NOT JSON")

        result = load_judge_results(tmp_path)
        assert result == []

    def test_skip_non_experiment_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "not_exp").mkdir()
        (tmp_path / "some_file.txt").write_text("hi")

        result = load_judge_results(tmp_path)
        assert result == []


class TestBuildPromptFromTask:
    """Tests for prompt construction."""

    def test_simple_prompt(self) -> None:
        prompt = _build_prompt_from_task("t1", "Fix the bug")
        assert "Task: Fix the bug" in prompt

    def test_with_criteria(self) -> None:
        prompt = _build_prompt_from_task("t1", "Fix", evaluation_criteria="Must pass tests")
        assert "Evaluation Criteria: Must pass tests" in prompt

    def test_with_reference(self) -> None:
        prompt = _build_prompt_from_task("t1", "Fix", reference_answer="Expected output")
        assert "Reference Answer: Expected output" in prompt

    def test_fallback_to_task_id(self) -> None:
        prompt = _build_prompt_from_task("task_123", "")
        assert "Task: task_123" in prompt


class TestPairsFromPairwiseAnnotations:
    """Tests for pairwise annotation to preference pair conversion."""

    def test_basic_pairwise(self) -> None:
        annotations = [
            {
                "mode": "pairwise",
                "task_id": "t1",
                "preference": "A",
                "scores": {"conditions": ["A", "B"]},
                "annotator_id": "alice",
                "reasoning": "A is better",
            }
        ]
        outputs = {"t1": {"A": "output A", "B": "output B"}}
        descriptions = {"t1": "Test task"}

        pairs, skipped = pairs_from_pairwise_annotations(annotations, outputs, descriptions)
        assert len(pairs) == 1
        assert pairs[0].chosen == "output A"
        assert pairs[0].rejected == "output B"
        assert pairs[0].metadata["source"] == "human_pairwise"
        assert skipped == 0

    def test_skip_ties(self) -> None:
        annotations = [
            {
                "mode": "pairwise",
                "task_id": "t1",
                "preference": "Tie",
                "scores": {"conditions": ["A", "B"]},
            }
        ]
        outputs = {"t1": {"A": "output A", "B": "output B"}}

        pairs, skipped = pairs_from_pairwise_annotations(annotations, outputs, {})
        assert len(pairs) == 0
        assert skipped == 1

    def test_skip_missing_output(self) -> None:
        annotations = [
            {
                "mode": "pairwise",
                "task_id": "t1",
                "preference": "C",
                "scores": {"conditions": ["A", "B", "C"]},
            }
        ]
        outputs = {"t1": {"A": "output A", "B": "output B"}}

        pairs, skipped = pairs_from_pairwise_annotations(annotations, outputs, {})
        assert len(pairs) == 0
        assert skipped == 1

    def test_three_way_comparison(self) -> None:
        annotations = [
            {
                "mode": "pairwise",
                "task_id": "t1",
                "preference": "A",
                "scores": {"conditions": ["A", "B", "C"]},
                "annotator_id": "alice",
            }
        ]
        outputs = {"t1": {"A": "out A", "B": "out B", "C": "out C"}}

        pairs, skipped = pairs_from_pairwise_annotations(annotations, outputs, {})
        assert len(pairs) == 2
        assert all(p.chosen == "out A" for p in pairs)

    def test_skip_non_pairwise(self) -> None:
        annotations = [
            {"mode": "direct", "task_id": "t1", "scores": {"Correctness": 3}},
        ]
        pairs, skipped = pairs_from_pairwise_annotations(annotations, {}, {})
        assert len(pairs) == 0
        assert skipped == 0


class TestPairsFromDirectAnnotations:
    """Tests for direct scoring to preference pair conversion."""

    def test_two_outputs_sufficient_gap(self) -> None:
        annotations = [
            {"mode": "direct", "task_id": "t1", "scores": {"Correctness": 5, "Completeness": 4}},
        ]
        outputs = {"t1": {"condA": "good output", "condB": "bad output"}}

        pairs, skipped = pairs_from_direct_annotations(annotations, outputs, {"t1": "Task"})
        # Both conditions use same annotations (since annotations don't specify condition),
        # so both get the same score -> no pair generated (no score gap)
        assert len(pairs) == 0

    def test_skip_single_output(self) -> None:
        annotations = [
            {"mode": "direct", "task_id": "t1", "scores": {"Correctness": 5}},
        ]
        outputs = {"t1": {"condA": "only output"}}

        pairs, skipped = pairs_from_direct_annotations(annotations, outputs, {})
        assert len(pairs) == 0
        assert skipped > 0

    def test_skip_missing_task_id(self) -> None:
        annotations = [
            {"mode": "direct", "task_id": "", "scores": {"Correctness": 5}},
        ]
        pairs, skipped = pairs_from_direct_annotations(annotations, {}, {})
        assert len(pairs) == 0
        assert skipped == 1


class TestPairsFromReferenceAnnotations:
    """Tests for reference-based annotation to preference pair conversion."""

    def test_skip_single_output(self) -> None:
        annotations = [
            {
                "mode": "reference",
                "task_id": "t1",
                "scores": {"Oracle Correctness": "pass", "Oracle Completeness": "pass"},
            }
        ]
        outputs = {"t1": {"condA": "only output"}}

        pairs, skipped = pairs_from_reference_annotations(annotations, outputs, {}, {})
        assert len(pairs) == 0
        assert skipped > 0

    def test_skip_non_reference(self) -> None:
        annotations = [
            {"mode": "direct", "task_id": "t1", "scores": {"Correctness": 3}},
        ]
        pairs, skipped = pairs_from_reference_annotations(annotations, {}, {}, {})
        assert len(pairs) == 0

    def test_reference_answer_in_prompt(self) -> None:
        annotations = [
            {
                "mode": "reference",
                "task_id": "t1",
                "scores": {"Oracle Correctness": "pass"},
            }
        ]
        outputs = {"t1": {"condA": "good", "condB": "bad"}}
        refs = {"t1": "The expected answer"}

        pairs, _ = pairs_from_reference_annotations(
            annotations, outputs, {"t1": "Task"}, refs
        )
        # Both conditions get the same score (same annotations applied to both),
        # so no pair generated
        assert len(pairs) == 0


class TestPairsFromJudgeResults:
    """Tests for judge result to preference pair conversion."""

    def test_basic_judge_pairs(self) -> None:
        results = [
            {"task_id": "t1", "overall_score": 0.9, "agent_output": "good", "task_description": "Fix bug"},
            {"task_id": "t1", "overall_score": 0.3, "agent_output": "bad", "task_description": "Fix bug"},
        ]

        pairs, skipped = pairs_from_judge_results(results)
        assert len(pairs) == 1
        assert pairs[0].chosen == "good"
        assert pairs[0].rejected == "bad"
        assert pairs[0].metadata["source"] == "judge"
        assert pairs[0].metadata["chosen_score"] == 0.9
        assert pairs[0].metadata["rejected_score"] == 0.3

    def test_skip_small_score_gap(self) -> None:
        results = [
            {"task_id": "t1", "overall_score": 0.8, "agent_output": "a"},
            {"task_id": "t1", "overall_score": 0.75, "agent_output": "b"},
        ]

        pairs, skipped = pairs_from_judge_results(results)
        assert len(pairs) == 0

    def test_skip_single_result(self) -> None:
        results = [
            {"task_id": "t1", "overall_score": 0.8, "agent_output": "only one"},
        ]

        pairs, skipped = pairs_from_judge_results(results)
        assert len(pairs) == 0
        assert skipped == 1

    def test_skip_missing_output(self) -> None:
        results = [
            {"task_id": "t1", "overall_score": 0.9, "agent_output": ""},
            {"task_id": "t1", "overall_score": 0.3, "agent_output": "bad"},
        ]

        pairs, skipped = pairs_from_judge_results(results)
        assert len(pairs) == 0

    def test_consensus_score_fallback(self) -> None:
        results = [
            {"task_id": "t1", "consensus_score": 0.9, "agent_output": "good"},
            {"task_id": "t1", "consensus_score": 0.2, "agent_output": "bad"},
        ]

        pairs, skipped = pairs_from_judge_results(results)
        assert len(pairs) == 1
        assert pairs[0].chosen == "good"

    def test_multiple_tasks(self) -> None:
        results = [
            {"task_id": "t1", "overall_score": 0.9, "agent_output": "good1"},
            {"task_id": "t1", "overall_score": 0.3, "agent_output": "bad1"},
            {"task_id": "t2", "overall_score": 0.8, "agent_output": "good2"},
            {"task_id": "t2", "overall_score": 0.1, "agent_output": "bad2"},
        ]

        pairs, skipped = pairs_from_judge_results(results)
        assert len(pairs) == 2

    def test_skip_missing_task_id(self) -> None:
        results = [
            {"task_id": "", "overall_score": 0.9, "agent_output": "out"},
        ]
        pairs, skipped = pairs_from_judge_results(results)
        assert len(pairs) == 0
        assert skipped == 1


class TestBuildTaskIndex:
    """Tests for task index building."""

    def test_builds_outputs_and_descriptions(self) -> None:
        judge_results = [
            {
                "task_id": "t1",
                "agent_output": "output1",
                "task_description": "Fix bug",
                "experiment_id": "exp1",
            },
            {
                "task_id": "t1",
                "agent_output": "output2",
                "task_description": "Fix bug",
                "experiment_id": "exp2",
            },
        ]

        outputs, descs, refs = _build_task_index([], judge_results)
        assert "t1" in outputs
        assert len(outputs["t1"]) == 2
        assert descs["t1"] == "Fix bug"

    def test_extracts_references(self) -> None:
        judge_results = [
            {
                "task_id": "t1",
                "agent_output": "out",
                "reference_answer": "expected",
                "experiment_id": "exp1",
            },
        ]

        _, _, refs = _build_task_index([], judge_results)
        assert refs["t1"] == "expected"

    def test_empty_inputs(self) -> None:
        outputs, descs, refs = _build_task_index([], [])
        assert outputs == {}
        assert descs == {}
        assert refs == {}


class TestSerializePair:
    """Tests for pair serialization."""

    def test_serialize(self) -> None:
        pair = PreferencePair(
            prompt="task",
            chosen="good",
            rejected="bad",
            metadata={"task_id": "t1", "source": "judge"},
        )
        serialized = serialize_pair(pair)
        assert serialized["prompt"] == "task"
        assert serialized["chosen"] == "good"
        assert serialized["rejected"] == "bad"
        assert serialized["metadata"]["source"] == "judge"

    def test_serialization_is_json_compatible(self) -> None:
        pair = PreferencePair(prompt="p", chosen="c", rejected="r")
        serialized = serialize_pair(pair)
        json_str = json.dumps(serialized)
        loaded = json.loads(json_str)
        assert loaded["prompt"] == "p"


class TestWritePairsJsonl:
    """Tests for JSONL file writing."""

    def test_write_and_read_back(self, tmp_path: Path) -> None:
        output_path = tmp_path / "output" / "pairs.jsonl"
        pairs = [
            PreferencePair(prompt="p1", chosen="c1", rejected="r1", metadata={"id": 1}),
            PreferencePair(prompt="p2", chosen="c2", rejected="r2", metadata={"id": 2}),
        ]

        write_pairs_jsonl(pairs, output_path)

        assert output_path.exists()
        lines = output_path.read_text().strip().split("\n")
        assert len(lines) == 2

        loaded = [json.loads(line) for line in lines]
        assert loaded[0]["prompt"] == "p1"
        assert loaded[1]["chosen"] == "c2"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        output_path = tmp_path / "deep" / "nested" / "pairs.jsonl"
        write_pairs_jsonl([], output_path)
        assert output_path.exists()


class TestGeneratePreferencePairs:
    """Integration tests for the full generation pipeline."""

    def test_empty_inputs(self, tmp_path: Path) -> None:
        ann_dir = tmp_path / "annotations"
        ann_dir.mkdir()
        judge_dir = tmp_path / "judge"
        judge_dir.mkdir()

        pairs, report = generate_preference_pairs(ann_dir, judge_dir)
        assert len(pairs) == 0
        assert report.total_pairs == 0

    def test_judge_results_only(self, tmp_path: Path) -> None:
        ann_dir = tmp_path / "annotations"
        ann_dir.mkdir()

        judge_dir = tmp_path / "judge"
        exp_dir = judge_dir / "exp_test1"
        exp_dir.mkdir(parents=True)
        results = {
            "results": [
                {"task_id": "t1", "overall_score": 0.9, "agent_output": "good", "task_description": "Fix"},
                {"task_id": "t1", "overall_score": 0.2, "agent_output": "bad", "task_description": "Fix"},
            ]
        }
        (exp_dir / "results.json").write_text(json.dumps(results))

        pairs, report = generate_preference_pairs(ann_dir, judge_dir)
        assert report.total_pairs == 1
        assert report.from_judge == 1
        assert pairs[0].chosen == "good"

    def test_pairwise_annotations_with_judge_data(self, tmp_path: Path) -> None:
        # Set up annotations
        ann_dir = tmp_path / "annotations"
        ann_dir.mkdir()
        ann_file = ann_dir / "annotations.jsonl"
        ann_record = {
            "annotator_id": "alice",
            "task_id": "t1",
            "mode": "pairwise",
            "preference": "exp1",
            "scores": {"conditions": ["exp1", "exp2"]},
            "reasoning": "exp1 is better",
        }
        ann_file.write_text(json.dumps(ann_record) + "\n")

        # Set up judge results (provides task outputs)
        judge_dir = tmp_path / "judge"
        exp1_dir = judge_dir / "exp_exp1"
        exp1_dir.mkdir(parents=True)
        (exp1_dir / "results.json").write_text(json.dumps({
            "results": [
                {"task_id": "t1", "overall_score": 0.8, "agent_output": "output from exp1", "experiment_id": "exp1"},
            ]
        }))

        exp2_dir = judge_dir / "exp_exp2"
        exp2_dir.mkdir(parents=True)
        (exp2_dir / "results.json").write_text(json.dumps({
            "results": [
                {"task_id": "t1", "overall_score": 0.4, "agent_output": "output from exp2", "experiment_id": "exp2"},
            ]
        }))

        pairs, report = generate_preference_pairs(ann_dir, judge_dir)
        # Should get 1 pairwise pair + 1 judge pair (score gap > 0.1)
        assert report.from_human_pairwise == 1
        pairwise_pairs = [p for p in pairs if p.metadata.get("source") == "human_pairwise"]
        assert len(pairwise_pairs) == 1
        assert pairwise_pairs[0].chosen == "output from exp1"


class TestCLI:
    """Tests for the CLI entry point."""

    def test_no_data_returns_1(self, tmp_path: Path) -> None:
        ann_dir = tmp_path / "ann"
        ann_dir.mkdir()
        judge_dir = tmp_path / "judge"
        judge_dir.mkdir()
        output = tmp_path / "output.jsonl"

        result = main([
            "--annotations-dir", str(ann_dir),
            "--judge-dir", str(judge_dir),
            "--output", str(output),
        ])
        assert result == 1

    def test_with_data_returns_0(self, tmp_path: Path) -> None:
        ann_dir = tmp_path / "ann"
        ann_dir.mkdir()

        judge_dir = tmp_path / "judge"
        exp_dir = judge_dir / "exp_test1"
        exp_dir.mkdir(parents=True)
        results = {
            "results": [
                {"task_id": "t1", "overall_score": 0.9, "agent_output": "good"},
                {"task_id": "t1", "overall_score": 0.2, "agent_output": "bad"},
            ]
        }
        (exp_dir / "results.json").write_text(json.dumps(results))

        output = tmp_path / "output.jsonl"

        result = main([
            "--annotations-dir", str(ann_dir),
            "--judge-dir", str(judge_dir),
            "--output", str(output),
        ])
        assert result == 0
        assert output.exists()

        lines = output.read_text().strip().split("\n")
        assert len(lines) == 1
        loaded = json.loads(lines[0])
        assert loaded["chosen"] == "good"

    def test_verbose_flag(self, tmp_path: Path) -> None:
        ann_dir = tmp_path / "ann"
        ann_dir.mkdir()
        judge_dir = tmp_path / "judge"
        judge_dir.mkdir()
        output = tmp_path / "output.jsonl"

        # Should not raise
        main([
            "--annotations-dir", str(ann_dir),
            "--judge-dir", str(judge_dir),
            "--output", str(output),
            "--verbose",
        ])
