#!/usr/bin/env python3
"""Fix MCP guidance in all task instructions - replace verbose version with simple one."""

from pathlib import Path

OLD_GUIDANCE = """You have access to **Sourcegraph Deep Search** to understand the codebase. Use it to:
- Find relevant code patterns and implementations
- Locate test cases and examples
- Understand the architecture and dependencies
- Search for similar fixes or related changes"""

NEW_GUIDANCE = """You have access to **Sourcegraph Deep Search** via MCP. Use it instead of grep or manual code exploration to quickly understand the codebase and locate relevant patterns."""


def fix_instruction(instruction_path: Path) -> bool:
    """Fix MCP guidance in instruction.md file."""
    content = instruction_path.read_text()
    
    if OLD_GUIDANCE not in content:
        return False
    
    content = content.replace(OLD_GUIDANCE, NEW_GUIDANCE)
    instruction_path.write_text(content)
    return True


def main():
    """Fix all task instructions."""
    project_root = Path(__file__).parent.parent
    benchmark_dir = project_root / "benchmarks"
    
    instruction_files = list(benchmark_dir.rglob("instruction.md"))
    print(f"Found {len(instruction_files)} instruction.md files")
    
    updated = 0
    
    for inst_file in sorted(instruction_files):
        if fix_instruction(inst_file):
            print(f"  ✓ Fixed: {inst_file.relative_to(project_root)}")
            updated += 1
    
    print(f"\nResults: {updated} fixed")
    return 0


if __name__ == "__main__":
    exit(main())
