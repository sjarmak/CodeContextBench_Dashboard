# CodeContextBench Observability Platform Refactor

## Executive Summary

Transform CodeContextBench from a local benchmark runner into an **observability and control plane** for VM-based Harbor evaluations, with bidirectional sync, abstract agent configuration, and integrated analysis pipeline.

---

## Architecture Overview

### Core Principles

1. **VM runs benchmarks, local interprets results** - VM is execution-only, all analysis happens locally
2. **Abstract agent configs** - Single source of truth for MCP/prompt configs, translated to agent-specific formats
3. **Bidirectional sync** - Push configs to VM, pull results back, feed analysis into config improvements
4. **IR + Patch evaluation** - IR-SDLC benchmarks measure both retrieval quality AND implementation correctness

---

## New Directory Structure

### Local (CodeContextBench)

```
CodeContextBench/
├── AGENTS.md                    # Project workflow guide
├── README.md                    # Overview

├── configs/                     # Abstract configuration layer
│   ├── agents/                  # Agent definitions (abstract)
│   │   ├── _base.yaml           # Shared defaults
│   │   ├── baseline.yaml        # No MCP
│   │   ├── strategic-deepsearch.yaml
│   │   ├── deepsearch-focused.yaml
│   │   ├── mcp-keyword-only.yaml
│   │   └── full-toolkit.yaml
│   ├── mcp/                     # MCP endpoint definitions
│   │   ├── sourcegraph-v1.yaml
│   │   └── sourcegraph-deepsearch.yaml
│   ├── benchmarks/              # Benchmark set definitions
│   │   ├── swebench-verified.yaml
│   │   ├── swebench-pro.yaml
│   │   └── ir-sdlc-multi-repo.yaml
│   └── experiments/             # Experiment definitions
│       └── 2026-01-02-baseline-vs-mcp.yaml

├── src/                         # Core library
│   ├── config/                  # Config layer
│   │   ├── __init__.py
│   │   ├── agent_schema.py      # Abstract agent config schema
│   │   ├── mcp_schema.py        # MCP endpoint schema
│   │   ├── experiment_schema.py # Experiment definition schema
│   │   └── loader.py            # Config loading/validation
│   ├── translate/               # Config translation layer
│   │   ├── __init__.py
│   │   ├── base.py              # Translator interface
│   │   ├── claude_translator.py # → .mcp.json, CLAUDE.md
│   │   ├── opencode_translator.py # → opencode.jsonc, skills/
│   │   └── openhands_translator.py # → config.toml, proxy
│   ├── sync/                    # VM sync layer
│   │   ├── __init__.py
│   │   ├── push.py              # Push configs to VM
│   │   ├── pull.py              # Pull results from VM
│   │   └── manifest.py          # Track what's synced
│   ├── ingest/                  # Result ingestion
│   │   ├── __init__.py
│   │   ├── harbor_parser.py     # Parse Harbor JSON logs
│   │   ├── transcript_parser.py # Parse claude-code.txt
│   │   ├── metrics_extractor.py # Extract tool usage, timing, costs
│   │   └── database.py          # Store in SQLite/DuckDB
│   ├── analysis/                # Analysis layer
│   │   ├── __init__.py
│   │   ├── comparator.py        # Baseline vs MCP comparison
│   │   ├── llm_judge.py         # LLM-as-judge evaluations
│   │   ├── ir_metrics.py        # Precision, Recall, MRR, NDCG
│   │   └── failure_patterns.py  # Pattern detection
│   ├── recommend/               # Recommendation layer
│   │   ├── __init__.py
│   │   ├── config_optimizer.py  # Suggest prompt/tool changes
│   │   └── experiment_tracker.py # Track experiments + progress
│   └── benchmark/               # Existing benchmark code (keep)
│       └── ...

├── dashboard/                   # Streamlit dashboard
│   ├── app.py                   # Main entry
│   ├── views/
│   │   ├── home.py              # Overview + quick stats
│   │   ├── experiments.py       # Experiment list + status
│   │   ├── ingestion.py         # Import results, validation
│   │   ├── analysis.py          # Interactive exploration
│   │   ├── comparison.py        # Agent comparison
│   │   ├── llm_judge.py         # Run/view LLM evaluations
│   │   ├── recommendations.py   # Config improvement suggestions
│   │   └── config_editor.py     # Edit abstract agent configs
│   └── utils/
│       └── ...

├── cli/                         # CLI tools
│   ├── __init__.py
│   ├── sync_cmd.py              # Push/pull commands
│   ├── ingest_cmd.py            # Import results
│   ├── analyze_cmd.py           # Run analysis
│   └── experiment_cmd.py        # Manage experiments

├── schemas/                     # JSON schemas for validation
│   ├── agent.schema.json
│   ├── mcp.schema.json
│   ├── experiment.schema.json
│   └── harbor_result.schema.json

├── data/                        # Local data storage
│   ├── results/                 # Synced from VM (raw)
│   │   └── <experiment_id>/
│   │       └── <job_id>/
│   │           ├── result.json
│   │           └── claude-code.txt
│   ├── metrics.db               # SQLite metrics store
│   └── experiments.db           # Experiment tracking

├── tests/                       # Unit + integration tests
└── scripts/                     # Utility scripts
    ├── vm_sync.sh               # Wrapper for rsync
    └── setup_vm.sh              # Initial VM setup
```

