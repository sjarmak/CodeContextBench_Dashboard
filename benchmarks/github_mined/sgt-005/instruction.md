# kubelet: Fix nil panic in podcertificatemanager

**Repository:** kubernetes  
**Difficulty:** EASY  
**Category:** cross_module_bug_fix

## Description

If the the PCR that kubelet created gets deleted before it is issued, a nil panic will be thrown while composing the error message.  This is fixed by taking the namespace and name from the current state, not from the (nil) object we just got from the informer.

This likely needs to be picked to 1.35.  The most likely scenario to hit this crash is if you create a pod that requests a certificate from a signer that is not implemented in the cluster (because you're still developing it, or you forg

## Task

Review the PR: kubelet: Fix nil panic in podcertificatemanager

Description: If the the PCR that kubelet created gets deleted before it is issued, a nil panic will be thrown while composing the error message.  This is fixed by taking the namespace and name from the current state, not from the (nil) object we just got from the informer.

This likely needs to be picked to 1.35.  The most likely scenario to hit this crash is if you create a pod that requests a certificate from a signer that is not implemented in the cluster (because you're still developing it, or you forg

Changes:
- 2 files modified
- 112 additions, 1 deletions

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
