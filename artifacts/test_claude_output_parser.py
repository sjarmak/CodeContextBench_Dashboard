"""Tests for Claude output parser and token extraction."""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from observability.claude_output_parser import ClaudeOutputParser, ClaudeTokenUsage


class TestClaudeTokenUsage:
    """Tests for ClaudeTokenUsage dataclass."""
    
    def test_token_usage_initialization(self):
        """Test ClaudeTokenUsage dataclass initialization."""
        usage = ClaudeTokenUsage(
            input_tokens=1234,
            output_tokens=567,
            model='claude-3-5-sonnet-20241022'
        )
        
        assert usage.input_tokens == 1234
        assert usage.output_tokens == 567
        assert usage.total_tokens == 1801
        assert usage.model == 'claude-3-5-sonnet-20241022'
    
    def test_token_usage_total_tokens(self):
        """Test total_tokens property."""
        usage = ClaudeTokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150
    
    def test_token_usage_default_values(self):
        """Test default values for ClaudeTokenUsage."""
        usage = ClaudeTokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.model is None
        assert usage.total_tokens == 0


class TestClaudeOutputParser:
    """Tests for ClaudeOutputParser class."""
    
    def test_parse_json_output_valid(self):
        """Test parsing valid JSON output."""
        json_str = json.dumps({
            'content': [{'type': 'text', 'text': 'Response'}],
            'usage': {'input_tokens': 100, 'output_tokens': 50}
        })
        
        result = ClaudeOutputParser.parse_json_output(json_str)
        
        assert 'content' in result
        assert 'usage' in result
        assert result['usage']['input_tokens'] == 100
    
    def test_parse_json_output_invalid(self):
        """Test parsing invalid JSON returns empty dict."""
        invalid_json = "not valid json {{"
        result = ClaudeOutputParser.parse_json_output(invalid_json)
        
        assert result == {}
    
    def test_extract_token_usage_from_json(self):
        """Test extracting token usage from Claude JSON response."""
        claude_json = {
            'content': [{'type': 'text', 'text': 'Response'}],
            'usage': {'input_tokens': 1234, 'output_tokens': 567},
            'model': 'claude-3-5-sonnet-20241022'
        }
        
        usage = ClaudeOutputParser.extract_token_usage_from_json(claude_json)
        
        assert usage.input_tokens == 1234
        assert usage.output_tokens == 567
        assert usage.total_tokens == 1801
        assert usage.model == 'claude-3-5-sonnet-20241022'
    
    def test_extract_token_usage_missing_fields(self):
        """Test extraction when fields are missing."""
        claude_json = {
            'content': [{'type': 'text', 'text': 'Response'}]
        }
        
        usage = ClaudeOutputParser.extract_token_usage_from_json(claude_json)
        
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.model is None
    
    def test_extract_json_from_log_simple(self):
        """Test extracting JSON object from log content."""
        log_content = 'Some text before\n{"usage": {"input_tokens": 100}}\nSome text after'
        
        json_str = ClaudeOutputParser._extract_json_from_log(log_content)
        
        assert json_str is not None
        parsed = json.loads(json_str)
        assert parsed['usage']['input_tokens'] == 100
    
    def test_extract_json_from_log_nested(self):
        """Test extracting nested JSON from log."""
        log_content = '''
        Before
        {
            "content": [{"type": "text", "text": "Response"}],
            "usage": {"input_tokens": 1234, "output_tokens": 567}
        }
        After
        '''
        
        json_str = ClaudeOutputParser._extract_json_from_log(log_content)
        
        assert json_str is not None
        parsed = json.loads(json_str)
        assert parsed['usage']['input_tokens'] == 1234
        assert parsed['usage']['output_tokens'] == 567
    
    def test_extract_json_from_log_with_strings(self):
        """Test extracting JSON with string content containing braces."""
        log_content = '{"text": "code: { x = 1; }", "usage": {"input_tokens": 100}}'
        
        json_str = ClaudeOutputParser._extract_json_from_log(log_content)
        
        assert json_str is not None
        parsed = json.loads(json_str)
        assert parsed['text'] == 'code: { x = 1; }'
        assert parsed['usage']['input_tokens'] == 100
    
    def test_extract_tokens_from_text_key_value(self):
        """Test extracting tokens from key-value format."""
        text = '''
        Claude CLI output:
        input_tokens: 1234
        output_tokens: 567
        model: claude-3-5-sonnet-20241022
        '''
        
        usage = ClaudeOutputParser._extract_tokens_from_text(text)
        
        assert usage.input_tokens == 1234
        assert usage.output_tokens == 567
        assert usage.model == 'claude-3-5-sonnet-20241022'
    
    def test_extract_tokens_from_text_equals_format(self):
        """Test extracting tokens from equals format."""
        text = 'input_tokens=1234, output_tokens=567'
        
        usage = ClaudeOutputParser._extract_tokens_from_text(text)
        
        assert usage.input_tokens == 1234
        assert usage.output_tokens == 567
    
    def test_extract_tokens_from_text_case_insensitive(self):
        """Test token extraction is case-insensitive."""
        text = 'Input_Tokens: 100, Output_Tokens: 50'
        
        usage = ClaudeOutputParser._extract_tokens_from_text(text)
        
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
    
    def test_extract_tokens_from_text_no_tokens(self):
        """Test extraction returns zeros when no tokens found."""
        text = 'Some random text without token information'
        
        usage = ClaudeOutputParser._extract_tokens_from_text(text)
        
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
    
    def test_parse_claude_log_file_json_format(self):
        """Test parsing Claude log file with JSON output."""
        with TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / 'claude.txt'
            
            log_content = json.dumps({
                'content': [{'type': 'text', 'text': 'Response'}],
                'usage': {'input_tokens': 1234, 'output_tokens': 567},
                'model': 'claude-3-5-sonnet-20241022'
            })
            
            log_path.write_text(log_content)
            
            usage = ClaudeOutputParser.parse_claude_log_file(log_path)
            
            assert usage.input_tokens == 1234
            assert usage.output_tokens == 567
            assert usage.model == 'claude-3-5-sonnet-20241022'
    
    def test_parse_claude_log_file_text_format(self):
        """Test parsing Claude log file with text format."""
        with TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / 'claude.txt'
            
            log_content = '''
            Claude Code executed successfully
            input_tokens: 1234
            output_tokens: 567
            '''
            
            log_path.write_text(log_content)
            
            usage = ClaudeOutputParser.parse_claude_log_file(log_path)
            
            assert usage.input_tokens == 1234
            assert usage.output_tokens == 567
    
    def test_parse_claude_log_file_missing(self):
        """Test parsing non-existent log file."""
        log_path = Path('/nonexistent/path/claude.txt')
        
        usage = ClaudeOutputParser.parse_claude_log_file(log_path)
        
        assert usage.total_tokens == 0
    
    def test_extract_from_task_execution(self):
        """Test extracting tokens from task execution directory."""
        with TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            logs_dir = task_dir / 'logs' / 'agent'
            logs_dir.mkdir(parents=True)
            
            # Create Claude output log
            log_file = logs_dir / 'claude.txt'
            log_content = json.dumps({
                'usage': {'input_tokens': 1234, 'output_tokens': 567}
            })
            log_file.write_text(log_content)
            
            usage = ClaudeOutputParser.extract_from_task_execution(task_dir)
            
            assert usage.input_tokens == 1234
            assert usage.output_tokens == 567
    
    def test_extract_from_task_execution_no_logs(self):
        """Test extraction when task has no logs."""
        with TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            
            usage = ClaudeOutputParser.extract_from_task_execution(task_dir)
            
            assert usage.total_tokens == 0
    
    def test_extract_from_task_execution_finds_stdout(self):
        """Test extraction checks multiple log locations."""
        with TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            logs_dir = task_dir / 'logs' / 'agent'
            logs_dir.mkdir(parents=True)
            
            # Create stdout log instead of claude.txt
            log_file = logs_dir / 'stdout.log'
            log_content = 'input_tokens: 500, output_tokens: 250'
            log_file.write_text(log_content)
            
            usage = ClaudeOutputParser.extract_from_task_execution(task_dir)
            
            assert usage.input_tokens == 500
            assert usage.output_tokens == 250
    
    def test_extract_from_all_logs(self):
        """Test extracting tokens from all logs in job directory."""
        with TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            
            # Create logs for multiple tasks
            task1_logs = job_dir / 'logs' / 'task1'
            task1_logs.mkdir(parents=True)
            (task1_logs / 'claude.txt').write_text(
                json.dumps({'usage': {'input_tokens': 100, 'output_tokens': 50}})
            )
            
            task2_logs = job_dir / 'logs' / 'task2'
            task2_logs.mkdir(parents=True)
            (task2_logs / 'stdout.txt').write_text('input_tokens: 200, output_tokens: 100')
            
            result = ClaudeOutputParser.extract_from_all_logs(job_dir)
            
            assert len(result) >= 1
            # At least one task's tokens should be extracted
            token_values = [usage.total_tokens for usage in result.values()]
            assert any(total > 0 for total in token_values)