### VM (Linux - ~/evals)

```
~/evals/
├── AGENTS.md                    # VM-specific workflow notes

├── configs/                     # Received from local (read-only)
│   ├── agents/                  # Translated agent configs
│   │   ├── claudecode/
│   │   │   ├── baseline/
│   │   │   │   └── CLAUDE.md
│   │   │   └── strategic-deepsearch/
│   │   │       ├── .mcp.json
│   │   │       └── CLAUDE.md
│   │   ├── opencode/
│   │   │   ├── baseline/
│   │   │   │   └── opencode.jsonc
│   │   │   └── strategic-deepsearch/
│   │   │       ├── opencode.jsonc
│   │   │       └── skills/sourcegraph.md
│   │   └── openhands/
│   │       └── ...
│   └── benchmarks/              # Harbor-compatible task sets
│       ├── swebench-verified/
│       ├── ir-sdlc-multi-repo/
│       └── ...

├── agents/                      # Agent implementations (Python)
│   ├── __init__.py
│   ├── base.py                  # Shared agent base
│   ├── claudecode.py            # Claude Code agent
│   ├── opencode.py              # OpenCode agent
│   └── openhands.py             # OpenHands agent

├── jobs/                        # Harbor job outputs
│   └── <experiment_id>/
│       └── <job_id>/
│           ├── result.json      # Harbor result
│           ├── claude-code.txt  # Agent transcript
│           ├── *.patch          # Generated patches
│           └── logs/            # Execution logs

├── experiments/                 # Experiment execution
│   ├── active/                  # Currently running
│   └── completed/               # Finished experiments

├── scripts/                     # Execution scripts
│   ├── run_experiment.py        # Main experiment runner
│   ├── validate_output.py       # Quick sanity checks
│   └── harbor_wrapper.sh        # Harbor CLI wrapper

└── .env.local                   # Credentials (never synced)
```

---

## Abstract Agent Config Schema

```yaml
# configs/agents/strategic-deepsearch.yaml
agent_id: strategic-deepsearch
display_name: "Strategic Deep Search"
description: "Uses Sourcegraph Deep Search at critical checkpoints"

# Base agent to extend
extends: _base

# MCP configuration
mcp:
  endpoints:
    - $ref: ../mcp/sourcegraph-v1.yaml
    - $ref: ../mcp/sourcegraph-deepsearch.yaml
  
  # Tool permissions (agent-agnostic names)
  tools:
    - sg_keyword_search
    - sg_nls_search
    - sg_read_file
    - sg_list_repos
    - sg_list_files
    - sg_go_to_definition
    - sg_commit_search
    - deepsearch

# Prompting configuration
prompts:
  system: |
    You MUST complete this task by making real code changes.
    
    You have access to Sourcegraph MCP tools for code understanding.
    Use Deep Search at these critical checkpoints:
    1. Initial codebase exploration
    2. Before making architectural decisions
    3. When stuck or unsure about approach
    
    For routine file operations, use local tools.
  
  claude_md: |
    # Sourcegraph Deep Search - Strategic Usage Guide
    
    ## When to Use Deep Search
    - Understanding overall architecture
    - Finding cross-cutting concerns
    - Answering "how does X work" questions
    
    ## When to Use Local Tools
    - Reading specific files you've identified
    - Making edits
    - Running tests

# Model configuration
model:
  default: anthropic/claude-haiku-4-5-20251001
  allowed:
    - anthropic/claude-haiku-4-5-20251001
    - anthropic/claude-sonnet-4-20250514

# Agent-specific overrides (optional)
overrides:
  claudecode:
    env:
      FORCE_AUTO_BACKGROUND_TASKS: "1"
      ENABLE_BACKGROUND_TASKS: "1"
      NODE_TLS_REJECT_UNAUTHORIZED: "0"
  
  opencode:
    # OpenCode-specific settings
    model_mapping:
      anthropic/claude-haiku-4-5-20251001: claude-3-5-haiku
```

