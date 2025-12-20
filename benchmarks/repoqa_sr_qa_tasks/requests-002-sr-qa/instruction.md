# RepoQA: Semantic Retrieval (SR-QA)

## Task: Find the Function

You are searching a large codebase for a specific function based on its behavior.

**Repository**: requests/requests  
**Language**: python  
**Commit**: bd8ffbc3b4eb53bb9c2d0fa098aa85b8e83a2319

## Function Description

```
Retrieves the host name from a URL
```

## Search Strategy

This function **cannot be found by searching for its name** because the name is not provided. You must:

1. **Understand the behavior** described above
2. **Use Sourcegraph MCP semantic search** to find functions matching this behavior
3. **Explore the code** using call graphs and references
4. **Narrow down** candidates until you find the exact function

### Sourcegraph MCP Tools You Should Use

- **`search_codebase`**: Semantic search for functions by behavior
- **`get_definition`**: Look up function definitions
- **`get_references`**: Find where functions are called
- **`get_call_graph`**: Understand function call relationships

## Output Format

You MUST provide your answer as valid JSON:

```json
{
  "function_path": "path/to/file.py",
  "function_name": "the_function_name",
  "justification": "Why this function matches: describe the behavior you found"
}
```

## Notes

- The file path should be relative to repository root
- Function names are case-sensitive
- Provide your best match even if uncertain; explain your reasoning
- The justification is scored on how well it explains the function's behavior

## Scoring

- ✅ **Perfect** (1.0): Correct path AND name
- ✅ **Good** (0.7-0.9): Correct path, similar name OR vice versa
- ⚠️ **Partial** (0.3-0.6): Close approximation
- ❌ **Incorrect** (0.0): Wrong function entirely

Use Sourcegraph MCP liberally. That's the point of this task.
