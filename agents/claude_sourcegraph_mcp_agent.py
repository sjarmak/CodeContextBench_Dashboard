"""Harbor-compatible Claude Code agent with Sourcegraph Deep Search MCP and implementation mode."""

import json
import os
from pathlib import Path
from typing import Any

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.base import ExecInput
from harbor.environments.base import BaseEnvironment
from harbor.models.trial.paths import EnvironmentPaths


class ClaudeCodeSourcegraphMCPAgent(ClaudeCode):
    """Claude Code with Sourcegraph Deep Search MCP and implementation mode enabled.
    
    Extends Harbor's built-in ClaudeCode agent to:
    1. Add Sourcegraph Deep Search via MCP (Model Context Protocol) server
    2. Enable implementation mode (exit read-only planning mode)
    
    Environment Variables (pass via harbor run --ek flags):
    - ANTHROPIC_API_KEY: Claude API key
    - SOURCEGRAPH_URL: Sourcegraph instance URL (e.g., https://sourcegraph.sourcegraph.com)
    - SOURCEGRAPH_ACCESS_TOKEN: Authentication token for Sourcegraph API

    The agent:
    - Creates .mcp.json configuration for Sourcegraph
    - Sends initial command to exit plan mode (enables actual code changes)
    - Credentials are injected by Harbor via --ek flags into the container environment
    - MCP server is configured to use HTTP transport via Sourcegraph's hosted MCP endpoint
    """

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        """
        Override to inject exit-plan-mode command and MCP configuration.
        
        This ensures Claude Code is in implementation mode (not read-only planning mode)
        and has Sourcegraph MCP configured.
        """
        import shlex
        
        # Get parent's commands
        parent_commands = super().create_run_agent_commands(instruction)
        
        # Get Sourcegraph credentials from environment
        sg_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN") or os.environ.get("SRC_ACCESS_TOKEN") or ""
        sg_url = os.environ.get("SOURCEGRAPH_URL") or os.environ.get("SRC_ENDPOINT") or "https://sourcegraph.sourcegraph.com"
        
        # Create MCP config if credentials available
        mcp_config = None
        if sg_token:
            # Ensure URL has protocol
            if not sg_url.startswith(('http://', 'https://')):
                sg_url = f"https://{sg_url}"
            sg_url = sg_url.rstrip('/')
            
            mcp_config = {
                "mcpServers": {
                    "sourcegraph": {
                        "type": "http",
                        "url": f"{sg_url}/.api/mcp/v1",
                        "headers": {
                            "Authorization": f"token {sg_token}"
                        }
                    }
                }
            }
        
        # Find the Claude execution command and inject exit-plan-mode
        result = []
        for cmd in parent_commands:
            if cmd.command and "claude " in cmd.command:
                # Inject exit plan mode command before the actual task
                # This tells Claude Code to exit planning mode and enable implementation
                exit_plan_mode_cmd = ExecInput(
                    command='echo "/ExitPlanMode" | claude --no-input',
                    env=cmd.env or {},
                )
                result.append(exit_plan_mode_cmd)
            
            result.append(cmd)
        
        return result
    
    async def _test_network_connectivity(self, environment: BaseEnvironment, sg_url: str) -> bool:
        """Test if container can reach Sourcegraph via HTTPS.
        
        Returns True if network test succeeds, False otherwise.
        Logs detailed diagnostic information for debugging.
        
        Note: Simplified version that creates a test script for Claude to run.
        The test is logged but not executed by the agent during setup.
        """
        self.logger.info(f"Preparing network connectivity test to {sg_url}...")
        
        # Create a test script that Claude can run if needed
        test_script = f"""#!/bin/bash
echo "=== Container Network Connectivity Test ==="
echo "Target: {sg_url}"
echo ""
echo "1. Testing HTTPS connectivity with curl:"
curl -v --max-time 10 {sg_url}/health 2>&1
echo ""
echo "Exit code: $?"
echo "=== Test Complete ==="
"""
        
        test_script_path = self.logs_dir / "network_test.sh"
        with open(test_script_path, "w") as f:
            f.write(test_script)
        
        # Upload test script for Claude to use if needed
        try:
            await environment.upload_file(
                source_path=test_script_path,
                target_path="/workspace/network_test.sh"
            )
            self.logger.info(f"✓ Network test script created: /workspace/network_test.sh")
            self.logger.info(f"  Claude can run it with: bash /workspace/network_test.sh")
            return True
        except Exception as e:
            self.logger.warning(f"⚠ Could not upload network test script: {e}")
            return False

    async def setup(self, environment: BaseEnvironment) -> None:
        """Setup Claude Code environment with Sourcegraph MCP.

        Creates .mcp.json for Sourcegraph configuration.
        API credentials are handled by Harbor normally.
        """

        # Get Sourcegraph credentials
        sg_url = os.environ.get("SOURCEGRAPH_URL") or os.environ.get("SRC_ENDPOINT") or ""
        sg_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN") or os.environ.get("SRC_ACCESS_TOKEN") or ""

        # Configure MCP if Sourcegraph credentials are available
        if sg_url and sg_token:
            # Ensure URL has protocol
            if not sg_url.startswith(('http://', 'https://')):
                sg_url = f"https://{sg_url}"

            # Ensure URL doesn't end with trailing slash
            sg_url = sg_url.rstrip('/')

            # Prepare network test script (but don't run it, just create it)
            await self._test_network_connectivity(environment, sg_url)

            # Create .mcp.json with Sourcegraph MCP configuration
            # Note: Sourcegraph MCP supports both "token" and "Bearer" schemes
            # "token ACCESSTOKEN" is for Sourcegraph API tokens
            # "Bearer ACCESSTOKEN" may also work depending on server config
            mcp_config = {
                "mcpServers": {
                    "sourcegraph": {
                        "type": "http",
                        "url": f"{sg_url}/.api/mcp/v1",
                        "headers": {
                            "Authorization": f"token {sg_token}"
                        }
                    }
                }
            }

            mcp_config_path = self.logs_dir / ".mcp.json"
            with open(mcp_config_path, "w") as f:
                json.dump(mcp_config, f, indent=2)

            # Upload .mcp.json to project root
            await environment.upload_file(
                source_path=mcp_config_path,
                target_path="/workspace/.mcp.json"
            )

            self.logger.info(f"✓ Created .mcp.json with Sourcegraph MCP configuration")

            # Create system_prompt.txt with mandatory requirement
            system_prompt = """You MUST complete this coding task by making actual code changes.

This is not a planning or analysis task. You are required to:
1. Understand the problem/bug/feature requirement
2. Locate the relevant code files
3. MAKE ACTUAL CODE CHANGES to implement the fix or feature
4. Test your implementation to ensure it works

Do not just analyze or plan the solution. You must write code and make modifications to actual files.

You have access to the following tools to complete this task:
- Read: read files
- Edit: edit files (use this to modify code)
- Write: create new files
- Bash: run commands including git operations
- Grep: search code
- Glob: find files

CRITICAL: You must make actual code modifications, not just analyze or plan. The task is complete only when code files have been changed and tests pass.
"""

            system_prompt_path = self.logs_dir / "system_prompt.txt"
            with open(system_prompt_path, "w") as f:
                f.write(system_prompt)

            # Upload system_prompt.txt to project root
            await environment.upload_file(
                source_path=system_prompt_path,
                target_path="/workspace/system_prompt.txt"
            )

            self.logger.info(f"✓ Created system_prompt.txt with mandatory code-change requirement")

            # Create CLAUDE.md with instructions for using Sourcegraph MCP
            claude_instructions = """# Sourcegraph MCP Available

You have access to **Sourcegraph MCP** via the Sourcegraph server. Use it to understand the codebase instead of relying on grep or manual file exploration.

## How to Use

When you need to understand code patterns, find relevant files, or explore the repository structure:
1. Use the Sourcegraph MCP tools to query the codebase intelligently
2. Ask questions about code patterns, dependencies, and implementations
3. Leverage Deep Search for complex queries across the entire codebase

## Available Tools

The Sourcegraph MCP server provides tools for:
- Searching and exploring code
- Understanding code structure and dependencies
- Finding usage patterns and implementations
- Analyzing code relationships

This is much more efficient than grep for understanding large codebases.

**IMPORTANT:** Remember you MUST make actual code changes to complete this task. See system_prompt.txt for details.
"""

            instructions_path = self.logs_dir / "CLAUDE.md"
            with open(instructions_path, "w") as f:
                f.write(claude_instructions)

            # Upload CLAUDE.md to project root
            await environment.upload_file(
                source_path=instructions_path,
                target_path="/workspace/CLAUDE.md"
            )

            self.logger.info(f"✓ Created CLAUDE.md with Sourcegraph MCP instructions")
        else:
            self.logger.warning(
                "⚠ Sourcegraph MCP not configured. Set SOURCEGRAPH_URL "
                "and SOURCEGRAPH_ACCESS_TOKEN environment variables."
            )
        
        # Run standard Claude Code setup
        await super().setup(environment)
