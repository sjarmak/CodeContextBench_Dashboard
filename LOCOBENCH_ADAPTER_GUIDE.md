# LoCoBench-Agent Harbor Adapter Guide

Complete walkthrough for creating a Harbor adapter for LoCoBench-Agent tasks that highlights code search/codebase understanding value.

## 1. Understand LoCoBench-Agent

From the repository analysis:
- **8,000 interactive scenarios** across 10 programming languages
- **Multi-turn evaluation** (up to 50 conversation turns per task)
- **Long-context scenarios** spanning 10K-1M tokens
- **8 specialized tools**: file operations, semantic search, code analysis
- **9 evaluation metrics** across comprehension and efficiency
- **10 languages**: Python, JavaScript, TypeScript, Java, C++, Go, Rust, PHP, Ruby, C#
- **8 task categories**: architectural understanding, bug investigation, feature implementation, etc.

**Key insight for MCP value:** Tasks involving semantic search, cross-file dependency traversal, and architectural understanding will benefit most from Sourcegraph MCP tools.

---

## 2. Select Subset for Code Search Value

Choose tasks where Sourcegraph MCP would have **high impact**:

### High-Value Categories:
1. **Architectural Understanding** - Finding how modules interact across large codebase
2. **Bug Investigation** - Locating root cause across multiple files
3. **Cross-File Dependency Traversal** - Understanding function call chains
4. **Semantic Search Tasks** - Finding functions by behavior/description

### Selection Strategy:
```bash
# Download LoCoBench-Agent data
gdown https://drive.google.com/uc?id=1HwPztd0bipUUi8zs7Pxo3StZCOnJBwVR
unzip data.zip

# Analyze data/ directory structure:
# - Typically JSONL format with task metadata
# - Look for tasks with these properties:
#   * Multiple files accessed (cross-file reasoning)
#   * High context length (1M tokens = lots to search)
#   * Semantic/architectural tasks (not syntax-level)
#   * Multi-hop dependencies (need to trace imports)
```

**Recommended**: Start with ~10-20 tasks from architectural understanding + bug investigation categories.

---

## 3. Directory Structure

Create `benchmarks/locobench_agent/` with this structure:

```
benchmarks/locobench_agent/
├── README.md                          # Benchmark documentation
├── DESIGN.md                          # Design decisions
├── IMPLEMENTATION.md                  # Implementation notes
├── run_adapter.py                     # Main conversion script
├── adapter.py                         # Harbor adapter class
├── verifiers.py                       # Verification logic (if needed)
├── templates/
│   ├── task.toml                      # Harbor task config template
│   ├── instruction.md                 # User-facing task instruction
│   ├── solution/
│   │   └── solve.sh                   # Reference solution script
│   ├── tests/
│   │   ├── test.sh                    # Test verification script
│   │   ├── verifier.py               # Verification logic
│   │   └── ground_truth_schema.json   # Ground truth format
│   └── environment/
│       └── Dockerfile                 # Task environment setup
├── tests/
│   ├── test_adapter.py               # Adapter unit tests
│   └── test_sample_tasks.py          # Integration tests
└── docs/
    └── TASK_SELECTION_CRITERIA.md    # How tasks were chosen
```

---

## 4. Step-by-Step Implementation

### Step 4.1: Create adapter.py

Pattern from `repoqa/adapter.py` and `dibench/adapter.py`:

