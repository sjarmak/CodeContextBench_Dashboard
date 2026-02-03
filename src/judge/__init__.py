"""Unified LLM Judge system for CodeContextBench.

Provides pairwise, direct (PR-review), and reference-based evaluation
with multi-model ensemble and bias detection.
"""

from src.judge.bias import (
    BiasLevel,
    BiasReport,
    compute_length_correlation,
    compute_position_consistency,
    generate_bias_report,
    inject_anti_bias_instructions,
)
from src.judge.metrics import (
    AgreementReport,
    compute_cohens_kappa,
    compute_fleiss_kappa,
    compute_krippendorff_alpha,
    compute_spearman_correlation,
    generate_agreement_report,
)
from src.judge.prompts import PromptTemplate, load_template, render
from src.judge.backends import (
    AnthropicBackend,
    AnthropicBackendConfig,
    JudgeBackend,
    OpenAIBackend,
    OpenAIBackendConfig,
    TogetherBackend,
    TogetherBackendConfig,
)
from src.judge.engine import JudgeConfig, JudgeError, UnifiedJudge, parse_json_response
from src.judge.ensemble import EnsembleConfig, EnsembleError, EnsembleJudge
from src.judge.experiment import (
    ExperimentDiff,
    JudgeExperiment,
    compare_experiments,
    create_experiment,
    list_experiments,
    load_experiment,
    save_experiment,
)
from src.judge.modes import DirectEvaluator, PairwiseEvaluator, ReferenceEvaluator
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

__all__ = [
    "AgreementReport",
    "AnthropicBackend",
    "AnthropicBackendConfig",
    "BiasLevel",
    "BiasReport",
    "CommentCategory",
    "DimensionScore",
    "DirectEvaluator",
    "DirectInput",
    "EnsembleConfig",
    "EnsembleError",
    "EnsembleJudge",
    "EnsembleVerdict",
    "ExperimentDiff",
    "EvaluationMode",
    "JudgeBackend",
    "JudgeConfig",
    "JudgeError",
    "JudgeExperiment",
    "JudgeInput",
    "JudgeVerdict",
    "LineComment",
    "OpenAIBackend",
    "OpenAIBackendConfig",
    "PairwiseEvaluator",
    "PairwiseInput",
    "ReferenceEvaluator",
    "PairwiseVerdict",
    "PromptTemplate",
    "ReferenceInput",
    "Severity",
    "TogetherBackend",
    "TogetherBackendConfig",
    "UnifiedJudge",
    "compare_experiments",
    "compute_cohens_kappa",
    "compute_fleiss_kappa",
    "compute_krippendorff_alpha",
    "compute_length_correlation",
    "compute_position_consistency",
    "compute_spearman_correlation",
    "create_experiment",
    "generate_agreement_report",
    "generate_bias_report",
    "inject_anti_bias_instructions",
    "list_experiments",
    "load_experiment",
    "load_template",
    "parse_json_response",
    "render",
    "save_experiment",
]
