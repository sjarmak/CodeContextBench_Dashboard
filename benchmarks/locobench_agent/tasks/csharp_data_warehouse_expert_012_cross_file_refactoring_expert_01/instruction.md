# LoCoBench-Agent Task

## Overview

**Task ID**: csharp_data_warehouse_expert_012_cross_file_refactoring_expert_01
**Category**: cross_file_refactoring
**Difficulty**: expert
**Language**: csharp
**Context Length**: 1113221 tokens
**Files**: 84

## Task Title

Centralize and Standardize Asynchronous Operation Retry Logic

## Description

The PulseOps Warehouse system ingests data from numerous external sources via APIs. Over time, different developers have implemented various data processing modules (represented by `module_*.txt`). A critical issue has emerged: transient network failures are handled inconsistently across these modules. Some use simple loops, some have fixed delays, and others implement rudimentary backoff strategies. This ad-hoc approach makes the system brittle, hard to monitor, and difficult to maintain. The task is to refactor this scattered and inconsistent error handling into a single, robust, and configurable resilience pattern.

## Your Task

Your task is to improve the resilience and maintainability of the PulseOps Warehouse by refactoring the existing error handling logic for external API calls.

1.  **Identify:** Scan all files in the `src/` directory, particularly the `module_*.txt` files, to locate all instances of manual retry loops. These are typically `for` or `while` loops containing a `try-catch` block that handles exceptions like `HttpRequestException`, `TimeoutException`, or `WebException` and attempts to retry the failed operation.

2.  **Design & Implement:** In `src/utils.txt`, create a new public static class named `ResilienceHelper`. Implement a generic, asynchronous static method `ExecuteWithRetryAsync<T>`. This method should accept a delegate (`Func<Task<T>>`) representing the asynchronous operation to execute. The method must implement an exponential backoff retry strategy.

3.  **Centralize Configuration:** The retry policy must be configurable. Add the following two public constants to the `src/constants.txt` file:
    *   `public const int API_MAX_RETRIES = 5;`
    *   `public const int API_INITIAL_BACKOFF_MS = 200;`
    The `ResilienceHelper` must use these constants to control its behavior.

4.  **Refactor:** Replace every identified ad-hoc retry loop throughout the `module_*.txt` files with a single call to your new `ResilienceHelper.ExecuteWithRetryAsync` method. You will need to wrap the original API call within a lambda expression to pass it to the helper. Ensure that the logic remains asynchronous and non-blocking.

5.  **Cleanup:** After replacing the logic, remove all the old, now-redundant `for`/`while` loops, `try-catch` blocks, and any associated manual delay or counter variables.

## Expected Approach

An expert developer would approach this task methodically:

1.  **Discovery:** Use a global search tool (like `grep` or an IDE's find-in-files feature) across the `src` directory for common exception types (`HttpRequestException`, `WebException`, `TimeoutException`) and patterns like `Task.Delay` inside `catch` blocks or loops. This will quickly identify the files and code blocks that need refactoring.

2.  **Analysis:** Review a few of the identified implementations to understand the common requirements and variations. This confirms the need for a generic solution that handles an `async` operation and returns its result.

3.  **Core Implementation:** Begin by defining the new constants in `src/constants.txt`. Then, create the `ResilienceHelper` class and the `ExecuteWithRetryAsync<T>` method in `src/utils.txt`. The implementation would involve a `for` or `while` loop that runs up to `API_MAX_RETRIES`. Inside the loop, a `try-catch` block would invoke the provided `Func<Task<T>>`. On a transient exception, it would calculate the exponential delay (`API_INITIAL_BACKOFF_MS * Math.Pow(2, attempt)`) and use `await Task.Delay()`. If all retries fail, the last exception should be re-thrown to let the caller handle a permanent failure.

4.  **Incremental Refactoring:** Go through each location identified in the discovery phase, one file at a time. Replace the entire multi-line retry block with a concise `await ResilienceHelper.ExecuteWithRetryAsync(async () => await original.ApiCallAsync(...));`. This careful, file-by-file approach minimizes the risk of breaking changes.

5.  **Verification:** After the refactoring, the developer would perform a final review of the diffs to ensure that only the retry mechanism was replaced and that no core business logic was inadvertently altered. They would also check that all old code artifacts have been removed.

## Evaluation Criteria

- **Correctness of Implementation:** The `ResilienceHelper` must correctly implement an exponential backoff strategy using the specified constants from `constants.txt`.
- **Completeness of Refactoring:** All identified ad-hoc retry loops across the relevant `module_*.txt` files must be successfully replaced.
- **Code Quality and Design:** The new `ResilienceHelper` must be generic (using `<T>`), asynchronous (`async/await`), and accept a delegate (`Func<Task<T>>`) to be maximally reusable.
- **Functional Preservation:** The refactoring must not alter the core business logic of the modules. The agent should only replace the error handling wrapper, not the operation itself.
- **Code Cleanliness:** The old, redundant retry loops and their associated variables must be completely removed from the codebase.
- **Configuration Centralization:** The agent must correctly add the new configuration values to `src/constants.txt` and use them in the `ResilienceHelper`, not hardcode them.

## Instructions

1. Explore the codebase in `/app/project/` to understand the existing implementation
2. Use MCP tools for efficient code navigation and understanding
3. Provide your solution in `/app/solution.md`

Your response should:
- Be comprehensive and address all aspects of the task
- Reference specific files and code sections where relevant
- Provide concrete recommendations or implementations as requested
- Consider the architectural implications of your solution

## Output Format

Write your complete solution to `/app/solution.md`. Include:
- Your analysis and reasoning
- Specific file paths and code references
- Any code changes or implementations (as applicable)
- Your final answer or recommendations
