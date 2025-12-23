#!/usr/bin/env python3
"""Write execution manifests with harness, tool profile, and metrics.

This module captures execution traces and metrics from Harbor benchmark runs
without heavy observability dependencies. Generates run_manifest.json with
standardized fields for downstream analysis.

Designed to replace NeMo with lightweight JSON-based observability.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from collections import Counter


@dataclass
class TokenUsage:
    """Track token consumption for a model call."""
    input_tokens: int = 0
    output_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ToolUsage:
    """Track a single tool invocation."""
    tool_name: str
    category: str  # "code_search", "file_operation", "code_generation", "verification"
    invocation_count: int = 1
    success_count: int = 0
    failure_count: int = 0
    avg_duration_sec: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ToolProfile:
    """Aggregate tool usage across a benchmark run."""
    tool_usage: Dict[str, ToolUsage]
    total_tool_invocations: int = 0
    total_unique_tools: int = 0
    search_queries_count: int = 0
    file_operations_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, handling dataclass fields."""
        return {
            'tool_usage': {
                name: asdict(usage)
                for name, usage in self.tool_usage.items()
            },
            'total_tool_invocations': self.total_tool_invocations,
            'total_unique_tools': self.total_unique_tools,
            'search_queries_count': self.search_queries_count,
            'file_operations_count': self.file_operations_count,
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_tokens': self.total_tokens,
        }


