# PRD: Harbor Benchmark Adapters & Quality Framework

## Introduction

This PRD defines the work to create Harbor adapters for five external benchmarks and establish infrastructure for evaluating benchmark quality. The goal is to expand our evaluation coverage for measuring the value-add of the Sourcegraph MCP (including deep search) by integrating diverse benchmark types beyond our current SWE-bench Pro and LoCoBench adapters.

The benchmarks target different aspects of agent capabilities:
- **AINativeBench**: End-to-end AI-native application workloads (8 scenarios)
- **DevAI**: Agent-as-a-judge evaluation paradigm (55 tasks, 365 requirements)
- **PRDBench**: PRD-to-implementation evaluation with conversational judging
- **SWE-Perf**: Performance optimization tasks (140 instances)
- **TheAgentCompany (TAC)**: Professional role simulations (175 tasks)

Additionally, we'll implement the HOW2BENCH 55-criteria checklist to validate our benchmarks measure the correct things.

## Goals

- Create Harbor-compatible adapters for 5 benchmarks with minimal smoke test validation (1-3 tasks each)
- Implement MCP-value scoring for task selection across all benchmarks
- Build standalone agent-as-a-judge evaluator that works with any Harbor benchmark results
- Establish HOW2BENCH quality framework for pre-flight validation, compliance auditing, and task scoring
- Ensure all adapters follow existing patterns (loader → adapter → CLI) for consistency
- Enable ingestion pipeline compatibility for dashboard analysis

## User Stories

---

### Phase 1: Adapter Infrastructure

#### US-001: AINativeBench Full Adapter
**Description:** As a benchmark operator, I want a full Harbor adapter for AINativeBench so that I can evaluate agents on end-to-end AI-native application workloads.

**Acceptance Criteria:**
- [ ] Create `benchmarks/ainativebench/` directory structure following LoCoBench pattern
- [ ] Implement `AINativeBenchTask` dataclass with fields: id, benchmark_name (one of 8), variant (single/mcp/a2a/h_a2a), test_cases, scoring_metrics
- [ ] Implement `AINativeBenchLoader` with `filter_by_benchmark()`, `filter_by_variant()` methods
- [ ] Implement `AINativeBenchAdapter` with template rendering for task.toml, instruction.md, Dockerfile
- [ ] Create language-specific Dockerfile templates (Python 3.10+, uv package manager)
- [ ] Implement verifier that parses AINativeBench's native `test_results/` JSON output
- [ ] Create `run_adapter.py` CLI with `--benchmark`, `--variant`, `--limit` flags
- [ ] Typecheck passes (`pyright benchmarks/ainativebench/`)

#### US-002: DevAI Full Adapter
**Description:** As a benchmark operator, I want a full Harbor adapter for DevAI so that I can evaluate agents on hierarchical requirement satisfaction with agent-as-a-judge.

**Acceptance Criteria:**
- [ ] Create `benchmarks/devai/` directory structure
- [ ] Implement `DevAITask` dataclass with fields: id, user_query, requirements (DAG structure), preferences, domain (ml/cv/nlp/rl/generative)
- [ ] Implement `DevAILoader` that parses the 55 tasks and their 365 requirements
- [ ] Implement `DevAIAdapter` with workspace generation matching DevAI's expected structure
- [ ] Create verifier that validates trajectory format against `trajectory-schema.json`
- [ ] Integrate agent-as-a-judge as evaluation option (see US-010)
- [ ] Create `run_adapter.py` CLI with `--domain`, `--limit` flags
- [ ] Typecheck passes

#### US-003: PRDBench Full Adapter
**Description:** As a benchmark operator, I want a full Harbor adapter for PRDBench so that I can evaluate agents on PRD-to-implementation tasks.

**Acceptance Criteria:**
- [ ] Create `benchmarks/prdbench/` directory structure
- [ ] Implement `PRDBenchTask` dataclass with fields: id, prd_content, test_plan, evaluation_criteria
- [ ] Implement `PRDBenchLoader` that reads `{task_id}/src/PRD.md` and `{task_id}/evaluation/detailed_test_plan.json`
- [ ] Implement `PRDBenchAdapter` with template rendering
- [ ] Create Dockerfile with conda environment support and multi-port configuration
- [ ] Implement verifier that runs PRDBench's native evaluation or agent-as-a-judge
- [ ] Create `run_adapter.py` CLI with `--task_ids`, `--limit` flags
- [ ] Typecheck passes

