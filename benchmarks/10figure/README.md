# 10Figure Benchmark Tasks

This directory contains Harbor task definitions generated from the 10Figure benchmark corpus. Tasks are generated using `gen_harbor_tasks.py` from 10Figure YAML task definitions.

## Directory Structure

```
10figure/
├── README.md                 # This file
├── templates/
│   └── test.sh.j2          # Jinja2 template for test script generation
└── [generated task dirs]    # Individual benchmark tasks
    ├── task_id/
    │   ├── instruction.md   # Human-readable task description
    │   ├── task.toml        # Harbor task metadata
    │   ├── task.yaml        # 10Figure task definition (for validator)
    │   ├── repo_path        # Path to repository in container
    │   ├── environment/
    │   │   └── Dockerfile   # Task container setup
    │   └── tests/
    │       └── test.sh      # Validation script (generated from template)
```

## Generating Tasks

To generate Harbor tasks from 10Figure YAML definitions:

```bash
cd /path/to/CodeContextBench
python3 runners/gen_harbor_tasks.py \
  --input <path/to/10figure/tasks> \
  --output benchmarks/10figure \
  --templates benchmarks/10figure/templates \
  --repo kubernetes \
  --corpus-root /10figure
```

### Parameters

- `--input` (required): Directory containing 10Figure task YAML files
- `--output` (required): Output directory for generated Harbor tasks
- `--templates` (required): Directory containing Jinja2 templates (this directory)
- `--repo`: Repository name for task environment (default: kubernetes)
- `--corpus-root`: Corpus root path in container (default: /10figure)

## Task Types

The generator supports the following 10Figure task types:

1. **cross_file_reasoning** - Trace function call chains across files
2. **refactor_rename** - Rename symbols throughout codebase
3. **api_upgrade** - Migrate deprecated API patterns
4. **bug_localization** - Find and fix bugs

Each task type generates appropriate instructions and validation scripts.

## Validation

The generated `tests/test.sh` script:

1. Checks for agent patch file at `/logs/agent/patch.diff`
2. Runs the validator with the patch and task definition
3. Extracts the overall score from validation result
4. Writes score to `/logs/verifier/reward.txt`

The validator expects:
- Patch file in unified diff format
- Task YAML with ground truth definition
- Access to corpus at `/10figure` with `scripts/validate_patch.py`

## Usage in Harbor

Each generated task can be executed in Harbor with:

```bash
harbor run \
  --dockerfile benchmarks/10figure/<task_id>/environment/Dockerfile \
  --test-script benchmarks/10figure/<task_id>/tests/test.sh \
  --config benchmarks/10figure/<task_id>/task.toml
```
