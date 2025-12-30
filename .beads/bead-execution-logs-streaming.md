# Bead: Fix Execution Logs Streaming in Harbor Dashboard

**Status:** OPEN  
**Priority:** P1  
**Created:** 2025-12-30

## Problem

When user clicks START button in harbor_dashboard.py Run tab, the "Execution Logs" section appears but no output is displayed during the Harbor evaluation. The subprocess is running but logs aren't streaming to the UI.

## Location

File: `/Users/sjarmak/CodeContextBench/harbor_dashboard.py`  
Lines: ~240-280 (Run tab implementation)

## Root Cause

The subprocess streaming logic likely has an issue with:
- Streamlit's event model and UI updates
- st.code() refresh behavior with subprocess iteration
- Buffering of stdout from subprocess

Current code:
```python
process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    env=env,
    cwd=str(PROJECT_ROOT),
    bufsize=1
)

log_lines = []
with log_container:
    log_display = st.code("", language="")

for line in iter(process.stdout.readline, ''):
    if line:
        log_lines.append(line.rstrip())
        with log_container:
            log_display.code('\n'.join(log_lines[-20:]), language="")
        time.sleep(0.01)

returncode = process.wait()
```

## Solution Needed

1. Debug actual subprocess output (test with simple command first)
2. Verify Streamlit container updates work correctly
3. Consider alternative streaming approach (threads, queues)
4. Test with actual Harbor run to see output

## Testing

- [ ] Create minimal subprocess test
- [ ] Verify logs display in basic case
- [ ] Test with actual Harbor evaluation
- [ ] Verify full run completes successfully

## Notes

- Everything else in dashboard works perfectly
- Task selection, results viewing, metrics all good
- Just the real-time log display needs fixing
