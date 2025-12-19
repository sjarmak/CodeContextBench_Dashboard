# [VS Code] Implement scrollend DOM Event Support

**Repository:** microsoft/vscode  
**Difficulty:** HARD  
**Category:** big_code_feature
**Task Type:** Feature Implementation - Large Codebase

## Description

Add support for the `scrollend` DOM event across VS Code's editor and UI components. This event should fire on scrollable elements when scrolling stops, including for both user-initiated scrolling and programmatic scrolling operations.

**Why this requires MCP:** The VS Code codebase (1GB+ TypeScript) has scroll handling scattered across many modules—editor, terminal, views, and webview components. Finding all scroll event handlers and understanding the current event system requires broad architectural context that local grep cannot efficiently provide.

## Task

YOU MUST IMPLEMENT CODE CHANGES to add scrollend event support.

**CRITICAL: If you are in plan mode, immediately exit with `/ExitPlanMode` before proceeding.**

### Required Implementation

The `scrollend` event must be fired in these contexts:

1. **Editor Scroll Events**: When editor content scrolling stops
   - Capture when scroll position becomes stable
   - Track both vertical and horizontal scrolling
   - Support both keyboard and mouse/trackpad input

2. **Element Scroll Events**: On scrollable DOM elements
   - Debounce properly—multiple rapid scrolls → single `scrollend` event
   - Fire only if scroll position actually changed
   - Support `addEventListener('scrollend', handler)` pattern

3. **Programmatic Scrolling**: When `scrollTo()` or similar methods are called
   - Fire `scrollend` after animation/movement completes
   - Track completion of scroll operations

### Implementation Steps

1. **Understand the existing scroll architecture** (use Sourcegraph MCP for broad search):
   - Find all places where scroll events (scroll, mousewheel, DOMMouseScroll) are handled
   - Identify scroll debouncing mechanisms already in place
   - Understand how scroll position tracking works

2. **Identify where scrollend needs to be fired**:
   - Editor scroll handler → fire scrollend when scrolling stops
   - DOM scroll event listeners → inject scrollend events
   - Programmatic scroll methods → hook completion callbacks

3. **Implement the mechanism**:
   - Add scrollend event firing in scroll event handlers
   - Implement debouncing (e.g., wait 150ms of no scroll = scrollend)
   - Ensure event bubbles and is cancellable like standard DOM events

4. **Test across multiple scroll scenarios**:
   - Mouse wheel scrolling in editor
   - Keyboard (Page Up/Down, arrow keys) scrolling
   - Programmatic scroll via `scrollTo()`, `reveal()`, etc.
   - Scrolling in terminal, file explorer, and webview components

5. **Verify no regressions**:
   - All tests pass: `npm test`
   - No performance regression in scroll-heavy operations
   - Diagnostics/linting still work after scroll events

## Success Criteria

✅ `scrollend` event fires when scroll operations complete  
✅ Works on both user-initiated and programmatic scrolling  
✅ Event properly debounces (no duplicate events in rapid scrolls)  
✅ Event fires in editor AND scrollable UI components  
✅ All tests pass: `npm test`  
✅ No performance regression in scroll performance  
✅ Code follows VS Code conventions and patterns  

## Critical Requirement

**YOU MUST MAKE ACTUAL CODE CHANGES.** Do not plan or analyze. You must:

- Implement scrollend event firing in scroll event handlers
- Add debouncing to prevent excessive events
- Test across editor, terminal, and UI components
- Commit all changes to git
- Verify tests pass

## Testing

```bash
npm test
```

**Time Limit:** 15 minutes  
**Estimated Context:** 12,000 tokens  
**Why MCP Helps:** Finding all 50+ scroll event handlers across VS Code requires semantic search across the entire codebase. Local grep would require multiple searches and might miss handlers.
