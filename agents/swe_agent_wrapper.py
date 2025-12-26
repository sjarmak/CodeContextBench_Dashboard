"""
SWE-agent wrapper for Harbor integration.

This module provides a Harbor-compatible agent that wraps SWE-agent
for use as a baseline on SWE-bench Pro tasks, optionally with
Sourcegraph MCP tools.

SWE-agent: https://github.com/scaleapi/SWE-bench_Pro-os/tree/main/SWE-agent
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

# Try to import Harbor agent base if available
try:
    from harbor.agents.base import BaseAgent
except ImportError:
    # Fallback for standalone usage
    class BaseAgent:
        """Stub base agent for standalone usage."""
        pass


class SWEAgentWrapper(BaseAgent):
    """
    Harbor-compatible wrapper for SWE-agent.
    
    This agent delegates to SWE-agent for solving SWE-bench tasks
    while optionally integrating Sourcegraph MCP tools for
    enhanced code understanding.
    
    Configuration:
        - SWE_AGENT_PATH: Path to SWE-agent installation
        - SOURCEGRAPH_ACCESS_TOKEN: For MCP integration (optional)
        - SOURCEGRAPH_URL: For MCP integration (optional)
    """
    
    def __init__(
        self,
        model: str = "claude-sonnet-4-5-20250929",
        swe_agent_path: Optional[str] = None,
        enable_mcp: bool = True,
        max_turns: int = 100,
        **kwargs: Any,
    ) -> None:
        self.model = model
        self.swe_agent_path = swe_agent_path or os.environ.get(
            "SWE_AGENT_PATH",
            os.path.expanduser("~/SWE-bench_Pro-os/SWE-agent")
        )
        self.enable_mcp = enable_mcp
        self.max_turns = max_turns
        self.extra_kwargs = kwargs
    
    def _setup_mcp_config(self) -> Optional[Path]:
        """Create MCP configuration file if credentials are available."""
        if not self.enable_mcp:
            return None
        
        token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN")
        url = os.environ.get("SOURCEGRAPH_URL")
        
        if not token or not url:
            return None
        
        config = {
            "mcpServers": {
                "sourcegraph": {
                    "command": "npx",
                    "args": ["-y", "@sourcegraph/mcp-server"],
                    "env": {
                        "SRC_ACCESS_TOKEN": token,
                        "SOURCEGRAPH_URL": url
                    }
                }
            }
        }
        
        # Write to temp file
        import json
        config_path = Path(tempfile.gettempdir()) / "mcp_config.json"
        config_path.write_text(json.dumps(config, indent=2))
        return config_path
    
    def run(
        self,
        task_dir: str,
        problem_statement: str,
        repo_path: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Run SWE-agent on a task.
        
        Args:
            task_dir: Path to Harbor task directory
            problem_statement: The issue description
            repo_path: Path to the repository
            **kwargs: Additional arguments
        
        Returns:
            Dict with 'patch' and 'success' keys
        """
        # Setup MCP if available
        mcp_config = self._setup_mcp_config()
        
        # Prepare SWE-agent command
        cmd = [
            "python", "-m", "sweagent.run.run_single",
            "--model_name", self.model,
            "--data_path", task_dir,
            "--repo_path", repo_path,
            "--max_turns", str(self.max_turns),
        ]
        
        # Add MCP config if available
        if mcp_config:
            cmd.extend(["--mcp_config", str(mcp_config)])
        
        # Run SWE-agent
        try:
            result = subprocess.run(
                cmd,
                cwd=self.swe_agent_path,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )
            
            # Parse output for patch
            patch = self._extract_patch(result.stdout)
            
            return {
                "patch": patch,
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "patch": "",
                "success": False,
                "error": "Timeout",
            }
        except Exception as e:
            return {
                "patch": "",
                "success": False,
                "error": str(e),
            }
    
    def _extract_patch(self, output: str) -> str:
        """Extract git patch from SWE-agent output."""
        # Look for patch in output
        lines = output.split("\n")
        in_patch = False
        patch_lines: List[str] = []
        
        for line in lines:
            if line.startswith("diff --git"):
                in_patch = True
            if in_patch:
                patch_lines.append(line)
                if line.startswith("-- ") and patch_lines:
                    # End of patch block
                    break
        
        return "\n".join(patch_lines)


class SWEAgentMCPAgent(SWEAgentWrapper):
    """
    SWE-agent with Sourcegraph MCP integration enabled.
    
    This variant always enables MCP if credentials are available,
    providing the agent with Deep Search and code intelligence
    capabilities.
    """
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(enable_mcp=True, **kwargs)


class SWEAgentBaselineAgent(SWEAgentWrapper):
    """
    Pure SWE-agent baseline without MCP.
    
    This variant disables MCP to provide a baseline for
    comparison with MCP-enhanced versions.
    """
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(enable_mcp=False, **kwargs)


# Export agents for Harbor discovery
__all__ = [
    "SWEAgentWrapper",
    "SWEAgentMCPAgent", 
    "SWEAgentBaselineAgent",
]
