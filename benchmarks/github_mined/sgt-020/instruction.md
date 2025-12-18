# Automated cherry pick of #133771: Fix completion of resource names

**Repository:** kubernetes  
**Difficulty:** EASY  
**Category:** cross_module_bug_fix

## Description

Cherry pick of #133771 on release-1.34.

#133771: Fix completion of resource names

For details on the cherry pick process, see the [cherry pick requests](https://git.k8s.io/community/contributors/devel/sig-release/cherry-picks.md) page.

```release-note
Fixed a 1.34 regression causing broken shell completion for api resources.
```

## Task

Review the PR: Automated cherry pick of #133771: Fix completion of resource names

Description: Cherry pick of #133771 on release-1.34.

#133771: Fix completion of resource names

For details on the cherry pick process, see the [cherry pick requests](https://git.k8s.io/community/contributors/devel/sig-release/cherry-picks.md) page.

```release-note
Fixed a 1.34 regression causing broken shell completion for api resources.
```

Changes:
- 2 files modified
- 100 additions, 3 deletions

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
