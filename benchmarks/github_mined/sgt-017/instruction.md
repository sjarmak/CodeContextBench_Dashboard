# Automated cherry pick of #133721: fix panic for the crd with subresource but lose openAPIV3Schema

**Repository:** kubernetes  
**Difficulty:** EASY  
**Category:** cross_module_bug_fix

## Description

Cherry pick of #133721 on release-1.33.

#133721: fix panic for the crd with subresource but lose openAPIV3Schema

For details on the cherry pick process, see the [cherry pick requests](https://git.k8s.io/community/contributors/devel/sig-release/cherry-picks.md) page.

```release-note
kube-apiserver: fix a possible panic validating a custom resource whose CustomResourceDefinition indicates a status subresource exists, but which does not define a `status` property in the `openAPIV3Schema`
```

## Task

Review the PR: Automated cherry pick of #133721: fix panic for the crd with subresource but lose openAPIV3Schema

Description: Cherry pick of #133721 on release-1.33.

#133721: fix panic for the crd with subresource but lose openAPIV3Schema

For details on the cherry pick process, see the [cherry pick requests](https://git.k8s.io/community/contributors/devel/sig-release/cherry-picks.md) page.

```release-note
kube-apiserver: fix a possible panic validating a custom resource whose CustomResourceDefinition indicates a status subresource exists, but which does not define a `status` property in the `openAPIV3Schema`
```

Changes:
- 2 files modified
- 143 additions, 1 deletions

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
