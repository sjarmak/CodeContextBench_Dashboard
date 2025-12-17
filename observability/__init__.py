"""Observability and metrics collection.

Provides lightweight JSON-based observability for benchmark executions.
Captures tool usage, execution metrics, and performance analysis without
heavy dependencies like NeMo.

Main exports:
- ManifestWriter: Write run_manifest.json from Harbor benchmark runs
- MetricsCollector: Collect and analyze execution metrics
"""

from .manifest_writer import ManifestWriter, ToolProfile, ToolUsage
from .metrics_collector import MetricsCollector, ExecutionMetrics

__all__ = [
    'ManifestWriter',
    'ToolProfile',
    'ToolUsage',
    'MetricsCollector',
    'ExecutionMetrics',
]