```python
# benchmarks/locobench_agent/adapter.py

import json
import shutil
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Dict, List, Optional

import importlib.util

# Import Harbor models (same pattern as existing adapters)
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

def _import_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Import Harbor models
difficulty_module = _import_module_from_file(
    "harbor.models.difficulty",
    src_path / "harbor" / "models" / "difficulty.py"
)
Difficulty = difficulty_module.Difficulty

task_config_module = _import_module_from_file(
    "harbor.models.task.config",
    src_path / "harbor" / "models" / "task" / "config.py"
)
AgentConfig = task_config_module.AgentConfig
EnvironmentConfig = task_config_module.EnvironmentConfig
TaskConfig = task_config_module.TaskConfig
VerifierConfig = task_config_module.VerifierConfig

task_paths_module = _import_module_from_file(
    "harbor.models.task.paths",
    src_path / "harbor" / "models" / "task" / "paths.py"
)
TaskPaths = task_paths_module.TaskPaths

ADAPTER_NAME = "locobench_agent"
TEMPLATE_DIR = Path(__file__).parent / "templates"

@dataclass
class LoCoBenchTask:
    """Represents a LoCoBench-Agent task instance."""
    task_id: str
    scenario_id: str              # LoCoBench scenario ID
    repository: str               # GitHub repo (user/repo)
    commit: str                   # Repository commit
    language: str                 # Programming language
    task_type: str                # architectural, bug, feature, etc.
    difficulty: str               # easy, medium, hard, expert
    context_length: int           # Token length of context
    instruction: str              # Task description
    ground_truth: Dict            # Expected solution metadata
    semantic_metadata: Dict       # Tags: cross_file, multi_hop, etc.
    
    @classmethod
    def from_dict(cls, data: dict) -> "LoCoBenchTask":
        return cls(
            task_id=data["task_id"],
            scenario_id=data.get("scenario_id"),
            repository=data["repository"],
            commit=data["commit"],
            language=data.get("language", "python"),
            task_type=data.get("task_type", "general"),
            difficulty=data.get("difficulty", "medium"),
            context_length=data.get("context_length", 0),
            instruction=data.get("instruction", ""),
            ground_truth=data.get("ground_truth", {}),
            semantic_metadata=data.get("semantic_metadata", {}),
        )

class LoCoBenchLoader:
    """Loads LoCoBench-Agent instances from dataset."""
    
    def __init__(self, dataset_path: Optional[Path] = None):
        self.dataset_path = dataset_path
        self._instances = {}
        
        if dataset_path and dataset_path.exists():
            self._load_dataset()
    
    def _load_dataset(self):
        """Load instances from JSONL dataset."""
        with open(self.dataset_path, "r") as f:
            for line in f:
                data = json.loads(line.strip())
                instance = LoCoBenchTask.from_dict(data)
                self._instances[instance.task_id] = instance
    
    def load(self, task_id: str) -> LoCoBenchTask:
        if task_id in self._instances:
            return self._instances[task_id]
        raise KeyError(f"Task not found: {task_id}")
    
    def all_ids(self) -> List[str]:
        return sorted(self._instances.keys())
    
    def filter_by_task_type(self, task_type: str) -> List[str]:
        """Filter tasks by type."""
        return [
            tid for tid in self._instances
            if self._instances[tid].task_type.lower() == task_type.lower()
        ]
    
    def filter_by_language(self, language: str) -> List[str]:
        """Filter tasks by language."""
        return [
            tid for tid in self._instances
            if self._instances[tid].language.lower() == language.lower()
        ]

class LoCoBenchAdapter:
    """Converts LoCoBench-Agent tasks to Harbor structure."""
    
    NAME = "locobench_agent"
    
    def __init__(
        self,
        task_dir: Path,
        dataset_path: Optional[Path] = None,
        **kwargs
    ):
        self.task_dir = Path(task_dir)
        self.loader = LoCoBenchLoader(dataset_path)
        self.templates_dir = TEMPLATE_DIR
    
    def _render_template(self, template_path: Path, context: dict) -> str:
        """Simple template rendering by replacing {key} placeholders."""
        content = template_path.read_text()
        for key, value in context.items():
            content = content.replace(f"{{{key}}}", str(value))
            content = content.replace(f"{{{{ {key} }}}}", str(value))
        return content
    
    def _create_instruction(self, task: LoCoBenchTask) -> str:
        """Create instruction.md from task."""
        template_path = self.templates_dir / "instruction.md"
        
        context = {
            "task_id": task.task_id,
            "scenario_id": task.scenario_id,
            "repository": task.repository,
            "language": task.language,
            "task_type": task.task_type,
            "difficulty": task.difficulty,
            "context_length": task.context_length,
            "instruction": task.instruction,
            "semantic_metadata": json.dumps(task.semantic_metadata, indent=2),
        }
        
        return self._render_template(template_path, context)
    
    def _prepare_task_from_template(
        self,
        task: LoCoBenchTask,
        output_dir: Path,
    ) -> None:
        """Prepare Harbor task directory."""
        # Clean and create output directory
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Harbor paths
        task_paths = TaskPaths(task_dir=output_dir)
        
        # Create directory structure
        task_paths.solution_dir.mkdir(parents=True, exist_ok=True)
        task_paths.tests_dir.mkdir(parents=True, exist_ok=True)
        task_paths.environment_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Write instruction.md
        instruction = self._create_instruction(task)
        task_paths.instruction_path.write_text(instruction)
        
        # 2. Create task.toml
        task_toml_template = self.templates_dir / "task.toml"
        if task_toml_template.exists():
            template_content = task_toml_template.read_text()
            task_config = TaskConfig.model_validate_toml(template_content)
            
            # Update metadata
            task_config.metadata["repository"] = task.repository
            task_config.metadata["commit"] = task.commit
            task_config.metadata["language"] = task.language
            task_config.metadata["task_type"] = task.task_type
            task_config.metadata["difficulty"] = task.difficulty
            task_config.metadata["context_length"] = task.context_length
            task_config.metadata["tags"] = [
                "locobench",
                task.language.lower(),
                task.task_type.lower(),
                task.difficulty.lower(),
            ]
            
            task_paths.config_path.write_text(task_config.model_dump_toml())
        else:
            raise FileNotFoundError(f"Template {task_toml_template} not found")
        
        # 3. Generate Dockerfile
        dockerfile_template = self.templates_dir / "environment" / "Dockerfile"
        if dockerfile_template.exists():
            dockerfile_content = self._render_template(
                dockerfile_template,
                {
                    "repository": task.repository,
                    "commit": task.commit,
                }
            )
            (task_paths.environment_dir / "Dockerfile").write_text(dockerfile_content)
        else:
            raise FileNotFoundError(f"Template {dockerfile_template} not found")
        
        # 4. Save ground truth
        ground_truth_path = task_paths.tests_dir / "ground_truth.json"
        with open(ground_truth_path, "w") as f:
            json.dump({
                "task_id": task.task_id,
                "scenario_id": task.scenario_id,
                "language": task.language,
                "task_type": task.task_type,
                "ground_truth": task.ground_truth,
                **task.semantic_metadata,
            }, f, indent=2)
        
        # 5. Generate test.sh
        test_template = self.templates_dir / "tests" / "test.sh"
        if test_template.exists():
            test_content = self._render_template(
                test_template,
                {
                    "task_id": task.task_id,
                    "scenario_id": task.scenario_id,
                }
            )
            task_paths.test_path.write_text(test_content)
            task_paths.test_path.chmod(0o755)
        else:
            raise FileNotFoundError(f"Template {test_template} not found")
        
        # 6. Save instance metadata
        metadata_path = task_paths.tests_dir / "instance.json"
        with open(metadata_path, "w") as f:
            json.dump({
                "task_id": task.task_id,
                "scenario_id": task.scenario_id,
                "repository": task.repository,
                "commit": task.commit,
                "language": task.language,
                "task_type": task.task_type,
                "difficulty": task.difficulty,
                "context_length": task.context_length,
            }, f, indent=2)
    
    def generate_task(self, task_id: str, local_task_id: str) -> None:
        """Generate a Harbor task for a LoCoBench instance."""
        task = self.loader.load(task_id)
        out_dir = self.task_dir / local_task_id
        out_dir.mkdir(parents=True, exist_ok=True)
        
        self._prepare_task_from_template(task, out_dir)
```

