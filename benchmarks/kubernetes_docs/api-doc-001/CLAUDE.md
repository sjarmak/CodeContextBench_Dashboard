# Kubernetes Documentation Task: api-doc-001

## Task
Generate comprehensive documentation (Markdown) for Kubernetes Server-Side Apply (SSA), specifically focusing on `managedfields`.

## Constraints
- **Sourcegraph Search**: You MUST only search within the `kubernetes-stripped` repository.
- **Cheating**: Do not attempt to find original `README.md` or `doc.go` files for this component; they have been removed from the local environment and are excluded from the `kubernetes-stripped` index.
- **Inference**: Use your understanding of the implementation code and related KEPs (which you can find via MCP) to write the documentation.

## Requirements for documentation
1. Provide an overview of Server-Side Apply (SSA) concepts.
2. Explain field ownership and managers.
3. Document merge semantics (atomic, granular, map, set).
4. Explain conflict detection and resolution.
5. Discuss migration from client-side apply.

## Verification
Write the final documentation to `staging/src/k8s.io/apimachinery/pkg/util/managedfields/README.md`.
