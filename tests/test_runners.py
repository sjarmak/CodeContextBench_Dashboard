"""Tests for benchmark runners and result aggregation."""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from runners.compare_results import load_harbor_results, compute_summary_stats
from runners.aggregator import load_results_from_jobs_dir, generate_aggregate_report


class TestResultLoading:
    """Tests for loading Harbor benchmark results."""
    
    @pytest.fixture
    def sample_result(self):
        """A sample Harbor result.json structure."""
        return {
            'task_name': 'test-task-001',
            'task_id': 'task-001',
            'trial_name': 'trial-1',
            'verifier_result': {
                'rewards': {
                    'reward': 1
                }
            },
            'agent_execution': {
                'duration_sec': 10.5
            },
            'patch_info': {
                'size_bytes': 2048,
                'files_changed': 3
            },
            'exception_info': None
        }
    
    @pytest.fixture
    def sample_result_with_error(self):
        """A sample Harbor result with error."""
        return {
            'task_name': 'test-task-002',
            'verifier_result': {
                'rewards': {
                    'reward': 0
                }
            },
            'agent_execution': {
                'duration_sec': 30.0
            },
            'patch_info': {
                'size_bytes': 0
            },
            'exception_info': {
                'type': 'TimeoutError',
                'message': 'Agent execution timeout after 30 seconds'
            }
        }
    
    def test_load_empty_directory(self):
        """Test loading from directory with no results."""
        with TemporaryDirectory() as tmpdir:
            results = load_harbor_results(tmpdir)
            assert results == []
    
    def test_load_single_result(self, sample_result):
        """Test loading a single result.json."""
        with TemporaryDirectory() as tmpdir:
            # Create directory structure like Harbor
            task_dir = Path(tmpdir) / "job-001" / "task-001"
            task_dir.mkdir(parents=True)
            
            result_file = task_dir / "result.json"
            result_file.write_text(json.dumps(sample_result))
            
            results = load_harbor_results(tmpdir)
            
            assert len(results) == 1
            assert results[0]['task_name'] == 'test-task-001'
            assert results[0]['success'] is True
            assert results[0]['agent_time'] == 10.5
            assert results[0]['patch_size'] == 2048
    
    def test_load_multiple_results(self, sample_result, sample_result_with_error):
        """Test loading multiple result.json files."""
        with TemporaryDirectory() as tmpdir:
            # Create multiple tasks
            for i, result_data in enumerate([sample_result, sample_result_with_error], 1):
                task_dir = Path(tmpdir) / f"job-001" / f"task-{i:03d}"
                task_dir.mkdir(parents=True)
                
                result_file = task_dir / "result.json"
                result_file.write_text(json.dumps(result_data))
            
            results = load_harbor_results(tmpdir)
            
            assert len(results) == 2
            # Check both success states
            success_states = [r['success'] for r in results]
            assert True in success_states
            assert False in success_states
            # Find the failed one
            failed = [r for r in results if not r['success']][0]
            assert failed['error_type'] == 'TimeoutError'


class TestSummaryStats:
    """Tests for computing summary statistics."""
    
    def test_empty_results(self):
        """Test stats on empty result set."""
        stats = compute_summary_stats([])
        
        assert stats['total'] == 0
        assert stats['successful'] == 0
        assert stats['accuracy'] == 0.0
        assert stats['avg_time'] == 0.0
    
    def test_single_success(self):
        """Test stats with single successful result."""
        results = [{
            'success': True,
            'agent_time': 10.0,
            'patch_size': 1024,
            'error_type': None
        }]
        
        stats = compute_summary_stats(results)
        
        assert stats['total'] == 1
        assert stats['successful'] == 1
        assert stats['accuracy'] == 100.0
        assert stats['avg_time'] == 10.0
    
    def test_mixed_results(self):
        """Test stats with mixed success/failure."""
        results = [
            {'success': True, 'agent_time': 10.0, 'patch_size': 1024, 'error_type': None},
            {'success': False, 'agent_time': 30.0, 'patch_size': 0, 'error_type': 'TimeoutError'},
            {'success': True, 'agent_time': 15.0, 'patch_size': 512, 'error_type': None},
        ]
        
        stats = compute_summary_stats(results)
        
        assert stats['total'] == 3
        assert stats['successful'] == 2
        assert stats['accuracy'] == pytest.approx(66.67, abs=0.1)
        assert stats['avg_time'] == pytest.approx(18.33, abs=0.1)
        assert stats['errors']['TimeoutError'] == 1
    
    def test_error_aggregation(self):
        """Test that errors are properly aggregated."""
        results = [
            {'success': False, 'agent_time': 30.0, 'patch_size': 0, 'error_type': 'TimeoutError'},
            {'success': False, 'agent_time': 25.0, 'patch_size': 0, 'error_type': 'TimeoutError'},
            {'success': False, 'agent_time': 5.0, 'patch_size': 0, 'error_type': 'ValueError'},
        ]
        
        stats = compute_summary_stats(results)
        
        assert stats['errors']['TimeoutError'] == 2
        assert stats['errors']['ValueError'] == 1


