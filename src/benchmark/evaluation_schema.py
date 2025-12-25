"""
Evaluation Report Schema and Writer

Defines the schema for evaluation_report.json that aggregates:
- Benchmark manifest metadata
- Harbor execution results
- LLM judge assessments
- Tool/token usage summaries
- Environment and provenance info
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import hashlib


@dataclass
class ToolUsageSummary:
    """Summary of tool usage during agent execution."""

    tool_name: str
    call_count: int
    success_count: int
    failure_count: int
    total_tokens: int = 0
    avg_tokens_per_call: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TokenMetrics:
    """Token usage metrics for an agent run."""

    total_input_tokens: int
    total_output_tokens: int
    total_cache_tokens: int
    total_cost_usd: Optional[float] = None

    # Detailed breakdown
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TimingMetrics:
    """Timing information for different execution phases."""

    environment_setup_sec: float
    agent_setup_sec: float
    agent_execution_sec: float
    verifier_sec: float
    total_sec: float

    started_at: str
    finished_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class JudgeAssessment:
    """LLM judge assessment for a dimension."""

    dimension: str  # "retrieval_quality", "code_quality", etc.
    score: float  # 1-5
    reasoning: str
    strengths: List[str]
    weaknesses: List[str]
    judge_model: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentRunEvaluation:
    """Evaluation results for a single agent run on a task."""

    # Identity
    trial_name: str
    task_name: str
    agent_name: str
    agent_import_path: str
    model_name: str

    # Results
    reward: float
    success: bool

    # Metrics
    token_metrics: TokenMetrics
    timing_metrics: TimingMetrics
    tool_usage: List[ToolUsageSummary]

    # Judge assessments (optional, populated by LLM judge)
    judge_assessments: List[JudgeAssessment] = field(default_factory=list)

    # Paths
    trajectory_path: str = ""
    result_path: str = ""

    # Error info
    exception_info: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trial_name": self.trial_name,
            "task_name": self.task_name,
            "agent_name": self.agent_name,
            "agent_import_path": self.agent_import_path,
            "model_name": self.model_name,
            "reward": self.reward,
            "success": self.success,
            "token_metrics": self.token_metrics.to_dict(),
            "timing_metrics": self.timing_metrics.to_dict(),
            "tool_usage": [t.to_dict() for t in self.tool_usage],
            "judge_assessments": [j.to_dict() for j in self.judge_assessments],
            "trajectory_path": self.trajectory_path,
            "result_path": self.result_path,
            "exception_info": self.exception_info,
        }


@dataclass
class BenchmarkMetadata:
    """Metadata about the benchmark from MANIFEST.json."""

    benchmark_id: str
    description: str
    task_root: str
    pipeline_version: str
    repo_commit: str
    generated_at: str

    # Dataset provenance
    datasets: List[Dict[str, Any]] = field(default_factory=list)

    # Environment fingerprint
    env_fingerprint_hash: str = ""

    # Validation breadcrumbs
    validation_steps: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentEvaluation:
    """Complete evaluation report for an experiment/profile run."""

    # Experiment identity
    experiment_id: str
    experiment_description: str
    profile_name: Optional[str] = None

    # Benchmark metadata (from MANIFEST.json)
    benchmark_metadata: Optional[BenchmarkMetadata] = None

    # Agent runs
    agent_runs: List[AgentRunEvaluation] = field(default_factory=list)

    # Summary statistics (computed)
    summary: Dict[str, Any] = field(default_factory=dict)

    # Report metadata
    report_version: str = "1.0.0"
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def compute_summary(self):
        """Compute aggregate statistics across all agent runs."""
        if not self.agent_runs:
            self.summary = {}
            return

        # Success rates by agent
        agent_stats: Dict[str, Dict[str, Any]] = {}
        for run in self.agent_runs:
            agent_name = run.agent_name
            if agent_name not in agent_stats:
                agent_stats[agent_name] = {
                    "total_runs": 0,
                    "successes": 0,
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                    "avg_reward": 0.0,
                    "judge_scores": {},
                }

            stats = agent_stats[agent_name]
            stats["total_runs"] += 1
            stats["successes"] += 1 if run.success else 0
            stats["total_tokens"] += run.token_metrics.total_input_tokens + run.token_metrics.total_output_tokens
            if run.token_metrics.total_cost_usd:
                stats["total_cost_usd"] += run.token_metrics.total_cost_usd

            # Average judge scores
            for assessment in run.judge_assessments:
                dim = assessment.dimension
                if dim not in stats["judge_scores"]:
                    stats["judge_scores"][dim] = []
                stats["judge_scores"][dim].append(assessment.score)

        # Compute averages
        for agent_name, stats in agent_stats.items():
            total = stats["total_runs"]
            stats["success_rate"] = stats["successes"] / total if total > 0 else 0.0
            stats["avg_tokens"] = stats["total_tokens"] / total if total > 0 else 0

            # Average judge scores by dimension
            for dim, scores in stats["judge_scores"].items():
                stats["judge_scores"][dim] = {
                    "mean": sum(scores) / len(scores) if scores else 0.0,
                    "min": min(scores) if scores else 0.0,
                    "max": max(scores) if scores else 0.0,
                }

        self.summary = {
            "total_runs": len(self.agent_runs),
            "agents": agent_stats,
        }

    def to_dict(self) -> Dict[str, Any]:
        self.compute_summary()
        return {
            "experiment_id": self.experiment_id,
            "experiment_description": self.experiment_description,
            "profile_name": self.profile_name,
            "benchmark_metadata": self.benchmark_metadata.to_dict() if self.benchmark_metadata else None,
            "agent_runs": [run.to_dict() for run in self.agent_runs],
            "summary": self.summary,
            "report_version": self.report_version,
            "generated_at": self.generated_at,
        }

    def save(self, output_path: Path):
        """Save evaluation report to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, input_path: Path) -> "ExperimentEvaluation":
        """Load evaluation report from JSON file."""
        with open(input_path) as f:
            data = json.load(f)

        # Reconstruct dataclass (simplified - assumes valid structure)
        obj = cls(
            experiment_id=data["experiment_id"],
            experiment_description=data["experiment_description"],
            profile_name=data.get("profile_name"),
            report_version=data.get("report_version", "1.0.0"),
            generated_at=data.get("generated_at", ""),
        )

        # Load benchmark metadata
        if data.get("benchmark_metadata"):
            bm = data["benchmark_metadata"]
            obj.benchmark_metadata = BenchmarkMetadata(**bm)

        # Load agent runs (simplified - would need full reconstruction)
        obj.summary = data.get("summary", {})

        return obj


def load_benchmark_manifest(manifest_path: Path) -> Optional[BenchmarkMetadata]:
    """Load benchmark metadata from MANIFEST.json."""
    if not manifest_path.exists():
        return None

    with open(manifest_path) as f:
        data = json.load(f)

    # Extract relevant fields
    env_fp = data.get("environment", {}).get("fingerprint", {})

    return BenchmarkMetadata(
        benchmark_id=data.get("benchmark_id", "unknown"),
        description=data.get("description", ""),
        task_root=data.get("task_root", ""),
        pipeline_version=data.get("pipeline", {}).get("version", "unknown"),
        repo_commit=data.get("repo_commit", ""),
        generated_at=data.get("generated_at", ""),
        datasets=data.get("datasets", []),
        env_fingerprint_hash=env_fp.get("combined_hash", ""),
        validation_steps=data.get("validation", {}).get("steps", []),
    )
