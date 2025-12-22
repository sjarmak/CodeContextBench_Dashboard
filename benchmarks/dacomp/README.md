# DAComp Adapter for Harbor

This adapter converts DAComp tasks into Harbor task directories for evaluation with baseline and MCP-enabled agents.

## Supported subsets

- **DAComp-DA (analysis)**: Natural-language data analysis tasks over SQLite databases.
- **DAComp-DE (engineering)**: Data engineering tasks (impl/evol/arch) with Python + SQL pipelines.

## Dataset download

DAComp datasets are hosted on HuggingFace. Follow the DAComp repo instructions to download and extract:

- DAComp-DA (English): `DAComp/dacomp-da`
- DAComp-DA (Chinese): `DAComp/dacomp-da-zh`
- DAComp-DE (English): `DAComp/dacomp-de`
- DAComp-DE (Chinese): `DAComp/dacomp-de-zh`

See the upstream guide: https://github.com/ByteDance-Seed/DAComp

## Generate Harbor tasks

### DAComp-DA

```bash
cd benchmarks/dacomp
python run_adapter.py --subset da \
  --dataset_path /path/to/dacomp-da/tasks/dacomp-da.jsonl \
  --tasks_root /path/to/dacomp-da/tasks \
  --output_dir ./tasks
```

### DAComp-DE

```bash
cd benchmarks/dacomp
python run_adapter.py --subset de \
  --tasks_root /path/to/dacomp-de/tasks \
  --output_dir ./tasks \
  --task_types impl evol arch
```

## Run with Harbor

```bash
harbor run --task benchmarks/dacomp/tasks/dacomp-001 \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent
```

## Notes

- DA tasks expect a markdown answer at `/app/answer.md`.
- DE impl/evol tasks expect a DuckDB output plus `/app/answer.md`.
- DE arch tasks expect a YAML answer at `/app/answer.yaml`.
- The verifier only checks for required outputs. Official scoring should use DAComp evaluation suites.
- If the adapter cannot find Harbor source files, set `HARBOR_SRC=~/harbor/src`.
