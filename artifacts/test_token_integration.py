"""Integration tests for token extraction and cost tracking workflow."""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from observability import ManifestWriter, ClaudeOutputParser


class TestTokenIntegration:
    """Integration tests for token extraction → manifest → cost calculation."""
    
    def test_full_workflow_extract_to_manifest(self):
        """Test complete workflow: extract tokens → write manifest with cost."""
        with TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            
            # Simulate Harbor result
            result_data = {
                'task_name': 'cross_file_reasoning_01',
                'task_id': 'task-001',
                'verifier_result': {'rewards': {'reward': 0.85}},
                'agent_execution': {'duration_sec': 15.5},
                'patch_info': {'size_bytes': 2048, 'files_changed': 3},
                'exception_info': None
            }
            
            # Write Harbor result
            result_file = task_dir / 'result.json'
            result_file.write_text(json.dumps(result_data))
            
            # Simulate Claude logs with token usage
            logs_dir = task_dir / 'logs' / 'agent'
            logs_dir.mkdir(parents=True)
            
            claude_output = {
                'content': [{'type': 'text', 'text': 'Here is the fix...'}],
                'usage': {'input_tokens': 2500, 'output_tokens': 1250},
                'model': 'claude-3-5-sonnet-20241022'
            }
            
            claude_log = logs_dir / 'claude.txt'
            claude_log.write_text(json.dumps(claude_output))
            
            # Extract tokens
            token_usage = ClaudeOutputParser.extract_from_task_execution(task_dir)
            assert token_usage.input_tokens == 2500
            assert token_usage.output_tokens == 1250
            
            # Write manifest with tokens
            writer = ManifestWriter(task_dir, model='claude-haiku-4-5')
            manifest_path = writer.write_manifest(
                harness_name='harbor-v1',
                agent_name='claude-baseline',
                benchmark_name='10figure',
                input_tokens=token_usage.input_tokens,
                output_tokens=token_usage.output_tokens
            )
            
            # Verify manifest contains tokens and cost
            with open(manifest_path) as f:
                manifest = json.load(f)
            
            assert manifest['result']['tokens']['input_tokens'] == 2500
            assert manifest['result']['tokens']['output_tokens'] == 1250
            assert manifest['result']['tokens']['total_tokens'] == 3750
            assert manifest['result']['cost_usd'] > 0
            
            # Verify cost calculation
            expected_cost = writer.calculate_cost(2500, 1250)
            assert manifest['result']['cost_usd'] == expected_cost
    
    def test_workflow_multiple_models(self):
        """Test token extraction with different model pricing."""
        with TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            
            # Create logs with tokens
            logs_dir = task_dir / 'logs' / 'agent'
            logs_dir.mkdir(parents=True)
            
            claude_log = logs_dir / 'claude.txt'
            claude_log.write_text(json.dumps({
                'usage': {'input_tokens': 1000, 'output_tokens': 500},
                'model': 'claude-3-5-sonnet-20241022'
            }))
            
            # Extract tokens
            token_usage = ClaudeOutputParser.extract_from_task_execution(task_dir)
            
            # Test cost calculation for different models
            models = {
                'claude-haiku-4-5': 0.002800,   # (1000 * 0.8 + 500 * 4.0) / 1M = 0.0028
                'claude-3-5-sonnet': 0.010500,  # (1000 * 3.0 + 500 * 15.0) / 1M = 0.0105
                'claude-3-opus': 0.052500,      # (1000 * 15.0 + 500 * 75.0) / 1M = 0.0525
            }
            
            for model, expected_cost in models.items():
                writer = ManifestWriter(task_dir, model=model)
                cost = writer.calculate_cost(token_usage.input_tokens, token_usage.output_tokens)
                
                # Allow small floating point differences
                assert abs(cost - expected_cost) < 0.000001, \
                    f"Model {model}: expected {expected_cost}, got {cost}"
    
    def test_workflow_handles_missing_tokens(self):
        """Test workflow gracefully handles missing token information."""
        with TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            
            # No logs directory
            # Extract should return zeros
            token_usage = ClaudeOutputParser.extract_from_task_execution(task_dir)
            assert token_usage.input_tokens == 0
            assert token_usage.output_tokens == 0
            
            # Should still be able to write manifest
            result_data = {
                'task_name': 'task_01',
                'task_id': 'task-001',
                'verifier_result': {'rewards': {'reward': 1.0}},
                'agent_execution': {'duration_sec': 10.0},
                'patch_info': {'size_bytes': 1024, 'files_changed': 1},
                'exception_info': None
            }
            
            result_file = task_dir / 'result.json'
            result_file.write_text(json.dumps(result_data))
            
            writer = ManifestWriter(task_dir)
            manifest_path = writer.write_manifest(
                'harbor-v1', 'claude-baseline', '10figure',
                input_tokens=0, output_tokens=0
            )
            
            assert manifest_path.exists()
            
            with open(manifest_path) as f:
                manifest = json.load(f)
            
            # Tokens should be zero but cost should still be calculable
            assert manifest['result']['tokens']['input_tokens'] == 0
            assert manifest['result']['cost_usd'] == 0.0
    
    def test_workflow_token_aggregation(self):
        """Test tokens are correctly aggregated in tool_profile."""
        with TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            
            # Create Harbor result
            result_data = {
                'task_name': 'task_01',
                'task_id': 'task-001',
                'verifier_result': {'rewards': {'reward': 1.0}},
                'agent_execution': {'duration_sec': 10.0},
                'patch_info': {'size_bytes': 1024, 'files_changed': 1},
                'exception_info': None
            }
            
            result_file = task_dir / 'result.json'
            result_file.write_text(json.dumps(result_data))
            
            # Write manifest with high token count
            writer = ManifestWriter(task_dir)
            manifest_path = writer.write_manifest(
                'harbor-v1', 'claude-baseline', '10figure',
                input_tokens=5000, output_tokens=2500
            )
            
            with open(manifest_path) as f:
                manifest = json.load(f)
            
            # Verify tokens aggregated in tool_profile
            assert manifest['tool_profile']['total_input_tokens'] == 5000
            assert manifest['tool_profile']['total_output_tokens'] == 2500
            assert manifest['tool_profile']['total_tokens'] == 7500
            
            # Verify tokens also in result
            assert manifest['result']['tokens']['total_tokens'] == 7500
