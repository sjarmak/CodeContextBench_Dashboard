#!/usr/bin/env python3
"""
Generate a ranked list of SWE-Bench Pro tasks by complexity.
Ranks tasks by patch size (lines changed) and file count as proxy for complexity.
"""

import re
import pandas as pd
from datasets import load_dataset

# Load SWE-Bench Pro public split
print("Loading SWE-Bench Pro dataset...")
ds = load_dataset("ScaleAI/SWE-bench_Pro", split="test")

def count_files_and_lines(patch: str):
    """Count files changed and total line changes in a patch."""
    # Count "diff --git" separators for file count
    file_count = patch.count("diff --git")
    # Number of lines changed (total lines in patch)
    line_count = len(patch.splitlines())
    return file_count, line_count

print("Processing tasks...")
rows = []
for rec in ds:
    files, lines = count_files_and_lines(rec["patch"])
    rows.append({
        "instance_id": rec["instance_id"],
        "repo": rec["repo"],
        "files_changed": files,
        "lines_changed": lines,
        "problem_statement_len": len(rec["problem_statement"])
    })

df = pd.DataFrame(rows)

# Filter to high complexity tasks
# (≥3 files changed AND ≥100 total lines of patch diff)
print("Filtering to high-complexity tasks (≥3 files, ≥100 lines)...")
filtered = df[(df.files_changed >= 3) & (df.lines_changed >= 100)]

# Rank by patch size (lines_changed) descending
ranked = filtered.sort_values(by="lines_changed", ascending=False)

# Save top 50
output_file = "top50_swebenchpro_complex.csv"
topN = ranked.head(50).reset_index(drop=True)
topN.to_csv(output_file, index=False)

print(f"\nGenerated {len(topN)} high-complexity tasks")
print(f"Saved to: {output_file}\n")
print(topN.to_string())

# Print summary stats
print(f"\n\nSummary Statistics:")
print(f"Total tasks in dataset: {len(df)}")
print(f"High-complexity tasks (≥3 files, ≥100 lines): {len(filtered)}")
print(f"Tasks in top 50: {len(topN)}")
print(f"\nComplexity ranges in top 50:")
print(f"  Files changed: {topN['files_changed'].min()}-{topN['files_changed'].max()}")
print(f"  Lines changed: {topN['lines_changed'].min()}-{topN['lines_changed'].max()}")
print(f"  Problem statement length: {topN['problem_statement_len'].min()}-{topN['problem_statement_len'].max()}")
