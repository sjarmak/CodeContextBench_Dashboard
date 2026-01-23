# LoCoBench-Agent Task

## Overview

**Task ID**: python_desktop_development_expert_021_architectural_understanding_expert_01
**Category**: architectural_understanding
**Difficulty**: expert
**Language**: python
**Context Length**: 1018897 tokens
**Files**: 73

## Task Title

Implement a System-Wide 'Focus Mode' Feature

## Description

FlockDesk is a modular desktop application designed for collaborative work. Its architecture is built upon several key principles: a central event bus for decoupled communication (`EventBus`), a plugin system for loading features as modules (`PluginManager`), a service layer for core functionalities (`SettingsService`, `AuthService`, etc.), and an MVVM (Model-View-ViewModel) pattern for the UI of each module. This scenario requires implementing a new global 'Focus Mode' feature. When a user enables Focus Mode, the application should reduce distractions from non-primary modules to help the user concentrate on a specific task (e.g., in the co-editor or whiteboard).

## Your Task

Your task is to implement the 'Focus Mode' feature across the FlockDesk application. This requires understanding and modifying multiple parts of the system, from core services to individual modules.

### Requirements:

1.  **Persistent State:** Introduce a new global setting, `focus_mode_enabled` (boolean), that persists across application restarts. The `SettingsService` is the designated component for managing user preferences.

2.  **Global Toggle:** Add a new menu item under the main 'View' menu in the application's menu bar to toggle Focus Mode on and off. This action should update the persistent state.

3.  **Event-Driven Communication:** When the Focus Mode state changes, a global event must be broadcasted across the application. You must use the existing `EventBus` for this purpose. Do not create direct dependencies between the menu bar and other modules.

4.  **Module-Level Reaction (Chat):** Modify the `Chat` module to react to Focus Mode changes. When Focus Mode is **enabled**, the chat module should visually indicate that notifications are snoozed and should suppress any new incoming message notifications.

5.  **Module-Level Reaction (Dashboard):** Modify the `Dashboard` module to react to Focus Mode changes. When Focus Mode is **enabled**, the main activity feed widget on the dashboard should be visually de-emphasized (e.g., greyed out or have its opacity lowered) to reduce visual noise.

Your implementation must respect the existing architectural patterns (Event-Driven, MVVM, Service Layer).

## Expected Approach

An expert developer would first analyze the codebase to confirm the architectural patterns. They would look for the `EventBus`, `SettingsService`, and the structure of the modules.

1.  **State Management:** The developer would identify `flockdesk/core/services/settings_service.py` and `configs/default_settings.json` as the correct places to manage the new setting. They would add `"focus_mode_enabled": false` to the JSON config and update the service to handle loading and saving this key.

2.  **Event Definition:** They would open `flockdesk/core/ipc/event_types.py` and define a new event, such as `FOCUS_MODE_CHANGED`, to standardize the communication contract.

3.  **Trigger Implementation:**
    *   They would find `flockdesk/core/shell/menu_bar.py` to add the new 'Toggle Focus Mode' QAction.
    *   To avoid putting logic in the UI, they would create a new `Command` in `flockdesk/core/shortcuts/commands.py`. This `ToggleFocusModeCommand` would be responsible for:
        a. Accessing the `SettingsService` to toggle the boolean value.
        b. Accessing the `EventBus` to publish the `FOCUS_MODE_CHANGED` event with the new state as a payload.
    *   The menu action in `menu_bar.py` would then be connected to trigger this new command.

4.  **Chat Module Modification:**
    *   The developer would identify `flockdesk/modules/chat/viewmodel/chat_vm.py` as the logic hub for the chat module.
    *   In the `ChatViewModel`'s constructor, they would subscribe to the `FOCUS_MODE_CHANGED` event on the `EventBus`.
    *   They would add a new observable property to the ViewModel, e.g., `self.is_snoozed`.
    *   The event handler would update `self.is_snoozed` based on the event payload.
    *   Finally, they would modify `flockdesk/modules/chat/view/chat_widget.py` to bind a UI element's visibility or style to the `is_snoozed` property of its ViewModel.

5.  **Dashboard Module Modification:**
    *   They would follow the exact same pattern as with the Chat module, but for the Dashboard components.
    *   They would modify `flockdesk/modules/dashboard/viewmodel/dashboard_vm.py` to subscribe to the event and manage a state property like `self.is_deemphasized`.
    *   They would then update `flockdesk/modules/dashboard/view/dashboard_widget.py` to change the styling of the activity feed based on this ViewModel property.

## Evaluation Criteria

- **Architectural Adherence (Event Bus):** Did the agent correctly use the `EventBus` for broadcasting the state change, or did it attempt to create direct, tightly-coupled calls between UI components and modules?
- **Architectural Adherence (Service Layer):** Was the `SettingsService` correctly identified and used as the single source of truth for the persistent 'Focus Mode' state?
- **Architectural Adherence (MVVM):** Were the changes in the modules correctly implemented within the ViewModel layer, with the View layer being a passive observer of the ViewModel's state?
- **Component Discovery:** Did the agent successfully locate and modify the correct, disparate set of files required for the task (settings config, event types, menu bar, command definitions, and multiple module ViewModels)?
- **Code Modularity:** Is the new code well-integrated without breaking existing patterns? Is the `ToggleFocusModeCommand` self-contained and reusable?
- **Completeness:** Does the final implementation satisfy all functional requirements: persistence, a working toggle, and the specified UI changes in both the Chat and Dashboard modules?

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
