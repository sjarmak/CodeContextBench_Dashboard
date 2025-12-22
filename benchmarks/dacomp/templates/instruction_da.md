# DAComp-DA Task: {instance_id}

## Objective

{instruction}

## Data Access

- SQLite database: `{sqlite_path}`
- You can use Python, pandas, or the `sqlite3` CLI.

## Requirements

- Ground every claim in the data.
- Use exact column names from the database schema.
- Call out assumptions explicitly.

## Output

Write your final response to `{answer_path}`.
- If you generate charts or images, save them under `/app/` and reference them in the markdown.
- Make sure `{answer_path}` is non-empty.

## Helpful Start

```bash
python3 - <<'PY'
import sqlite3

conn = sqlite3.connect("{sqlite_path}")
cur = conn.cursor()

# List tables
print(cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
PY
```