class TestClaudeOutputParserIntegration:
    """Integration tests for token extraction across full task runs."""
    
    def test_full_workflow_json_output(self):
        """Test full workflow of parsing Claude JSON output."""
        # Simulate complete Claude API response
        claude_response = {
            'id': 'msg_12345',
            'type': 'message',
            'role': 'assistant',
            'content': [
                {
                    'type': 'text',
                    'text': 'Here is the fix for the bug...\n\n```python\n# fixed code\n```'
                }
            ],
            'model': 'claude-3-5-sonnet-20241022',
            'usage': {
                'input_tokens': 2500,
                'output_tokens': 1250
            }
        }
        
        json_str = json.dumps(claude_response)
        parsed = ClaudeOutputParser.parse_json_output(json_str)
        usage = ClaudeOutputParser.extract_token_usage_from_json(parsed)
        
        assert usage.input_tokens == 2500
        assert usage.output_tokens == 1250
        assert usage.total_tokens == 3750
        assert usage.model == 'claude-3-5-sonnet-20241022'
    
    def test_mixed_log_content(self):
        """Test parsing log with mixed JSON and text content."""
        log_content = '''
        Starting Claude execution...
        {"usage": {"input_tokens": 1000, "output_tokens": 500}, "model": "claude-3-5-sonnet"}
        Execution completed.
        '''
        
        # Test that we extract JSON from mixed content
        json_str = ClaudeOutputParser._extract_json_from_log(log_content)
        assert json_str is not None
        
        parsed = json.loads(json_str)
        assert parsed['usage']['input_tokens'] == 1000
        assert parsed['usage']['output_tokens'] == 500
        assert parsed['model'] == 'claude-3-5-sonnet'