### Step 4.2: Create run_adapter.py

```python
#!/usr/bin/env python3
"""
Script to run LoCoBench-Agent adapter.

Usage:
    python run_adapter.py --dataset_path path/to/dataset.jsonl \
                          --output_dir path/to/output \
                          --task_types architectural bug \
                          --limit 10
"""

import argparse
import logging
from pathlib import Path

from adapter import LoCoBenchAdapter, LoCoBenchLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(
        description="Convert LoCoBench-Agent instances to Harbor tasks"
    )
    parser.add_argument(
        "--dataset_path",
        type=Path,
        required=True,
        help="Path to LoCoBench-Agent JSONL dataset file"
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        required=True,
        help="Output directory for Harbor tasks"
    )
    parser.add_argument(
        "--task_types",
        nargs="+",
        default=None,
        choices=[
            "architectural",
            "bug",
            "feature",
            "refactor",
            "test",
            "documentation",
            "dependency",
            "optimization"
        ],
        help="Filter by task types (high MCP value: architectural, bug, dependency)"
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=None,
        help="Filter by languages (e.g., python javascript rust)"
    )
    parser.add_argument(
        "--difficulty",
        nargs="+",
        default=None,
        choices=["easy", "medium", "hard", "expert"],
        help="Filter by difficulty level"
    )
    parser.add_argument(
        "--min_context_length",
        type=int,
        default=None,
        help="Minimum context length in tokens (larger = more search needed)"
    )
    parser.add_argument(
        "--task_ids",
        nargs="+",
        default=None,
        help="Specific task IDs to convert"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of tasks to generate (default: all)"
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.dataset_path.exists():
        logger.error(f"Dataset file not found: {args.dataset_path}")
        return
    
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize adapter
    logger.info("Initializing LoCoBench-Agent adapter...")
    adapter = LoCoBenchAdapter(
        task_dir=args.output_dir,
        dataset_path=args.dataset_path
    )
    
    # Get task IDs to convert
    all_task_ids = adapter.loader.all_ids()
    logger.info(f"Found {len(all_task_ids)} total tasks in dataset")
    
    # Filter by task type
    selected_ids = all_task_ids
    if args.task_types:
        filtered = []
        for task_type in args.task_types:
            filtered.extend(adapter.loader.filter_by_task_type(task_type))
        selected_ids = list(set(filtered))
        logger.info(f"Filtered to {len(selected_ids)} tasks by type: {args.task_types}")
    
    # Filter by language
    if args.languages:
        filtered = []
        for lang in args.languages:
            filtered.extend(adapter.loader.filter_by_language(lang))
        selected_ids = [tid for tid in selected_ids if tid in filtered]
        logger.info(f"Filtered to {len(selected_ids)} tasks by language: {args.languages}")
    
    # Filter by difficulty
    if args.difficulty:
        selected_ids = [
            tid for tid in selected_ids
            if adapter.loader.load(tid).difficulty in args.difficulty
        ]
        logger.info(f"Filtered to {len(selected_ids)} tasks by difficulty: {args.difficulty}")
    
    # Filter by context length
    if args.min_context_length:
        selected_ids = [
            tid for tid in selected_ids
            if adapter.loader.load(tid).context_length >= args.min_context_length
        ]
        logger.info(f"Filtered to {len(selected_ids)} tasks with context >= {args.min_context_length} tokens")
    
    # Filter by specific IDs
    if args.task_ids:
        selected_ids = [tid for tid in selected_ids if tid in args.task_ids]
        logger.info(f"Filtered to {len(selected_ids)} specific tasks")
    
    # Apply limit
    if args.limit:
        selected_ids = selected_ids[:args.limit]
        logger.info(f"Limited to {args.limit} tasks")
    
    # Generate tasks
    logger.info(f"\nGenerating {len(selected_ids)} Harbor tasks...")
    for i, task_id in enumerate(selected_ids, 1):
        try:
            task = adapter.loader.load(task_id)
            local_id = f"{task.language}-{task.task_type}-{i:03d}"
            adapter.generate_task(task_id, local_id)
            logger.info(f"  [{i}/{len(selected_ids)}] {local_id}: {task_id}")
        except Exception as e:
            logger.error(f"  Failed to generate task {task_id}: {e}")
    
    logger.info("\n✅ Done!")

if __name__ == "__main__":
    main()
```

