"""Harbor-compatible Claude Code agent with Sourcegraph MCP support."""

import json
import os
from pathlib import Path
from typing import Any

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.base import ExecInput
from harbor.models.trial.paths import EnvironmentPaths


class ClaudeCodeMCP(ClaudeCode):
    """
    Claude Code with Sourcegraph MCP server support.
    
    Extends Harbor's built-in ClaudeCode agent to add MCP configuration.
    """
    
    @staticmethod
    def name() -> str:
        return "claude-code-mcp"
    
    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        """
        Create commands to run Claude Code with MCP server configured.
        
        First get parent commands, then inject MCP configuration.
        """
        import shlex
        
        # Get parent's commands (handles auth, Claude setup, etc.)
        parent_commands = super().create_run_agent_commands(instruction)
        
        # Get Sourcegraph credentials from environment
        src_token = os.environ.get("SRC_ACCESS_TOKEN", "")
        src_url = os.environ.get("SOURCEGRAPH_URL", "https://sourcegraph.sourcegraph.com")
        
        if not src_token:
            print("WARNING: SRC_ACCESS_TOKEN not set - MCP server will not work")
        
        # Find the Claude execution command (last command usually)
        # and inject --mcp-config flag + env vars
        modified_commands = []
        for cmd in parent_commands:
            if cmd.command and "claude " in cmd.command:
                # Inject MCP config flag after "claude"
                mcp_config_path = (EnvironmentPaths.agent_dir / "sessions" / "mcp.json").as_posix()
                
                # Build env var prefix for command (env VAR=value ...)
                env_prefix_parts = []
                if cmd.env:
                    for key, val in cmd.env.items():
                        if val:  # Skip empty values
                            env_prefix_parts.append(f"{key}={shlex.quote(val)}")
                
                env_prefix = " ".join(env_prefix_parts)
                if env_prefix:
                    env_prefix += " "
                
                modified_cmd = cmd.command.replace(
                    "claude ",
                    f"{env_prefix}claude --mcp-config {mcp_config_path} "
                )
                modified_commands.append(
                    ExecInput(
                        command=modified_cmd,
                        env={},  # Env already in command
                    )
                )
            else:
                modified_commands.append(cmd)
        
        # Create MCP config before running Claude
        mcp_config = {
            "mcpServers": {
                "sourcegraph": {
                    "command": "npx",
                    "args": ["-y", "@sourcegraph/mcp-server"],
                    "env": {
                        "SRC_ACCESS_TOKEN": src_token,
                        "SOURCEGRAPH_URL": src_url,
                    }
                }
            }
        }
        
        mcp_config_json = json.dumps(mcp_config, indent=2)
        mcp_setup = ExecInput(
            command=f"mkdir -p $CLAUDE_CONFIG_DIR && cat > $CLAUDE_CONFIG_DIR/mcp.json << 'MCPEOF'\n{mcp_config_json}\nMCPEOF",
            env={"CLAUDE_CONFIG_DIR": (EnvironmentPaths.agent_dir / "sessions").as_posix()},
        )
        
        # Insert MCP setup before the claude command
        result = []
        for i, cmd in enumerate(modified_commands):
            if cmd.command and "claude " in cmd.command:
                result.append(mcp_setup)
            result.append(cmd)
        
        return result