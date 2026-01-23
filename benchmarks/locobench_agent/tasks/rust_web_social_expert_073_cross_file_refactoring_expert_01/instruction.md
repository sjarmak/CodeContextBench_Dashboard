# LoCoBench-Agent Task

## Overview

**Task ID**: rust_web_social_expert_073_cross_file_refactoring_expert_01
**Category**: cross_file_refactoring
**Difficulty**: expert
**Language**: rust
**Context Length**: 1067411 tokens
**Files**: 86

## Task Title

Refactor Disparate Event Publishing Logic into a Centralized, Generic Service

## Description

In the EduPulse Live application, various modules are responsible for publishing events to a central event bus (e.g., user logged in, new content created, session started). This logic was implemented independently in each module as the features were developed. As a result, there is significant code duplication related to event serialization, connection handling, and error management across multiple files. This technical debt makes the system harder to maintain and introduces inconsistencies. This task involves refactoring this scattered logic into a single, robust, and reusable event publishing service.

## Your Task

Your task is to improve the architecture of the EduPulse Live application by centralizing all event publishing logic.

1.  **Analyze the existing implementation:** Examine the source code in `src/module_15.txt`, `src/module_48.txt`, and `src/module_77.txt`. Each of these files contains a distinct function that serializes a module-specific struct to JSON and sends it to an event stream. These functions contain duplicated logic for serialization, error handling, and interacting with a mock event stream client.

2.  **Create a new, centralized module:**
    *   Create a new file named `src/event_publisher.txt`.
    *   Inside this new file, define a struct `EventPublisher` that will manage the connection to the event stream.
    *   Implement a `new()` function for `EventPublisher` that initializes it. For configuration, it should call the mock function `get_event_bus_config()` located in `src/utils.txt`.

3.  **Implement a generic publishing method:**
    *   On the `EventPublisher` struct, create a public, asynchronous method: `publish<T: serde::Serialize + Sync>`. This method should accept a payload of any type `T` that can be serialized.
    *   This `publish` method will be responsible for:
        a. Serializing the payload to a JSON string.
        b. Calling the mock `send_event_to_stream()` function from `src/utils.txt`.
        c. Handling potential errors from serialization or sending, returning a `Result`.
    *   Define a custom `EventPublisherError` enum within `src/event_publisher.txt` to standardize error reporting for this service.

4.  **Refactor existing modules:**
    *   Modify `src/module_15.txt`, `src/module_48.txt`, and `src/module_77.txt` to use the new `EventPublisher` service.
    *   Remove the original, now-redundant event publishing functions from these three modules.
    *   Update the call sites within those modules to instantiate and use the `EventPublisher`'s `publish` method.
    *   Ensure you add the necessary `use crate::event_publisher::{...}` statements at the top of the modified files.

## Expected Approach

An expert developer would approach this task systematically:

1.  **Discovery & Analysis:** First, they would read the three specified modules (`module_15`, `module_48`, `module_77`) and `utils.txt`. They would identify the common code patterns related to creating a client, serializing data using `serde_json`, calling the send function, and handling errors. They would also note the differences, such as the specific struct types being serialized and any minor variations in logging or error messages.

2.  **Design the Abstraction:** Based on the analysis, they would design the new `event_publisher` module. This involves defining the API for the new service: the `EventPublisher` struct to hold state (like the event bus configuration), the `EventPublisherError` enum to unify error types, and the generic `publish` method signature, using `T: serde::Serialize` to make it reusable.

3.  **Implementation of the Core Service:** The developer would create the `src/event_publisher.txt` file and implement the designed components. They would import necessary dependencies like `serde`, `serde_json`, and the mock functions from `crate::utils`. The `publish` method would encapsulate the `serde_json::to_string` call and the `send_event_to_stream` call within a `try-catch` (`Result`-based) block.

4.  **Incremental Refactoring:** The developer would then refactor each of the three modules one by one.
    *   For each module, they would add the `use crate::event_publisher::EventPublisher;` statement.
    *   They would locate the code that calls the old publishing function.
    *   They would replace that section of code with the instantiation of the new `EventPublisher` and a call to its `publish` method, passing the relevant event struct.
    *   Once all call sites within a module are updated, they would safely delete the old, duplicated publishing function.

5.  **Verification:** Throughout the process, the developer would be mentally compiling the code, ensuring that lifetimes, ownership, and trait bounds are satisfied. They would confirm that the new `use` statements are correct and that the refactoring hasn't altered the application's high-level behavior.

## Evaluation Criteria

- **Correctness of Centralization:** Was the duplicated event publishing logic successfully consolidated into the new `src/event_publisher.txt` module?
- **Proper Use of Generics:** Is the new `publish` method correctly implemented using Rust generics (`<T: serde::Serialize>`) to handle different event data structures without code duplication?
- **Code Elimination:** Were the old, redundant publishing functions and their associated helper logic completely removed from `module_15`, `module_48`, and `module_77`?
- **Architectural Improvement:** Does the solution correctly use a struct (`EventPublisher`) to manage state and configuration, demonstrating an understanding of dependency management over static functions?
- **Dependency Resolution:** Are the necessary `use` statements correctly added to the refactored modules to import the new service?
- **Error Handling:** Is a new, unified `EventPublisherError` type created and used correctly in the `publish` method's return signature?
- **Surgical Precision:** Did the agent avoid making unnecessary or unrelated changes to the files or the broader codebase?

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
