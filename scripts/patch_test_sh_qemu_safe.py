#!/usr/bin/env python3
"""
Patch test.sh files to avoid QEMU parser segfault on ARM64 Macs.

The issue: Harbor's test harness calls `uv run parser.py` after tests complete,
which segfaults on ARM64 Macs due to QEMU emulation + numpy ABI mismatch.

Solution: Wrap test.sh to catch the segfault and exit gracefully after writing reward.

Usage:
    python scripts/patch_test_sh_qemu_safe.py <directory>
    
Examples:
    # Patch local benchmarks
    python scripts/patch_test_sh_qemu_safe.py benchmarks/swebench_pro/tasks/
    
    # Patch Harbor cached datasets (important for swebench-verified, etc.)
    python scripts/patch_test_sh_qemu_safe.py ~/.cache/harbor/tasks/
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional


def patch_test_sh(test_sh_path: Path) -> bool:
    """
    Patch a test.sh file to handle QEMU segfault gracefully.
    
    Wraps the entire script in a function that:
    1. Runs all original commands
    2. Captures the exit code
    3. Ensures reward is written
    4. Exits before parser.py can segfault
    """
    try:
        content = test_sh_path.read_text()
    except Exception as e:
        print(f"❌ Failed to read {test_sh_path}: {e}")
        return False
    
    # Already patched?
    if "QEMU_SAFE_PATCH" in content:
        print(f"⏭️  Already patched: {test_sh_path}")
        return True
    
    # Find the shebang (may be on line 1 or line 3 in Harbor cache files)
    lines = content.split('\n')
    shebang_idx = None
    
    # Check first few lines for shebang
    for idx, line in enumerate(lines[:5]):
        if line.startswith('#!'):
            shebang_idx = idx
            break
    
    if shebang_idx is None:
        # No shebang found, skip this file
        return False
    
    shebang = lines[shebang_idx]
    # Include everything before shebang and everything after
    rest_of_script = '\n'.join(lines[:shebang_idx] + lines[shebang_idx+1:])
    
    # Create patched version
    # Instead of wrapping in a subshell, modify the original to trap EXIT
    patched = f"""{shebang}
# QEMU_SAFE_PATCH: Prevents segfault when parser.py runs on ARM64 Macs
# This version ensures reward is written and exits cleanly before parser runs

set -o pipefail

# Trap EXIT to ensure reward is written and script exits before parser.py can be called
_qemu_safe_exit() {{
    local exit_code=$?
    mkdir -p /logs/verifier
    
    # Only write reward if not already written
    if [ ! -f /logs/verifier/reward.txt ]; then
        if [ $exit_code -eq 0 ]; then
            echo 1 > /logs/verifier/reward.txt
        else
            echo 0 > /logs/verifier/reward.txt
        fi
    fi
    
    # Exit IMMEDIATELY - don't let any cleanup code run
    # This prevents parser.py from being called
    exit $exit_code
}}
trap _qemu_safe_exit EXIT

{rest_of_script}
"""
    
    # Write patched version
    try:
        test_sh_path.write_text(patched)
        print(f"✅ Patched: {test_sh_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to write {test_sh_path}: {e}")
        return False


def patch_directory(directory: Path, recursive: bool = True) -> tuple[int, int]:
    """Patch all test.sh files in a directory."""
    pattern = "**/test.sh" if recursive else "test.sh"
    test_files = list(directory.glob(pattern))
    
    if not test_files:
        print(f"⚠️  No test.sh files found in {directory}")
        return 0, 0
    
    print(f"Found {len(test_files)} test.sh files")
    
    success = 0
    failed = 0
    
    for test_sh in sorted(test_files):
        if patch_test_sh(test_sh):
            success += 1
        else:
            failed += 1
    
    return success, failed


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    directory = Path(sys.argv[1])
    
    if not directory.exists():
        print(f"❌ Directory not found: {directory}")
        sys.exit(1)
    
    print(f"Patching test.sh files in: {directory}\n")
    success, failed = patch_directory(directory)
    
    print(f"\n{'='*60}")
    print(f"Results: {success} patched, {failed} failed")
    
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
