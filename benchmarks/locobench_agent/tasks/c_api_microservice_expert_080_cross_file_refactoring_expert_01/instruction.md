# LoCoBench-Agent Task

## Overview

**Task ID**: c_api_microservice_expert_080_cross_file_refactoring_expert_01
**Category**: cross_file_refactoring
**Difficulty**: expert
**Language**: c
**Context Length**: 1101018 tokens
**Files**: 77

## Task Title

Centralize Disparate Logging Mechanisms into a Unified Logging Module

## Description

The 'MercuryMonolith Commerce Hub' is a large, legacy C-based microservice that has evolved over many years. As a result of contributions from various teams, it suffers from significant technical debt. A primary issue is the lack of a standardized logging system. Different modules implement logging in ad-hoc ways: some print directly to stdout, others to stderr, some use custom file logging, and there's no consistent format or control over log verbosity. This makes debugging production issues and monitoring system health extremely difficult. This task involves refactoring the entire monolith to use a single, unified, and configurable logging module.

## Your Task

Your task is to introduce a centralized logging system and refactor the entire codebase to use it. You must preserve all existing functionality.

1.  **Create a new logging module:**
    -   Create two new files: `src/logging.h` and `src/logging.c`.

2.  **Implement the logging API in `src/logging.h` and `src/logging.c`:**
    -   The system must support distinct log levels. Define an enum in `src/logging.h`:
        `typedef enum { LOG_LEVEL_DEBUG, LOG_LEVEL_INFO, LOG_LEVEL_WARN, LOG_LEVEL_ERROR } LogLevel;`
    -   Create an initialization function: `void log_init(LogLevel level, const char* log_file);`. This function should set the minimum log level to output and the destination file. If `log_file` is `NULL`, all logs should go to `stderr`.
    -   Create a core, variadic logging function: `void log_message(LogLevel level, const char* file, int line, const char* fmt, ...);`. This function should handle the actual logging logic, including checking against the configured log level.
    -   Create a set of convenience macros in `src/logging.h` that automatically provide file and line information:
        -   `#define LOG_DEBUG(fmt, ...) log_message(LOG_LEVEL_DEBUG, __FILE__, __LINE__, fmt, ##__VA_ARGS__)`
        -   `#define LOG_INFO(fmt, ...) log_message(LOG_LEVEL_INFO, __FILE__, __LINE__, fmt, ##__VA_ARGS__)`
        -   `#define LOG_WARN(fmt, ...) log_message(LOG_LEVEL_WARN, __FILE__, __LINE__, fmt, ##__VA_ARGS__)`
        -   `#define LOG_ERROR(fmt, ...) log_message(LOG_LEVEL_ERROR, __FILE__, __LINE__, fmt, ##__VA_ARGS__)`

3.  **Integrate the logging system:**
    -   Locate the application's main entry point, which is the function `mercury_hub_main` within `src/module_31.txt`.
    -   In `mercury_hub_main`, add a call to `log_init()` at the beginning. Configure it to use `LOG_LEVEL_INFO` and output to `stderr` (pass `NULL` for the filename).

4.  **Perform the cross-file refactoring:**
    -   Systematically scan all source files in the `src/` directory.
    -   Identify and replace all ad-hoc logging calls. These primarily consist of `printf(...)` and `fprintf(stderr, ...)` statements that are clearly used for logging (e.g., they start with prefixes like "INFO:", "DEBUG:", "[ERROR]").
    -   Map the old logging statements to the new macros based on their content:
        -   Statements indicating errors, failures, or fatal conditions should use `LOG_ERROR`.
        -   Statements with "warn" or "warning" should use `LOG_WARN`.
        -   Statements used for debugging (e.g., prefixed with "DEBUG:") should use `LOG_DEBUG`.
        -   All other informational logging should use `LOG_INFO`.
    -   Ensure that the format string and all variable arguments from the original `printf`/`fprintf` calls are correctly passed to the new logging macros.

5.  **Update Includes:**
    -   For every source file that you modify to use the new logging macros, add `#include "logging.h"` at the top.

## Expected Approach

An expert developer would approach this task methodically:

1.  **Analysis & Scoping:** Begin by using a tool like `grep` or a search-in-files feature to find all instances of `printf` and `fprintf(stderr,`. This helps to understand the scope and variety of logging patterns used across the project.

2.  **API-First Implementation:** First, create `src/logging.h` to define the public interface (the `enum`, function prototypes, and macros). This establishes a clear contract for the rest of the work. Then, implement the logic in `src/logging.c`, paying careful attention to the use of `va_list` for the variadic functions and managing the file pointer for logging.

3.  **Centralized Initialization:** Locate `mercury_hub_main` in `src/module_31.txt`. Add the `#include "logging.h"` and the `log_init(LOG_LEVEL_INFO, NULL);` call near the top of the function. This ensures the system is ready before any other module can use it.

4.  **Incremental Refactoring:** Process the files one by one or in logical groups. For each file:
    a. Add `#include "logging.h"`.
    b. Find each logging statement.
    c. Determine the appropriate log level (`LOG_ERROR`, `LOG_WARN`, etc.) based on the string's content.
    d. Replace the old call (e.g., `fprintf(stderr, "ERROR: Failed to process request %d\n", request_id);`) with the new macro (`LOG_ERROR("Failed to process request %d", request_id);`), ensuring the format string is stripped of prefixes and the arguments are transferred correctly.

5.  **Verification:** After the refactoring, the developer would perform a full conceptual compilation of the project to check for syntax errors, missing includes, or incorrect function signatures. They would then run the test suite (`tests/test_main.txt`) to ensure no functional regressions were introduced. A final check would involve running the application and observing `stderr` to confirm the new, formatted logs are appearing as expected.

## Evaluation Criteria

- **Correctness of New Module:** The implementation in `src/logging.c` and `src/logging.h` must be correct, complete, and free of bugs. It must handle variadic arguments and file I/O properly.
- **Completeness of Refactoring:** The agent must identify and replace all relevant ad-hoc logging statements across all source files. A partial refactoring is a partial success.
- **Accuracy of Replacement:** The agent must correctly map old log messages to the new log levels. It must also accurately transfer format strings and all associated arguments to the new macros without modification.
- **Code Integrity and Non-Regression:** The refactored code must be syntactically correct (conceptually compilable). No existing logic should be broken, and the functionality covered by `tests/test_main.txt` must be preserved.
- **Correct Initialization:** The `log_init()` function must be called exactly once at the specified entry point (`mercury_hub_main` in `src/module_31.txt`) with the correct parameters.
- **Header Management:** The agent must correctly add `#include "logging.h"` to all files where the new macros are used, and only those files.

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
