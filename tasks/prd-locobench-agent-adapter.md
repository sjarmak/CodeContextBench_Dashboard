# PRD: LoCoBench-Agent Harbor Adapter

## Introduction

Create a Harbor adapter for LoCoBench-Agent benchmark tasks, selecting ~50 tasks that best demonstrate the value of code search and codebase understanding tools (Sourcegraph MCP). The adapter will convert LoCoBench-Agent's 8,000 interactive scenarios into Harbor's task format, focusing on tasks where semantic search, cross-file reasoning, and architectural understanding provide measurable advantages over baseline agents.

## Goals

- Download and parse LoCoBench-Agent dataset (8,000 scenarios across 10 languages)
- Develop task selection criteria that maximize MCP value demonstration
- Select ~50 high-impact tasks based on complexity metrics (files modified, context breadth, multi-hop dependencies)
- Create Harbor adapter following existing patterns (repoqa, dibench, swebench_pro)
- Validate adapter works with baseline agent on 1-2 smoke test tasks
- Document selection criteria and adapter usage

## User Stories

### US-001: Download and explore LoCoBench-Agent dataset
**Description:** As a developer, I need to download the LoCoBench-Agent data so I can analyze its structure and select appropriate tasks.

**Acceptance Criteria:**
- [ ] Download LoCoBench-Agent data from Google Drive link
- [ ] Unzip and document directory structure in `benchmarks/locobench_agent/DATA_EXPLORATION.md`
- [ ] Identify key fields: task_id, repository, commit, language, task_type, context_length, ground_truth format
- [ ] Document any schema differences from expected LOCOBENCH_ADAPTER_GUIDE.md assumptions

### US-002: Define task selection criteria for MCP value
**Description:** As a benchmark designer, I want clear criteria for selecting tasks that will show MCP advantages so the benchmark is impactful.

**Acceptance Criteria:**
- [ ] Define quantitative metrics: min files modified (>3), min context length (>50K tokens), cross-file dependencies required
- [ ] Define qualitative filters: architectural understanding, bug investigation, dependency traversal task types
- [ ] Create `docs/TASK_SELECTION_CRITERIA.md` documenting the scoring/filtering approach
- [ ] Selection is language-agnostic (complexity over language diversity)

### US-003: Create dataset extraction script
**Description:** As a developer, I need to extract LoCoBench-Agent data into JSONL format so the adapter can consume it.

**Acceptance Criteria:**
- [ ] Create `benchmarks/locobench_agent/extract_dataset.py`
- [ ] Script reads LoCoBench-Agent native format and outputs normalized JSONL
- [ ] Each JSONL line contains: task_id, scenario_id, repository, commit, language, task_type, difficulty, context_length, instruction, ground_truth, semantic_metadata
- [ ] Script handles edge cases (missing fields, malformed data) gracefully
- [ ] Typecheck passes

### US-004: Implement task scoring and selection
**Description:** As a benchmark designer, I need to score and rank tasks by MCP value so I can select the top 50.

**Acceptance Criteria:**
- [ ] Create `benchmarks/locobench_agent/select_tasks.py`
- [ ] Implement scoring function based on: files_modified_count, context_length, cross_file_flag, multi_hop_flag, task_type
- [ ] Output ranked list with scores to `benchmarks/locobench_agent/selected_tasks.json`
- [ ] Select top 50 tasks, log selection rationale
- [ ] Typecheck passes

### US-005: Create Harbor adapter class
**Description:** As a developer, I need an adapter that converts LoCoBench tasks to Harbor format so they can run in the benchmark framework.

**Acceptance Criteria:**
- [ ] Create `benchmarks/locobench_agent/adapter.py` following repoqa/dibench patterns
- [ ] Implement `LoCoBenchTask` dataclass with all required fields
- [ ] Implement `LoCoBenchLoader` to load from JSONL
- [ ] Implement `LoCoBenchAdapter.generate_task()` to create Harbor task directories
- [ ] Adapter imports Harbor models correctly (TaskConfig, TaskPaths, etc.)
- [ ] Typecheck passes

### US-006: Create task templates
**Description:** As a developer, I need templates for Harbor task generation so tasks have consistent structure.

