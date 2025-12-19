"""Harbor-compatible Claude Code agent with autonomous implementation mode (no MCP).

This agent extends Harbor's built-in ClaudeCode to inject autonomous environment
variables that enable headless/autonomous operation mode, where Claude Code
automatically implements code changes instead of entering interactive planning mode.

This agent is used for the baseline comparison in benchmarks - it has the same
autonomous capabilities as the MCP agent but without Sourcegraph Deep Search.
"""

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.base import ExecInput


class BaselineClaudeCodeAgent(ClaudeCode):
    """Claude Code with autonomous implementation mode enabled (no MCP).
    
    Extends Harbor's built-in ClaudeCode agent to:
    1. Enable autonomous/headless operation mode
    2. Use implementation-focused command-line flags
    3. Ensure agents make actual code changes instead of planning
    
    The autonomous environment variables are the critical control mechanism that
    makes Claude Code operate in implementation mode instead of planning/analysis mode.
    
    This agent is used as the baseline for benchmarking - it provides a fair
    comparison point to the MCP agent by having the same autonomous mode but
    without Sourcegraph Deep Search integration.
    """

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        """
        Override to enable autonomous implementation mode.
        
        This modifies the Claude Code command to:
        1. Add autonomous environment variables (FORCE_AUTO_BACKGROUND_TASKS, ENABLE_BACKGROUND_TASKS)
        2. Use --permission-mode acceptEdits to enable file modifications
        3. Explicitly whitelist all necessary tools (Read, Edit, Write, Bash, Grep, Glob)
        
        The autonomous environment variables are the critical control mechanism that makes
        Claude Code operate in implementation mode instead of planning/analysis mode.
        """
        
        # Get parent's commands
        parent_commands = super().create_run_agent_commands(instruction)
        
        # All tools Claude needs for implementation
        allowed_tools = "Bash,Read,Edit,Write,Grep,Glob,Skill,TodoWrite,Task,TaskOutput"
        
        # Modify the Claude command to enable implementation mode with full tool access
        result = []
        for cmd in parent_commands:
            if cmd.command and "claude " in cmd.command:
                # Inject both --permission-mode and --allowedTools
                # This enables actual code changes and ensures tools are available
                modified_command = cmd.command.replace(
                    "claude ",
                    f"claude --permission-mode acceptEdits --allowedTools {allowed_tools} "
                )
                
                # CRITICAL: Add autonomous environment variables
                # These are undocumented Claude CLI flags that enable headless/autonomous operation
                # Without these, Claude Code defaults to interactive planning mode
                env = cmd.env or {}
                env_with_autonomous = {
                    **env,
                    'FORCE_AUTO_BACKGROUND_TASKS': '1',
                    'ENABLE_BACKGROUND_TASKS': '1'
                }
                
                self.logger.info(f"Modified command for autonomous implementation mode with tool whitelist")
                self.logger.info(f"Tools enabled: {allowed_tools}")
                self.logger.info(f"Autonomous mode enabled: FORCE_AUTO_BACKGROUND_TASKS=1, ENABLE_BACKGROUND_TASKS=1")
                result.append(
                    ExecInput(command=modified_command, env=env_with_autonomous)
                )
            else:
                result.append(cmd)
        
        return result
