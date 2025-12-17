#!/usr/bin/env python3
"""Parse NeMo-Agent-Toolkit structured traces for execution metrics.

NeMo traces provide granular execution data:
- Per-tool latency and token counts
- Failed tool calls with error details
- Operation timeline with dependencies
- Overall workflow metrics

This module extracts structured data from NeMo trace JSON output.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import statistics


@dataclass
class ToolCallMetrics:
    """Metrics from a single tool invocation."""
    tool_name: str
    invocation_id: str
    duration_sec: float
    input_tokens: int = 0
    output_tokens: int = 0
    success: bool = True
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class NeMoExecutionTrace:
    """Complete execution trace from NeMo Agent Toolkit."""
    workflow_name: str
    start_time: datetime
    end_time: Optional[datetime]
    total_duration_sec: float
    tool_calls: List[ToolCallMetrics] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    success: bool = True
    error_type: Optional[str] = None
    raw_trace: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens
    
    @property
    def tool_call_count(self) -> int:
        return len(self.tool_calls)
    
    @property
    def failed_tool_calls(self) -> List[ToolCallMetrics]:
        return [tc for tc in self.tool_calls if not tc.success]
    
    @property
    def unique_tools(self) -> List[str]:
        return list(set(tc.tool_name for tc in self.tool_calls))
    
    @property
    def tool_call_count_by_tool(self) -> Dict[str, int]:
        """Count tool calls grouped by tool name."""
        counts: Dict[str, int] = {}
        for tc in self.tool_calls:
            counts[tc.tool_name] = counts.get(tc.tool_name, 0) + 1
        return counts
    
    @property
    def avg_tool_latency_sec(self) -> float:
        if not self.tool_calls:
            return 0.0
        return statistics.mean(tc.duration_sec for tc in self.tool_calls)
    
    @property
    def tool_latency_by_tool(self) -> Dict[str, float]:
        """Average latency per tool."""
        by_tool: Dict[str, List[float]] = {}
        for tc in self.tool_calls:
            if tc.tool_name not in by_tool:
                by_tool[tc.tool_name] = []
            by_tool[tc.tool_name].append(tc.duration_sec)
        
        return {
            tool: statistics.mean(latencies)
            for tool, latencies in by_tool.items()
        }
    
    @property
    def token_count_by_tool(self) -> Dict[str, Dict[str, int]]:
        """Token counts grouped by tool."""
        by_tool: Dict[str, Dict[str, int]] = {}
        for tc in self.tool_calls:
            if tc.tool_name not in by_tool:
                by_tool[tc.tool_name] = {'input_tokens': 0, 'output_tokens': 0}
            by_tool[tc.tool_name]['input_tokens'] += tc.input_tokens
            by_tool[tc.tool_name]['output_tokens'] += tc.output_tokens
        
        return by_tool
    
    @property
    def failure_rate(self) -> float:
        """Percentage of tool calls that failed."""
        if not self.tool_calls:
            return 0.0
        failed = len(self.failed_tool_calls)
        return (failed / self.tool_call_count) * 100.0
    
    @property
    def failure_rate_by_tool(self) -> Dict[str, float]:
        """Failure rate per tool."""
        counts_by_tool = self.tool_call_count_by_tool
        failures_by_tool: Dict[str, int] = {}
        
        for tc in self.failed_tool_calls:
            failures_by_tool[tc.tool_name] = failures_by_tool.get(tc.tool_name, 0) + 1
        
        return {
            tool: (failures_by_tool.get(tool, 0) / counts_by_tool[tool]) * 100.0
            for tool in counts_by_tool
        }


class NeMoTraceParser:
    """Parse NeMo-Agent-Toolkit trace output."""
    
    @staticmethod
    def parse_trace_file(trace_path: Path) -> Optional[NeMoExecutionTrace]:
        """Parse a NeMo trace JSON file.
        
        Args:
            trace_path: Path to NeMo trace JSON file
            
        Returns:
            NeMoExecutionTrace object, or None if parsing fails
        """
        if not trace_path.exists():
            return None
        
        try:
            with open(trace_path) as f:
                data = json.load(f)
            return NeMoTraceParser._parse_trace_data(data)
        except Exception:
            return None
    
    @staticmethod
    def _parse_trace_data(data: Dict[str, Any]) -> NeMoExecutionTrace:
        """Parse NeMo trace data dictionary.
        
        NeMo traces typically have this structure:
        {
            "workflow_name": "...",
            "start_time": "2025-12-17T16:00:00.000Z",
            "end_time": "2025-12-17T16:00:15.000Z",
            "duration_sec": 15.0,
            "tool_calls": [
                {
                    "tool_name": "sourcegraph_search",
                    "invocation_id": "tc_001",
                    "duration_sec": 2.5,
                    "input_tokens": 100,
                    "output_tokens": 250,
                    "success": true
                },
                ...
            ],
            "total_input_tokens": 1234,
            "total_output_tokens": 5678,
            "success": true
        }
        """
        workflow_name = data.get('workflow_name', 'unknown')
        
        # Parse timestamps
        start_time_str = data.get('start_time')
        end_time_str = data.get('end_time')
        
        start_time = NeMoTraceParser._parse_timestamp(start_time_str) if start_time_str else datetime.now()
        end_time = NeMoTraceParser._parse_timestamp(end_time_str) if end_time_str else None
        
        total_duration = data.get('duration_sec', 0.0)
        
        # Parse tool calls
        tool_calls = []
        tool_calls_data = data.get('tool_calls', [])
        
        for tc_data in tool_calls_data:
            tool_call = NeMoTraceParser._parse_tool_call(tc_data)
            if tool_call:
                tool_calls.append(tool_call)
        
        # Token totals
        total_input_tokens = data.get('total_input_tokens', 0)
        total_output_tokens = data.get('total_output_tokens', 0)
        
        # Compute totals from tool calls if not provided
        if not total_input_tokens and tool_calls:
            total_input_tokens = sum(tc.input_tokens for tc in tool_calls)
        if not total_output_tokens and tool_calls:
            total_output_tokens = sum(tc.output_tokens for tc in tool_calls)
        
        success = data.get('success', True)
        error_type = data.get('error_type')
        
        return NeMoExecutionTrace(
            workflow_name=workflow_name,
            start_time=start_time,
            end_time=end_time,
            total_duration_sec=total_duration,
            tool_calls=tool_calls,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            success=success,
            error_type=error_type,
            raw_trace=data
        )
    
    @staticmethod
    def _parse_tool_call(data: Dict[str, Any]) -> Optional[ToolCallMetrics]:
        """Parse a single tool call record."""
        try:
            tool_name = data.get('tool_name', 'unknown')
            invocation_id = data.get('invocation_id', '')
            duration_sec = float(data.get('duration_sec', 0.0))
            input_tokens = int(data.get('input_tokens', 0))
            output_tokens = int(data.get('output_tokens', 0))
            success = data.get('success', True)
            error_type = data.get('error_type')
            error_message = data.get('error_message')
            
            timestamp_str = data.get('timestamp')
            timestamp = NeMoTraceParser._parse_timestamp(timestamp_str) if timestamp_str else None
            
            return ToolCallMetrics(
                tool_name=tool_name,
                invocation_id=invocation_id,
                duration_sec=duration_sec,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                success=success,
                error_type=error_type,
                error_message=error_message,
                timestamp=timestamp
            )
        except Exception:
            return None
    
    @staticmethod
    def _parse_timestamp(timestamp_str: str) -> Optional[datetime]:
        """Parse ISO 8601 timestamp."""
        try:
            # Handle both with and without 'Z' suffix
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            return datetime.fromisoformat(timestamp_str)
        except Exception:
            return None
    
    @staticmethod
    def extract_from_task_execution(task_dir: Path) -> Optional[NeMoExecutionTrace]:
        """Extract NeMo trace from a task execution directory.
        
        Searches for NeMo trace files in common locations:
        - logs/nemo/trace.json
        - logs/trace.json
        - nemo_trace.json
        
        Args:
            task_dir: Path to task execution directory
            
        Returns:
            NeMoExecutionTrace if found, None otherwise
        """
        trace_paths = [
            task_dir / 'logs' / 'nemo' / 'trace.json',
            task_dir / 'logs' / 'trace.json',
            task_dir / 'nemo_trace.json',
            task_dir / 'trace.json',
        ]
        
        for trace_path in trace_paths:
            if trace_path.exists():
                trace = NeMoTraceParser.parse_trace_file(trace_path)
                if trace:
                    return trace
        
        return None
    
    @staticmethod
    def extract_from_all_traces(job_dir: Path) -> Dict[str, NeMoExecutionTrace]:
        """Extract all NeMo traces from a job directory.
        
        Args:
            job_dir: Job directory containing traces
            
        Returns:
            Dictionary mapping task IDs to their traces
        """
        traces: Dict[str, NeMoExecutionTrace] = {}
        
        logs_dir = job_dir / 'logs'
        if not logs_dir.exists():
            return traces
        
        # Find all trace.json files
        for trace_file in logs_dir.rglob('trace.json'):
            trace = NeMoTraceParser.parse_trace_file(trace_file)
            if trace:
                # Use relative path as key
                key = str(trace_file.relative_to(logs_dir))
                traces[key] = trace
        
        return traces


class NeMoMetricsExtractor:
    """Extract structured metrics from NeMo traces for manifests."""
    
    @staticmethod
    def extract_tool_profile(trace: NeMoExecutionTrace) -> Dict[str, Any]:
        """Extract tool profile metrics from trace.
        
        Returns a structure compatible with ManifestWriter tool_profile.
        """
        tool_usage = {}
        
        for tool_name in trace.unique_tools:
            # Count calls for this tool
            calls_for_tool = [tc for tc in trace.tool_calls if tc.tool_name == tool_name]
            success_count = sum(1 for tc in calls_for_tool if tc.success)
            failure_count = len(calls_for_tool) - success_count
            
            # Latency
            latencies = [tc.duration_sec for tc in calls_for_tool]
            avg_latency = statistics.mean(latencies) if latencies else 0.0
            
            # Tokens
            tokens = trace.token_count_by_tool.get(tool_name, {})
            
            tool_usage[tool_name] = {
                'tool_name': tool_name,
                'category': NeMoMetricsExtractor._classify_tool(tool_name),
                'invocation_count': len(calls_for_tool),
                'success_count': success_count,
                'failure_count': failure_count,
                'avg_duration_sec': avg_latency,
                'input_tokens': tokens.get('input_tokens', 0),
                'output_tokens': tokens.get('output_tokens', 0),
            }
        
        return {
            'tool_usage': tool_usage,
            'total_tool_invocations': trace.tool_call_count,
            'total_unique_tools': len(trace.unique_tools),
            'failed_tool_calls': len(trace.failed_tool_calls),
            'failure_rate_percent': trace.failure_rate,
            'total_input_tokens': trace.total_input_tokens,
            'total_output_tokens': trace.total_output_tokens,
            'total_tokens': trace.total_tokens,
            'avg_tool_latency_sec': trace.avg_tool_latency_sec,
        }
    
    @staticmethod
    def _classify_tool(tool_name: str) -> str:
        """Classify a tool by category."""
        lower_name = tool_name.lower()
        
        if 'search' in lower_name or 'sourcegraph' in lower_name:
            return 'code_search'
        elif any(op in lower_name for op in ['grep', 'cat', 'find', 'read', 'file']):
            return 'file_operation'
        elif any(op in lower_name for op in ['git', 'patch', 'write', 'edit']):
            return 'code_generation'
        elif 'test' in lower_name or 'run' in lower_name or 'exec' in lower_name:
            return 'verification'
        else:
            return 'other'
    
    @staticmethod
    def extract_failure_analysis(trace: NeMoExecutionTrace) -> Dict[str, Any]:
        """Extract failure analysis from trace."""
        failure_by_type: Dict[str, int] = {}
        failure_by_tool: Dict[str, int] = {}
        
        for tc in trace.failed_tool_calls:
            if tc.error_type:
                failure_by_type[tc.error_type] = failure_by_type.get(tc.error_type, 0) + 1
            failure_by_tool[tc.tool_name] = failure_by_tool.get(tc.tool_name, 0) + 1
        
        return {
            'total_failures': len(trace.failed_tool_calls),
            'failure_rate_percent': trace.failure_rate,
            'failures_by_type': failure_by_type,
            'failures_by_tool': failure_by_tool,
            'failure_rate_by_tool': trace.failure_rate_by_tool,
        }
