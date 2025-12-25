"""Harbor-compatible Claude Code agent with autonomous implementation mode.

This agent extends Harbor's built-in ClaudeCode to inject autonomous environment
variables that enable headless/autonomous operation mode, where Claude Code
automatically implements code changes instead of entering interactive planning mode.

Supports optional MCP configuration:
- None: Pure baseline with no MCP
- Sourcegraph: Full Sourcegraph MCP with all tools (keyword, NLS, Deep Search)
- Deep Search: Deep Search-only MCP endpoint

Configuration via environment variable: BASELINE_MCP_TYPE (none|sourcegraph|deepsearch)
"""

import json
import os
from pathlib import Path

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.base import ExecInput
from harbor.environments.base import BaseEnvironment


class BaselineClaudeCodeAgent(ClaudeCode):
    """Claude Code with autonomous implementation mode and optional MCP.

    Extends Harbor's built-in ClaudeCode agent to:
    1. Enable autonomous/headless operation mode
    2. Use implementation-focused command-line flags
    3. Ensure agents make actual code changes instead of planning
    4. Optionally configure MCP (Sourcegraph or Deep Search)

    The autonomous environment variables are the critical control mechanism that
    makes Claude Code operate in implementation mode instead of planning/analysis mode.

    MCP Configuration (via BASELINE_MCP_TYPE environment variable):
    - "none" or unset: No MCP, pure baseline
    - "sourcegraph": Full Sourcegraph MCP with all tools
    - "deepsearch": Deep Search-only MCP endpoint
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

    async def setup(self, environment: BaseEnvironment) -> None:
        """Setup agent environment with optional MCP configuration."""
        mcp_type = os.environ.get("BASELINE_MCP_TYPE", "none").lower()

        if mcp_type == "sourcegraph":
            await self._setup_sourcegraph_mcp(environment)
        elif mcp_type == "deepsearch":
            await self._setup_deepsearch_mcp(environment)
        else:
            # Pure baseline - no MCP
            self.logger.info("BaselineClaudeCodeAgent: Pure baseline (no MCP)")

        await super().setup(environment)

    async def _setup_sourcegraph_mcp(self, environment: BaseEnvironment) -> None:
        """Configure Sourcegraph MCP with all tools (keyword, NLS, Deep Search)."""
        sg_url = os.environ.get("SOURCEGRAPH_URL") or os.environ.get("SRC_ENDPOINT") or ""
        sg_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN") or os.environ.get("SRC_ACCESS_TOKEN") or ""

        if not sg_url or not sg_token:
            self.logger.warning("Sourcegraph credentials not found. Skipping MCP setup.")
            return

        if not sg_url.startswith(("http://", "https://")):
            sg_url = f"https://{sg_url}"
        sg_url = sg_url.rstrip("/")

        # Full Sourcegraph MCP config
        mcp_config = {
            "mcpServers": {
                "sourcegraph": {
                    "type": "http",
                    "url": f"{sg_url}/.api/mcp/v1",
                    "headers": {"Authorization": f"token {sg_token}"},
                }
            }
        }

        mcp_config_path = self.logs_dir / ".mcp.json"
        with open(mcp_config_path, "w") as f:
            json.dump(mcp_config, f, indent=2)

        await environment.upload_file(
            source_path=mcp_config_path, target_path="/workspace/.mcp.json"
        )
        self.logger.info(f"BaselineClaudeCodeAgent: Sourcegraph MCP configured ({sg_url})")

        # Upload CLAUDE.md with Sourcegraph instructions
        claude_md_content = """# Sourcegraph MCP Tools

## Available Tools

You have access to Sourcegraph MCP with the following tools:

- `sg_keyword_search` - Fast exact string matching across the codebase
- `sg_nls_search` - Natural language semantic search
- `sg_deepsearch` - Deep semantic search with context understanding

## Usage Guidelines

Use the most appropriate tool for your task:
- Exact matches (function/class/variable names): `sg_keyword_search`
- Conceptual questions: `sg_nls_search`
- Understanding architecture and code relationships: `sg_deepsearch`

Local tools (Grep, Glob, Read) are available for file-specific operations.
"""

        claude_md_path = self.logs_dir / "CLAUDE.md"
        with open(claude_md_path, "w") as f:
            f.write(claude_md_content)

        await environment.upload_file(
            source_path=claude_md_path, target_path="/workspace/CLAUDE.md"
        )
        self.logger.info("BaselineClaudeCodeAgent: Sourcegraph CLAUDE.md uploaded")

    async def _setup_deepsearch_mcp(self, environment: BaseEnvironment) -> None:
        """Configure Deep Search-only MCP endpoint."""
        # Check for dedicated Deep Search endpoint first
        deepsearch_url = os.environ.get("DEEPSEARCH_MCP_URL") or ""
        deepsearch_token = os.environ.get("DEEPSEARCH_MCP_TOKEN") or ""

        # Fall back to Sourcegraph with Deep Search path
        if not deepsearch_url:
            sg_url = os.environ.get("SOURCEGRAPH_URL") or os.environ.get("SRC_ENDPOINT") or ""
            sg_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN") or os.environ.get("SRC_ACCESS_TOKEN") or ""

            if sg_url and sg_token:
                if not sg_url.startswith(("http://", "https://")):
                    sg_url = f"https://{sg_url}"
                deepsearch_url = sg_url.rstrip("/") + "/.api/mcp/deepsearch"
                deepsearch_token = sg_token

        if not deepsearch_url or not deepsearch_token:
            self.logger.warning("Deep Search credentials not found. Skipping MCP setup.")
            return

        if not deepsearch_url.startswith(("http://", "https://")):
            deepsearch_url = f"https://{deepsearch_url}"
        deepsearch_url = deepsearch_url.rstrip("/")

        # Deep Search MCP config
        mcp_config = {
            "mcpServers": {
                "deepsearch": {
                    "type": "http",
                    "url": deepsearch_url,
                    "headers": {"Authorization": f"token {deepsearch_token}"},
                }
            }
        }

        mcp_config_path = self.logs_dir / ".mcp.json"
        with open(mcp_config_path, "w") as f:
            json.dump(mcp_config, f, indent=2)

        await environment.upload_file(
            source_path=mcp_config_path, target_path="/workspace/.mcp.json"
        )
        self.logger.info(f"BaselineClaudeCodeAgent: Deep Search MCP configured ({deepsearch_url})")

        # Upload CLAUDE.md with Deep Search instructions
        claude_md_content = """# Sourcegraph Deep Search

## Available Tool

You have access to Sourcegraph Deep Search (`sg_deepsearch`) via MCP.

## What is Deep Search?

Deep Search is a powerful semantic search tool that understands code relationships,
architecture patterns, and cross-file dependencies.

## When to Use Deep Search

Use `sg_deepsearch` to:
- Understand code architecture and subsystem structure
- Find all usages and relationships of functions/classes
- Trace data flow across multiple files
- Discover code patterns and conventions
- Answer architectural questions

## Usage Pattern

```
1. Use Deep Search to understand the problem space
2. Identify relevant files and code locations
3. Read specific files with local Read tool
4. Make targeted code changes
```

Local tools (Grep, Glob, Read) are available for file-specific operations after
you've used Deep Search to understand the context.
"""

        claude_md_path = self.logs_dir / "CLAUDE.md"
        with open(claude_md_path, "w") as f:
            f.write(claude_md_content)

        await environment.upload_file(
            source_path=claude_md_path, target_path="/workspace/CLAUDE.md"
        )
        self.logger.info("BaselineClaudeCodeAgent: Deep Search CLAUDE.md uploaded")
