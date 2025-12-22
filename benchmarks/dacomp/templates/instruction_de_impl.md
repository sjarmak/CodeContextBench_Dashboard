# DAComp-DE Impl Task: {instance_id}

## Objective

Implement the data pipeline defined in the data contract to produce a clean DuckDB database.

## Task Files

All task assets are in `{task_dir}`:
- Raw data: `{task_dir}/raw_data/`
- SQL models: `{task_dir}/sql/`
- Pipeline config: `{task_dir}/config/`
- Data contract: `{contract_path}`
- Pipeline entrypoint: `{task_dir}/run.py`

## Requirements

1. Update SQL and/or `run.py` to satisfy the data contract.
2. Run `python3 run.py` from `{task_dir}` to generate `{output_db}`.
3. Write a short summary of your changes to `{answer_path}`.

## Output

- The DuckDB output must exist at `{task_dir}/{output_db}`.
- `{answer_path}` must be non-empty.
