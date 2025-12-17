"""Observability and metrics collection.

Provides lightweight JSON-based observability for benchmark executions.
Captures tool usage, execution metrics, and performance analysis with
support for structured NeMo-Agent-Toolkit traces.

Main exports:
- ManifestWriter: Write run_manifest.json from Harbor benchmark runs
- MetricsCollector: Collect and analyze execution metrics
- ClaudeOutputParser: Extract token usage from Claude CLI output (legacy)
- NeMoTraceParser: Parse NeMo-Agent-Toolkit structured execution traces
- NeMoMetricsExtractor: Extract metrics from NeMo traces for manifests
"""

from .manifest_writer import ManifestWriter, ToolProfile, ToolUsage
from .metrics_collector import MetricsCollector, ExecutionMetrics
from .claude_output_parser import ClaudeOutputParser, ClaudeTokenUsage
from .nemo_trace_parser import (
    NeMoTraceParser,
    NeMoExecutionTrace,
    ToolCallMetrics,
    NeMoMetricsExtractor,
)

__all__ = [
    'ManifestWriter',
    'ToolProfile',
    'ToolUsage',
    'MetricsCollector',
    'ExecutionMetrics',
    'ClaudeOutputParser',
    'ClaudeTokenUsage',
    'NeMoTraceParser',
    'NeMoExecutionTrace',
    'ToolCallMetrics',
    'NeMoMetricsExtractor',
]
