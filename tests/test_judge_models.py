"""Unit tests for unified judge data models."""

from enum import Enum

import pytest

from src.judge.models import (
    CommentCategory,
    DimensionScore,
    DirectInput,
    EnsembleVerdict,
    EvaluationMode,
    JudgeInput,
    JudgeVerdict,
    LineComment,
    PairwiseInput,
    PairwiseVerdict,
    ReferenceInput,
    Severity,
)


class TestEvaluationMode:
    def test_values(self):
        assert EvaluationMode.PAIRWISE.value == "pairwise"
        assert EvaluationMode.DIRECT.value == "direct"
        assert EvaluationMode.REFERENCE_BASED.value == "reference_based"

    def test_all_modes_exist(self):
        modes = {m.name for m in EvaluationMode}
        assert modes == {"PAIRWISE", "DIRECT", "REFERENCE_BASED"}


class TestSeverityAndCategory:
    def test_severity_values(self):
        assert Severity.CRITICAL.value == "critical"
        assert Severity.WARNING.value == "warning"
        assert Severity.SUGGESTION.value == "suggestion"
        assert Severity.PRAISE.value == "praise"

    def test_category_values(self):
        assert CommentCategory.CORRECTNESS.value == "correctness"
        assert CommentCategory.STYLE.value == "style"
        assert CommentCategory.SECURITY.value == "security"
        assert CommentCategory.PERFORMANCE.value == "performance"


class TestJudgeInput:
    def test_construction(self):
        inp = JudgeInput(
            task_id="task-001",
            task_description="Fix the bug",
            evaluation_mode=EvaluationMode.DIRECT,
        )
        assert inp.task_id == "task-001"
        assert inp.task_description == "Fix the bug"
        assert inp.evaluation_mode == EvaluationMode.DIRECT
        assert inp.ground_truth is None
        assert inp.evaluation_criteria is None

    def test_with_optional_fields(self):
        inp = JudgeInput(
            task_id="task-002",
            task_description="Implement feature",
            evaluation_mode=EvaluationMode.REFERENCE_BASED,
            ground_truth="expected output",
            evaluation_criteria="Must pass all tests",
        )
        assert inp.ground_truth == "expected output"
        assert inp.evaluation_criteria == "Must pass all tests"

    def test_immutability(self):
        inp = JudgeInput(
            task_id="task-001",
            task_description="Fix the bug",
            evaluation_mode=EvaluationMode.DIRECT,
        )
        with pytest.raises(AttributeError):
            inp.task_id = "modified"  # type: ignore[misc]


class TestPairwiseInput:
    def test_construction(self):
        inp = PairwiseInput(
            task_id="task-001",
            task_description="Compare outputs",
            evaluation_mode=EvaluationMode.PAIRWISE,
            outputs={
                "BASELINE": "output A",
                "MCP_BASE": "output B",
                "MCP_FULL": "output C",
            },
        )
        assert len(inp.outputs) == 3
        assert inp.outputs["BASELINE"] == "output A"

    def test_inherits_judge_input(self):
        inp = PairwiseInput(
            task_id="task-001",
            task_description="Compare",
            evaluation_mode=EvaluationMode.PAIRWISE,
        )
        assert isinstance(inp, JudgeInput)

    def test_default_empty_outputs(self):
        inp = PairwiseInput(
            task_id="task-001",
            task_description="Compare",
            evaluation_mode=EvaluationMode.PAIRWISE,
        )
        assert inp.outputs == {}

    def test_immutability(self):
        inp = PairwiseInput(
            task_id="task-001",
            task_description="Compare",
            evaluation_mode=EvaluationMode.PAIRWISE,
            outputs={"A": "a"},
        )
        with pytest.raises(AttributeError):
            inp.outputs = {}  # type: ignore[misc]