class ManifestWriter:
    """Write execution manifests from Harbor benchmark runs."""

    MAX_QUERY_SAMPLES = 10
    MAX_FILE_SAMPLES = 10
    
    # Model pricing (cost per 1M tokens) - update as API prices change
    MODEL_PRICING = {
        'claude-haiku-4-5': {
            'input_cost_per_1m': 0.8,
            'output_cost_per_1m': 4.0,
        },
        'claude-sonnet-4-5': {
            'input_cost_per_1m': 3.0,
            'output_cost_per_1m': 15.0,
        },
        'claude-3-5-sonnet': {
            'input_cost_per_1m': 3.0,
            'output_cost_per_1m': 15.0,
        },
        'claude-3-opus': {
            'input_cost_per_1m': 15.0,
            'output_cost_per_1m': 75.0,
        },
        'claude-3-sonnet': {
            'input_cost_per_1m': 3.0,
            'output_cost_per_1m': 15.0,
        },
        'claude-3-haiku': {
            'input_cost_per_1m': 0.25,
            'output_cost_per_1m': 1.25,
        },
    }
    
    # Tool detection patterns (fallback for legacy logs)
    TOOL_PATTERNS = {
        'sourcegraph_deep_search': (
            r'(ds start|ds ask|sourcegraph.*deep.*search)',
            'code_search'
        ),
        'file_operations': (
            r'(cat |grep |ls |find |diff |patch)',
            'file_operation'
        ),
        'git_operations': (
            r'(git diff|git log|git status|git commit)',
            'code_generation'
        ),
        'agent_execution': (
            r'(harbor run|claude.*code|agent.*command)',
            'code_generation'
        ),
        'test_verification': (
            r'(test\.sh|pytest|npm test|validation)',
            'verification'
        ),
    }

    TOOL_CATEGORY_BY_NAME = {
        'Grep': 'code_search',
        'Glob': 'code_search',
        'Read': 'file_operation',
        'Write': 'code_generation',
        'Edit': 'code_generation',
        'MultiEdit': 'code_generation',
        'NotebookEdit': 'code_generation',
        'TodoWrite': 'planning',
        'Task': 'planning',
        'TaskOutput': 'planning',
        'Skill': 'planning',
        'Bash': 'shell',
    }
    
    def __init__(self, job_dir: Path, model: str = 'claude-haiku-4-5'):
        """Initialize manifest writer for a Harbor job directory.
        
        Args:
            job_dir: Path to Harbor job output directory
            model: Model name for pricing calculation (default: claude-3-5-sonnet)
        """
        self.job_dir = Path(job_dir)
        self.result_file = self.job_dir / 'result.json'
        self.logs_dir = self.job_dir / 'logs'
        self.artifact_dir = self.job_dir / 'artifacts'
        self.model = model
    
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD for token usage.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Cost in USD
        """
        pricing = self.MODEL_PRICING.get(self.model, self.MODEL_PRICING['claude-haiku-4-5'])
        
        input_cost = (input_tokens / 1_000_000) * pricing['input_cost_per_1m']
        output_cost = (output_tokens / 1_000_000) * pricing['output_cost_per_1m']
        
        return round(input_cost + output_cost, 6)
    
    def parse_harbor_result(self) -> Dict[str, Any]:
        """Parse Harbor result.json file.
        
        Returns:
            Parsed result data, or empty dict if file not found
        """
        if not self.result_file.exists():
            return {}
        
        try:
            with open(self.result_file) as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to parse result.json: {e}")
            return {}
    
    def extract_tool_usage(self, logs_dir: Optional[Path] = None) -> ToolProfile:
        """Extract tool usage metrics from Harbor logs.
        
        Scans agent stdout/stderr logs and parses commands to detect tool usage.
        
        Args:
            logs_dir: Override logs directory path
            
        Returns:
            ToolProfile with aggregated tool usage
        """
        tool_profile, _ = self._parse_tool_usage(logs_dir=logs_dir)
        return tool_profile

    def _parse_tool_usage(
        self,
        logs_dir: Optional[Path] = None
    ) -> Tuple[ToolProfile, Dict[str, Any]]:
        session_logs = self._find_agent_session_logs()
        if session_logs:
            return self._extract_tool_usage_from_sessions(session_logs)

        logs_path = logs_dir or self.logs_dir
        tool_usage: Dict[str, ToolUsage] = {}
        
        if not logs_path.exists():
            return ToolProfile(tool_usage={}, total_tool_invocations=0), {}
        
        # Search for agent logs
        agent_logs = []
        for log_file in logs_path.rglob('*'):
            if log_file.is_file() and any(x in log_file.name for x in ['agent', 'stdout', 'stderr']):
                agent_logs.append(log_file)
        
        # Parse tool usage from logs
        search_count = 0
        file_ops_count = 0
        total_invocations = 0
        
        for log_file in agent_logs:
            try:
                with open(log_file) as f:
                    content = f.read()
                
                # Detect tools by pattern
                for tool_name, (pattern, category) in self.TOOL_PATTERNS.items():
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        count = len(matches)
                        total_invocations += count
                        
                        if tool_name not in tool_usage:
                            tool_usage[tool_name] = ToolUsage(
                                tool_name=tool_name,
                                category=category,
                                invocation_count=count,
                                success_count=count,  # Assume success if present in log
                                failure_count=0
                            )
                        else:
                            tool_usage[tool_name].invocation_count += count
                            tool_usage[tool_name].success_count += count
                        
                        if category == 'code_search':
                            search_count += count
                        elif category == 'file_operation':
                            file_ops_count += count
            except Exception as e:
                print(f"Warning: Failed to parse log {log_file}: {e}")
                continue
        
        profile = ToolProfile(
            tool_usage=tool_usage,
            total_tool_invocations=total_invocations,
            total_unique_tools=len(tool_usage),
            search_queries_count=search_count,
            file_operations_count=file_ops_count,
        )
        return profile, {}

    def _find_agent_session_logs(self) -> List[Path]:
        session_logs = []
        for log_file in self.job_dir.rglob('agent-*.jsonl'):
            if 'agent' in log_file.parts and 'sessions' in log_file.parts:
                session_logs.append(log_file)
        return sorted(session_logs)

    def _extract_tool_usage_from_sessions(
        self,
        session_logs: List[Path]
    ) -> Tuple[ToolProfile, Dict[str, Any]]:
        tool_usage: Dict[str, ToolUsage] = {}
        tool_invocations = 0
        search_queries_count = 0
        file_operations_count = 0
        file_reads = 0
        unique_files_read = set()

        search_success_count = 0
        search_empty_count = 0
        search_failure_count = 0
        search_result_count = 0

        search_queries = []
        search_tool_counts = Counter()
        search_tools_used = set()

        tool_lookup: Dict[str, Dict[str, Any]] = {}

        for session_log in session_logs:
            try:
                with open(session_log) as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        message = event.get('message', {})
                        content = message.get('content')
                        if not isinstance(content, list):
                            continue

                        for entry in content:
                            entry_type = entry.get('type')
                            if entry_type == 'tool_use':
                                tool_use_id = entry.get('id')
                                tool_name = entry.get('name', 'unknown')
                                tool_input = entry.get('input') or {}

                                usage = tool_usage.get(tool_name)
                                if not usage:
                                    usage = ToolUsage(
                                        tool_name=tool_name,
                                        category=self._default_tool_category(tool_name),
                                        invocation_count=0,
                                        success_count=0,
                                        failure_count=0,
                                    )
                                    tool_usage[tool_name] = usage

                                usage.invocation_count += 1
                                tool_invocations += 1

                                invocation_category = self._categorize_tool_invocation(
                                    tool_name, tool_input
                                )
                                if invocation_category == 'code_search':
                                    search_queries_count += 1
                                    search_tools_used.add(tool_name)
                                    search_tool_counts[tool_name] += 1
                                    query = self._extract_search_query(tool_name, tool_input)
                                    if query:
                                        search_queries.append(query)
                                elif invocation_category == 'file_operation':
                                    file_operations_count += 1

                                if tool_name == 'Read':
                                    file_reads += 1
                                    file_path = tool_input.get('file_path')
                                    if file_path:
                                        unique_files_read.add(file_path)

                                if tool_use_id:
                                    tool_lookup[tool_use_id] = {
                                        'tool_name': tool_name,
                                        'category': invocation_category,
                                    }

                            elif entry_type == 'tool_result':
                                tool_use_id = entry.get('tool_use_id')
                                tool_meta = tool_lookup.get(tool_use_id)
                                if not tool_meta:
                                    continue

                                tool_name = tool_meta['tool_name']
                                invocation_category = tool_meta['category']

                                usage = tool_usage.get(tool_name)
                                if not usage:
                                    continue

                                is_error = bool(entry.get('is_error'))
                                tool_result = event.get('toolUseResult', {}) or {}
                                if not isinstance(tool_result, dict):
                                    tool_result = {}
                                duration_ms = tool_result.get('durationMs')
                                if duration_ms is None:
                                    duration_ms = tool_result.get('duration_ms')

                                if is_error:
                                    usage.failure_count += 1
                                else:
                                    usage.success_count += 1
                                if duration_ms is not None:
                                    self._update_avg_duration(
                                        usage, float(duration_ms) / 1000.0
                                    )

                                if invocation_category == 'code_search':
                                    if is_error:
                                        search_failure_count += 1
                                    else:
                                        result_count = self._estimate_result_count(
                                            tool_result, entry.get('content')
                                        )
                                        if result_count == 0:
                                            search_empty_count += 1
                                        else:
                                            search_success_count += 1
                                            search_result_count += result_count

                                if tool_name == 'Read' and tool_result:
                                    file_path = self._extract_file_path_from_result(
                                        tool_result
                                    )
                                    if file_path:
                                        unique_files_read.add(file_path)
            except OSError:
                continue

        profile = ToolProfile(
            tool_usage=tool_usage,
            total_tool_invocations=tool_invocations,
            total_unique_tools=len(tool_usage),
            search_queries_count=search_queries_count,
            file_operations_count=file_operations_count,
        )

        retrieval_metrics = {
            'search_success_count': search_success_count,
            'search_empty_count': search_empty_count,
            'search_failure_count': search_failure_count,
            'search_result_count': search_result_count,
            'search_query_samples': search_queries[: self.MAX_QUERY_SAMPLES],
            'search_tool_counts': dict(search_tool_counts),
            'search_tools_used': sorted(search_tools_used),
            'file_read_count': file_reads,
            'unique_files_read': len(unique_files_read),
            'file_read_samples': list(unique_files_read)[: self.MAX_FILE_SAMPLES],
        }

        return profile, retrieval_metrics

    def _default_tool_category(self, tool_name: str) -> str:
        lower_name = tool_name.lower()
        if lower_name.startswith('sg_') or 'sourcegraph' in lower_name:
            return 'code_search'
        if 'deepsearch' in lower_name or 'search' in lower_name:
            return 'code_search'
        return self.TOOL_CATEGORY_BY_NAME.get(tool_name, 'other')

    def _categorize_tool_invocation(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        if tool_name == 'Bash':
            return self._categorize_bash_command(tool_input.get('command', ''))
        return self._default_tool_category(tool_name)

    @staticmethod
    def _categorize_bash_command(command: str) -> str:
        cmd_lower = command.lower()
        if any(token in cmd_lower for token in ['pytest', 'npm test', 'go test', 'cargo test']):
            return 'verification'
        if any(token in cmd_lower for token in ['rg ', 'grep', 'git grep', 'ripgrep', 'ag ', 'ack']):
            return 'code_search'
        if any(token in cmd_lower for token in ['cat ', 'sed ', 'head ', 'tail ', 'less ', 'more ']):
            return 'file_operation'
        if any(token in cmd_lower for token in ['ls ', 'find ', 'tree ', 'pwd']):
            return 'file_operation'
        return 'other'

    def _extract_search_query(self, tool_name: str, tool_input: Dict[str, Any]) -> Optional[str]:
        if tool_name in {'Grep', 'Glob'}:
            return tool_input.get('pattern')
        lower_name = tool_name.lower()
        if lower_name.startswith('sg_') or 'sourcegraph' in lower_name:
            for key in ['query', 'pattern', 'search_query', 'q', 'search']:
                if key in tool_input:
                    return str(tool_input.get(key))
        if tool_name == 'Bash':
            command = tool_input.get('command', '').strip()
            return command if command else None
        return None

    @staticmethod
    def _estimate_result_count(tool_result: Dict[str, Any], content: Any) -> int:
        counts = []
        if isinstance(tool_result, dict):
            for key in ['numFiles', 'numLines', 'num_matches', 'numMatches']:
                if key in tool_result:
                    try:
                        counts.append(int(tool_result[key]))
                    except (ValueError, TypeError):
                        pass
            filenames = tool_result.get('filenames')
            if isinstance(filenames, list):
                counts.append(len(filenames))
            results = tool_result.get('results')
            if isinstance(results, list):
                counts.append(len(results))
            matches = tool_result.get('matches')
            if isinstance(matches, list):
                counts.append(len(matches))
            content_text = tool_result.get('content')
            if isinstance(content_text, str):
                counts.append(1 if content_text.strip() else 0)
            stdout = tool_result.get('stdout')
            if isinstance(stdout, str):
                counts.append(1 if stdout.strip() else 0)
        if isinstance(content, str):
            counts.append(1 if content.strip() else 0)
        if isinstance(content, list):
            counts.append(len(content))
        return max(counts) if counts else 0

    @staticmethod
    def _extract_file_path_from_result(tool_result: Dict[str, Any]) -> Optional[str]:
        file_entry = tool_result.get('file')
        if isinstance(file_entry, dict):
            return file_entry.get('filePath')
        return None

    @staticmethod
    def _update_avg_duration(usage: ToolUsage, duration_sec: float) -> None:
        completed = usage.success_count + usage.failure_count
        if completed <= 1:
            usage.avg_duration_sec = duration_sec
            return
        previous_total = usage.avg_duration_sec * (completed - 1)
        usage.avg_duration_sec = (previous_total + duration_sec) / completed

    @staticmethod
    def _parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            if value.endswith('Z'):
                value = value.replace('Z', '+00:00')
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _duration_from_timestamps(self, start: Optional[str], end: Optional[str]) -> float:
        start_dt = self._parse_iso_timestamp(start)
        end_dt = self._parse_iso_timestamp(end)
        if not start_dt or not end_dt:
            return 0.0
        duration = (end_dt - start_dt).total_seconds()
        return max(0.0, duration)
    
    def build_result_summary(
        self,
        result: Dict[str, Any],
        input_tokens: int = 0,
        output_tokens: int = 0
    ) -> Dict[str, Any]:
        """Build result summary from Harbor result.json.
        
        Extracts: task name, success/failure, reward, execution time, errors, tokens, costs.
        
        Args:
            result: Parsed Harbor result dictionary
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
            
        Returns:
            Standardized result summary
        """
        verifier_result = result.get('verifier_result', {})
        rewards = verifier_result.get('rewards', {})
        reward = rewards.get('reward', 0.0)
        
        agent_execution = result.get('agent_execution', {})
        patch_info = result.get('patch_info', {})
        exception_info = result.get('exception_info', {})

        duration_sec = float(agent_execution.get('duration_sec', 0) or 0)
        if duration_sec == 0:
            duration_sec = self._duration_from_timestamps(
                agent_execution.get('started_at'),
                agent_execution.get('finished_at')
            )
        if duration_sec == 0:
            duration_sec = self._duration_from_timestamps(
                result.get('started_at'),
                result.get('finished_at')
            )
        
        # Calculate cost from tokens
        cost_usd = self.calculate_cost(input_tokens, output_tokens)
        
        return {
            'task_name': result.get('task_name', 'unknown'),
            'task_id': result.get('task_id', result.get('task_name', 'unknown')),
            'success': reward > 0,
            'reward': float(reward),
            'duration_sec': float(duration_sec),
            'patch_size_bytes': int(patch_info.get('size_bytes', 0)),
            'files_changed': int(patch_info.get('files_changed', 0)),
            'error_type': exception_info.get('type') if exception_info else None,
            'error_message': exception_info.get('message') if exception_info else None,
            'tokens': {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': input_tokens + output_tokens,
            },
            'cost_usd': cost_usd,
        }
    
    def build_retrieval_metrics(self, tool_profile: ToolProfile) -> Dict[str, Any]:
        """Build retrieval metrics from tool usage.
        
        Tracks code search effectiveness and retrieval patterns.
        
        Args:
            tool_profile: Aggregated tool usage profile
            
        Returns:
            Retrieval metrics dictionary
        """
        return {
            'total_searches': tool_profile.search_queries_count,
            'total_file_ops': tool_profile.file_operations_count,
            'tools_used': list(tool_profile.tool_usage.keys()),
            'tool_diversity': tool_profile.total_unique_tools,
        }
    
    def write_manifest(
        self,
        harness_name: str,
        agent_name: str,
        benchmark_name: str,
        override_result: Optional[Dict[str, Any]] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        nemo_trace: Optional[Any] = None  # NeMoExecutionTrace
    ) -> Path:
        """Write run_manifest.json with all execution data.
        
        Supports both legacy token extraction and structured NeMo traces.
        
        Args:
            harness_name: Name of benchmark harness (e.g., "harbor-v1")
            agent_name: Agent implementation (e.g., "claude-baseline", "claude-mcp")
            benchmark_name: Benchmark set name (e.g., "10figure", "terminal-bench")
            override_result: Optional override for result (for testing)
            input_tokens: Number of input tokens used in the run
            output_tokens: Number of output tokens used in the run
            nemo_trace: Optional NeMoExecutionTrace for structured metrics
            
        Returns:
            Path to written manifest file
        """
        # Parse Harbor result
        result = override_result or self.parse_harbor_result()
        if isinstance(result, dict):
            agent_result = result.get('agent_result', {}) or {}
        else:
            agent_result = {}

        if input_tokens == 0:
            input_tokens = int(agent_result.get('n_input_tokens', 0) or 0)
        if output_tokens == 0:
            output_tokens = int(agent_result.get('n_output_tokens', 0) or 0)
        
        # If NeMo trace provided, extract structured metrics
        if nemo_trace:
            from .nemo_trace_parser import NeMoMetricsExtractor
            
            # Use NeMo trace for tool profile and tokens
            tool_profile_dict = NeMoMetricsExtractor.extract_tool_profile(nemo_trace)
            input_tokens = input_tokens or nemo_trace.total_input_tokens
            output_tokens = output_tokens or nemo_trace.total_output_tokens
            tool_profile = None
            extra_retrieval_metrics: Dict[str, Any] = {}
        else:
            tool_profile, extra_retrieval_metrics = self._parse_tool_usage()
            tool_profile.total_input_tokens = input_tokens
            tool_profile.total_output_tokens = output_tokens
            tool_profile_dict = tool_profile.to_dict()
        
        # Build summaries
        result_summary = self.build_result_summary(result, input_tokens, output_tokens)
        
        # Build retrieval metrics from tool profile
        tools_used = list(tool_profile_dict.get('tool_usage', {}).keys())
        retrieval_metrics = {
            'total_searches': 0,
            'total_file_ops': 0,
            'tools_used': tools_used,
            'tool_diversity': len(tools_used),
            'search_success_count': 0,
            'search_empty_count': 0,
            'search_failure_count': 0,
            'search_success_rate': 0.0,
            'search_result_count': 0,
            'search_query_samples': [],
            'search_tool_counts': {},
            'search_tools_used': [],
            'file_read_count': 0,
            'unique_files_read': 0,
            'file_read_samples': [],
        }

        if tool_profile:
            retrieval_metrics.update(self.build_retrieval_metrics(tool_profile))
            retrieval_metrics.update(extra_retrieval_metrics)
            total_searches = retrieval_metrics.get('total_searches', 0)
            successful = retrieval_metrics.get('search_success_count', 0)
            if total_searches:
                retrieval_metrics['search_success_rate'] = (
                    successful / total_searches * 100
                )
        
        # Create manifest
        manifest = {
            'timestamp': datetime.now().isoformat(),
            'harness': {
                'name': harness_name,
                'version': '1.0',
                'framework': 'harbor',
            },
            'execution': {
                'agent': agent_name,
                'benchmark': benchmark_name,
                'job_dir': str(self.job_dir),
            },
            'tool_profile': tool_profile_dict,
            'result': result_summary,
            'retrieval_metrics': retrieval_metrics,
        }
        
        # Add NeMo-specific metrics if trace provided
        if nemo_trace:
            from .nemo_trace_parser import NeMoMetricsExtractor
            manifest['nemo_metrics'] = {
                'workflow_name': nemo_trace.workflow_name,
                'total_duration_sec': nemo_trace.total_duration_sec,
                'tool_call_count': nemo_trace.tool_call_count,
                'failed_tool_calls': len(nemo_trace.failed_tool_calls),
                'failure_rate_percent': nemo_trace.failure_rate,
                'tool_latency_by_tool': nemo_trace.tool_latency_by_tool,
                'failure_analysis': NeMoMetricsExtractor.extract_failure_analysis(nemo_trace),
            }
        
        # Write manifest
        manifest_path = self.job_dir / 'run_manifest.json'
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        return manifest_path
    
    @staticmethod
    def aggregate_manifests(manifest_paths: List[Path]) -> Dict[str, Any]:
        """Aggregate multiple run manifests.
        
        Combines multiple run_manifest.json files for cross-benchmark analysis.
        
        Args:
            manifest_paths: Paths to run_manifest.json files
            
        Returns:
            Aggregated manifest data
        """
        manifests = []
        for path in manifest_paths:
            try:
                with open(path) as f:
                    manifests.append(json.load(f))
            except Exception as e:
                print(f"Warning: Failed to load manifest {path}: {e}")
                continue
        
        if not manifests:
            return {
                'timestamp': datetime.now().isoformat(),
                'total_runs': 0,
                'runs': [],
                'aggregate_metrics': {},
            }
        
        # Compute aggregate metrics
        total_searches = sum(m['retrieval_metrics']['total_searches'] for m in manifests)
        total_file_ops = sum(m['retrieval_metrics']['total_file_ops'] for m in manifests)
        successful = sum(1 for m in manifests if m['result']['success'])
        avg_duration = sum(m['result']['duration_sec'] for m in manifests) / len(manifests)
        
        # Collect all unique tools used
        all_tools = set()
        for m in manifests:
            all_tools.update(m['retrieval_metrics']['tools_used'])
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_runs': len(manifests),
            'runs': [m for m in manifests],
            'aggregate_metrics': {
                'total_searches': total_searches,
                'total_file_ops': total_file_ops,
                'successful_runs': successful,
                'success_rate': successful / len(manifests) * 100 if manifests else 0,
                'avg_duration_sec': avg_duration,
                'unique_tools_used': sorted(list(all_tools)),
            }
        }
