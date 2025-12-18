# Automated cherry pick of #132895: Fixes scheduler nil panic due to empty init container request&limit

**Repository:** kubernetes  
**Difficulty:** EASY  
**Category:** cross_module_bug_fix

## Description

Cherry pick of #132895 on release-1.33.

#132895: Fixes scheduler nil panic due to empty init container request&limit

For details on the cherry pick process, see the [cherry pick requests](https://git.k8s.io/community/contributors/devel/sig-release/cherry-picks.md) page.

```release-note
Fixes a 1.33 regression that can cause a nil panic in kube-scheduler when aggregating resource requests across container's spec and status.
```

## Task

Review the PR: Automated cherry pick of #132895: Fixes scheduler nil panic due to empty init container request&limit

Description: Cherry pick of #132895 on release-1.33.

#132895: Fixes scheduler nil panic due to empty init container request&limit

For details on the cherry pick process, see the [cherry pick requests](https://git.k8s.io/community/contributors/devel/sig-release/cherry-picks.md) page.

```release-note
Fixes a 1.33 regression that can cause a nil panic in kube-scheduler when aggregating resource requests across container's spec and status.
```

Changes:
- 2 files modified
- 78 additions, 15 deletions

Tasks:
1. Understand the issue being fixed
2. Review the solution in the merged PR
3. Implement the fix to pass all tests
4. Verify: run "go test ./..." successfully

## Success Criteria

All tests pass: run "go test ./..." successfully.
Code follows repository conventions.
No regressions in existing functionality.
All 2 modified files updated correctly.

## Testing

Run the test command to verify your implementation:

```bash
go test ./...
```

**Time Limit:** 10 minutes  
**Estimated Context:** 8000 tokens