### Step 4.3: Create Templates

**`templates/task.toml`:**
```toml
[metadata]
name = "LoCoBench-Agent Task"
description = "Long-context software engineering task from LoCoBench-Agent"
repository = "{repository}"
commit = "{commit}"
language = "{language}"
task_type = "{task_type}"
difficulty = "{difficulty}"

[environment]
type = "docker"
build_context = "environment"

[agent]
mode = "autonomous"

[tests]
command = "tests/test.sh"
```

**`templates/instruction.md`:**
```markdown
# Task: {task_id}

**Repository**: {repository}  
**Commit**: {commit}  
**Language**: {language}  
**Type**: {task_type}  
**Difficulty**: {difficulty}  
**Context Length**: {context_length} tokens

## Task Instructions

{instruction}

## Evaluation Criteria

{semantic_metadata}

## Key Requirements

- Maintain code style consistency
- All existing tests must continue to pass
- Document any new dependencies
```

**`templates/environment/Dockerfile`:**
```dockerfile
FROM python:3.11-slim

WORKDIR /task

# Clone repository
RUN git clone https://github.com/{repository}.git /task/repo
WORKDIR /task/repo
RUN git checkout {commit}

# Install dependencies (customize per language)
RUN apt-get update && apt-get install -y build-essential

COPY . /task/
```

