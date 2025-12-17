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


@dataclass
class ToolUsage:
    """Track a single tool invocation."""
    tool_name: str
    category: str  # "code_search", "file_operation", "code_generation", "verification"
    invocation_count: int = 1
    success_count: int = 0
    failure_count: int = 0
    avg_duration_sec: float = 0.0


@dataclass
class ToolProfile:
    """Aggregate tool usage across a benchmark run."""
    tool_usage: Dict[str, ToolUsage]
    total_tool_invocations: int = 0
    total_unique_tools: int = 0
    search_queries_count: int = 0
    file_operations_count: int = 0
    
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
        }


class ManifestWriter:
    """Write execution manifests from Harbor benchmark runs."""
    
    # Tool detection patterns
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
    
    def __init__(self, job_dir: Path):
        """Initialize manifest writer for a Harbor job directory.
        
        Args:
            job_dir: Path to Harbor job output directory
        """
        self.job_dir = Path(job_dir)
        self.result_file = self.job_dir / 'result.json'
        self.logs_dir = self.job_dir / 'logs'
        self.artifact_dir = self.job_dir / 'artifacts'
    
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
        logs_path = logs_dir or self.logs_dir
        tool_usage: Dict[str, ToolUsage] = {}
        
        if not logs_path.exists():
            return ToolProfile(tool_usage={}, total_tool_invocations=0)
        
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
        
        return profile
    
    def build_result_summary(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Build result summary from Harbor result.json.
        
        Extracts: task name, success/failure, reward, execution time, errors.
        
        Args:
            result: Parsed Harbor result dictionary
            
        Returns:
            Standardized result summary
        """
        verifier_result = result.get('verifier_result', {})
        rewards = verifier_result.get('rewards', {})
        reward = rewards.get('reward', 0.0)
        
        agent_execution = result.get('agent_execution', {})
        patch_info = result.get('patch_info', {})
        exception_info = result.get('exception_info', {})
        
        return {
            'task_name': result.get('task_name', 'unknown'),
            'task_id': result.get('task_id', result.get('task_name', 'unknown')),
            'success': reward > 0,
            'reward': float(reward),
            'duration_sec': float(agent_execution.get('duration_sec', 0)),
            'patch_size_bytes': int(patch_info.get('size_bytes', 0)),
            'files_changed': int(patch_info.get('files_changed', 0)),
            'error_type': exception_info.get('type') if exception_info else None,
            'error_message': exception_info.get('message') if exception_info else None,
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
        override_result: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Write run_manifest.json with all execution data.
        
        Args:
            harness_name: Name of benchmark harness (e.g., "harbor-v1")
            agent_name: Agent implementation (e.g., "claude-baseline", "claude-mcp")
            benchmark_name: Benchmark set name (e.g., "10figure", "terminal-bench")
            override_result: Optional override for result (for testing)
            
        Returns:
            Path to written manifest file
        """
        # Parse Harbor result
        result = override_result or self.parse_harbor_result()
        
        # Extract tool usage from logs
        tool_profile = self.extract_tool_usage()
        
        # Build summaries
        result_summary = self.build_result_summary(result)
        retrieval_metrics = self.build_retrieval_metrics(tool_profile)
        
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
            'tool_profile': tool_profile.to_dict(),
            'result': result_summary,
            'retrieval_metrics': retrieval_metrics,
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