#### US-004: SWE-Perf Wrapper Adapter
**Description:** As a benchmark operator, I want a thin wrapper adapter for SWE-Perf so that I can evaluate agents on performance optimization tasks using their existing infrastructure.

**Acceptance Criteria:**
- [ ] Create `benchmarks/sweperf/` directory structure
- [ ] Implement `SWEPerfTask` dataclass with fields: id, repo_name, target_function, human_solution_reference, baseline_runtime
- [ ] Implement `SWEPerfLoader` that loads the 140 instances from their dataset
- [ ] Implement thin `SWEPerfAdapter` that generates Harbor metadata (task.toml, instruction.md) wrapping SWE-Perf's evaluation
- [ ] Dockerfile pulls SWE-Perf's existing container/environment
- [ ] Verifier wraps SWE-Perf's runtime measurement and converts to reward.json (runtime_reduction as primary metric)
- [ ] Create `run_adapter.py` CLI with `--repo`, `--limit` flags
- [ ] Typecheck passes

#### US-005: TheAgentCompany Wrapper Adapter Completion
**Description:** As a benchmark operator, I want to complete the TAC wrapper adapter (started in `tac_mcp_value/`) so that I can evaluate agents on professional role simulations.

**Acceptance Criteria:**
- [ ] Review existing `benchmarks/tac_mcp_value/` implementation
- [ ] Complete `TACTask` dataclass if missing fields
- [ ] Complete `TACLoader` with `filter_by_role()` (SWE, PM, DS, HR, Finance, Admin)
- [ ] Ensure adapter wraps TAC's Docker images and `/utils/eval.py` evaluator
- [ ] Verify MCP configuration injection via environment variables works
- [ ] Create/update `run_adapter.py` CLI with `--role`, `--limit` flags
- [ ] Document which of the 175 tasks are selected for MCP-value testing
- [ ] Typecheck passes

---

### Phase 2: MCP-Value Task Selection

#### US-006: MCP-Value Scoring Framework
**Description:** As a benchmark operator, I want a reusable MCP-value scoring system so that I can select high-value tasks from any benchmark for MCP evaluation.

**Acceptance Criteria:**
- [ ] Create `src/task_selection/mcp_value_scorer.py` with `MCPValueScorer` class
- [ ] Implement scoring dimensions: context_complexity (0.3), cross_file_deps (0.3), semantic_search_potential (0.2), task_category_weight (0.2)
- [ ] Create `score_task(task: dict) -> float` method returning 0.0-1.0
- [ ] Create `select_top_tasks(tasks: list, n: int) -> list` method
- [ ] Implement benchmark-specific scoring adapters that normalize task metadata to common format
- [ ] Add unit tests for scorer with known task examples
- [ ] Typecheck passes

#### US-007: Task Selection Scripts per Benchmark
**Description:** As a benchmark operator, I want task selection scripts for each benchmark so that I can generate MCP-value-optimized task subsets.

**Acceptance Criteria:**
- [ ] Create `benchmarks/ainativebench/select_tasks.py` using MCPValueScorer
- [ ] Create `benchmarks/devai/select_tasks.py` using MCPValueScorer
- [ ] Create `benchmarks/prdbench/select_tasks.py` using MCPValueScorer
- [ ] Create `benchmarks/sweperf/select_tasks.py` using MCPValueScorer
- [ ] Update `benchmarks/tac_mcp_value/select_tasks.py` to use MCPValueScorer
- [ ] Each script outputs ranked task list with scores to `selected_tasks.json`
- [ ] Typecheck passes

---

### Phase 3: Agent-as-a-Judge Infrastructure

#### US-008: Standalone Agent-as-a-Judge Evaluator
**Description:** As a benchmark operator, I want a standalone agent-as-a-judge tool so that I can evaluate any Harbor benchmark results using LLM-based judgment.

