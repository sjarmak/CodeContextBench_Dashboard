"""Claude Code with Sourcegraph MCP server integration.

Extends ClaudeCodeAgent to add Model Context Protocol (MCP) server support for:
- Sourcegraph code search capabilities
- MCP server configuration and connection
- Automatic context gathering from Sourcegraph repositories
- Enhanced code understanding through Deep Search APIs

MCP configuration is handled via environment variables that are read at runtime,
with .mcp.json generated in the workspace before Claude Code execution.
"""

import json
import os
import shlex
from pathlib import Path
from typing import Dict, List

from .claude_agent import ClaudeCodeAgent
from ._harbor_base import ExecInput


# MCP guidance to prepend to all instructions
MCP_GUIDANCE = """You have access to Sourcegraph via Model Context Protocol (MCP).

USE THE MCP TOOLS TO UNDERSTAND THE CODEBASE:
1. Use available tools to search for function definitions, class implementations, and usage patterns
2. Find test files and understand how the code is tested
3. Understand the module relationships and dependencies
4. Make targeted, informed code changes based on this understanding

This deep codebase understanding will help you:
- Make accurate, well-targeted changes
- Avoid regressions
- Write code consistent with the existing patterns
- Understand the test infrastructure

Example search queries:
- "Find the definition of [function_name] and show how it's used"
- "What modules import [module_name]?"
- "Find all test files for [module_name]"
- "Where is [constant_name] defined and what references it?"

---

"""


class ClaudeCodeSourcegraphMCPAgent(ClaudeCodeAgent):
    """Claude Code with Sourcegraph MCP server for code intelligence.
    
    Inherits baseline Claude Code functionality and adds:
    - Sourcegraph MCP server configuration via .mcp.json
    - SOURCEGRAPH_ACCESS_TOKEN authentication
    - Integration with Sourcegraph Deep Search APIs via MCP
    
    MCP configuration is generated at runtime using environment variables:
    - SOURCEGRAPH_ACCESS_TOKEN: API token for authentication
    - SOURCEGRAPH_MCP_URL: URL of MCP endpoint (defaults to cloud)
    
    Before Claude Code execution, .mcp.json is created in /workspace with
    the configured credentials, which Claude Code auto-discovers on startup.
    """
    
    def name(self) -> str:
        """Agent name for Harbor framework.
        
        Returns:
            "claude-code-sourcegraph-mcp"
        """
        return "claude-code-sourcegraph-mcp"
    
    def get_agent_command(self, instruction: str, repo_dir: str) -> str:
        """Generate Claude Code CLI command with MCP guidance and configuration.
        
        Prepends MCP usage guidance to the instruction so Claude Code
        knows to use Sourcegraph Deep Search for code understanding.
        Expects .mcp.json to already be created in the workspace by
        create_run_agent_commands().
        
        Args:
            instruction: The task instruction/prompt for Claude Code
            repo_dir: Path to repository (literal path or shell variable)
            
        Returns:
            Shell command string to execute Claude Code with MCP guidance
        """
        # Prepend MCP guidance to instruction
        enhanced_instruction = MCP_GUIDANCE + instruction
        
        # Don't quote repo_dir if it's a shell variable
        if repo_dir.startswith('$'):
            repo_path = repo_dir
        else:
            repo_path = shlex.quote(repo_dir)
        
        # Quote the instruction for safe shell execution
        escaped_instruction = shlex.quote(enhanced_instruction)
        
        # Claude Code in print mode with JSON output
        # Claude auto-discovers .mcp.json in /workspace
        # MCP config populated from SOURCEGRAPH_MCP_URL and SOURCEGRAPH_ACCESS_TOKEN
        return (
            f'export HOME=/root && cd {repo_path} && '
            f'claude -p '
            f'--output-format json '
            f'{escaped_instruction} '
            '2>&1 | tee /logs/agent/claude.txt'
        )
    
    def get_agent_env(self) -> Dict[str, str]:
        """Get environment variables for Claude Code with Sourcegraph MCP.
        
        Adds Sourcegraph credentials and MCP configuration to the base Claude environment:
        - ANTHROPIC_API_KEY: Claude API key for authentication
        - SOURCEGRAPH_ACCESS_TOKEN: Sourcegraph API token for MCP
        - SOURCEGRAPH_MCP_URL: URL of Sourcegraph MCP endpoint
        
        Returns:
            Dictionary with API keys and Sourcegraph MCP configuration
            
        Raises:
            ValueError: If required environment variables not set
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable must be set")
        
        src_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN")
        if not src_token:
            raise ValueError(
                "SOURCEGRAPH_ACCESS_TOKEN environment variable must be set for Sourcegraph MCP. "
                "Get a token from https://sourcegraph.sourcegraph.com/user/settings/tokens"
            )
        
        return {
            "ANTHROPIC_API_KEY": api_key,
            "SOURCEGRAPH_ACCESS_TOKEN": src_token,
            "SOURCEGRAPH_MCP_URL": os.environ.get(
                "SOURCEGRAPH_MCP_URL",
                "https://sourcegraph.sourcegraph.com/.api/mcp/v1"
            ),
        }
    
    def create_run_agent_commands(self, instruction: str) -> List[ExecInput]:
        """Create commands to run MCP-enabled agent and capture git diff.
        
        Extends the base implementation to:
        1. Create .mcp.json configuration before Claude Code execution
        2. Run agent with MCP guidance
        3. Capture git diff as normal
        
        Args:
            instruction: The task instruction to pass to the agent
            
        Returns:
            List of ExecInput commands for Harbor to execute
        """
        # Get base commands from parent class
        base_commands = super().create_run_agent_commands(instruction)
        
        if not base_commands:
            return base_commands
        
        # Get the main command (should be only one)
        main_cmd = base_commands[0]
        
        # Create MCP config setup script
        mcp_setup_script = self._create_mcp_setup_script()
        
        # Prepend MCP setup to the command
        updated_command = mcp_setup_script + "\n" + main_cmd.command
        
        return [
            ExecInput(
                command=updated_command,
                env=main_cmd.env,
                timeout_sec=main_cmd.timeout_sec,
            )
        ]
    
    def _create_mcp_setup_script(self) -> str:
        """Create shell script to write .mcp.json configuration.
        
        Returns:
            Shell script that creates .mcp.json in /workspace with Sourcegraph
            credentials from environment variables
        """
        return '''
# Create .mcp.json configuration for Sourcegraph MCP
MCP_URL="${SOURCEGRAPH_MCP_URL:-https://sourcegraph.sourcegraph.com/.api/mcp/v1}"
MCP_TOKEN="${SOURCEGRAPH_ACCESS_TOKEN:-}"

if [ -z "$MCP_TOKEN" ]; then
    echo "⚠️  Warning: SOURCEGRAPH_ACCESS_TOKEN not set - MCP disabled"
else
    mkdir -p /workspace
    cat > /workspace/.mcp.json << EOF
{
  "mcpServers": {
    "sourcegraph": {
      "type": "http",
      "url": "$MCP_URL",
      "headers": {
        "Authorization": "token $MCP_TOKEN"
      }
    }
  }
}
EOF
    echo "✓ Created /workspace/.mcp.json for Sourcegraph MCP"
fi
'''
    
    @property
    def _install_agent_template_path(self) -> Path:
        """Path to MCP-enabled Claude Code installation template.
        
        Can use the same base Claude installation template, as MCP
        configuration is handled at runtime via environment variables.
        
        Returns:
            Path to agents/install-claude.sh.j2 Jinja2 template
        """
        return Path(__file__).parent / "install-claude.sh.j2"