---

## MCP Endpoint Schema

```yaml
# configs/mcp/sourcegraph-v1.yaml
endpoint_id: sourcegraph-v1
display_name: "Sourcegraph MCP v1"
url: https://sourcegraph.sourcegraph.com/.api/mcp/v1

auth:
  type: token
  env_var: SOURCEGRAPH_ACCESS_TOKEN
  header_format: "token {token}"

tools:
  - id: sg_keyword_search
    description: Fast keyword-based search across large codebases
  - id: sg_nls_search
    description: Natural language semantic search
  - id: sg_read_file
    description: Read file contents with full context
  - id: sg_list_repos
    description: List available repositories
  - id: sg_list_files
    description: Find files by pattern
  - id: sg_go_to_definition
    description: Navigate to symbol definitions
  - id: sg_commit_search
    description: Search commit history
```

---

## Experiment Schema

```yaml
# configs/experiments/2026-01-02-baseline-vs-mcp.yaml
experiment_id: 2026-01-02-baseline-vs-mcp
name: "Baseline vs MCP Comparison - SWE-bench Pro"
description: "Compare baseline Claude Code against strategic Deep Search on first 10 SWE-bench Pro tasks"

# Hypothesis being tested
hypothesis: |
  Strategic use of Deep Search will improve task completion rate
  by providing better initial context for complex codebases.

# Agents to compare
agents:
  - $ref: ../agents/baseline.yaml
  - $ref: ../agents/strategic-deepsearch.yaml

# Benchmark configuration
benchmark:
  $ref: ../benchmarks/swebench-pro.yaml
  task_filter:
    limit: 10
    # Or explicit list:
    # include:
    #   - django__django-15800
    #   - sympy__sympy-25104

# Execution settings
execution:
  n_attempts: 1
  timeout_multiplier: 1.0
  concurrent_trials: 1
  model: anthropic/claude-haiku-4-5-20251001

# Success criteria
success_criteria:
  min_improvement: 0.05  # 5% improvement in pass rate
  confidence_level: 0.95

# Tracking
created_at: 2026-01-02T10:00:00Z
created_by: stephanie_jarmak
status: pending  # pending → running → completed → analyzed
```

---

## Data Flow

### 1. Config Push Flow

```
Local: Edit abstract config (YAML)
    ↓
Local: Validate against schema
    ↓
Local: Translate to agent-specific formats
    ↓
Local: Package into sync bundle
    ↓
rsync → VM: configs/
```

### 2. Experiment Execution Flow

```
VM: Receive configs/
    ↓
VM: run_experiment.py reads experiment YAML
    ↓
VM: Harbor CLI executes tasks
    ↓
VM: Results written to jobs/<experiment_id>/
    ↓
VM: validate_output.py runs sanity checks
```

### 3. Result Pull Flow

```
VM: jobs/<experiment_id>/ ready
    ↓
rsync → Local: data/results/<experiment_id>/
    ↓
Local: ingest/harbor_parser.py extracts structure
    ↓
Local: ingest/transcript_parser.py extracts tool usage
    ↓
Local: ingest/metrics_extractor.py computes metrics
    ↓
Local: Store in data/metrics.db
```

### 4. Analysis → Recommendation Flow

```
Local: Comparator computes baseline vs MCP delta
    ↓
Local: LLM-as-judge evaluates quality dimensions
    ↓
Local: Failure analyzer detects patterns
    ↓
Local: Config optimizer suggests improvements
    ↓
Local: Updated abstract config
    ↓
(Back to Config Push Flow)
```

---

## IR-SDLC-Factory Integration

### Benchmark Generation Flow

```
IR-SDLC-Factory: Generate IR tasks (JSONL)
    ↓
IR-SDLC-Factory: python -m app.main generate-harbor
    ↓
Output: Harbor-compatible task directories
    ↓
Copy to: CodeContextBench/configs/benchmarks/ir-sdlc-*/
    ↓
Push to VM via sync
```

### Dual Evaluation

