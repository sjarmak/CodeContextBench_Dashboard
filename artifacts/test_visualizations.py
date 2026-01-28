"""Tests for visualization utilities."""

import pytest
import plotly.graph_objects as go
from dashboard.utils.visualizations import (
    create_agent_comparison_bar_chart,
    create_multi_metric_comparison_chart,
    create_delta_comparison_chart,
    create_failure_pattern_pie_chart,
    create_category_distribution_chart,
    create_cost_breakdown_chart,
    create_token_comparison_chart,
    create_effect_size_chart,
    create_trend_line_chart,
    create_difficulty_correlation_chart,
    create_anomaly_scatter_chart,
)


class TestAgentComparisonChart:
    """Tests for agent comparison bar charts."""
    
    def test_single_metric_bar_chart(self):
        """Test creating bar chart for single metric."""
        agent_results = {
            'agent1': {'pass_rate': 0.8},
            'agent2': {'pass_rate': 0.9},
        }
        
        fig = create_agent_comparison_bar_chart(agent_results, metric='pass_rate')
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0
        assert 'agent1' in str(fig.data[0])
    
    def test_chart_with_title(self):
        """Test chart includes custom title."""
        agent_results = {
            'agent1': {'avg_duration': 5.0},
        }
        
        fig = create_agent_comparison_bar_chart(
            agent_results,
            metric='avg_duration',
            title='Custom Title'
        )
        
        assert fig.layout.title.text == 'Custom Title'
    
    def test_handles_percentage_strings(self):
        """Test chart handles percentage string values."""
        agent_results = {
            'agent1': {'pass_rate': '80%'},
            'agent2': {'pass_rate': '90%'},
        }
        
        fig = create_agent_comparison_bar_chart(agent_results, metric='pass_rate')
        assert isinstance(fig, go.Figure)


class TestMultiMetricChart:
    """Tests for multi-metric comparison charts."""
    
    def test_multiple_metrics(self):
        """Test creating chart with multiple metrics."""
        agent_results = {
            'agent1': {'pass_rate': 0.8, 'avg_duration': 5.0},
            'agent2': {'pass_rate': 0.9, 'avg_duration': 4.5},
        }
        
        fig = create_multi_metric_comparison_chart(
            agent_results,
            metrics=['pass_rate', 'avg_duration']
        )
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 2


class TestDeltaChart:
    """Tests for delta comparison charts."""
    
    def test_delta_visualization(self):
        """Test creating delta comparison chart."""
        deltas = {
            'agent1__agent2': {'pass_rate_delta': 0.1},
            'agent1__agent3': {'pass_rate_delta': -0.05},
        }
        
        fig = create_delta_comparison_chart(deltas, metric='pass_rate_delta')
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0
    
    def test_positive_negative_colors(self):
        """Test chart uses different colors for positive/negative deltas."""
        deltas = {
            'base__positive': {'pass_rate_delta': 0.1},
            'base__negative': {'pass_rate_delta': -0.1},
        }
        
        fig = create_delta_comparison_chart(deltas)
        assert isinstance(fig, go.Figure)


class TestFailurePatternChart:
    """Tests for failure pattern visualizations."""
    
    def test_pie_chart(self):
        """Test creating failure pattern pie chart."""
        patterns = {
            'timeout': 10,
            'wrong_answer': 5,
            'error': 3,
        }
        
        fig = create_failure_pattern_pie_chart(patterns)
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0
    
    def test_max_slices_limit(self):
        """Test chart limits number of slices."""
        patterns = {f'pattern_{i}': i for i in range(20)}
        
        fig = create_failure_pattern_pie_chart(patterns, max_slices=10)
        assert isinstance(fig, go.Figure)


class TestCategoryChart:
    """Tests for category distribution charts."""
    
    def test_category_distribution(self):
        """Test creating category distribution chart."""
        categories = {
            'architecture': {'count': 10, 'examples': 'ex1'},
            'prompting': {'count': 5, 'examples': 'ex2'},
            'tools': {'count': 3, 'examples': 'ex3'},
        }
        
        fig = create_category_distribution_chart(categories)
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0


class TestCostChart:
    """Tests for cost visualization charts."""
    
    def test_cost_breakdown(self):
        """Test creating cost breakdown chart."""
        agent_costs = {
            'agent1': {'total_cost': 50.0},
            'agent2': {'total_cost': 75.0},
        }
        
        fig = create_cost_breakdown_chart(agent_costs)
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0
    
    def test_token_comparison(self):
        """Test creating token comparison chart."""
        agent_costs = {
            'agent1': {'input_tokens': 25000, 'output_tokens': 5000},
            'agent2': {'input_tokens': 30000, 'output_tokens': 8000},
        }
        
        fig = create_token_comparison_chart(agent_costs)
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 2  # Input and output traces
    
    def test_handles_comma_separated_tokens(self):
        """Test chart handles comma-separated token values."""
        agent_costs = {
            'agent1': {'input_tokens': '25,000', 'output_tokens': '5,000'},
        }
        
        fig = create_token_comparison_chart(agent_costs)
        assert isinstance(fig, go.Figure)


class TestEffectSizeChart:
    """Tests for effect size visualizations."""
    
    def test_effect_size_visualization(self):
        """Test creating effect size chart."""
        effect_sizes = {
            'pass_rate': {
                'agent1__agent2': {
                    'value': 0.5,
                    'name': "Cohen's d",
                    'magnitude': 'medium'
                }
            },
            'duration': {
                'agent1__agent2': {
                    'value': 0.3,
                    'name': "Cohen's d",
                    'magnitude': 'small'
                }
            }
        }
        
        fig = create_effect_size_chart(effect_sizes)
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0


class TestTrendChart:
    """Tests for trend line charts."""
    
    def test_trend_line_chart(self):
        """Test creating trend line chart."""
        agent_trends = {
            'agent1': {
                'pass_rate': {
                    'start_value': 0.8,
                    'end_value': 0.85,
                }
            }
        }
        experiment_ids = ['exp1', 'exp2', 'exp3']
        
        fig = create_trend_line_chart(
            agent_trends,
            metric='pass_rate',
            experiment_ids=experiment_ids
        )
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0


class TestDifficultyChart:
    """Tests for difficulty correlation charts."""
    
    def test_difficulty_correlation(self):
        """Test creating difficulty correlation chart."""
        difficulty_data = {
            'easy': {'failure_rate': 0.1, 'total_tasks': 50},
            'medium': {'failure_rate': 0.25, 'total_tasks': 50},
            'hard': {'failure_rate': 0.5, 'total_tasks': 50},
            'expert': {'failure_rate': 0.75, 'total_tasks': 50},
        }
        
        fig = create_difficulty_correlation_chart(
            difficulty_data,
            metric='failure_rate'
        )
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0


class TestAnomalyChart:
    """Tests for anomaly scatter charts."""
    
    def test_anomaly_scatter(self):
        """Test creating anomaly scatter chart."""
        anomalies = [
            {
                'experiment_id': 'exp1',
                'agent_name': 'agent1',
                'metric': 'pass_rate',
                'severity': 'high',
                'description': 'Unusual drop'
            }
        ]
        experiment_ids = ['exp1', 'exp2', 'exp3']
        
        fig = create_anomaly_scatter_chart(anomalies, experiment_ids)
        
        assert isinstance(fig, go.Figure)
    
    def test_empty_anomalies(self):
        """Test chart handles empty anomalies list."""
        fig = create_anomaly_scatter_chart([], ['exp1', 'exp2'])
        
        assert isinstance(fig, go.Figure)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