**Acceptance Criteria:**
- [ ] Create `src/evaluation/agent_judge.py` with `AgentJudge` class
- [ ] Implement `evaluate_result(task: HarborResult, criteria: list[str]) -> JudgmentResult` method
- [ ] Support configurable LLM backend (OpenAI, Anthropic) via environment variables
- [ ] Implement structured output parsing for requirement satisfaction scores
- [ ] Create `JudgmentResult` dataclass with: overall_score, requirement_scores (dict), reasoning, confidence
- [ ] Add rate limiting and retry logic for API calls
- [ ] Typecheck passes

#### US-009: Agent-as-a-Judge CLI
**Description:** As a benchmark operator, I want a CLI for agent-as-a-judge so that I can batch-evaluate results from any experiment.

**Acceptance Criteria:**
- [ ] Create `scripts/run_agent_judge.py` CLI
- [ ] Support `--results_dir` to point to Harbor results
- [ ] Support `--criteria_file` for custom evaluation criteria (JSON/YAML)
- [ ] Support `--output_dir` for judgment results
- [ ] Support `--model` flag (default: gpt-4o)
- [ ] Output judgments to `{task_id}_judgment.json` files
- [ ] Generate summary report with aggregate statistics
- [ ] Typecheck passes

#### US-010: Agent-as-a-Judge Verifier Integration
**Description:** As a benchmark operator, I want to use agent-as-a-judge as a verifier option in any adapter so that I can choose between deterministic and LLM-based evaluation.

**Acceptance Criteria:**
- [ ] Create `src/evaluation/agent_judge_verifier.py` implementing Harbor verifier interface
- [ ] Verifier reads task criteria from `ground_truth.json` or dedicated criteria file
- [ ] Verifier outputs standard `reward.json` with judgment score as primary metric
- [ ] Add `verifier_type` option to task.toml template: "deterministic" | "agent_judge" | "hybrid"
- [ ] Update adapter base template to support verifier type selection
- [ ] Document usage in adapter README files
- [ ] Typecheck passes

---

### Phase 4: HOW2BENCH Quality Framework

#### US-011: HOW2BENCH Checklist Data Model
**Description:** As a quality engineer, I want the 55-criteria HOW2BENCH checklist as structured data so that I can programmatically assess benchmark quality.

**Acceptance Criteria:**
- [ ] Create `src/quality/how2bench_checklist.py` with all 55 criteria as structured data
- [ ] Organize criteria into categories: data_quality, reproducibility, methodology
- [ ] Each criterion has: id, category, description, severity (critical/important/recommended), automated (bool)
- [ ] Create `ChecklistResult` dataclass with: criterion_id, passed, evidence, notes
- [ ] Create `BenchmarkAuditReport` dataclass aggregating all results
- [ ] Typecheck passes

#### US-012: Pre-flight Validation Checks
**Description:** As a benchmark operator, I want automated pre-flight checks before deploying adapters so that I can catch quality issues early.

**Acceptance Criteria:**
- [ ] Create `src/quality/preflight_validator.py` with `PreflightValidator` class
- [ ] Implement checks for: task.toml schema validity, Dockerfile buildability, test.sh executability
- [ ] Implement checks for: ground_truth.json presence, instruction.md completeness
- [ ] Implement checks for: no hardcoded secrets, valid timeout values, resource limits set
- [ ] Return structured validation report with pass/fail per check
- [ ] Create `scripts/validate_adapter.py` CLI that runs preflight on adapter directory
- [ ] Typecheck passes

#### US-013: Documentation Compliance Audit
**Description:** As a quality engineer, I want to generate compliance reports for each benchmark so that I can track quality improvements.

**Acceptance Criteria:**
- [ ] Create `src/quality/compliance_auditor.py` with `ComplianceAuditor` class
- [ ] Implement `audit_benchmark(benchmark_dir: Path) -> BenchmarkAuditReport`
- [ ] Check README.md presence and required sections
- [ ] Check DESIGN.md with task selection rationale
- [ ] Check LICENSE compatibility
- [ ] Check data source attribution
- [ ] Generate markdown compliance report
- [ ] Create `scripts/audit_benchmark.py` CLI
- [ ] Typecheck passes

#### US-014: Task Quality Scoring
**Description:** As a quality engineer, I want to score individual tasks against applicable HOW2BENCH criteria so that I can identify low-quality tasks.

