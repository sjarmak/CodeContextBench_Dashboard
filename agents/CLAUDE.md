# Claude Code Integration Guide

## Sourcegraph MCP Available

When using `ClaudeCodeSourcegraphMCPAgent`, Sourcegraph Deep Search is available via Model Context Protocol (MCP).

### Using Sourcegraph Deep Search

For code understanding and context gathering, use the `deep_search` tool:

```
Use the deep_search tool to understand the codebase structure:
- Query for function/class definitions
- Find usage patterns
- Understand module relationships
- Locate test files and examples
```

### Example Queries

For understanding code before making changes:
- "Find the definition of [function_name] and show how it's used"
- "What modules import [module_name]?"
- "Find all test files for [module_name]"
- "Where is [constant_name] defined and what references it?"

### Benefits

- Faster codebase comprehension
- Better accuracy for cross-file changes
- Understanding of test patterns
- Discovery of related code

## Running Tasks

Tasks include full repository context. Use:
1. Deep Search to understand structure
2. Read files to examine implementations
3. Make targeted changes
4. Test changes against task requirements
