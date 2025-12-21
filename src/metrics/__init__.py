"""
Enterprise Metrics Collection for AI Coding Agents

This module provides comprehensive metrics collection for evaluating AI coding agent
performance through an enterprise-informed lens.

Based on research from ENTERPRISE_CODEBASES.md:
- 58% of developer time on comprehension
- 35% on navigation/search
- 23min context switch recovery time
- Build/test feedback loop impact

Key components:
- EnterpriseMetricsCollector: Main metrics collection class
- Phase: Enum for activity categorization
- enterprise_metrics_schema.json: JSON schema for metrics format
"""

from .enterprise_collector import (
    EnterpriseMetricsCollector,
    Phase,
    ToolCategory,
    parse_timestamp,
    detect_bash_category
)

__all__ = [
    'EnterpriseMetricsCollector',
    'Phase',
    'ToolCategory',
    'parse_timestamp',
    'detect_bash_category',
]

__version__ = '1.0.0'
