"""
IR-SDLC-Bench: Information Retrieval for Software Development Lifecycle Tasks

This module provides the core functionality for generating and evaluating
information retrieval tasks across enterprise-scale software repositories,
with full compatibility with the Harbor evaluation framework.
"""

from .task_types import (
    SDLCTaskType,
    BugTriageTask,
    CodeReviewTask,
    DependencyAnalysisTask,
    ArchitectureUnderstandingTask,
    SecurityAuditTask,
    RefactoringAnalysisTask,
    TestCoverageTask,
    DocumentationLinkingTask,
    get_task_generator,
    TASK_GENERATORS,
)

from .data_structures import (
    IRTask,
    RetrievalResult,
    GroundTruth,
    IREvaluationResult,
    IRDataset,
    CodeLocation,
    RetrievalGranularity,
)

from .harbor_adapter import (
    HarborTaskGenerator,
    HarborConfig,
    generate_harbor_task,
    generate_harbor_dataset,
    generate_registry_entry,
)

from .metrics import (
    IRMetrics,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_mrr,
    compute_ndcg,
    compute_map,
    compute_hit_rate,
    compute_f1_at_k,
    compute_file_level_recall,
    compute_function_level_precision,
    compute_cross_module_coverage,
    compute_context_efficiency,
    aggregate_metrics,
)

from .llm_judge import (
    LLMJudge,
    LLMJudgeScore,
    JudgeInput,
    JudgeResult,
    EvaluationDimension,
    EvaluationCriterion,
    MockLLMBackend,
    compute_judge_aggregate_scores,
    export_results_to_json,
    DEFAULT_CRITERIA,
)

__all__ = [
    # Task Types
    "SDLCTaskType",
    "BugTriageTask",
    "CodeReviewTask",
    "DependencyAnalysisTask",
    "ArchitectureUnderstandingTask",
    "SecurityAuditTask",
    "RefactoringAnalysisTask",
    "TestCoverageTask",
    "DocumentationLinkingTask",
    "get_task_generator",
    "TASK_GENERATORS",
    # Data Structures
    "IRTask",
    "RetrievalResult",
    "GroundTruth",
    "IREvaluationResult",
    "IRDataset",
    "CodeLocation",
    "RetrievalGranularity",
    # Harbor Adapter
    "HarborTaskGenerator",
    "HarborConfig",
    "generate_harbor_task",
    "generate_harbor_dataset",
    "generate_registry_entry",
    # Metrics
    "IRMetrics",
    "compute_precision_at_k",
    "compute_recall_at_k",
    "compute_mrr",
    "compute_ndcg",
    "compute_map",
    "compute_hit_rate",
    "compute_f1_at_k",
    "compute_file_level_recall",
    "compute_function_level_precision",
    "compute_cross_module_coverage",
    "compute_context_efficiency",
    "aggregate_metrics",
    # LLM Judge
    "LLMJudge",
    "LLMJudgeScore",
    "JudgeInput",
    "JudgeResult",
    "EvaluationDimension",
    "EvaluationCriterion",
    "MockLLMBackend",
    "compute_judge_aggregate_scores",
    "export_results_to_json",
    "DEFAULT_CRITERIA",
]
