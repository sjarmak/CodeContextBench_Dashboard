# Kubernetes Documentation Task: kubelet-doc-001

## Task
Generate comprehensive documentation (Markdown) for the Kubelet Topology Manager (`pkg/kubelet/cm/topologymanager`).

## Constraints
- **Sourcegraph Search**: You MUST only search within the `kubernetes-stripped` repository.
- **Cheating**: Do not attempt to find original `README.md` or `doc.go` files for this component; they have been removed from the local environment and are excluded from the `kubernetes-stripped` index.
- **Inference**: Use your understanding of the implementation code and related KEPs (which you can find via MCP) to write the documentation.

## Requirements for documentation
1. Provide an overview of the Topology Manager's purpose.
2. Explain NUMA topology concepts as they apply here.
3. Document all policy types: `none`, `best-effort`, `restricted`, `single-numa-node`.
4. Describe the `HintProvider` interface.
5. Explain integration with CPU, Memory, and Device managers.

## Verification
Write the final documentation to `pkg/kubelet/cm/topologymanager/README.md`.
