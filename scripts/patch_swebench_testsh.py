#!/usr/bin/env python3
"""
Patch SWE-bench test.sh files to copy $LOG_FILE to Harbor's expected location.

This fixes the issue where Harbor's mounted /logs/verifier directory never
receives the full test output because SWE-bench test.sh writes to a temp file.
"""

import sys
from pathlib import Path


def patch_test_sh(test_sh_path: Path) -> bool:
    """
    Patch a test.sh file to copy $LOG_FILE to /logs/verifier/test-stdout.txt.
    
    Returns True if patched, False if already patched or error.
    """
    if not test_sh_path.exists():
        print(f"❌ File not found: {test_sh_path}")
        return False
    
    content = test_sh_path.read_text()
    
    # Check if already patched
    if "cp \"$LOG_FILE\" /logs/verifier/test-stdout.txt" in content:
        print(f"✓ Already patched: {test_sh_path}")
        return False
    
    # Find the location to insert the patch (after parser runs, before reward logging)
    patch_marker = "# ----------------------- Reward logging for Harbor ------------------------"
    
    if patch_marker not in content:
        print(f"❌ Could not find patch location in: {test_sh_path}")
        return False
    
    # Insert the patch
    patch_line = """
# Copy full log to Harbor's expected location (for mounted environments)
# This ensures Harbor sees the complete output including parser results
cp "$LOG_FILE" /logs/verifier/test-stdout.txt 2>/dev/null || true

"""
    
    patched_content = content.replace(patch_marker, patch_line + patch_marker)
    
    # Write back
    test_sh_path.write_text(patched_content)
    print(f"✅ Patched: {test_sh_path}")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python patch_swebench_testsh.py <path-to-test.sh-or-benchmark-dir>")
        print("       python patch_swebench_testsh.py benchmarks/swebench_verified")
        sys.exit(1)
    
    path = Path(sys.argv[1])
    
    if path.is_file() and path.name == "test.sh":
        # Single file
        patch_test_sh(path)
    elif path.is_dir():
        # Directory - find all test.sh files
        test_sh_files = list(path.rglob("tests/test.sh"))
        print(f"Found {len(test_sh_files)} test.sh files in {path}")
        
        patched = 0
        for test_sh in test_sh_files:
            if patch_test_sh(test_sh):
                patched += 1
        
        print(f"\nPatched {patched}/{len(test_sh_files)} files")
    else:
        print(f"❌ Invalid path: {path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
