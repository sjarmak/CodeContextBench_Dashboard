#!/usr/bin/env python3
"""Add Sourcegraph Deep Search guidance to all task instructions.

Prepends MCP section to instruction.md files so Claude knows to use Deep Search.
"""

from pathlib import Path
import re

MCP_GUIDANCE = """## Sourcegraph Deep Search Available

You have access to **Sourcegraph Deep Search** via MCP. Use it instead of grep or manual code exploration to quickly understand the codebase and locate relevant patterns.

"""


def add_mcp_guidance(instruction_path: Path) -> bool:
    """Add MCP guidance to instruction.md file.
    
    Returns True if updated, False if already has guidance.
    """
    content = instruction_path.read_text()
    
    # Check if already has MCP guidance
    if "Sourcegraph Deep Search" in content:
        return False
    
    # Find where to insert (after title and metadata, before Description)
    # Pattern: after lines like **Category:** or **Difficulty:**
    
    # Insert after first 4 lines (title, blank, metadata)
    lines = content.split('\n')
    insert_pos = 0
    
    # Find the blank line or first non-metadata line
    for i, line in enumerate(lines):
        if i > 0 and (line.startswith('## ') or line.strip() == ''):
            if line.startswith('## Description'):
                insert_pos = i
                break
            elif line.strip() == '':
                # Keep looking
                continue
    
    if insert_pos == 0:
        # Fallback: insert after metadata section (look for last metadata line)
        for i, line in enumerate(lines):
            if line.startswith('**'):
                insert_pos = i + 1
    
    if insert_pos == 0:
        insert_pos = 4  # Default fallback
    
    # Insert guidance
    new_lines = lines[:insert_pos] + ['', MCP_GUIDANCE.rstrip()] + [''] + lines[insert_pos:]
    instruction_path.write_text('\n'.join(new_lines))
    return True


def main():
    """Add MCP guidance to all task instructions."""
    project_root = Path(__file__).parent.parent
    benchmark_dir = project_root / "benchmarks"
    
    if not benchmark_dir.exists():
        print(f"❌ Benchmark dir not found: {benchmark_dir}")
        return 1
    
    # Find all instruction.md files
    instruction_files = list(benchmark_dir.rglob("instruction.md"))
    print(f"Found {len(instruction_files)} instruction.md files")
    
    updated = 0
    skipped = 0
    
    for inst_file in sorted(instruction_files):
        try:
            if add_mcp_guidance(inst_file):
                print(f"  ✓ Updated: {inst_file.relative_to(project_root)}")
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  ❌ Error updating {inst_file}: {e}")
    
    print(f"\nResults: {updated} updated, {skipped} skipped")
    return 0


if __name__ == "__main__":
    exit(main())