class TestDirectInput:
    def test_construction(self):
        inp = DirectInput(
            task_id="task-001",
            task_description="Review code",
            evaluation_mode=EvaluationMode.DIRECT,
            agent_output="def foo(): pass",
            code_changes="+ def foo(): pass",
            trajectory=[{"step": 1, "action": "edit"}],
        )
        assert inp.agent_output == "def foo(): pass"
        assert inp.code_changes == "+ def foo(): pass"
        assert len(inp.trajectory) == 1

    def test_defaults(self):
        inp = DirectInput(
            task_id="task-001",
            task_description="Review",
            evaluation_mode=EvaluationMode.DIRECT,
        )
        assert inp.agent_output == ""
        assert inp.code_changes is None
        assert inp.trajectory == []


class TestReferenceInput:
    def test_construction(self):
        inp = ReferenceInput(
            task_id="task-001",
            task_description="Evaluate correctness",
            evaluation_mode=EvaluationMode.REFERENCE_BASED,
            agent_output="agent solution",
            reference_answer="correct solution",
            context_files=["src/main.py", "src/utils.py"],
        )
        assert inp.agent_output == "agent solution"
        assert inp.reference_answer == "correct solution"
        assert len(inp.context_files) == 2

    def test_defaults(self):
        inp = ReferenceInput(
            task_id="task-001",
            task_description="Evaluate",
            evaluation_mode=EvaluationMode.REFERENCE_BASED,
        )
        assert inp.agent_output == ""
        assert inp.reference_answer == ""
        assert inp.context_files == []


class TestLineComment:
    def test_construction(self):
        comment = LineComment(
            file_path="src/main.py",
            line_range=(10, 15),
            severity=Severity.CRITICAL,
            comment="Potential SQL injection",
            category=CommentCategory.SECURITY,
        )
        assert comment.file_path == "src/main.py"
        assert comment.line_range == (10, 15)
        assert comment.severity == Severity.CRITICAL
        assert comment.category == CommentCategory.SECURITY

    def test_immutability(self):
        comment = LineComment(
            file_path="src/main.py",
            line_range=(1, 5),
            severity=Severity.WARNING,
            comment="Consider refactoring",
            category=CommentCategory.STYLE,
        )
        with pytest.raises(AttributeError):
            comment.comment = "changed"  # type: ignore[misc]


class TestDimensionScore:
    def test_construction(self):
        score = DimensionScore(
            dimension="Correctness",
            score=0.85,
            weight=0.3,
            evidence="All tests pass",
            reasoning="Code correctly implements the feature",
        )
        assert score.dimension == "Correctness"
        assert score.score == 0.85
        assert score.weight == 0.3

    def test_immutability(self):
        score = DimensionScore(
            dimension="Quality",
            score=0.7,
            weight=0.2,
            evidence="Clean code",
            reasoning="Well structured",
        )
        with pytest.raises(AttributeError):
            score.score = 0.9  # type: ignore[misc]


class TestJudgeVerdict:
    def _make_verdict(self, **overrides):
        defaults = {
            "mode": EvaluationMode.DIRECT,
            "scores": {
                "correctness": DimensionScore(
                    dimension="correctness",
                    score=0.8,
                    weight=0.3,
                    evidence="Tests pass",
                    reasoning="Correct implementation",
                )
            },
            "overall_score": 0.8,
            "reasoning": "Good overall",
            "evidence": ["test output shows pass"],
            "confidence": 0.9,
            "model_id": "claude-sonnet-4-20250514",
        }
        defaults.update(overrides)
        return JudgeVerdict(**defaults)

    def test_construction(self):
        verdict = self._make_verdict()
        assert verdict.mode == EvaluationMode.DIRECT
        assert verdict.overall_score == 0.8
        assert verdict.confidence == 0.9
        assert verdict.model_id == "claude-sonnet-4-20250514"
        assert len(verdict.scores) == 1
        assert verdict.line_comments == []
        assert verdict.metadata == {}

    def test_with_line_comments(self):
        comment = LineComment(
            file_path="src/main.py",
            line_range=(1, 3),
            severity=Severity.SUGGESTION,
            comment="Add docstring",
            category=CommentCategory.STYLE,
        )
        verdict = self._make_verdict(line_comments=[comment])
        assert len(verdict.line_comments) == 1
        assert verdict.line_comments[0].severity == Severity.SUGGESTION

    def test_with_metadata(self):
        verdict = self._make_verdict(metadata={"latency_ms": 1200})
        assert verdict.metadata["latency_ms"] == 1200

    def test_immutability(self):
        verdict = self._make_verdict()
        with pytest.raises(AttributeError):
            verdict.overall_score = 0.5  # type: ignore[misc]