IR-SDLC benchmarks measure **both**:

1. **IR Metrics** (computed from tool usage in transcript)
   - Which files did the agent retrieve?
   - Precision@K, Recall@K against ground truth
   - Did MCP improve retrieval accuracy?

2. **Patch Correctness** (standard Harbor evaluation)
   - Did the agent produce a working solution?
   - Does the patch pass tests?

### Metrics Schema for IR Tasks

```python
@dataclass
class IRTaskMetrics:
    # Standard Harbor metrics
    task_id: str
    passed: bool
    patch_quality: float
    
    # IR-specific metrics
    retrieved_files: list[str]
    ground_truth_files: list[str]
    precision_at_5: float
    precision_at_10: float
    recall_at_5: float
    recall_at_10: float
    mrr: float  # Mean Reciprocal Rank
    ndcg_at_10: float
    
    # Tool usage analysis
    mcp_tool_calls: int
    local_search_calls: int  # grep, find, etc.
    mcp_vs_local_ratio: float
```

---

## CLI Commands

```bash
# Sync operations
ccb sync push              # Push configs to VM
ccb sync pull              # Pull results from VM
ccb sync status            # Show sync status

# Experiment management
ccb experiment create      # Create new experiment
ccb experiment run <id>    # Trigger experiment on VM (via SSH)
ccb experiment status      # Show experiment status
ccb experiment list        # List all experiments

# Ingestion
ccb ingest <experiment_id> # Parse and store results
ccb ingest --validate-only # Validate without storing

# Analysis
ccb analyze compare <exp>  # Compare agents in experiment
ccb analyze judge <exp>    # Run LLM-as-judge
ccb analyze failures <exp> # Analyze failure patterns

# Config management
ccb config validate        # Validate all configs
ccb config translate       # Generate agent-specific configs
ccb config diff <a> <b>    # Compare two agent configs
```

---

## Dashboard Views

### 1. Home
- Quick stats: experiments pending/running/completed
- Recent results summary
- Sync status

### 2. Experiments
- List all experiments with status
- Create new experiment wizard
- Link to detailed analysis

### 3. Ingestion
- Import results from sync
- Validation status
- Error highlighting for quick iteration

### 4. Analysis
- Interactive exploration of metrics
- Filter by agent, benchmark, task
- Time-series of improvements

### 5. Comparison
- Side-by-side agent comparison
- Statistical significance testing
- Visual diff of tool usage patterns

### 6. LLM Judge
- Configure evaluation dimensions
- Run evaluations
- View scores with explanations

### 7. Recommendations
- Suggested config changes
- Based on failure patterns
- One-click apply to config

### 8. Config Editor
- Edit abstract agent configs
- Preview translated output
- Validate and push

---

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [ ] Abstract config schema + validation
- [ ] Agent translators (Claude, OpenCode, OpenHands)
- [ ] Sync layer (push/pull)
- [ ] Basic CLI

### Phase 2: Ingestion Pipeline (Week 2)
- [ ] Harbor JSON parser
- [ ] Transcript parser (tool usage extraction)
- [ ] Metrics extractor
- [ ] Database schema

### Phase 3: Analysis Layer (Week 3)
- [ ] Comparator (baseline vs MCP)
- [ ] IR metrics calculator
- [ ] LLM-as-judge integration
- [ ] Failure pattern detection

### Phase 4: Dashboard Refresh (Week 4)
- [ ] Refactor existing views
- [ ] Add new views (ingestion, recommendations)
- [ ] Config editor
- [ ] Interactive analysis

### Phase 5: IR-SDLC Integration (Week 5)
- [ ] Benchmark generation pipeline
- [ ] Dual evaluation (IR + patch)
- [ ] Cross-project metrics

### Phase 6: Recommendation Engine (Week 6)
- [ ] Pattern → suggestion mapping
- [ ] Config diff generation
- [ ] Experiment tracking improvements

---

## Migration Path

1. **Freeze current ~/evals state** - Create snapshot
2. **Restructure VM directories** - New clean structure
3. **Migrate existing agents** - Extract into abstract configs
4. **Migrate existing jobs** - Into new jobs/ structure
5. **Validate roundtrip** - Push config, run task, pull result
6. **Parallel operation** - Run both old and new for 1 week
7. **Cutover** - Archive old structure

---

## Next Steps

1. Review and approve this architecture
2. Create implementation tasks in bd
3. Start with Phase 1: Core Infrastructure