**`templates/tests/test.sh`:**
```bash
#!/bin/bash
set -e

TASK_ID="{task_id}"
SCENARIO_ID="{scenario_id}"

echo "Running verification for $TASK_ID..."

# Verify solution exists
if [ ! -d "solution" ]; then
    echo "❌ No solution/ directory found"
    exit 1
fi

# Run task-specific verification
python3 tests/verifier.py \
    --task_id "$TASK_ID" \
    --scenario_id "$SCENARIO_ID" \
    --ground_truth tests/ground_truth.json

echo "✅ Task complete"
```

---

## 5. Creating the Dataset

You need to extract/convert LoCoBench-Agent data into JSONL format:

```python
# benchmarks/locobench_agent/extract_dataset.py
# Extract from LoCoBench-Agent data/ directory into JSONL format

import json
from pathlib import Path

def extract_locobench_to_jsonl(locobench_dir: Path, output_jsonl: Path):
    """
    Extract LoCoBench-Agent scenarios to JSONL format.
    Adjust based on actual LoCoBench-Agent directory structure.
    """
    tasks = []
    
    # Adapt this to your LoCoBench-Agent data structure
    # Example: data/scenarios/{task_id}/metadata.json
    for task_dir in locobench_dir.glob("scenarios/*"):
        metadata_file = task_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                data = json.load(f)
            
            # Normalize to adapter format
            task = {
                "task_id": data.get("task_id", task_dir.name),
                "scenario_id": data.get("scenario_id"),
                "repository": data.get("repository"),
                "commit": data.get("commit"),
                "language": data.get("language"),
                "task_type": data.get("task_type"),
                "difficulty": data.get("difficulty"),
                "context_length": data.get("context_length", 0),
                "instruction": data.get("instruction", ""),
                "ground_truth": data.get("ground_truth", {}),
                "semantic_metadata": {
                    "cross_file": data.get("cross_file", False),
                    "multi_hop": data.get("multi_hop_dependencies", False),
                    "requires_semantic_search": True,  # Most tasks do
                }
            }
            tasks.append(task)
    
    # Write JSONL
    with open(output_jsonl, "w") as f:
        for task in tasks:
            f.write(json.dumps(task) + "\n")
    
    print(f"Extracted {len(tasks)} tasks to {output_jsonl}")

if __name__ == "__main__":
    extract_locobench_to_jsonl(
        Path("/path/to/LoCoBench-Agent/data"),
        Path("locobench_dataset.jsonl")
    )
```

