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
        
        Adds MCP configuration setup before running Claude.
        """
        import shlex
        
        # Get Sourcegraph credentials from environment
        src_token = os.environ.get("SRC_ACCESS_TOKEN", "")
        src_url = os.environ.get("SOURCEGRAPH_URL", "https://sourcegraph.sourcegraph.com")
        
        if not src_token:
            print("WARNING: SRC_ACCESS_TOKEN not set - MCP server will not work")
        
        # Build environment for Claude
        env = {
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
            "CLAUDE_CODE_OAUTH_TOKEN": os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", ""),
            "FORCE_AUTO_BACKGROUND_TASKS": "1",
            "ENABLE_BACKGROUND_TASKS": "1",
            "SRC_ACCESS_TOKEN": src_token,
            "SOURCEGRAPH_URL": src_url,
        }
        
        # Remove empty credentials
        env = {k: v for k, v in env.items() if v}
        
        if self.model_name:
            env["ANTHROPIC_MODEL"] = self.model_name.split("/")[-1]
        elif "ANTHROPIC_MODEL" in os.environ:
            env["ANTHROPIC_MODEL"] = os.environ["ANTHROPIC_MODEL"]
        
        if "MAX_THINKING_TOKENS" in os.environ:
            env["MAX_THINKING_TOKENS"] = os.environ["MAX_THINKING_TOKENS"]
        
        env["CLAUDE_CONFIG_DIR"] = (EnvironmentPaths.agent_dir / "sessions").as_posix()
        
        # MCP configuration
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
        escaped_instruction = shlex.quote(instruction)
        
        return [
            # Create config directories
            ExecInput(
                command=(
                    "mkdir -p $CLAUDE_CONFIG_DIR/debug $CLAUDE_CONFIG_DIR/projects/-app "
                    "$CLAUDE_CONFIG_DIR/shell-snapshots $CLAUDE_CONFIG_DIR/statsig "
                    "$CLAUDE_CONFIG_DIR/todos"
                ),
                env=env,
            ),
            # Write MCP configuration
            ExecInput(
                command=f"cat > $CLAUDE_CONFIG_DIR/mcp.json << 'MCPEOF'\n{mcp_config_json}\nMCPEOF",
                env=env,
            ),
            # Verify MCP config was created
            ExecInput(
                command="echo 'MCP config:' && cat $CLAUDE_CONFIG_DIR/mcp.json",
                env=env,
            ),
            # Run Claude with MCP enabled
            ExecInput(
                command=(
                    f"claude --verbose --output-format stream-json "
                    f"--mcp-config $CLAUDE_CONFIG_DIR/mcp.json "
                    f"-p {escaped_instruction} --allowedTools "
                    f"{' '.join(self.ALLOWED_TOOLS)} 2>&1 </dev/null | tee "
                    f"/logs/agent/claude-code.txt"
                ),
                env=env,
            )
        ]