**Acceptance Criteria:**
- [ ] Create `src/quality/task_quality_scorer.py` with `TaskQualityScorer` class
- [ ] Implement scoring against applicable criteria: instruction clarity, ground truth validity, evaluation determinism
- [ ] Score each task 0.0-1.0 with breakdown by criterion
- [ ] Flag tasks below threshold (default 0.7) for review
- [ ] Create `scripts/score_task_quality.py` CLI
- [ ] Output quality scores to `task_quality_report.json`
- [ ] Typecheck passes

#### US-015: Quality Dashboard Integration
**Description:** As a quality engineer, I want quality metrics visible in the dashboard so that I can monitor benchmark health.

**Acceptance Criteria:**
- [ ] Add `benchmark_quality` table to database schema with: benchmark_id, checklist_scores, preflight_status, last_audited
- [ ] Create ingestion for quality reports into database
- [ ] Add quality summary to benchmark metadata in dashboard
- [ ] Display pre-flight validation status on benchmark detail page
- [ ] Typecheck passes

---

### Phase 5: Smoke Test Validation

#### US-016: Smoke Test Runner
**Description:** As a benchmark operator, I want a smoke test runner so that I can validate adapters produce correct output before full VM deployment.

**Acceptance Criteria:**
- [ ] Create `scripts/smoke_test_adapter.py` CLI
- [ ] Support `--adapter_dir` pointing to benchmark adapter
- [ ] Support `--num_tasks` (default: 3) for number of tasks to test
- [ ] Generate tasks using adapter's `run_adapter.py`
- [ ] Validate generated task structure (task.toml, instruction.md, Dockerfile, test.sh present)
- [ ] Optionally build Docker image (`--build` flag)
- [ ] Optionally run verifier with mock agent output (`--verify` flag)
- [ ] Output smoke test report with pass/fail per task
- [ ] Typecheck passes

#### US-017: AINativeBench Smoke Test
**Description:** As a benchmark operator, I want smoke test validation for AINativeBench adapter so that I can confirm it works before VM deployment.

**Acceptance Criteria:**
- [ ] Run smoke test on 1-3 AINativeBench tasks
- [ ] Verify task.toml has correct metadata (category: ainativebench)
- [ ] Verify instruction.md contains benchmark-specific instructions
- [ ] Verify reward.json output format matches Harbor spec
- [ ] Document any adapter-specific setup requirements
- [ ] Smoke test passes

#### US-018: DevAI Smoke Test
**Description:** As a benchmark operator, I want smoke test validation for DevAI adapter so that I can confirm it works before VM deployment.

**Acceptance Criteria:**
- [ ] Run smoke test on 1-3 DevAI tasks
- [ ] Verify trajectory schema validation works
- [ ] Verify agent-as-a-judge integration produces valid judgment
- [ ] Verify reward.json output format matches Harbor spec
- [ ] Smoke test passes

#### US-019: PRDBench Smoke Test
**Description:** As a benchmark operator, I want smoke test validation for PRDBench adapter so that I can confirm it works before VM deployment.

**Acceptance Criteria:**
- [ ] Run smoke test on 1-3 PRDBench tasks
- [ ] Verify PRD.md content is correctly embedded in instruction.md
- [ ] Verify test_plan.json is accessible to verifier
- [ ] Verify reward.json output format matches Harbor spec
- [ ] Smoke test passes

#### US-020: SWE-Perf Smoke Test
**Description:** As a benchmark operator, I want smoke test validation for SWE-Perf adapter so that I can confirm it works before VM deployment.

**Acceptance Criteria:**
- [ ] Run smoke test on 1-3 SWE-Perf tasks
- [ ] Verify wrapper correctly invokes SWE-Perf evaluation
- [ ] Verify runtime_reduction metric is captured in reward.json
- [ ] Verify reward.json output format matches Harbor spec
- [ ] Smoke test passes

#### US-021: TAC Smoke Test
**Description:** As a benchmark operator, I want smoke test validation for TAC adapter so that I can confirm it works before VM deployment.

**Acceptance Criteria:**
- [ ] Run smoke test on 1-3 TAC tasks
- [ ] Verify TAC Docker image wrapper works
- [ ] Verify MCP configuration injection works
- [ ] Verify TAC's eval.py output is converted to reward.json
- [ ] Smoke test passes

