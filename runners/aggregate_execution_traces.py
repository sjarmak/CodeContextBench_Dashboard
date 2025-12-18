#!/usr/bin/env python3
"""Aggregate comprehensive execution traces from Harbor runs.

Combines:
- Task instruction (from instruction.md)
- Agent configuration
- Agent request/response
- Code changes (patch.diff)
- Test results (reward.txt, test output)
- Token usage and metrics

Creates complete interaction thread for learning and analysis.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import re

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from observability import ClaudeOutputParser


@dataclass
class ExecutionTrace:
    """Complete execution trace for a single task."""
    task_id: str
    task_instruction: str
    agent_config: Dict[str, Any]
    agent_request: Optional[str]
    agent_response: Optional[Dict[str, Any]]
    code_changes: str
    test_reward: float
    test_output: str
    metrics: Dict[str, Any]
    status: str  # "pass", "fail", "error"


class ExecutionTraceAggregator:
    """Aggregate complete execution traces from Harbor job directories."""
    
    def __init__(self, job_dir: Path):
        self.job_dir = job_dir
        
    def aggregate_task(self, task_dir: Path) -> Optional[ExecutionTrace]:
        """Aggregate trace for a single task execution.
        
        Args:
            task_dir: Path to task trial directory (e.g., sgt-001__XXXX)
            
        Returns:
            ExecutionTrace object, or None if incomplete
        """
        task_id = task_dir.name
        
        try:
            # 1. Get task instruction
            instruction = self._get_task_instruction(task_dir)
            
            # 2. Get agent config
            config = self._get_agent_config(task_dir)
            
            # 3. Get agent request/response
            agent_request, agent_response = self._get_agent_interaction(task_dir)
            
            # 4. Get code changes
            patch = self._get_code_changes(task_dir)
            
            # 5. Get test results
            reward = self._get_test_reward(task_dir)
            test_output = self._get_test_output(task_dir)
            
            # 6. Get metrics
            metrics = self._get_metrics(task_dir)
            
            # 7. Determine status
            status = self._determine_status(task_dir, reward)
            
            return ExecutionTrace(
                task_id=task_id,
                task_instruction=instruction,
                agent_config=config,
                agent_request=agent_request,
                agent_response=agent_response,
                code_changes=patch,
                test_reward=reward,
                test_output=test_output,
                metrics=metrics,
                status=status
            )
            
        except Exception as e:
            print(f"ERROR aggregating {task_id}: {e}", file=sys.stderr)
            return None
    
    def _get_task_instruction(self, task_dir: Path) -> str:
        """Extract task instruction from benchmark."""
        # Find the benchmark directory
        config_file = task_dir / 'config.json'
        if not config_file.exists():
            return ""
        
        try:
            with open(config_file) as f:
                config = json.load(f)
            
            # Get task path from config
            task_path = config.get('task', {}).get('path', '')
            if not task_path:
                return ""
            
            # Read instruction.md from benchmark
            benchmark_root = Path(__file__).parent.parent
            instruction_file = benchmark_root / task_path / 'instruction.md'
            
            if instruction_file.exists():
                return instruction_file.read_text()
            return ""
        except Exception as e:
            print(f"Failed to get instruction: {e}", file=sys.stderr)
            return ""
    
    def _get_agent_config(self, task_dir: Path) -> Dict[str, Any]:
        """Extract agent configuration."""
        config_file = task_dir / 'config.json'
        if not config_file.exists():
            return {}
        
        try:
            with open(config_file) as f:
                full_config = json.load(f)
            
            # Extract just the agent config
            return {
                'agent': full_config.get('agent', {}),
                'model': full_config.get('agent', {}).get('model_name'),
                'timestamp': full_config.get('trial_name'),
            }
        except Exception:
            return {}
    
    def _get_agent_interaction(self, task_dir: Path) -> tuple[Optional[str], Optional[Dict]]:
        """Extract agent request and response."""
        claude_file = task_dir / 'agent' / 'claude.txt'
        if not claude_file.exists():
            return None, None
        
        try:
            content = claude_file.read_text()
            
            # Try to extract JSON response
            parser = ClaudeOutputParser()
            json_str = parser._extract_json_from_log(content)
            
            response = None
            if json_str:
                try:
                    response = json.loads(json_str)
                except json.JSONDecodeError:
                    pass
            
            # Request is implicit (the instruction), response is the JSON
            return None, response
        except Exception:
            return None, None
    
    def _get_code_changes(self, task_dir: Path) -> str:
        """Extract code changes from patch.diff."""
        patch_file = task_dir / 'agent' / 'patch.diff'
        if not patch_file.exists():
            return ""
        
        try:
            return patch_file.read_text()
        except Exception:
            return ""
    
    def _get_test_reward(self, task_dir: Path) -> float:
        """Extract test reward."""
        reward_file = task_dir / 'verifier' / 'reward.txt'
        if not reward_file.exists():
            reward_file = task_dir / 'reward.txt'
        
        if not reward_file.exists():
            return 0.0
        
        try:
            return float(reward_file.read_text().strip())
        except Exception:
            return 0.0
    
    def _get_test_output(self, task_dir: Path) -> str:
        """Extract test output."""
        test_stdout = task_dir / 'verifier' / 'test-stdout.txt'
        if not test_stdout.exists():
            test_stdout = task_dir / 'test-stdout.txt'
        
        if not test_stdout.exists():
            return ""
        
        try:
            content = test_stdout.read_text()
            # Return first 2000 chars for summary
            return content[:2000]
        except Exception:
            return ""
    
    def _get_metrics(self, task_dir: Path) -> Dict[str, Any]:
        """Extract execution metrics."""
        metrics = {}
        
        # Token usage
        claude_file = task_dir / 'agent' / 'claude.txt'
        if claude_file.exists():
            try:
                usage = ClaudeOutputParser.parse_claude_log_file(claude_file)
                metrics['tokens'] = {
                    'input': usage.input_tokens,
                    'output': usage.output_tokens,
                    'total': usage.total_tokens,
                }
            except Exception:
                pass
        
        # Manifest metrics
        manifest_file = task_dir / 'run_manifest.json'
        if manifest_file.exists():
            try:
                with open(manifest_file) as f:
                    manifest = json.load(f)
                metrics['manifest'] = {
                    'timestamp': manifest.get('timestamp'),
                    'harness': manifest.get('harness'),
                }
            except Exception:
                pass
        
        return metrics
    
    def _determine_status(self, task_dir: Path, reward: float) -> str:
        """Determine task status."""
        # Check for exceptions
        exception_file = task_dir / 'exception.txt'
        if exception_file.exists():
            return "error"
        
        # Check reward
        if reward >= 1.0:
            return "pass"
        elif reward > 0.0:
            return "partial"
        else:
            return "fail"
    
    def aggregate_all(self) -> Dict[str, Any]:
        """Aggregate all task traces in job directory."""
        # Find all task directories (sgt-XXX__YYYY pattern)
        task_dirs = sorted([d for d in self.job_dir.glob('sgt-*_*') if d.is_dir()])
        
        traces = []
        for task_dir in task_dirs:
            trace = self.aggregate_task(task_dir)
            if trace:
                traces.append(trace)
        
        # Summary stats
        total = len(traces)
        passed = sum(1 for t in traces if t.status == "pass")
        failed = sum(1 for t in traces if t.status == "fail")
        errors = sum(1 for t in traces if t.status == "error")
        
        return {
            'job_dir': str(self.job_dir),
            'timestamp': self.job_dir.name,
            'traces': [asdict(t) for t in traces],
            'summary': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'errors': errors,
                'success_rate': passed / total if total > 0 else 0,
            }
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Aggregate comprehensive execution traces from Harbor runs'
    )
    parser.add_argument(
        '--job-dir',
        type=Path,
        required=True,
        help='Harbor job directory (e.g., jobs/harbor-mcp-final/2025-12-18__07-56-35)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('artifacts/execution-traces.json'),
        help='Output file for traces'
    )
    parser.add_argument(
        '--task',
        help='Aggregate only specific task (e.g., sgt-001)'
    )
    
    args = parser.parse_args()
    
    if not args.job_dir.exists():
        print(f"Job directory not found: {args.job_dir}", file=sys.stderr)
        return 1
    
    aggregator = ExecutionTraceAggregator(args.job_dir)
    
    if args.task:
        # Single task
        task_dir = next((d for d in args.job_dir.glob(f'{args.task}_*') if d.is_dir()), None)
        if not task_dir:
            print(f"Task directory not found: {args.task}", file=sys.stderr)
            return 1
        
        trace = aggregator.aggregate_task(task_dir)
        if trace:
            result = asdict(trace)
        else:
            print(f"Failed to aggregate {args.task}", file=sys.stderr)
            return 1
    else:
        # All tasks
        result = aggregator.aggregate_all()
    
    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"Traces written to: {args.output}")
    
    # Print summary if available
    if isinstance(result, dict) and 'summary' in result:
        summary = result['summary']
        print(f"\nSummary:")
        print(f"  Total: {summary['total']}")
        print(f"  Passed: {summary['passed']}")
        print(f"  Failed: {summary['failed']}")
        print(f"  Errors: {summary['errors']}")
        print(f"  Success Rate: {summary['success_rate']:.1%}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