**Acceptance Criteria:**
- [ ] Create `templates/task.toml` with metadata placeholders
- [ ] Create `templates/instruction.md` with task description format
- [ ] Create `templates/environment/Dockerfile` for task execution environment
- [ ] Create `templates/tests/test.sh` for verification script
- [ ] Templates use `{placeholder}` syntax for variable substitution

### US-007: Create run_adapter.py CLI
**Description:** As a developer, I need a CLI script to generate Harbor tasks from selected LoCoBench tasks.

**Acceptance Criteria:**
- [ ] Create `benchmarks/locobench_agent/run_adapter.py`
- [ ] Support `--dataset_path`, `--output_dir`, `--task_ids`, `--limit` arguments
- [ ] Log progress and any errors during generation
- [ ] Generated tasks follow Harbor directory structure (instruction.md, task.toml, tests/, environment/)
- [ ] Typecheck passes

### US-008: Generate 50 selected tasks
**Description:** As a developer, I need to generate the 50 selected tasks into Harbor format.

**Acceptance Criteria:**
- [ ] Run adapter on selected_tasks.json to generate 50 task directories
- [ ] Tasks saved to `benchmarks/locobench_agent/tasks/`
- [ ] Each task directory contains: instruction.md, task.toml, tests/ground_truth.json, tests/test.sh, environment/Dockerfile
- [ ] No generation errors for selected tasks

### US-009: Smoke test with baseline agent
**Description:** As a developer, I need to validate the adapter works by running 1-2 tasks with the baseline agent.

**Acceptance Criteria:**
- [ ] Select 2 diverse tasks from the 50 (different languages/types)
- [ ] Run `harbor run` with baseline agent on each task
- [ ] Tasks execute without adapter/framework errors
- [ ] Document any issues or adjustments needed in `benchmarks/locobench_agent/SMOKE_TEST_RESULTS.md`

### US-010: Create benchmark documentation
**Description:** As a developer, I need documentation so others can understand and use the LoCoBench adapter.

**Acceptance Criteria:**
- [ ] Create `benchmarks/locobench_agent/README.md` with overview, setup, and usage
- [ ] Create `benchmarks/locobench_agent/DESIGN.md` explaining adapter architecture
- [ ] Document task selection criteria and MCP value hypothesis
- [ ] Include example commands for running tasks

## Functional Requirements

- FR-1: The extraction script must handle LoCoBench-Agent's native data format and convert to normalized JSONL
- FR-2: The selection script must score tasks using: context_length (weight: 0.3), files_modified (weight: 0.3), cross_file_deps (weight: 0.2), task_type_bonus (weight: 0.2)
- FR-3: Task type bonuses: architectural_understanding=1.0, bug_investigation=0.9, dependency_traversal=0.8, feature_implementation=0.5
- FR-4: The adapter must create valid Harbor task directories that pass `harbor validate`
- FR-5: Templates must support variable substitution for: task_id, repository, commit, language, task_type, difficulty, context_length, instruction
- FR-6: The Dockerfile must clone the target repository at the specified commit
- FR-7: The test.sh must invoke a verifier that checks agent output against ground_truth.json

## Non-Goals

- No full benchmark run (50 tasks) locally - that happens on VM
- No dashboard integration in this phase
- No custom verifier logic beyond basic ground truth comparison
- No MCP agent comparison locally - just baseline smoke test
- No language-specific optimizations in task selection

## Technical Considerations

- Follow existing adapter patterns in `benchmarks/repoqa/` and `benchmarks/dibench/`
- Use Harbor models from `src/harbor/models/` via dynamic import pattern
- LoCoBench-Agent data is ~2GB zipped - ensure adequate disk space
- Some repositories may be archived/unavailable - handle gracefully
- Context length in tokens - may need to verify this maps to actual file sizes

## Success Metrics

- 50 tasks generated without errors
- 2 smoke test tasks complete with baseline agent (pass or fail, but no framework errors)
- Selection criteria documented with rationale
- Adapter code follows existing Harbor patterns (reviewable by comparing to repoqa/dibench)

## Open Questions

- What is the exact format of LoCoBench-Agent's ground_truth field? (Need to explore data)
- Are all 8,000 repositories still accessible on GitHub? (May need fallback strategy)
- What verification approach should test.sh use? (Exact match vs semantic comparison)
- Does Harbor have a standard way to handle multi-turn evaluation, or do we collapse to single-turn?