---

## Functional Requirements

### Adapter Requirements
- FR-1: All adapters must follow the loader → adapter → CLI pattern established in LoCoBench
- FR-2: All adapters must output Harbor-compatible task structure (task.toml, instruction.md, environment/, tests/)
- FR-3: All verifiers must output `/logs/verifier/reward.json` and `/logs/verifier/reward.txt`
- FR-4: All adapters must support MCP configuration via environment variables
- FR-5: Full adapters (AINativeBench, DevAI, PRDBench) must implement custom evaluation logic
- FR-6: Wrapper adapters (SWE-Perf, TAC) must delegate to existing benchmark infrastructure

### Task Selection Requirements
- FR-7: MCPValueScorer must be benchmark-agnostic with pluggable normalization
- FR-8: Task selection must output ranked JSON with scores for auditability
- FR-9: Selection criteria weights must be configurable per benchmark

### Agent-as-a-Judge Requirements
- FR-10: Standalone evaluator must work with any Harbor result directory
- FR-11: Judgment results must include per-requirement scores and reasoning
- FR-12: Verifier integration must be opt-in via task.toml configuration

### Quality Framework Requirements
- FR-13: Pre-flight validation must run without network access (offline-capable)
- FR-14: Compliance audit must generate human-readable markdown reports
- FR-15: Task quality scores must integrate with existing dashboard database

### Smoke Test Requirements
- FR-16: Smoke tests must validate structure without requiring full task execution
- FR-17: Smoke tests must complete in under 5 minutes per adapter
- FR-18: Smoke test failures must provide actionable error messages

## Non-Goals (Out of Scope)

- Full benchmark execution (handled on VM infrastructure)
- Performance optimization of adapter code
- UI for adapter creation (CLI-only)
- Real-time benchmark monitoring
- Multi-tenant adapter isolation
- Adapter versioning/rollback
- Integration with external CI/CD systems
- Support for benchmarks not listed in this PRD

## Technical Considerations

### Dependencies
- Existing Harbor framework in `src/ir_sdlc/` and `src/ingest/`
- Existing adapter patterns in `benchmarks/swebench_pro/` and `benchmarks/locobench_agent/`
- LLM APIs (OpenAI, Anthropic) for agent-as-a-judge
- Docker for container builds

### File Organization
```
benchmarks/
├── ainativebench/           # US-001, US-007, US-017
├── devai/                   # US-002, US-007, US-018
├── prdbench/                # US-003, US-007, US-019
├── sweperf/                 # US-004, US-007, US-020
└── tac_mcp_value/           # US-005, US-007, US-021 (existing)

src/
├── task_selection/
│   └── mcp_value_scorer.py  # US-006
├── evaluation/
│   ├── agent_judge.py       # US-008
│   └── agent_judge_verifier.py  # US-010
└── quality/
    ├── how2bench_checklist.py   # US-011
    ├── preflight_validator.py   # US-012
    ├── compliance_auditor.py    # US-013
    └── task_quality_scorer.py   # US-014

scripts/
├── run_agent_judge.py       # US-009
├── validate_adapter.py      # US-012
├── audit_benchmark.py       # US-013
├── score_task_quality.py    # US-014
└── smoke_test_adapter.py    # US-016
```

### Integration Points
- Ingestion pipeline (`src/ingest/`) for result parsing
- Dashboard database (`src/ingest/database.py`) for quality metrics
- Config loader (`src/config/loader.py`) for benchmark configuration

## Success Metrics

- All 5 adapters pass smoke tests (1-3 tasks each) with valid reward.json output
- Agent-as-a-judge produces consistent scores (±0.1) on repeated evaluations
- Pre-flight validation catches 100% of malformed task structures
- Quality audit reports generated for all supported benchmarks
- Adapters are compatible with existing ingestion pipeline (no parser changes needed)

## Open Questions

1. Should agent-as-a-judge cache judgments for identical task+result pairs?
2. What is the SWE-Perf dataset access method (HuggingFace, GitHub, API)?
3. Should quality scores block deployment or just warn?
4. How should we handle benchmark updates/versioning from upstream?
