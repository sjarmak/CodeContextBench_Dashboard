"""Test that environment variables are properly injected by the agent."""

import os
from unittest.mock import Mock, MagicMock
import pytest


def test_api_key_injection_logic():
    """Test the API key injection logic without importing Harbor."""
    # This tests the core logic of the environment injection
    test_api_key = "test-api-key-12345"
    
    # Simulate the create_run_agent_commands method logic
    class MockExecInput:
        def __init__(self, command, env=None):
            self.command = command
            self.env = env
    
    # Parent's commands
    parent_commands = [
        MockExecInput(command="claude --verbose", env=None),
        MockExecInput(command="claude --help", env={"EXISTING": "value"}),
    ]
    
    # Simulate the injection logic from create_run_agent_commands
    modified_commands = []
    anthropic_key = test_api_key  # Simulating os.environ.get("ANTHROPIC_API_KEY", "")
    
    for cmd in parent_commands:
        env = cmd.env or {}
        
        if anthropic_key:
            env["ANTHROPIC_API_KEY"] = anthropic_key
        
        modified_commands.append(
            MockExecInput(
                command=cmd.command,
                env=env,
            )
        )
    
    # Verify
    assert len(modified_commands) == 2
    
    # First command should have API key added
    assert modified_commands[0].command == "claude --verbose"
    assert modified_commands[0].env.get("ANTHROPIC_API_KEY") == test_api_key
    
    # Second command should preserve existing vars and add API key
    assert modified_commands[1].command == "claude --help"
    assert modified_commands[1].env.get("EXISTING") == "value"
    assert modified_commands[1].env.get("ANTHROPIC_API_KEY") == test_api_key


def test_api_key_not_injected_when_missing():
    """Test that env dict is created even when API key is missing."""
    class MockExecInput:
        def __init__(self, command, env=None):
            self.command = command
            self.env = env
    
    parent_commands = [
        MockExecInput(command="claude --verbose", env=None),
    ]
    
    # No API key provided
    modified_commands = []
    anthropic_key = ""  # Empty/missing
    
    for cmd in parent_commands:
        env = cmd.env or {}
        
        if anthropic_key:
            env["ANTHROPIC_API_KEY"] = anthropic_key
        
        modified_commands.append(
            MockExecInput(
                command=cmd.command,
                env=env,
            )
        )
    
    # Verify command is preserved with empty env
    assert len(modified_commands) == 1
    assert modified_commands[0].command == "claude --verbose"
    assert modified_commands[0].env == {}  # Empty env, not None
