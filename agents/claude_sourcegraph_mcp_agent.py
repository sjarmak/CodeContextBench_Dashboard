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
        Override to enable implementation mode with full tool access.
        
        This modifies the Claude Code command to:
        1. Add autonomous environment variables (FORCE_AUTO_BACKGROUND_TASKS, ENABLE_BACKGROUND_TASKS)
        2. Use --permission-mode acceptEdits to enable file modifications
        3. Explicitly whitelist all necessary tools (Read, Edit, Write, Bash, Grep, Glob)
        4. Configure Sourcegraph MCP for deep search capabilities
        
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
                
                self.logger.info(f"Modified command for implementation mode with tool whitelist")
                self.logger.info(f"Tools enabled: {allowed_tools}")
                self.logger.info(f"Autonomous mode enabled: FORCE_AUTO_BACKGROUND_TASKS=1, ENABLE_BACKGROUND_TASKS=1")
                result.append(
                    ExecInput(command=modified_command, env=env_with_autonomous)
                )
            else:
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

            # Try to read CLAUDE.md from benchmark directory and inject MCP guidance
            # This allows task suites to provide specific search strategy guidance
            claude_md_content = "# Sourcegraph MCP Available\n\nYou have access to **Sourcegraph MCP** via the Sourcegraph server. Use it to understand the codebase.\n"
            
            # Try to find and read benchmark CLAUDE.md
            benchmark_dir = Path.cwd() / "benchmarks"
            if benchmark_dir.exists():
                # Look for CLAUDE.md in parent benchmark dirs (e.g., benchmarks/big_code_mcp/CLAUDE.md)
                for claude_path in benchmark_dir.rglob("CLAUDE.md"):
                    try:
                        with open(claude_path, "r") as f:
                            content = f.read()
                            if content.strip():
                                self.logger.info(f"✓ Found benchmark guidance: {claude_path.relative_to(Path.cwd())}")
                                claude_md_content = content
                                break
                    except Exception as e:
                        self.logger.debug(f"Could not read {claude_path}: {e}")

            instructions_path = self.logs_dir / "CLAUDE.md"
            with open(instructions_path, "w") as f:
                f.write(claude_md_content)

            # Upload CLAUDE.md to project root
            await environment.upload_file(
                source_path=instructions_path,
                target_path="/workspace/CLAUDE.md"
            )

            self.logger.info(f"✓ Created CLAUDE.md with task-specific search strategy guidance")
        else:
            self.logger.warning(
                "⚠ Sourcegraph MCP not configured. Set SOURCEGRAPH_URL "
                "and SOURCEGRAPH_ACCESS_TOKEN environment variables."
            )
        
        # Run standard Claude Code setup
        await super().setup(environment)
