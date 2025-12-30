#!/usr/bin/env python3
"""
Patch test.sh files to avoid QEMU parser segfault on ARM64 Macs.

The issue: Harbor's test harness calls `uv run parser.py` after tests complete,
which segfaults on ARM64 Macs due to QEMU emulation + numpy ABI mismatch.

Solution: Wrap test.sh to catch the segfault and exit gracefully after writing reward.

Usage:
    python scripts/patch_test_sh_qemu_safe.py <benchmark-dir>
    
Example:
    python scripts/patch_test_sh_qemu_safe.py benchmarks/swebench_pro/tasks/
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
    
    # Find the shebang and preserve it
    lines = content.split('\n')
    if not lines[0].startswith('#!'):
        print(f"❌ No shebang found in {test_sh_path}")
        return False
    
    shebang = lines[0]
    rest_of_script = '\n'.join(lines[1:])
    
    # Create patched version
    patched = f"""{shebang}
# QEMU_SAFE_PATCH: Prevents segfault when parser.py runs on ARM64 Macs
# This wrapper ensures reward is written and exits cleanly

set -o pipefail  # Propagate pipe failures

# Capture test output and exit code
{{
{rest_of_script}
}}
TEST_EXIT_CODE=$?

# Ensure reward is written (final safeguard)
if [ ! -f /logs/verifier/reward.txt ]; then
    mkdir -p /logs/verifier
    if [ "$TEST_EXIT_CODE" -eq 0 ]; then
        echo 1 > /logs/verifier/reward.txt
    else
        echo 0 > /logs/verifier/reward.txt
    fi
fi

# Exit with test result BEFORE parser.py runs
# This prevents the QEMU segfault that occurs during parser cleanup
exit $TEST_EXIT_CODE
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
