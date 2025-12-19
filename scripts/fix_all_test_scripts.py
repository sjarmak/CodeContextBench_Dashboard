#!/usr/bin/env python3
"""
Fix test.sh scripts for all main set tasks.
Update from comparing HEAD to comparing pre_fix_rev.
"""

import re
from pathlib import Path
import json
import toml

def fix_test_script(task_dir: Path) -> bool:
    """Fix test.sh to compare against pre_fix_rev"""
    
    test_sh_path = task_dir / "tests" / "test.sh"
    task_toml_path = task_dir / "task.toml"
    
    if not test_sh_path.exists() or not task_toml_path.exists():
        return False
    
    # Get pre_fix_rev from task.toml
    try:
        with open(task_toml_path) as f:
            task_data = toml.load(f)
        pre_fix_rev = task_data.get("task", {}).get("pre_fix_rev")
        if not pre_fix_rev:
            return False
    except:
        return False
    
    # Read test.sh
    with open(test_sh_path) as f:
        content = f.read()
    
    # Already fixed if it has PRE_FIX_REV variable
    if "PRE_FIX_REV=" in content:
        return False
    
    # Pattern 1: Replace hardcoded commit hashes with variable definition
    # This handles sgt-002, sgt-003, etc. that have placeholder hashes
    pattern = r'pre_fix_rev = "[^"]*"'
    replacement = f'PRE_FIX_REV="{pre_fix_rev}"'
    
    # Fix comparison against HEAD -> pre_fix_rev
    content = re.sub(
        r'git diff --exit-code HEAD',
        'git diff --exit-code "$PRE_FIX_REV"',
        content
    )
    content = re.sub(
        r'git diff HEAD --stat',
        'git diff "$PRE_FIX_REV" --stat',
        content
    )
    content = re.sub(
        r'git diff HEAD --name-only',
        'git diff "$PRE_FIX_REV" --name-only',
        content
    )
    content = re.sub(
        r'git diff HEAD torch/csrc',
        'git diff "$PRE_FIX_REV" torch/csrc',
        content
    )
    content = re.sub(
        r'git diff HEAD >',
        'git diff "$PRE_FIX_REV" >',
        content
    )
    
    # Add PRE_FIX_REV definition near top (after mkdir -p /logs/verifier)
    if 'mkdir -p /logs/verifier' in content and 'PRE_FIX_REV=' not in content:
        content = content.replace(
            'mkdir -p /logs/verifier\n',
            f'mkdir -p /logs/verifier\nPRE_FIX_REV="{pre_fix_rev}"\n'
        )
    
    # Write back
    with open(test_sh_path, 'w') as f:
        f.write(content)
    
    return True

def main():
    tasks_dir = Path("benchmarks/github_mined")
    
    fixed = 0
    for task_dir in sorted(tasks_dir.glob("sgt-*")):
        if task_dir.is_dir() and fix_test_script(task_dir):
            print(f"✓ Fixed {task_dir.name}")
            fixed += 1
        else:
            print(f"- Skipped {task_dir.name}")
    
    print(f"\nFixed {fixed} test scripts")

if __name__ == "__main__":
    main()
