# Kubernetes Documentation Task: sched-doc-001

## Task
Generate a comprehensive `README.md` for the `podtopologyspread` scheduler plugin.

## Constraints
- **Sourcegraph Search**: You MUST only search within the `kubernetes-stripped` repository.
- **Cheating**: Do not attempt to find original `README.md` or `doc.go` files for this plugin; they have been removed from the local environment and are excluded from the `kubernetes-stripped` index.
- **Inference**: Use your understanding of the implementation code and related KEPs (which you can find via MCP) to write the documentation.

## Requirements for README.md
1. Explain the purpose of the plugin and topology spread constraints.
2. Document the filtering and scoring logic.
3. Explain key concepts: `MaxSkew`, `TopologyKey`, `WhenUnsatisfiable`.
4. Provide usage examples and configuration options.
5. Reference related features and KEPs.

## Verification
Write the final documentation to `pkg/scheduler/framework/plugins/podtopologyspread/README.md`.
