# Kubernetes Documentation Task: ctrl-doc-001

## Task
Generate comprehensive package documentation (`doc.go`) for the Kubernetes Garbage Collector controller (`pkg/controller/garbagecollector`).

## Constraints
- **Sourcegraph Search**: You MUST only search within the `kubernetes-stripped` repository.
- **Cheating**: Do not attempt to find original `doc.go` or `README.md` files for this controller; they have been removed from the local environment and are excluded from the `kubernetes-stripped` index.
- **Inference**: Use your understanding of the implementation code and related design documents (which you can find via MCP) to write the documentation.

## Requirements for doc.go
1. Explain the purpose of the Garbage Collector controller and cascading deletion.
2. Describe the garbage collection algorithm (dependency graph construction).
3. Explain different deletion modes: `orphan`, `foreground`, `background`.
4. Document how finalizers are handled.
5. Follow Go documentation conventions.

## Verification
Write the final documentation to `pkg/controller/garbagecollector/doc.go`.
