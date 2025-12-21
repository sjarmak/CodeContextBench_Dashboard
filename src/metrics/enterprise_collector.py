#!/usr/bin/env python3
"""
Enterprise Metrics Collector

Collects enterprise-informed metrics from agent trajectories in real-time or post-hoc.
Based on ENTERPRISE_CODEBASES.md research and enterprise_metrics_schema.json.

Usage:
    # Post-hoc analysis
    collector = EnterpriseMetricsCollector()
    metrics = collector.process_trajectory(jsonl_path)

    # Real-time collection
    collector = EnterpriseMetricsCollector(realtime=True)
    collector.on_event(event)
    metrics = collector.finalize()
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
from enum import Enum

class Phase(Enum):
    """Agent activity phases"""
    COMPREHENSION = "comprehension"
    NAVIGATION = "navigation"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    UNKNOWN = "unknown"

class ToolCategory(Enum):
    """Tool categorization for phase detection"""
    READ = ["Read", "Grep", "Glob"]
    SEARCH_MCP = ["sg_keyword_search", "sg_nls_search", "sg_deepsearch", "sg_search"]
    WRITE = ["Write", "Edit", "NotebookEdit"]
    BASH_GENERAL = ["Bash"]
    TEST = []  # Detected by command content
    BUILD = []  # Detected by command content

def parse_timestamp(ts_str: str) -> datetime:
    """Parse ISO 8601 timestamp."""
    return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))

def detect_bash_category(command: str) -> Tuple[Phase, str]:
    """
    Categorize bash command by phase and subcategory.

    Returns: (Phase, subcategory)
    """
    cmd_lower = command.lower()

    # Test detection
    if any(pattern in cmd_lower for pattern in [
        'npm test', 'pytest', 'python -m pytest', 'cargo test',
        'go test', 'mvn test', 'gradle test', 'make test', './test'
    ]):
        return (Phase.TESTING, "test")

    # Build detection
    if any(pattern in cmd_lower for pattern in [
        'npm run build', 'cargo build', 'go build', 'mvn compile',
        'gradle build', 'make build', 'make all', 'npm run compile'
    ]):
        return (Phase.TESTING, "build")

    # Search/navigation
    if any(pattern in cmd_lower for pattern in [
        'grep', 'rg ', 'find ', 'locate', 'fd ', 'ag ', 'ack'
    ]):
        return (Phase.NAVIGATION, "search")

    # File exploration
    if any(pattern in cmd_lower for pattern in [
        'ls ', 'tree', 'cat ', 'less ', 'more ', 'head ', 'tail '
    ]):
        return (Phase.COMPREHENSION, "explore")

    # Git operations (usually exploration)
    if cmd_lower.startswith(('git log', 'git show', 'git diff', 'git blame')):
        return (Phase.COMPREHENSION, "git_explore")

    # Git modifications
    if cmd_lower.startswith(('git add', 'git commit', 'git push')):
        return (Phase.IMPLEMENTATION, "git_commit")

    return (Phase.UNKNOWN, "general")

class EnterpriseMetricsCollector:
    """
    Collects enterprise-informed metrics from agent trajectories.

    Tracks time allocation, navigation patterns, tool usage, build/test cycles,
    comprehension indicators, and more.
    """

    def __init__(self, realtime: bool = False, task_metadata: Optional[Dict] = None):
        """
        Initialize metrics collector.

        Args:
            realtime: If True, process events as they arrive. If False, batch process.
            task_metadata: Optional metadata (task_id, agent_type, etc.)
        """
        self.realtime = realtime
        self.task_metadata = task_metadata or {}

        # Core metrics
        self.events: List[Dict] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.last_event_time: Optional[datetime] = None

        # Token tracking
        self.tokens = {
            'total_input': 0,
            'total_output': 0,
            'cache_read': 0,
            'cache_creation': 0,
            'by_phase': defaultdict(int)
        }

        # Phase tracking
        self.phase_actions = Counter()
        self.current_phase = Phase.UNKNOWN

        # Tool usage
        self.tool_calls = Counter()
        self.tool_timeline: List[Dict] = []
        self.mcp_searches = 0
        self.mcp_tools_detected: List[str] = []

        # File access
        self.files_read: set = set()
        self.files_written: set = set()
        self.file_access_timeline: List[Dict] = []
        self.file_read_counts = Counter()
        self.current_file: Optional[str] = None
        self.file_dwell_starts: Dict[str, datetime] = {}
        self.file_dwell_times = defaultdict(float)

        # Navigation metrics
        self.file_reads_count = 0
        self.file_writes_count = 0

        # Build/test tracking
        self.test_runs = 0
        self.build_attempts = 0
        self.test_timeline: List[Dict] = []
        self.first_test_time: Optional[datetime] = None

        # Implementation tracking
        self.first_edit_time: Optional[datetime] = None
        self.edit_operations = 0

        # Search patterns
        self.search_queries: List[Dict] = []

        # Context switching
        self.file_switches = 0
        self.context_switches: List[Dict] = []

        # Error tracking
        self.errors: List[Dict] = []

        # Think time (pauses between actions)
        self.think_times: List[float] = []

    def on_event(self, event: Dict) -> None:
        """
        Process a single event (real-time or batch).

        Args:
            event: JSONL event dict
        """
        self.events.append(event)

        timestamp = parse_timestamp(event['timestamp'])

        # Track timing
        if self.start_time is None:
            self.start_time = timestamp

        if self.last_event_time:
            think_time = (timestamp - self.last_event_time).total_seconds()
            if think_time > 1.0:  # More than 1 second = thinking
                self.think_times.append(think_time)

        self.end_time = timestamp
        self.last_event_time = timestamp

        # Process by event type
        event_type = event.get('type')

        if event_type == 'assistant':
            self._process_assistant_message(event, timestamp)
        elif event_type == 'user':
            self._process_user_message(event, timestamp)

    def _process_assistant_message(self, event: Dict, timestamp: datetime) -> None:
        """Process assistant message for tool calls and tokens."""
        message = event.get('message', {})

        # Track tokens
        usage = message.get('usage', {})
        self.tokens['total_input'] += usage.get('input_tokens', 0)
        self.tokens['total_input'] += usage.get('cache_read_input_tokens', 0)
        self.tokens['total_output'] += usage.get('output_tokens', 0)
        self.tokens['cache_read'] += usage.get('cache_read_input_tokens', 0)
        self.tokens['cache_creation'] += usage.get('cache_creation_input_tokens', 0)

        # Track by phase (approximate)
        phase_key = self.current_phase.value if self.current_phase != Phase.UNKNOWN else 'unknown'
        self.tokens['by_phase'][phase_key] += (
            usage.get('input_tokens', 0) +
            usage.get('output_tokens', 0)
        )

        # Process tool calls
        content = message.get('content', [])
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'tool_use':
                self._process_tool_call(item, timestamp)

    def _process_user_message(self, event: Dict, timestamp: datetime) -> None:
        """Process user message for tool results."""
        message = event.get('message', {})
        content = message.get('content', [])

        for item in content:
            if isinstance(item, dict) and item.get('type') == 'tool_result':
                self._process_tool_result(item, timestamp)

    def _process_tool_call(self, tool_use: Dict, timestamp: datetime) -> None:
        """Process a tool call and categorize by phase."""
        tool_name = tool_use.get('name')
        tool_input = tool_use.get('input', {})

        if not tool_name:
            return

        self.tool_calls[tool_name] += 1

        # Detect phase
        phase = self._detect_phase(tool_name, tool_input)
        self.current_phase = phase
        self.phase_actions[phase] += 1

        # Track in timeline
        self.tool_timeline.append({
            'timestamp': timestamp.isoformat(),
            'tool': tool_name,
            'phase': phase.value,
            'input': tool_input
        })

        # MCP detection
        if tool_name.startswith('sg_'):
            self.mcp_searches += 1
            if tool_name not in self.mcp_tools_detected:
                self.mcp_tools_detected.append(tool_name)

            # Track search query
            query = tool_input.get('query') or tool_input.get('pattern') or str(tool_input)
            self.search_queries.append({
                'timestamp': timestamp.isoformat(),
                'tool': tool_name,
                'query': query
            })

        # File access tracking
        if tool_name == 'Read':
            file_path = tool_input.get('file_path')
            if file_path:
                self._track_file_read(file_path, timestamp)

        elif tool_name in ['Write', 'Edit', 'NotebookEdit']:
            file_path = tool_input.get('file_path') or tool_input.get('notebook_path')
            if file_path:
                self._track_file_write(file_path, timestamp)

        # Bash command categorization
        elif tool_name == 'Bash':
            command = tool_input.get('command', '')
            bash_phase, subcategory = detect_bash_category(command)

            if bash_phase != Phase.UNKNOWN:
                self.current_phase = bash_phase
                self.phase_actions[bash_phase] += 1

            if subcategory == 'test':
                self.test_runs += 1
                if self.first_test_time is None:
                    self.first_test_time = timestamp
                self.test_timeline.append({
                    'timestamp': timestamp.isoformat(),
                    'action': 'test',
                    'command': command
                })
            elif subcategory == 'build':
                self.build_attempts += 1
                self.test_timeline.append({
                    'timestamp': timestamp.isoformat(),
                    'action': 'build',
                    'command': command
                })
            elif subcategory == 'search':
                # Bash search is navigation
                query = command
                self.search_queries.append({
                    'timestamp': timestamp.isoformat(),
                    'tool': 'Bash (search)',
                    'query': query
                })

    def _process_tool_result(self, tool_result: Dict, timestamp: datetime) -> None:
        """Process tool result to track errors and success."""
        is_error = tool_result.get('is_error', False)
        content = tool_result.get('content', '')

        if is_error and content:
            # Try to categorize error
            error_type = self._categorize_error(content)
            self.errors.append({
                'timestamp': timestamp.isoformat(),
                'error_type': error_type,
                'error_message': content[:200]  # Truncate
            })

    def _detect_phase(self, tool_name: str, tool_input: Dict) -> Phase:
        """
        Detect which phase this tool call belongs to.

        Based on enterprise research:
        - Comprehension: Reading to understand
        - Navigation: Searching and exploring
        - Implementation: Writing code
        - Testing: Running tests/builds
        """
        # Direct categorization
        if tool_name in ToolCategory.READ.value:
            # Read can be comprehension OR reference during implementation
            # Heuristic: if we haven't edited yet, it's comprehension
            if self.first_edit_time is None:
                return Phase.COMPREHENSION
            else:
                return Phase.NAVIGATION

        if tool_name in ToolCategory.SEARCH_MCP.value:
            return Phase.NAVIGATION

        if tool_name in ToolCategory.WRITE.value:
            return Phase.IMPLEMENTATION

        if tool_name == 'Bash':
            # Handled in _process_tool_call
            return Phase.UNKNOWN

        return Phase.UNKNOWN

    def _track_file_read(self, file_path: str, timestamp: datetime) -> None:
        """Track a file read operation."""
        self.files_read.add(file_path)
        self.file_reads_count += 1
        self.file_read_counts[file_path] += 1

        self.file_access_timeline.append({
            'timestamp': timestamp.isoformat(),
            'action': 'read',
            'file': file_path
        })

        # Track context switch
        if self.current_file and self.current_file != file_path:
            self.file_switches += 1
            self.context_switches.append({
                'timestamp': timestamp.isoformat(),
                'from_file': self.current_file,
                'to_file': file_path
            })

            # Update dwell time for previous file
            if self.current_file in self.file_dwell_starts:
                dwell_duration = (timestamp - self.file_dwell_starts[self.current_file]).total_seconds()
                self.file_dwell_times[self.current_file] += dwell_duration

        self.current_file = file_path
        self.file_dwell_starts[file_path] = timestamp

    def _track_file_write(self, file_path: str, timestamp: datetime) -> None:
        """Track a file write operation."""
        self.files_written.add(file_path)
        self.file_writes_count += 1
        self.edit_operations += 1

        if self.first_edit_time is None:
            self.first_edit_time = timestamp

        self.file_access_timeline.append({
            'timestamp': timestamp.isoformat(),
            'action': 'write',
            'file': file_path
        })

        # Track context switch
        if self.current_file and self.current_file != file_path:
            self.file_switches += 1
            self.context_switches.append({
                'timestamp': timestamp.isoformat(),
                'from_file': self.current_file,
                'to_file': file_path
            })

        self.current_file = file_path
        self.file_dwell_starts[file_path] = timestamp

    def _categorize_error(self, error_message: str) -> str:
        """Categorize error by type."""
        msg_lower = error_message.lower()

        if any(keyword in msg_lower for keyword in ['syntaxerror', 'syntax error', 'unexpected token']):
            return 'syntax'
        elif any(keyword in msg_lower for keyword in ['typeerror', 'type error', 'cannot read property']):
            return 'type'
        elif any(keyword in msg_lower for keyword in ['importerror', 'modulenotfound', 'cannot find module']):
            return 'import'
        elif any(keyword in msg_lower for keyword in ['timeout', 'timed out']):
            return 'timeout'
        else:
            return 'logic'

    def finalize(self) -> Dict[str, Any]:
        """
        Finalize metrics collection and return complete metrics object.

        Returns:
            Dict matching enterprise_metrics_schema.json
        """
        if not self.start_time or not self.end_time:
            raise ValueError("No events processed")

        total_duration = (self.end_time - self.start_time).total_seconds()

        # Calculate time allocation percentages
        total_actions = sum(self.phase_actions.values())

        time_allocation = {
            'total_actions': total_actions,
            'comprehension_actions': self.phase_actions[Phase.COMPREHENSION],
            'navigation_actions': self.phase_actions[Phase.NAVIGATION],
            'implementation_actions': self.phase_actions[Phase.IMPLEMENTATION],
            'testing_actions': self.phase_actions[Phase.TESTING],
        }

        if total_actions > 0:
            time_allocation.update({
                'comprehension_pct': 100 * self.phase_actions[Phase.COMPREHENSION] / total_actions,
                'navigation_pct': 100 * self.phase_actions[Phase.NAVIGATION] / total_actions,
                'implementation_pct': 100 * self.phase_actions[Phase.IMPLEMENTATION] / total_actions,
                'testing_pct': 100 * self.phase_actions[Phase.TESTING] / total_actions,
            })
        else:
            time_allocation.update({
                'comprehension_pct': 0,
                'navigation_pct': 0,
                'implementation_pct': 0,
                'testing_pct': 0,
            })

        # Always add baseline comparison
        time_allocation['baseline_comparison'] = {
            'comprehension_gap': time_allocation['comprehension_pct'] - 58.0,
            'navigation_gap': time_allocation['navigation_pct'] - 35.0
        }

        # Add timing
        if self.first_edit_time:
            time_allocation['time_to_first_edit'] = (self.first_edit_time - self.start_time).total_seconds()
        if self.first_test_time:
            time_allocation['time_to_first_test'] = (self.first_test_time - self.start_time).total_seconds()

        # Navigation metrics
        navigation_efficiency = (
            self.file_reads_count / max(1, self.file_writes_count)
        )

        reread_files = [f for f, count in self.file_read_counts.items() if count > 1]
        reread_ratio = len(reread_files) / max(1, len(self.files_read))

        navigation = {
            'file_reads': self.file_reads_count,
            'file_writes': self.file_writes_count,
            'unique_files_read': len(self.files_read),
            'unique_files_written': len(self.files_written),
            'navigation_efficiency': navigation_efficiency,
            'reread_ratio': reread_ratio,
            'rereads': dict(self.file_read_counts),
            'file_access_timeline': self.file_access_timeline,
            'dwell_time': dict(self.file_dwell_times)
        }

        # Tool usage
        tool_usage = {
            'tool_calls': dict(self.tool_calls),
            'tool_timeline': self.tool_timeline,
            'mcp_searches': self.mcp_searches,
            'mcp_tools_detected': self.mcp_tools_detected,
            'search_queries': self.search_queries
        }

        # Build/test
        build_test = {
            'test_runs': self.test_runs,
            'build_attempts': self.build_attempts,
            'test_timeline': self.test_timeline
        }

        # Context switching
        rapid_switches = sum(
            1 for i in range(1, len(self.context_switches))
            if parse_timestamp(self.context_switches[i]['timestamp']) -
               parse_timestamp(self.context_switches[i-1]['timestamp']) < timedelta(seconds=30)
        )

        context_switching = {
            'file_switches': self.file_switches,
            'rapid_switches': rapid_switches,
            'thrashing_detected': rapid_switches > 5,
            'avg_dwell_time': sum(self.file_dwell_times.values()) / max(1, len(self.file_dwell_times)),
            'context_switches': self.context_switches
        }

        # Comprehension indicators
        comprehension = {
            'reread_for_understanding': len(reread_files)
        }

        if self.think_times:
            comprehension['think_time'] = {
                'avg_before_first_edit': self.think_times[0] if self.think_times else 0,
                'avg_between_reads': sum(self.think_times) / len(self.think_times)
            }

        # Implementation
        implementation = {
            'edit_operations': self.edit_operations
        }

        # Errors
        error_counts = Counter(e['error_type'] for e in self.errors)
        errors = {
            'syntax_errors': error_counts.get('syntax', 0),
            'type_errors': error_counts.get('type', 0),
            'import_errors': error_counts.get('import', 0),
            'logic_errors': error_counts.get('logic', 0),
            'error_timeline': self.errors
        }

        # Assemble complete metrics
        metrics = {
            'metadata': {
                'task_id': self.task_metadata.get('task_id', 'unknown'),
                'agent_type': self.task_metadata.get('agent_type', 'unknown'),
                'timestamp': self.start_time.isoformat(),
                'version': '1.0.0',
                **{k: v for k, v in self.task_metadata.items()
                   if k not in ['task_id', 'agent_type']}
            },
            'execution': {
                'start_time': self.start_time.isoformat(),
                'end_time': self.end_time.isoformat(),
                'total_duration': total_duration,
                'total_events': len(self.events)
            },
            'tokens': {
                'total_input': self.tokens['total_input'],
                'total_output': self.tokens['total_output'],
                'total': self.tokens['total_input'] + self.tokens['total_output'],
                'cache_read': self.tokens['cache_read'],
                'cache_creation': self.tokens['cache_creation'],
                'by_phase': dict(self.tokens['by_phase'])
            },
            'time_allocation': time_allocation,
            'navigation': navigation,
            'tool_usage': tool_usage,
            'build_test': build_test,
            'comprehension': comprehension,
            'implementation': implementation,
            'context_switching': context_switching,
            'errors': errors
        }

        return metrics

    def process_trajectory(self, jsonl_path: Path, task_metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Process a complete trajectory file (batch mode).

        Args:
            jsonl_path: Path to trajectory JSONL file
            task_metadata: Optional metadata to include

        Returns:
            Complete metrics dict
        """
        if task_metadata:
            self.task_metadata.update(task_metadata)

        with open(jsonl_path) as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    self.on_event(event)

        return self.finalize()
