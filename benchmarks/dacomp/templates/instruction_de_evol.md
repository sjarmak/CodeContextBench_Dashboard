# DAComp-DE Evol Task: {instance_id}

## Objective

Evolve the existing data pipeline to meet new requirements.

## Task Files

All task assets are in `{task_dir}`:
- Requirements: `{question_path}`
- Raw data: `{task_dir}/raw_data/`
- SQL models: `{task_dir}/sql/`
- Pipeline config: `{task_dir}/config/`
- Pipeline entrypoint: `{task_dir}/run.py`

## Requirements

1. Read the requirements in `{question_path}`.
2. Update SQL and/or `run.py` to implement the changes.
3. Run `python3 run.py` from `{task_dir}` to generate `{output_db}`.
4. Write a short summary of your changes to `{answer_path}`.

## Output

- The DuckDB output must exist at `{task_dir}/{output_db}`.
- `{answer_path}` must be non-empty.