---

## 6. Running the Adapter

```bash
cd benchmarks/locobench_agent

# 1. Extract dataset from LoCoBench-Agent
python extract_dataset.py

# 2. Generate Harbor tasks for high-MCP-value subset
python run_adapter.py \
  --dataset_path locobench_dataset.jsonl \
  --output_dir ./tasks \
  --task_types architectural bug dependency \
  --min_context_length 50000 \
  --limit 20

# 3. Verify generated tasks
ls tasks/
# Should see: python-architectural-001/, python-bug-002/, etc.
```

---

## 7. Running with Agents

```bash
# Run with Strategic Deep Search Agent (recommended for MCP value)
harbor run --path benchmarks/locobench_agent/tasks/python-bug-001 \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1

# Run baseline for comparison
harbor run --path benchmarks/locobench_agent/tasks/python-bug-001 \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1
```

---

## 8. Task Selection Strategy for MCP Value

**High MCP Value Tasks:**
- ✅ **Architectural Understanding**: Finding how modules interact across 100K+ lines
- ✅ **Bug Investigation**: Locating root cause across unrelated files
- ✅ **Cross-Repo Dependencies**: Understanding external package usage patterns
- ✅ **Semantic Search**: "Find all functions that validate user input"

**Low MCP Value Tasks:**
- ❌ **Syntax fixes**: Single-file changes (linting)
- ❌ **Simple refactors**: Rename variable (doesn't require search)
- ❌ **Obvious bugs**: Error is in function call site (not cross-file)

**Filter criteria:**
```bash
# Select tasks that need codebase search
python run_adapter.py \
  --dataset_path locobench_dataset.jsonl \
  --output_dir ./high_mcp_value_tasks \
  --task_types architectural bug dependency \
  --min_context_length 100000 \
  --difficulty hard expert \
  --limit 15
```

---

## 9. Documentation to Create

**README.md** - Overview, task counts, setup instructions  
**DESIGN.md** - Why these tasks, how they were selected  
**IMPLEMENTATION.md** - Adapter architecture, data flow  
**docs/TASK_SELECTION_CRITERIA.md** - Which tasks, why they matter for MCP

---

## 10. Comparison Matrix

After running both baseline and MCP-variant agents, analyze:

| Metric | Baseline | Strategic Deep Search | Improvement |
|--------|----------|----------------------|-------------|
| Tasks solved | 8/15 | 12/15 | +4 (+50%) |
| Avg context tokens used | 45K | 80K | Search helps |
| Functions correctly identified | 65% | 85% | +20% |
| Cross-file understanding | 40% | 75% | +35% |

---

## Next Steps

1. Download LoCoBench-Agent data from Google Drive
2. Analyze directory structure, normalize to JSONL format
3. Create `extract_dataset.py` to convert
4. Implement adapter.py following the patterns above
5. Create templates/ directory with instruction.md, task.toml, Dockerfile, test.sh
6. Test with 1-2 tasks: `harbor run ...`
7. Generate full 15-20 task subset
8. Run comparison: baseline vs StrategicDeepSearchAgent
9. Document findings in MANIFEST.md

---

## Reference Files

- Existing adapters: `benchmarks/{repoqa,dibench,swebench_pro}/`
- Harbor documentation: `~/harbor/adapters/ADAPTER_QUICKREF.md`
- Agent documentation: `AGENTS.md` → Benchmark Agents section
