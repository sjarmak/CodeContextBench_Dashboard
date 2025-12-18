#!/usr/bin/env python3
"""Capture comprehensive execution trace for a single Harbor task execution.

This script aggregates complete data from a single task run, including:
- Full streaming conversation output (all turns)
- Code changes (patch.diff, patch.stat)
- Test results and validation
- Execution metrics (tokens, time, tool calls)
- Deep Search queries (for MCP agent only)

Used to validate that agents are actually making code changes and that tests
are real (not fake successes like `make test` with no target).
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import re
import subprocess

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from observability import ClaudeOutputParser
except ImportError:
    ClaudeOutputParser = None


@dataclass
class ConversationTurn:
    """Single turn in multi-turn conversation."""
    turn_number: int
    role: str  # "user" or "assistant"
    content: str
    tokens_input: int = 0
    tokens_output: int = 0
    tool_name: Optional[str] = None  # If turn involves tool call
    tool_input: Optional[Dict] = None
    tool_result: Optional[str] = None


@dataclass
class ExecutionMetrics:
    """Execution metrics for task run."""
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    execution_time_sec: Optional[float] = None
    total_turns: int = 0
    tool_calls: int = 0
    deep_search_queries: int = 0


@dataclass
class CodeChanges:
    """Code changes made by agent."""
    patch_diff: str
    patch_stat: str
    files_modified: List[str]
    total_additions: int = 0
    total_deletions: int = 0
    is_empty: bool = False


@dataclass
class TestResults:
    """Test execution results."""
    passed: bool
    reward_value: float
    test_output: str
    test_stderr: str = ""
    validation_checks: Dict[str, bool] = None  # File existence, pattern matching, etc.


@dataclass
class SingleTaskTrace:
    """Complete trace for single task execution."""
    task_id: str
    agent_name: str
    timestamp: str
    system_prompt: str
    task_instruction: str
    conversation: List[ConversationTurn]
    code_changes: CodeChanges
    test_results: TestResults
    metrics: ExecutionMetrics
    status: str  # "success", "failure", "validation_error"
    error_message: Optional[str] = None


class SingleTaskTraceAggregator:
    """Aggregate complete trace for a single Harbor task execution."""
    
    def __init__(self, task_dir: Path):
        """Initialize with task execution directory.
        
        Args:
            task_dir: Path to task trial directory (e.g., sgt-001__XXXXX)
        """
        self.task_dir = task_dir
        self.task_id = task_dir.name
    
    def aggregate(self) -> Optional[SingleTaskTrace]:
        """Aggregate complete trace for this task.
        
        Returns:
            SingleTaskTrace object, or None if aggregation fails
        """
        try:
            # Get task metadata
            agent_name = self._get_agent_name()
            timestamp = self._get_timestamp()
            
            # Get system prompt and instruction
            system_prompt = self._get_system_prompt()
            task_instruction = self._get_task_instruction()
            
            # Parse full conversation
            conversation = self._parse_conversation()
            
            # Get code changes
            code_changes = self._get_code_changes()
            
            # Get test results
            test_results = self._get_test_results()
            
            # Get execution metrics
            metrics = self._get_metrics(conversation)
            
            # Determine status
            status = self._determine_status(code_changes, test_results)
            error_message = None if status == "success" else self._get_error_message()
            
            return SingleTaskTrace(
                task_id=self.task_id,
                agent_name=agent_name,
                timestamp=timestamp,
                system_prompt=system_prompt,
                task_instruction=task_instruction,
                conversation=conversation,
                code_changes=code_changes,
                test_results=test_results,
                metrics=metrics,
                status=status,
                error_message=error_message
            )
            
        except Exception as e:
            print(f"ERROR aggregating {self.task_id}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return None
    
    def _get_agent_name(self) -> str:
        """Extract agent name from config."""
        config_file = self.task_dir / 'config.json'
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
                return config.get('agent', {}).get('name', 'unknown')
            except Exception:
                pass
        return 'unknown'
    
    def _get_timestamp(self) -> str:
        """Get task execution timestamp."""
        config_file = self.task_dir / 'config.json'
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
                return config.get('trial_name', '')
            except Exception:
                pass
        return ''
    
    def _get_system_prompt(self) -> str:
        """Extract system prompt saved by agent."""
        prompt_file = self.task_dir / 'agent' / 'system_prompt.txt'
        if prompt_file.exists():
            try:
                return prompt_file.read_text()
            except Exception:
                pass
        return ''
    
    def _get_task_instruction(self) -> str:
        """Extract task instruction from benchmark."""
        config_file = self.task_dir / 'config.json'
        if not config_file.exists():
            return ""
        
        try:
            with open(config_file) as f:
                config = json.load(f)
            
            task_path = config.get('task', {}).get('path', '')
            if not task_path:
                return ""
            
            benchmark_root = Path(__file__).parent.parent
            instruction_file = benchmark_root / task_path / 'instruction.md'
            
            if instruction_file.exists():
                return instruction_file.read_text()
            return ""
        except Exception:
            return ""
    
    def _parse_conversation(self) -> List[ConversationTurn]:
        """Parse full multi-turn conversation from claude.txt.
        
        Extracts all turns including system, user, and assistant messages.
        """
        claude_file = self.task_dir / 'agent' / 'claude.txt'
        if not claude_file.exists():
            return []
        
        try:
            content = claude_file.read_text()
            turns = []
            turn_number = 0
            
            # Parse Claude output format (could be streaming JSON or text)
            # This is a best-effort parser - Claude output format may vary
            
            # Try to find JSON objects (streaming format)
            json_objects = self._extract_json_objects(content)
            
            for i, json_obj in enumerate(json_objects):
                turn = self._parse_json_turn(json_obj, i)
                if turn:
                    turns.append(turn)
            
            return turns
        except Exception as e:
            print(f"Warning: Failed to parse conversation: {e}", file=sys.stderr)
            return []
    
    def _extract_json_objects(self, content: str) -> List[Dict]:
        """Extract all JSON objects from content."""
        objects = []
        depth = 0
        start_idx = -1
        in_string = False
        escape_next = False
        
        for i, char in enumerate(content):
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                continue
            
            if not in_string:
                if char in '{[':
                    if depth == 0:
                        start_idx = i
                    depth += 1
                elif char in '}]':
                    depth -= 1
                    if depth == 0 and start_idx >= 0:
                        try:
                            obj_str = content[start_idx:i+1]
                            obj = json.loads(obj_str)
                            objects.append(obj)
                        except json.JSONDecodeError:
                            pass
                        start_idx = -1
        
        return objects
    
    def _parse_json_turn(self, json_obj: Dict, turn_num: int) -> Optional[ConversationTurn]:
        """Parse a single JSON turn from Claude output."""
        try:
            # Handle different possible formats
            if 'type' in json_obj and json_obj['type'] == 'message':
                return ConversationTurn(
                    turn_number=turn_num,
                    role='assistant',
                    content=str(json_obj.get('content', '')),
                    tokens_output=json_obj.get('usage', {}).get('output_tokens', 0)
                )
            elif 'content' in json_obj:
                return ConversationTurn(
                    turn_number=turn_num,
                    role='assistant',
                    content=str(json_obj.get('content', '')),
                    tokens_output=json_obj.get('usage', {}).get('output_tokens', 0)
                )
        except Exception:
            pass
        
        return None
    
    def _get_code_changes(self) -> CodeChanges:
        """Extract code changes from patch.diff and patch.stat."""
        patch_file = self.task_dir / 'agent' / 'patch.diff'
        stat_file = self.task_dir / 'agent' / 'patch.stat'
        
        patch_diff = ""
        patch_stat = ""
        
        if patch_file.exists():
            try:
                patch_diff = patch_file.read_text()
            except Exception:
                pass
        
        if stat_file.exists():
            try:
                patch_stat = stat_file.read_text()
            except Exception:
                pass
        
        # Parse file modifications from stat
        files_modified = self._parse_modified_files(patch_stat)
        additions, deletions = self._parse_diff_stats(patch_stat)
        
        return CodeChanges(
            patch_diff=patch_diff,
            patch_stat=patch_stat,
            files_modified=files_modified,
            total_additions=additions,
            total_deletions=deletions,
            is_empty=len(patch_diff) == 0
        )
    
    def _parse_modified_files(self, patch_stat: str) -> List[str]:
        """Extract list of modified files from git diff --stat output."""
        files = []
        for line in patch_stat.split('\n'):
            # Format: "filepath | additions deletions changes"
            if '|' in line:
                filepath = line.split('|')[0].strip()
                if filepath:
                    files.append(filepath)
        return files
    
    def _parse_diff_stats(self, patch_stat: str) -> tuple[int, int]:
        """Extract total additions and deletions from git diff --stat."""
        additions = 0
        deletions = 0
        
        for line in patch_stat.split('\n'):
            # Match patterns like "+123" and "-456"
            plus_match = re.search(r'\+(\d+)', line)
            minus_match = re.search(r'-(\d+)', line)
            
            if plus_match:
                additions += int(plus_match.group(1))
            if minus_match:
                deletions += int(minus_match.group(1))
        
        return additions, deletions
    
    def _get_test_results(self) -> TestResults:
        """Extract test results and validation."""
        reward_file = self.task_dir / 'verifier' / 'reward.txt'
        test_stdout = self.task_dir / 'verifier' / 'test-stdout.txt'
        test_stderr = self.task_dir / 'verifier' / 'test-stderr.txt'
        
        reward_value = 0.0
        test_output = ""
        test_stderr_str = ""
        
        if reward_file.exists():
            try:
                reward_value = float(reward_file.read_text().strip())
            except Exception:
                pass
        
        if test_stdout.exists():
            try:
                test_output = test_stdout.read_text()
            except Exception:
                pass
        
        if test_stderr.exists():
            try:
                test_stderr_str = test_stderr.read_text()
            except Exception:
                pass
        
        passed = reward_value >= 1.0
        
        # Run validation checks
        validation_checks = self._run_validation_checks()
        
        return TestResults(
            passed=passed,
            reward_value=reward_value,
            test_output=test_output,
            test_stderr=test_stderr_str,
            validation_checks=validation_checks
        )
    
    def _run_validation_checks(self) -> Dict[str, bool]:
        """Run validation checks on task execution."""
        checks = {
            'code_changes_exist': False,
            'patch_diff_non_empty': False,
            'test_files_found': False,
            'system_prompt_saved': False,
        }
        
        # Check code changes
        patch_file = self.task_dir / 'agent' / 'patch.diff'
        if patch_file.exists() and patch_file.stat().st_size > 0:
            checks['patch_diff_non_empty'] = True
            checks['code_changes_exist'] = True
        
        # Check test output exists
        test_file = self.task_dir / 'verifier' / 'test-stdout.txt'
        if test_file.exists():
            checks['test_files_found'] = True
        
        # Check system prompt saved
        prompt_file = self.task_dir / 'agent' / 'system_prompt.txt'
        if prompt_file.exists():
            checks['system_prompt_saved'] = True
        
        return checks
    
    def _get_metrics(self, conversation: List[ConversationTurn]) -> ExecutionMetrics:
        """Extract execution metrics from task run."""
        metrics = ExecutionMetrics(
            total_turns=len(conversation)
        )
        
        # Extract token counts
        claude_file = self.task_dir / 'agent' / 'claude.txt'
        if claude_file.exists() and ClaudeOutputParser:
            try:
                usage = ClaudeOutputParser.parse_claude_log_file(claude_file)
                metrics.input_tokens = usage.input_tokens
                metrics.output_tokens = usage.output_tokens
                metrics.total_tokens = usage.total_tokens
            except Exception:
                pass
        
        # Count tool calls and deep search queries
        for turn in conversation:
            if turn.tool_name:
                metrics.tool_calls += 1
                if 'deep_search' in str(turn.tool_name).lower():
                    metrics.deep_search_queries += 1
        
        return metrics
    
    def _determine_status(self, code_changes: CodeChanges, test_results: TestResults) -> str:
        """Determine overall task status."""
        # Status must consider:
        # 1. Whether code changes were actually made
        # 2. Whether tests passed
        # 3. Whether validation checks passed
        
        if code_changes.is_empty:
            return "validation_error"  # No code changes = immediate failure
        
        if test_results.passed:
            return "success"
        
        return "failure"  # Code changes but tests failed
    
    def _get_error_message(self) -> str:
        """Extract error message if task failed."""
        exception_file = self.task_dir / 'exception.txt'
        if exception_file.exists():
            try:
                return exception_file.read_text()
            except Exception:
                pass
        return ""


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Capture comprehensive execution trace for single Harbor task'
    )
    parser.add_argument(
        '--task-dir',
        type=Path,
        required=True,
        help='Harbor task directory (e.g., jobs/run-name/YYYY-MM-DD__HH-MM-SS/sgt-001__XXXXX)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Output file for trace (default: task_dir/trace.json)'
    )
    
    args = parser.parse_args()
    
    if not args.task_dir.exists():
        print(f"Task directory not found: {args.task_dir}", file=sys.stderr)
        return 1
    
    # Aggregate trace
    aggregator = SingleTaskTraceAggregator(args.task_dir)
    trace = aggregator.aggregate()
    
    if not trace:
        print(f"Failed to aggregate trace for {args.task_dir}", file=sys.stderr)
        return 1
    
    # Determine output file
    if not args.output:
        args.output = args.task_dir / 'trace.json'
    
    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(asdict(trace), f, indent=2)
    
    print(f"Trace written to: {args.output}")
    
    # Print summary
    print(f"\nTask: {trace.task_id}")
    print(f"Agent: {trace.agent_name}")
    print(f"Status: {trace.status}")
    print(f"Code changes: {trace.code_changes.total_additions} additions, {trace.code_changes.total_deletions} deletions")
    print(f"Test passed: {trace.test_results.passed}")
    print(f"Tokens: {trace.metrics.total_tokens}")
    print(f"Turns: {trace.metrics.total_turns}")
    
    if trace.error_message:
        print(f"Error: {trace.error_message[:200]}")
    
    return 0 if trace.status == "success" else 1


if __name__ == '__main__':
    sys.exit(main())
