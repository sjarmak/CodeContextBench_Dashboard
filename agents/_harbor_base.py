"""Stub Harbor base classes for development.

These provide the interface that BasePatchAgent expects from Harbor framework.
In production, these should be replaced with actual harbor.agents.installed.base imports.

This allows agents to be tested and developed before Harbor infrastructure is set up.
"""

from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class ExecInput:
    """Command execution input for Harbor."""
    command: str
    env: Optional[Dict[str, str]] = None
    timeout_sec: Optional[int] = None


class AgentContext:
    """Context for agent execution (Harbor stub)."""
    pass


class BaseInstalledAgent:
    """Base class for installed agents (Harbor stub)."""
    
    def populate_context_post_run(self, context: AgentContext) -> None:
        """Populate context after execution."""
        pass
