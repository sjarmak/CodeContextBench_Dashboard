# Harbor Cache Patching for QEMU Segfault Fix

## Issue Found

When running evaluations using Harbor datasets (e.g., `swebench-verified@1.0`), the reward was still returning 0 due to QEMU parser segfault, even though we had patched `benchmarks/swebench_pro/tasks/`.

**Root cause:** Harbor fetches official datasets from its cache directory (`~/.cache/harbor/tasks/`), and those test.sh files were **not** patched.

## Solution

Patch the Harbor cache directory in addition to local benchmarks:

```bash
# Patch local benchmarks
python scripts/patch_test_sh_qemu_safe.py benchmarks/swebench_pro/tasks/

# Patch Harbor cached datasets
python scripts/patch_test_sh_qemu_safe.py ~/.cache/harbor/tasks/
```

## Results

- **Local benchmarks**: 731 test.sh files patched
- **Harbor cache**: 501 test.sh files patched
- **Total**: 1,232 test.sh files protected from QEMU segfault

## Technical Detail

Harbor cache test.sh files have malformed formatting:
- Line 1: Comment about "testbed" (corrupted)
- Line 2: Empty line
- Line 3: Actual `#!/bin/bash` shebang
- Line 4+: Script content

The updated patcher now searches lines 1-5 for the shebang instead of assuming it's on line 1.

## Dashboard Compatibility

Now the dashboard works with both:
- Local benchmark paths: `--path benchmarks/swebench_pro/tasks/instance_<task>`
- Harbor datasets: `--dataset swebench-verified@1.0 --task-name <task>`

Both use patched test.sh files, so rewards will be written correctly without QEMU segfaults.

## One-Time Setup

Run both patch commands once:

```bash
python scripts/patch_test_sh_qemu_safe.py benchmarks/swebench_pro/tasks/
python scripts/patch_test_sh_qemu_safe.py ~/.cache/harbor/tasks/
```

Then use dashboard and CLI commands normally—no additional setup needed.

## Future Harbor Datasets

If you download additional datasets that aren't currently in the cache, run the patcher again on the cache directory to patch them:

```bash
python scripts/patch_test_sh_qemu_safe.py ~/.cache/harbor/tasks/
```

The script is idempotent and will only patch unpatched files.
