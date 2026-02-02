"""
Ingestion pipeline for parsing and storing Harbor evaluation results and transcripts.

Provides:
- HarborResultParser: Parse Harbor result.json files
- TranscriptParser: Extract tool usage from agent transcripts
- TrajectoryParser: Extract per-tool token usage from trajectory.json (ATIF format)
- MetricsDatabase: SQLite storage for metrics
- IngestionOrchestrator: Orchestrate full pipeline
- AgentConfig / detect_agent_config: Auto-detect MCP configuration from trial dirs
"""

from .config_detector import AgentConfig, AgentConfigResult, detect_agent_config
from .harbor_parser import HarborResult, HarborResultParser
from .transcript_parser import TranscriptMetrics, TranscriptParser, AgentToolProfile
from .trajectory_parser import TrajectoryMetrics, TrajectoryParser
from .database import MetricsDatabase
from .orchestrator import IngestionOrchestrator

__all__ = [
    "AgentConfig",
    "AgentConfigResult",
    "detect_agent_config",
    "HarborResult",
    "HarborResultParser",
    "TranscriptMetrics",
    "TranscriptParser",
    "AgentToolProfile",
    "TrajectoryMetrics",
    "TrajectoryParser",
    "MetricsDatabase",
    "IngestionOrchestrator",
]
