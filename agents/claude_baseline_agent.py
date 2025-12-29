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
        # Include MCP tools for Sourcegraph integration (mcp__<server>__<tool>)
        base_tools = "Bash,Read,Edit,Write,Grep,Glob,Skill,TodoWrite,Task,TaskOutput"
        mcp_tools = "mcp__sourcegraph__sg_deepsearch,mcp__sourcegraph__sg_keyword_search,mcp__sourcegraph__sg_nls_search,mcp__sourcegraph__sg_read_file,mcp__deepsearch__deepsearch"
        allowed_tools = f"{base_tools},{mcp_tools}"
        
        # Check if MCP is configured
        mcp_type = os.environ.get("BASELINE_MCP_TYPE", "none").lower()
        mcp_config_flag = ""
        if mcp_type in ["sourcegraph", "deepsearch"]:
            mcp_config_flag = "--mcp-config /logs/agent/sessions/.mcp.json "

        # Modify the Claude command to enable implementation mode with full tool access
        result = []
        for cmd in parent_commands:
            if cmd.command and "claude " in cmd.command:
                # Inject --permission-mode, --allowedTools, and --mcp-config (if MCP enabled)
                # This enables actual code changes and ensures tools are available
                modified_command = cmd.command.replace(
                    "claude ",
                    f"claude --permission-mode acceptEdits {mcp_config_flag}--allowedTools {allowed_tools} "
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

        # Upload to CLAUDE_CONFIG_DIR (where Claude Code looks for MCP config)
        # Harbor sets CLAUDE_CONFIG_DIR=/logs/agent/sessions
        await environment.upload_file(
            source_path=mcp_config_path, target_path="/logs/agent/sessions/.mcp.json"
        )
        self.logger.info(f"BaselineClaudeCodeAgent: Sourcegraph MCP configured at /logs/agent/sessions/ ({sg_url})")

        # Upload CLAUDE.md with Sourcegraph instructions
        claude_md_content = """# MANDATORY: Use Sourcegraph MCP Tools

## YOU MUST USE MCP TOOLS BEFORE LOCAL TOOLS

You have Sourcegraph MCP configured. **Your first action should be an MCP tool call.**

## MCP Tool Names (use exactly these)

- `mcp__sourcegraph__sg_deepsearch` - **USE THIS FIRST** - Deep semantic search
- `mcp__sourcegraph__sg_keyword_search` - Exact string matching
- `mcp__sourcegraph__sg_nls_search` - Natural language search
- `mcp__sourcegraph__sg_read_file` - Read indexed file

## First Action

Before using Bash/Grep/Read, call:
```
mcp__sourcegraph__sg_deepsearch(query="<describe the issue>")
```

## Why MCP First?

The codebase is indexed in Sourcegraph. MCP tools provide:
- Full cross-file code understanding
- Semantic relationship awareness
- Faster navigation than local grep

Local tools (Grep, Glob, Read) should be used AFTER MCP identifies relevant files.
"""

        claude_md_path = self.logs_dir / "CLAUDE.md"
        with open(claude_md_path, "w") as f:
            f.write(claude_md_content)

        await environment.upload_file(
            source_path=claude_md_path, target_path="/testbed/CLAUDE.md"
        )
        self.logger.info("BaselineClaudeCodeAgent: Sourcegraph CLAUDE.md uploaded to /testbed")

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

        # Upload to CLAUDE_CONFIG_DIR (where Claude Code looks for MCP config)
        # Harbor sets CLAUDE_CONFIG_DIR=/logs/agent/sessions
        await environment.upload_file(
            source_path=mcp_config_path, target_path="/logs/agent/sessions/.mcp.json"
        )
        self.logger.info(f"BaselineClaudeCodeAgent: Deep Search MCP configured at /logs/agent/sessions/ ({deepsearch_url})")

        # Upload CLAUDE.md with Deep Search instructions
        claude_md_content = """# MANDATORY: Use Deep Search MCP Tool

## YOUR FIRST ACTION MUST BE A DEEP SEARCH CALL

You have Sourcegraph Deep Search MCP configured. **Call it before any local tools.**

## MCP Tool Name (use exactly this)

- `mcp__deepsearch__deepsearch` - **CALL THIS FIRST** - Deep semantic search

## First Action

Before using Bash/Grep/Read, you MUST call:
```
mcp__deepsearch__deepsearch(query="<describe the issue>")
```

Example:
```
mcp__deepsearch__deepsearch(query="TypeError combine_vars VarsWithSources dict")
```

## Why Deep Search First?

1. The codebase is fully indexed in Sourcegraph
2. Deep Search understands semantic code relationships
3. Local grep only does pattern matching
4. Deep Search finds the right code immediately

## FORBIDDEN First Actions

❌ `Bash("grep ...")` - Do NOT grep before Deep Search
❌ `Read("some/file.py")` - Do NOT read random files first
❌ Starting with local file exploration

## Correct Workflow

1. **FIRST**: `mcp__deepsearch__deepsearch(query="...")`
2. **THEN**: Read specific files from results
3. **THEN**: Make targeted code changes
"""

        claude_md_path = self.logs_dir / "CLAUDE.md"
        with open(claude_md_path, "w") as f:
            f.write(claude_md_content)

        await environment.upload_file(
            source_path=claude_md_path, target_path="/testbed/CLAUDE.md"
        )
        self.logger.info("BaselineClaudeCodeAgent: Deep Search CLAUDE.md uploaded to /testbed")
