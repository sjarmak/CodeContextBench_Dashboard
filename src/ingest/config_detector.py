"""
Detect agent configuration (Baseline/MCP-Base/MCP-Full) from trial directory.

Detection strategy:
1. Parse .mcp.json in {trial}/agent/.mcp.json or {trial}/agent/sessions/.mcp.json
2. Fall back to folder name convention (baseline/, deepsearch/, sourcegraph/)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class AgentConfig(str, Enum):
    """Agent MCP configuration type."""

    BASELINE = "BASELINE"
    MCP_BASE = "MCP_BASE"
    MCP_FULL = "MCP_FULL"


@dataclass(frozen=True)
class AgentConfigResult:
    """Immutable result of agent config detection."""

    config: AgentConfig
    source: str  # "mcp_json" or "folder_name"
    mcp_json_path: str | None = None


_MCP_JSON_LOCATIONS = (
    "agent/.mcp.json",
    "agent/sessions/.mcp.json",
)

_FOLDER_NAME_MAP: dict[str, AgentConfig] = {
    "baseline": AgentConfig.BASELINE,
    "deepsearch": AgentConfig.MCP_FULL,
    "sourcegraph": AgentConfig.MCP_BASE,
    "sourcegraph_hybrid": AgentConfig.MCP_BASE,
}


def _classify_mcp_json(data: dict) -> AgentConfig:
    """Classify AgentConfig from parsed .mcp.json content.

    Rules:
    - No mcpServers or empty servers -> BASELINE
    - Has server with 'deepsearch' in URL -> MCP_FULL
    - Has sourcegraph server without deepsearch -> MCP_BASE
    """
    servers = data.get("mcpServers")
    if not servers:
        return AgentConfig.BASELINE

    for server_name, server_config in servers.items():
        url = ""
        if isinstance(server_config, dict):
            url = server_config.get("url", "")
        if "deepsearch" in url.lower() or "deepsearch" in server_name.lower():
            return AgentConfig.MCP_FULL

    # Has servers but no deepsearch -> MCP_BASE
    return AgentConfig.MCP_BASE


def _detect_from_folder_name(trial_dir: Path) -> AgentConfig | None:
    """Infer config from parent directory naming convention.

    Walks up from trial dir looking for known folder names like
    baseline/, deepsearch/, sourcegraph/, sourcegraph_hybrid/.
    """
    for parent in (trial_dir, *trial_dir.parents):
        name = parent.name.lower()
        if name in _FOLDER_NAME_MAP:
            return _FOLDER_NAME_MAP[name]
    return None


def detect_agent_config(trial_dir: Path) -> AgentConfig:
    """Detect agent configuration from a trial directory.

    Args:
        trial_dir: Path to a trial directory containing agent/ subfolder.

    Returns:
        Detected AgentConfig enum value.
    """
    result = detect_agent_config_detailed(trial_dir)
    return result.config


def detect_agent_config_detailed(trial_dir: Path) -> AgentConfigResult:
    """Detect agent configuration with full detection metadata.

    Args:
        trial_dir: Path to a trial directory containing agent/ subfolder.

    Returns:
        AgentConfigResult with config type, detection source, and file path.
    """
    # Strategy 1: Parse .mcp.json
    for rel_path in _MCP_JSON_LOCATIONS:
        mcp_path = trial_dir / rel_path
        if mcp_path.is_file():
            try:
                data = json.loads(mcp_path.read_text(encoding="utf-8"))
                config = _classify_mcp_json(data)
                return AgentConfigResult(
                    config=config,
                    source="mcp_json",
                    mcp_json_path=str(mcp_path),
                )
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Malformed .mcp.json at %s: %s", mcp_path, exc)
                continue

    # Strategy 2: Folder name convention
    folder_config = _detect_from_folder_name(trial_dir)
    if folder_config is not None:
        return AgentConfigResult(config=folder_config, source="folder_name")

    # Default: assume baseline if no MCP evidence found
    logger.info("No MCP config detected for %s, defaulting to BASELINE", trial_dir)
    return AgentConfigResult(config=AgentConfig.BASELINE, source="folder_name")
