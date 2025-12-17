#!/usr/bin/env python3
"""Parse Claude CLI output to extract token usage and costs.

Claude Code CLI with --output-format json produces structured JSON output that includes:
- Response content from the model
- Token usage metadata (input_tokens, output_tokens)
- Model information

This module extracts token usage from Claude output files and logs.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ClaudeTokenUsage:
    """Token usage extracted from Claude API response."""
    input_tokens: int = 0
    output_tokens: int = 0
    model: Optional[str] = None
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class ClaudeOutputParser:
    """Parse Claude CLI output to extract token usage and metadata."""
    
    @staticmethod
    def parse_json_output(json_str: str) -> Dict[str, Any]:
        """Parse Claude JSON output string.
        
        Claude CLI with --output-format json produces structured JSON output.
        
        Args:
            json_str: JSON string from Claude CLI output
            
        Returns:
            Parsed JSON object, or empty dict if parsing fails
        """
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {}
    
    @staticmethod
    def extract_token_usage_from_json(claude_json: Dict[str, Any]) -> ClaudeTokenUsage:
        """Extract token usage from Claude JSON response.
        
        Looks for token usage in the 'usage' field which Claude API includes:
        {
            "content": [...],
            "usage": {
                "input_tokens": 1234,
                "output_tokens": 567
            },
            "model": "claude-3-5-sonnet-20241022"
        }
        
        Args:
            claude_json: Parsed Claude JSON response
            
        Returns:
            ClaudeTokenUsage object with extracted tokens
        """
        usage_dict = claude_json.get('usage', {})
        
        return ClaudeTokenUsage(
            input_tokens=usage_dict.get('input_tokens', 0),
            output_tokens=usage_dict.get('output_tokens', 0),
            model=claude_json.get('model')
        )
    
    @staticmethod
    def parse_claude_log_file(log_path: Path) -> ClaudeTokenUsage:
        """Parse Claude CLI log file to extract token usage.
        
        The log file contains Claude CLI output which may include:
        1. JSON output (if --output-format json was used)
        2. Human-readable output with token counts
        3. Error messages
        
        Args:
            log_path: Path to claude.txt or similar log file
            
        Returns:
            ClaudeTokenUsage with extracted token counts
        """
        if not log_path.exists():
            return ClaudeTokenUsage()
        
        try:
            with open(log_path) as f:
                content = f.read()
        except Exception:
            return ClaudeTokenUsage()
        
        # Try to extract JSON-formatted output first
        json_match = ClaudeOutputParser._extract_json_from_log(content)
        if json_match:
            try:
                claude_json = json.loads(json_match)
                return ClaudeOutputParser.extract_token_usage_from_json(claude_json)
            except json.JSONDecodeError:
                pass
        
        # Fallback: try to extract token counts from human-readable output
        # Claude CLI may output token info in formats like:
        # - "Tokens used: input=1234, output=567"
        # - "input_tokens: 1234"
        # - "output_tokens: 567"
        return ClaudeOutputParser._extract_tokens_from_text(content)
    
    @staticmethod
    def _extract_json_from_log(content: str) -> Optional[str]:
        """Extract JSON object from log content.
        
        Finds the first complete JSON object in the content.
        
        Args:
            content: Log file content
            
        Returns:
            JSON string if found, None otherwise
        """
        # Try to find JSON starting with { or [
        depth = 0
        in_string = False
        escape_next = False
        start_idx = -1
        
        for i, char in enumerate(content):
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and depth > 0:
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
                        return content[start_idx:i+1]
        
        return None
    
    @staticmethod
    def _extract_tokens_from_text(content: str) -> ClaudeTokenUsage:
        """Extract token counts from human-readable text.
        
        Looks for patterns like:
        - "input_tokens: 1234"
        - "output_tokens: 567"
        - "tokens used: input=1234, output=567"
        
        Args:
            content: Text content to search
            
        Returns:
            ClaudeTokenUsage with extracted tokens (may be 0 if not found)
        """
        usage = ClaudeTokenUsage()
        
        # Pattern: "input_tokens: 1234" or "input_tokens=1234"
        input_match = re.search(r'input_tokens[:\s=]+(\d+)', content, re.IGNORECASE)
        if input_match:
            usage.input_tokens = int(input_match.group(1))
        
        # Pattern: "output_tokens: 567" or "output_tokens=567"
        output_match = re.search(r'output_tokens[:\s=]+(\d+)', content, re.IGNORECASE)
        if output_match:
            usage.output_tokens = int(output_match.group(1))
        
        # Pattern: "model: claude-3-5-sonnet-20241022" or similar
        model_match = re.search(r'model[:\s=]+([a-zA-Z0-9\-_.]+)', content, re.IGNORECASE)
        if model_match:
            usage.model = model_match.group(1)
        
        return usage
    
    @staticmethod
    def extract_from_task_execution(task_dir: Path) -> ClaudeTokenUsage:
        """Extract token usage from a completed task execution directory.
        
        Searches for Claude output in common log locations:
        - logs/agent/claude.txt
        - logs/agent/stdout.log
        - logs/agent/output.json
        
        Args:
            task_dir: Path to task execution directory
            
        Returns:
            ClaudeTokenUsage with extracted token counts
        """
        # Check common log locations
        log_paths = [
            task_dir / 'logs' / 'agent' / 'claude.txt',
            task_dir / 'logs' / 'agent' / 'stdout.log',
            task_dir / 'logs' / 'agent' / 'output.json',
            task_dir / 'logs' / 'agent.txt',
            task_dir / 'logs' / 'stdout.txt',
        ]
        
        for log_path in log_paths:
            if log_path.exists():
                usage = ClaudeOutputParser.parse_claude_log_file(log_path)
                if usage.total_tokens > 0:
                    return usage
        
        # If no token info found in logs, return empty usage
        return ClaudeTokenUsage()
    
    @staticmethod
    def extract_from_all_logs(job_dir: Path) -> Dict[str, ClaudeTokenUsage]:
        """Extract token usage from all log files in a job directory.
        
        Args:
            job_dir: Job directory containing logs
            
        Returns:
            Dictionary mapping task names to their token usage
        """
        token_usage: Dict[str, ClaudeTokenUsage] = {}
        
        logs_dir = job_dir / 'logs'
        if not logs_dir.exists():
            return token_usage
        
        # Find all agent-related log files
        for log_file in logs_dir.rglob('*'):
            if log_file.is_file() and any(x in log_file.name for x in ['claude', 'agent', 'stdout', 'output']):
                usage = ClaudeOutputParser.parse_claude_log_file(log_file)
                if usage.total_tokens > 0:
                    # Use relative path as key
                    key = str(log_file.relative_to(logs_dir))
                    token_usage[key] = usage
        
        return token_usage
