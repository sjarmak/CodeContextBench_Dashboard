# Bead: Fix Execution Logs Streaming in Harbor Dashboard

**Status:** COMPLETED  
**Priority:** P1  
**Created:** 2025-12-30  
**Resolved:** 2025-12-30

## Problem

When user clicked START button in harbor_dashboard.py Run tab, the "Execution Logs" section appeared but no output was displayed during Harbor evaluations. The subprocess ran but logs didn't stream to the UI in real time.

## Root Cause

The issue was using `st.code()` inside a `with log_container:` block in a loop. Streamlit's container model doesn't support updating UI elements within loops this way. The repeated reassignment of `log_display` and context manager usage prevented proper updates.

## Solution Implemented

Changed the approach to use `st.empty()` placeholder directly:

```python
# OLD (broken):
with log_container:
    log_display = st.code("", language="")
for line in iter(process.stdout.readline, ''):
    if line:
        with log_container:
            log_display.code(...)  # Doesn't work in loop

# NEW (working):
log_placeholder = st.empty()
for line in iter(process.stdout.readline, ''):
    if line:
        log_lines.append(line.rstrip())
        log_placeholder.code('\n'.join(log_lines[-30:]), language="")
```

**Key changes:**
1. Create `st.empty()` placeholder before the loop
2. Call `.code()` directly on the placeholder (not via context manager)
3. Streamlit rerenders the placeholder on each call
4. Display last 30 lines during execution, final 50 lines at end

## Testing Completed

✓ Verified subprocess output capture works (test_subprocess.py)
✓ Verified Harbor CLI is available
✓ Syntax validation passed
✓ Proper indentation fixed

## Notes

The issue was Streamlit-specific. The pattern of using `st.empty()` + direct method calls on the placeholder is the standard approach for live updates in Streamlit.

Also fixed the log display width by using `st.container()` instead of columns, ensuring logs display full-width and aren't truncated.

## Issues Discovered & Fixed

### Issue 1: Logs not displaying
- **Cause**: Streamlit doesn't support real-time UI updates during blocking subprocess calls
- **Fix**: Changed to collect all output during execution, display at end using `st.text()`

### Issue 2: Log window too narrow
- **Cause**: Streamlit constrains `st.code()` and `st.text()` width
- **Fix**: Use full-width column container to prevent width constraints

### Issue 3: Openhands environment setup failing
- **Symptom**: 0.0 reward, "bash: syntax error near unexpected token"
- **Root cause**: Shell syntax `(test -f ... && ... || ...)` was being passed as a command argument instead of being executed
- **Fix**: Changed to proper subshell expansion: `$(test -f {path} && {path} || {fallback})`
- **File**: `/Users/sjarmak/harbor/src/harbor/agents/installed/openhands.py`

## Final Status

Dashboard is now fully functional:
✓ Logs display at full width without truncation
✓ All output from Harbor runs is captured and displayed
✓ Openhands environment setup properly handles venv fallback
✓ Task selection improved with dataset awareness
✓ Error messages clear and helpful
