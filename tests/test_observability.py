"""Tests for observability modules: manifest_writer and metrics_collector."""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime

from observability.manifest_writer import ManifestWriter, ToolProfile, ToolUsage
from observability.metrics_collector import MetricsCollector, ExecutionMetrics


class TestToolProfile:
    """Tests for ToolProfile dataclass."""
    
    def test_tool_profile_to_dict(self):
        """Test ToolProfile.to_dict() conversion."""
        usage = ToolUsage(
            tool_name='sourcegraph_deep_search',
            category='code_search',
            invocation_count=5,
            success_count=4,
            failure_count=1,
            avg_duration_sec=2.5
        )
        
        profile = ToolProfile(
            tool_usage={'sourcegraph': usage},
            total_tool_invocations=5,
            total_unique_tools=1,
            search_queries_count=5,
            file_operations_count=0
        )
        
        result = profile.to_dict()
        
        assert 'tool_usage' in result
        assert 'sourcegraph' in result['tool_usage']
        assert result['tool_usage']['sourcegraph']['tool_name'] == 'sourcegraph_deep_search'
        assert result['total_tool_invocations'] == 5


class TestManifestWriter:
    """Tests for ManifestWriter class."""
    
    @pytest.fixture
    def sample_result(self):
        """Sample Harbor result.json structure."""
        return {
            'task_name': 'cross_file_reasoning_01',
            'task_id': 'task-001',
            'verifier_result': {
                'rewards': {
                    'reward': 0.85
                }
            },
            'agent_execution': {
                'duration_sec': 15.5
            },
            'patch_info': {
                'size_bytes': 2048,
                'files_changed': 3
            },
            'exception_info': None
        }
    
    @pytest.fixture
    def sample_result_with_error(self):
        """Sample Harbor result with error."""
        return {
            'task_name': 'bug_localization_01',
            'task_id': 'task-002',
            'verifier_result': {
                'rewards': {
                    'reward': 0.0
                }
            },
            'agent_execution': {
                'duration_sec': 30.0
            },
            'patch_info': {
                'size_bytes': 0,
                'files_changed': 0
            },
            'exception_info': {
                'type': 'TimeoutError',
                'message': 'Agent execution timeout after 30 seconds'
            }
        }
    
    def test_parse_harbor_result_success(self, sample_result):
        """Test parsing successful Harbor result."""
        with TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            
            # Write result.json
            result_file = job_dir / 'result.json'
            result_file.write_text(json.dumps(sample_result))
            
            writer = ManifestWriter(job_dir)
            result = writer.parse_harbor_result()
            
            assert result['task_name'] == 'cross_file_reasoning_01'
            assert result['task_id'] == 'task-001'
    
    def test_parse_harbor_result_missing_file(self):
        """Test parsing when result.json doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            writer = ManifestWriter(job_dir)
            result = writer.parse_harbor_result()
            
            assert result == {}
    
    def test_build_result_summary_success(self, sample_result):
        """Test building result summary for successful execution."""
        with TemporaryDirectory() as tmpdir:
            writer = ManifestWriter(Path(tmpdir))
            summary = writer.build_result_summary(sample_result)
            
            assert summary['task_name'] == 'cross_file_reasoning_01'
            assert summary['success'] is True
            assert summary['reward'] == 0.85
            assert summary['duration_sec'] == 15.5
            assert summary['patch_size_bytes'] == 2048
            assert summary['files_changed'] == 3
            assert summary['error_type'] is None
    
    def test_build_result_summary_error(self, sample_result_with_error):
        """Test building result summary for failed execution."""
        with TemporaryDirectory() as tmpdir:
            writer = ManifestWriter(Path(tmpdir))
            summary = writer.build_result_summary(sample_result_with_error)
            
            assert summary['task_name'] == 'bug_localization_01'
            assert summary['success'] is False
            assert summary['reward'] == 0.0
            assert summary['error_type'] == 'TimeoutError'
            assert 'timeout' in summary['error_message'].lower()

    def test_build_result_summary_duration_fallback(self):
        """Test duration fallback from timestamp fields."""
        with TemporaryDirectory() as tmpdir:
            writer = ManifestWriter(Path(tmpdir))
            result = {
                'task_name': 'duration-test',
                'task_id': 'duration-test',
                'verifier_result': {'rewards': {'reward': 1.0}},
                'agent_execution': {
                    'started_at': '2025-12-22T17:50:34.000000',
                    'finished_at': '2025-12-22T17:50:44.500000'
                },
                'patch_info': {'size_bytes': 0, 'files_changed': 0},
                'exception_info': None
            }
            summary = writer.build_result_summary(result)

            assert summary['duration_sec'] == pytest.approx(10.5)
    
    def test_build_retrieval_metrics(self):
        """Test building retrieval metrics from tool profile."""
        usage = ToolUsage(
            tool_name='sourcegraph_deep_search',
            category='code_search',
            invocation_count=3
        )
        
        profile = ToolProfile(
            tool_usage={'search': usage},
            total_tool_invocations=3,
            total_unique_tools=1,
            search_queries_count=3,
            file_operations_count=2
        )
        
        with TemporaryDirectory() as tmpdir:
            writer = ManifestWriter(Path(tmpdir))
            metrics = writer.build_retrieval_metrics(profile)
            
            assert metrics['total_searches'] == 3
            assert metrics['total_file_ops'] == 2
            assert 'search' in metrics['tools_used']
            assert metrics['tool_diversity'] == 1
    
    def test_extract_tool_usage_empty_logs(self):
        """Test tool usage extraction with no logs."""
        with TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            writer = ManifestWriter(job_dir)
            profile = writer.extract_tool_usage()
            
            assert profile.total_tool_invocations == 0
            assert profile.total_unique_tools == 0

    def test_extract_tool_usage_from_sessions(self, sample_result):
        """Test tool usage extraction from agent session JSONL logs."""
        with TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            session_dir = job_dir / 'agent' / 'sessions' / 'projects' / '-app'
            session_dir.mkdir(parents=True)
            session_log = session_dir / 'agent-test.jsonl'

            events = [
                {
                    'type': 'assistant',
                    'message': {
                        'content': [
                            {
                                'type': 'tool_use',
                                'id': 'toolu_1',
                                'name': 'Grep',
                                'input': {'pattern': 'foo', 'path': '/app'}
                            }
                        ]
                    }
                },
                {
                    'type': 'user',
                    'message': {
                        'content': [
                            {
                                'type': 'tool_result',
                                'tool_use_id': 'toolu_1',
                                'content': '',
                                'is_error': False
                            }
                        ]
                    },
                    'toolUseResult': {
                        'numLines': 0,
                        'numFiles': 0,
                        'content': ''
                    }
                },
                {
                    'type': 'assistant',
                    'message': {
                        'content': [
                            {
                                'type': 'tool_use',
                                'id': 'toolu_2',
                                'name': 'Read',
                                'input': {'file_path': '/app/file.py'}
                            }
                        ]
                    }
                },
                {
                    'type': 'user',
                    'message': {
                        'content': [
                            {
                                'type': 'tool_result',
                                'tool_use_id': 'toolu_2',
                                'content': 'data',
                                'is_error': False
                            }
                        ]
                    },
                    'toolUseResult': {
                        'file': {'filePath': '/app/file.py', 'content': 'data'}
                    }
                },
                {
                    'type': 'assistant',
                    'message': {
                        'content': [
                            {
                                'type': 'tool_use',
                                'id': 'toolu_3',
                                'name': 'Bash',
                                'input': {'command': 'rg foo /app'}
                            }
                        ]
                    }
                },
                {
                    'type': 'user',
                    'message': {
                        'content': [
                            {
                                'type': 'tool_result',
                                'tool_use_id': 'toolu_3',
                                'content': 'match',
                                'is_error': False
                            }
                        ]
                    },
                    'toolUseResult': {'stdout': 'match\n', 'stderr': ''}
                },
                {
                    'type': 'assistant',
                    'message': {
                        'content': [
                            {
                                'type': 'tool_use',
                                'id': 'toolu_4',
                                'name': 'Glob',
                                'input': {'pattern': '**/*.py'}
                            }
                        ]
                    }
                },
                {
                    'type': 'user',
                    'message': {
                        'content': [
                            {
                                'type': 'tool_result',
                                'tool_use_id': 'toolu_4',
                                'content': '',
                                'is_error': False
                            }
                        ]
                    },
                    'toolUseResult': {
                        'filenames': ['/app/a.py', '/app/b.py'],
                        'numFiles': 2
                    }
                }
            ]

            session_log.write_text('\n'.join(json.dumps(e) for e in events))

            writer = ManifestWriter(job_dir)
            profile = writer.extract_tool_usage()

            assert profile.total_tool_invocations == 4
            assert profile.search_queries_count == 3
            assert profile.file_operations_count == 1

            manifest_path = writer.write_manifest(
                harness_name='harbor-v1',
                agent_name='claude-baseline',
                benchmark_name='10figure',
                override_result=sample_result
            )

            with open(manifest_path) as f:
                manifest = json.load(f)

            retrieval = manifest['retrieval_metrics']
            assert retrieval['total_searches'] == 3
            assert retrieval['search_success_count'] == 2
            assert retrieval['search_empty_count'] == 1
            assert retrieval['search_result_count'] == 3
            assert retrieval['file_read_count'] == 1
            assert retrieval['unique_files_read'] == 1
            assert '/app/file.py' in retrieval['file_read_samples']
    
    def test_write_manifest_complete(self, sample_result):
        """Test writing complete run manifest."""
        with TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            writer = ManifestWriter(job_dir)
            
            manifest_path = writer.write_manifest(
                harness_name='harbor-v1',
                agent_name='claude-baseline',
                benchmark_name='10figure',
                override_result=sample_result
            )
            
            assert manifest_path.exists()
            
            # Read and verify manifest
            with open(manifest_path) as f:
                manifest = json.load(f)
            
            assert manifest['harness']['name'] == 'harbor-v1'
            assert manifest['execution']['agent'] == 'claude-baseline'
            assert manifest['execution']['benchmark'] == '10figure'
            assert manifest['result']['task_name'] == 'cross_file_reasoning_01'
            assert manifest['result']['success'] is True
            assert 'tool_profile' in manifest
            assert 'retrieval_metrics' in manifest

    def test_write_manifest_uses_agent_result_tokens(self, sample_result):
        """Test token fallback from agent_result when tokens are missing."""
        with TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            writer = ManifestWriter(job_dir)
            result = dict(sample_result)
            result['agent_result'] = {'n_input_tokens': 10, 'n_output_tokens': 5}

            manifest_path = writer.write_manifest(
                harness_name='harbor-v1',
                agent_name='claude-baseline',
                benchmark_name='10figure',
                override_result=result
            )

            with open(manifest_path) as f:
                manifest = json.load(f)

            tokens = manifest['result']['tokens']
            assert tokens['input_tokens'] == 10
            assert tokens['output_tokens'] == 5
    
    def test_aggregate_manifests_empty(self):
        """Test aggregating empty manifest list."""
        result = ManifestWriter.aggregate_manifests([])
        
        assert result['total_runs'] == 0
        assert result['runs'] == []
        assert result['aggregate_metrics'] == {}
    
    def test_aggregate_manifests_multiple(self, sample_result):
        """Test aggregating multiple manifests."""
        with TemporaryDirectory() as tmpdir:
            # Create two job directories with manifests
            job1_dir = Path(tmpdir) / 'job1'
            job1_dir.mkdir()
            
            job2_dir = Path(tmpdir) / 'job2'
            job2_dir.mkdir()
            
            # Write manifests
            manifest1_path = job1_dir / 'run_manifest.json'
            writer1 = ManifestWriter(job1_dir)
            writer1.write_manifest(
                'harbor-v1', 'claude-baseline', '10figure',
                override_result=sample_result
            )
            
            # Create second result with different values
            result2 = sample_result.copy()
            result2['verifier_result'] = {'rewards': {'reward': 1.0}}
            result2['agent_execution'] = {'duration_sec': 10.0}
            
            manifest2_path = job2_dir / 'run_manifest.json'
            writer2 = ManifestWriter(job2_dir)
            writer2.write_manifest(
                'harbor-v1', 'claude-mcp', '10figure',
                override_result=result2
            )
            
            # Aggregate
            manifests = [manifest1_path, manifest2_path]
            aggregated = ManifestWriter.aggregate_manifests(manifests)
            
            assert aggregated['total_runs'] == 2
            assert len(aggregated['runs']) == 2
            assert aggregated['aggregate_metrics']['successful_runs'] == 2
            assert aggregated['aggregate_metrics']['success_rate'] == 100.0


class TestExecutionMetrics:
    """Tests for ExecutionMetrics dataclass."""
    
    def test_execution_metrics_success(self):
        """Test ExecutionMetrics for successful execution."""
        m = ExecutionMetrics(
            task_id='task-001',
            agent='claude-baseline',
            benchmark='10figure',
            success=True,
            reward=0.85,
            duration_sec=15.5,
            patch_size_bytes=2048,
            files_changed=3,
            error_type=None
        )
        
        assert m.task_id == 'task-001'
        assert m.success is True
        assert m.error_type is None


class TestMetricsCollector:
    """Tests for MetricsCollector class."""
    
    @pytest.fixture
    def sample_manifests(self):
        """Generate sample manifest data."""
        return [
            {
                'timestamp': datetime.now().isoformat(),
                'harness': {'name': 'harbor-v1', 'version': '1.0'},
                'execution': {'agent': 'claude-baseline', 'benchmark': '10figure'},
                'tool_profile': {
                    'tool_usage': {},
                    'total_tool_invocations': 5,
                    'total_unique_tools': 2,
                    'search_queries_count': 3,
                    'file_operations_count': 2
                },
                'result': {
                    'task_id': 'task-001',
                    'success': True,
                    'reward': 0.85,
                    'duration_sec': 15.5,
                    'patch_size_bytes': 2048,
                    'files_changed': 3,
                    'error_type': None
                },
                'retrieval_metrics': {'total_searches': 3, 'tools_used': ['search', 'file']}
            },
            {
                'timestamp': datetime.now().isoformat(),
                'harness': {'name': 'harbor-v1', 'version': '1.0'},
                'execution': {'agent': 'claude-mcp', 'benchmark': '10figure'},
                'tool_profile': {
                    'tool_usage': {},
                    'total_tool_invocations': 8,
                    'total_unique_tools': 3,
                    'search_queries_count': 5,
                    'file_operations_count': 3
                },
                'result': {
                    'task_id': 'task-002',
                    'success': True,
                    'reward': 1.0,
                    'duration_sec': 12.0,
                    'patch_size_bytes': 3072,
                    'files_changed': 4,
                    'error_type': None
                },
                'retrieval_metrics': {'total_searches': 5, 'tools_used': ['search', 'file', 'git']}
            }
        ]
    
    def test_extract_metrics(self, sample_manifests):
        """Test extracting metrics from manifests."""
        with TemporaryDirectory() as tmpdir:
            collector = MetricsCollector(Path(tmpdir))
            metrics = collector.extract_metrics(sample_manifests)
            
            assert len(metrics) == 2
            assert metrics[0].task_id == 'task-001'
            assert metrics[1].task_id == 'task-002'
            assert all(m.success for m in metrics)

    def test_extract_metrics_normalizes_task_id(self):
        """Test extracting metrics with non-string task IDs."""
        with TemporaryDirectory() as tmpdir:
            collector = MetricsCollector(Path(tmpdir))
            manifests = [
                {
                    'execution': {'agent': 'claude-mcp', 'benchmark': '10figure'},
                    'result': {
                        'task_id': {'path': 'benchmarks/big_code_mcp/big-code-vsc-001'},
                        'success': True,
                        'reward': 1.0,
                        'duration_sec': 1.0,
                        'patch_size_bytes': 0,
                        'files_changed': 0,
                        'error_type': None
                    }
                }
            ]
            metrics = collector.extract_metrics(manifests)

            assert metrics[0].task_id == 'benchmarks/big_code_mcp/big-code-vsc-001'
    
    def test_compute_summary_stats_empty(self):
        """Test summary stats on empty metrics."""
        with TemporaryDirectory() as tmpdir:
            collector = MetricsCollector(Path(tmpdir))
            stats = collector.compute_summary_stats([])
            
            assert stats['total'] == 0
            assert stats['successful'] == 0
            assert stats['success_rate'] == 0.0
            assert stats['avg_duration_sec'] == 0.0
    
    def test_compute_summary_stats(self, sample_manifests):
        """Test computing summary statistics."""
        with TemporaryDirectory() as tmpdir:
            collector = MetricsCollector(Path(tmpdir))
            metrics = collector.extract_metrics(sample_manifests)
            stats = collector.compute_summary_stats(metrics)
            
            assert stats['total'] == 2
            assert stats['successful'] == 2
            assert stats['success_rate'] == 100.0
            assert stats['avg_duration_sec'] == pytest.approx(13.75)
            assert stats['avg_patch_size_bytes'] == 2560
            assert stats['avg_files_changed'] == 3.5
    
    def test_compute_per_agent_stats(self, sample_manifests):
        """Test computing per-agent statistics."""
        with TemporaryDirectory() as tmpdir:
            collector = MetricsCollector(Path(tmpdir))
            metrics = collector.extract_metrics(sample_manifests)
            stats = collector.compute_per_agent_stats(metrics)
            
            assert 'claude-baseline' in stats
            assert 'claude-mcp' in stats
            assert stats['claude-baseline']['total'] == 1
            assert stats['claude-mcp']['total'] == 1
    
    def test_compute_per_benchmark_stats(self, sample_manifests):
        """Test computing per-benchmark statistics."""
        with TemporaryDirectory() as tmpdir:
            collector = MetricsCollector(Path(tmpdir))
            metrics = collector.extract_metrics(sample_manifests)
            stats = collector.compute_per_benchmark_stats(metrics)
            
            assert '10figure' in stats
            assert stats['10figure']['total'] == 2
            assert stats['10figure']['success_rate'] == 100.0
    
    def test_detect_regression_success(self):
        """Test regression detection for improvement."""
        baseline = [
            ExecutionMetrics('t1', 'baseline', 'bench', False, 0.0, 30.0, 0, 0, 'TimeoutError'),
            ExecutionMetrics('t2', 'baseline', 'bench', True, 1.0, 15.0, 1024, 2, None),
        ]
        
        treatment = [
            ExecutionMetrics('t1', 'treatment', 'bench', True, 1.0, 12.0, 512, 1, None),
            ExecutionMetrics('t2', 'treatment', 'bench', True, 1.0, 14.0, 1024, 2, None),
        ]
        
        with TemporaryDirectory() as tmpdir:
            collector = MetricsCollector(Path(tmpdir))
            regression = collector.detect_regression(baseline, treatment, threshold_percent=10.0)
            
            # Should detect improvement in success rate
            assert len(regression['improvements']) > 0
            assert regression['treatment_stats']['success_rate'] == 100.0
            assert regression['baseline_stats']['success_rate'] == 50.0
    
    def test_generate_report(self, sample_manifests):
        """Test generating comprehensive metrics report."""
        with TemporaryDirectory() as tmpdir:
            collector = MetricsCollector(Path(tmpdir))
            metrics = collector.extract_metrics(sample_manifests)
            report = collector.generate_report(metrics)
            
            assert 'overall' in report
            assert 'per_agent' in report
            assert 'per_benchmark' in report
            assert 'task_consistency' in report
            assert report['total_metrics'] == 2
    
    def test_write_report(self, sample_manifests):
        """Test writing metrics report to file."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            collector = MetricsCollector(tmpdir_path)
            metrics = collector.extract_metrics(sample_manifests)
            report = collector.generate_report(metrics)
            
            report_path = tmpdir_path / 'metrics_report.json'
            collector.write_report(report, report_path)
            
            assert report_path.exists()
            
            # Verify written report
            with open(report_path) as f:
                written_report = json.load(f)
            
            assert written_report['total_metrics'] == 2
            assert written_report['overall']['success_rate'] == 100.0