class TestAggregation:
    """Tests for cross-benchmark aggregation."""
    
    def test_empty_results_aggregation(self):
        """Test aggregation with no results."""
        report = generate_aggregate_report([])
        
        assert report['total_tasks'] == 0
        assert report['total_successful'] == 0
        assert report['overall_accuracy'] == 0.0
    
    def test_single_run_aggregation(self):
        """Test aggregation with single run."""
        results = [
            {'run_dir': 'baseline-001', 'task_name': 'task-001', 'success': True, 'agent_time': 10.0, 'patch_size': 1024, 'error_type': None},
            {'run_dir': 'baseline-001', 'task_name': 'task-002', 'success': False, 'agent_time': 30.0, 'patch_size': 0, 'error_type': 'TimeoutError'},
        ]
        
        report = generate_aggregate_report(results)
        
        assert report['total_tasks'] == 2
        assert report['total_successful'] == 1
        assert report['overall_accuracy'] == 50.0
        assert 'baseline-001' in report['by_run']
        assert report['by_run']['baseline-001']['accuracy'] == 50.0
    
    def test_multi_run_aggregation(self):
        """Test aggregation across multiple runs."""
        results = [
            # Baseline run
            {'run_dir': 'baseline-001', 'task_name': 'task-001', 'success': True, 'agent_time': 10.0, 'patch_size': 1024, 'error_type': None},
            {'run_dir': 'baseline-001', 'task_name': 'task-002', 'success': False, 'agent_time': 30.0, 'patch_size': 0, 'error_type': 'TimeoutError'},
            # Treatment run
            {'run_dir': 'treatment-001', 'task_name': 'task-001', 'success': True, 'agent_time': 12.0, 'patch_size': 1024, 'error_type': None},
            {'run_dir': 'treatment-001', 'task_name': 'task-002', 'success': True, 'agent_time': 15.0, 'patch_size': 512, 'error_type': None},
        ]
        
        report = generate_aggregate_report(results)
        
        assert report['total_tasks'] == 4
        assert report['total_successful'] == 3
        assert report['overall_accuracy'] == 75.0
        assert len(report['by_run']) == 2
        
        # Baseline should be 50% success
        assert report['by_run']['baseline-001']['accuracy'] == 50.0
        # Treatment should be 100% success
        assert report['by_run']['treatment-001']['accuracy'] == 100.0
    
    def test_task_consistency_detection(self):
        """Test detection of inconsistent tasks across runs."""
        results = [
            # Task-001: succeeds in baseline, fails in treatment (inconsistent)
            {'run_dir': 'baseline-001', 'task_name': 'task-001', 'success': True, 'agent_time': 10.0, 'patch_size': 1024, 'error_type': None},
            {'run_dir': 'treatment-001', 'task_name': 'task-001', 'success': False, 'agent_time': 30.0, 'patch_size': 0, 'error_type': 'TimeoutError'},
            # Task-002: succeeds in both (consistent)
            {'run_dir': 'baseline-001', 'task_name': 'task-002', 'success': True, 'agent_time': 15.0, 'patch_size': 512, 'error_type': None},
            {'run_dir': 'treatment-001', 'task_name': 'task-002', 'success': True, 'agent_time': 14.0, 'patch_size': 512, 'error_type': None},
        ]
        
        report = generate_aggregate_report(results)
        
        # Task-001 should have 50% success rate (inconsistent)
        assert report['by_task']['task-001']['success_rate'] == 50.0
        # Task-002 should have 100% success rate (consistent)
        assert report['by_task']['task-002']['success_rate'] == 100.0