class TestPairwiseVerdict:
    def test_construction(self):
        verdict = PairwiseVerdict(
            mode=EvaluationMode.PAIRWISE,
            scores={},
            overall_score=0.75,
            reasoning="A is better than B",
            evidence=["A has cleaner code"],
            confidence=0.85,
            model_id="gpt-4o",
            rankings=["MCP_FULL", "BASELINE"],
            win_rates={"MCP_FULL": 0.7, "BASELINE": 0.3},
            preference_matrix={
                "MCP_FULL": {"BASELINE": 0.7},
                "BASELINE": {"MCP_FULL": 0.3},
            },
            ties=1,
        )
        assert verdict.rankings == ["MCP_FULL", "BASELINE"]
        assert verdict.win_rates["MCP_FULL"] == 0.7
        assert verdict.ties == 1

    def test_inherits_judge_verdict(self):
        verdict = PairwiseVerdict(
            mode=EvaluationMode.PAIRWISE,
            scores={},
            overall_score=0.5,
            reasoning="Tied",
            evidence=[],
            confidence=0.5,
            model_id="test",
        )
        assert isinstance(verdict, JudgeVerdict)

    def test_defaults(self):
        verdict = PairwiseVerdict(
            mode=EvaluationMode.PAIRWISE,
            scores={},
            overall_score=0.5,
            reasoning="Tied",
            evidence=[],
            confidence=0.5,
            model_id="test",
        )
        assert verdict.rankings == []
        assert verdict.win_rates == {}
        assert verdict.preference_matrix == {}
        assert verdict.ties == 0


class TestEnsembleVerdict:
    def test_construction(self):
        v1 = JudgeVerdict(
            mode=EvaluationMode.DIRECT,
            scores={},
            overall_score=0.8,
            reasoning="Good",
            evidence=[],
            confidence=0.9,
            model_id="claude",
        )
        v2 = JudgeVerdict(
            mode=EvaluationMode.DIRECT,
            scores={},
            overall_score=0.7,
            reasoning="Decent",
            evidence=[],
            confidence=0.85,
            model_id="gpt-4o",
        )
        ensemble = EnsembleVerdict(
            consensus_score=0.75,
            per_model_verdicts=[v1, v2],
            vote_distribution={"0.8": 1, "0.7": 1},
            agreement_score=0.85,
            confidence=0.87,
        )
        assert ensemble.consensus_score == 0.75
        assert len(ensemble.per_model_verdicts) == 2
        assert ensemble.agreement_score == 0.85

    def test_immutability(self):
        ensemble = EnsembleVerdict(
            consensus_score=0.5,
            per_model_verdicts=[],
            vote_distribution={},
            agreement_score=0.0,
            confidence=0.0,
        )
        with pytest.raises(AttributeError):
            ensemble.consensus_score = 0.9  # type: ignore[misc]


class TestImports:
    """Test that all public types are exported from src.judge."""

    def test_all_exports(self):
        from src.judge import (
            CommentCategory,
            DimensionScore,
            DirectInput,
            EnsembleVerdict,
            EvaluationMode,
            JudgeInput,
            JudgeVerdict,
            LineComment,
            PairwiseInput,
            PairwiseVerdict,
            ReferenceInput,
            Severity,
        )

        # Verify they are the correct types
        assert issubclass(EvaluationMode, Enum)
        assert issubclass(Severity, Enum)
        assert issubclass(CommentCategory, Enum)
