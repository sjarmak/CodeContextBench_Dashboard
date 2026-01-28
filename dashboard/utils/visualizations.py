"""
Visualization utilities for dashboard views.

Provides Plotly-based chart functions for common analysis visualizations.
All charts support filtered data and update when filters change.
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


def create_agent_comparison_bar_chart(
    agent_results: Dict[str, Dict[str, Any]],
    metric: str = "pass_rate",
    title: Optional[str] = None
) -> go.Figure:
    """
    Create bar chart comparing agents on a single metric.
    
    Args:
        agent_results: Dict mapping agent names to metric dicts
        metric: Metric name to display (pass_rate, avg_duration, mcp_calls, etc.)
        title: Chart title (auto-generated if None)
        
    Returns:
        Plotly Figure object
    """
    agents = []
    values = []
    
    for agent_name, result in agent_results.items():
        agents.append(agent_name)
        value = result.get(metric, 0)
        # Handle percentage values
        if isinstance(value, str) and '%' in value:
            value = float(value.rstrip('%')) / 100
        elif isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                value = 0
        values.append(value)
    
    df = pd.DataFrame({
        "Agent": agents,
        metric: values
    })
    
    fig = px.bar(
        df,
        x="Agent",
        y=metric,
        title=title or f"{metric.replace('_', ' ').title()} by Agent",
        labels={metric: metric.replace('_', ' ').title()},
        color="Agent",
        hover_data={metric: ":.4f"}
    )
    
    fig.update_layout(
        hovermode="x unified",
        showlegend=False,
    )
    
    return fig


def create_multi_metric_comparison_chart(
    agent_results: Dict[str, Dict[str, Any]],
    metrics: List[str],
    title: Optional[str] = None
) -> go.Figure:
    """
    Create grouped bar chart comparing multiple metrics across agents.
    
    Args:
        agent_results: Dict mapping agent names to metric dicts
        metrics: List of metrics to compare
        title: Chart title
        
    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    
    for metric in metrics:
        agents = []
        values = []
        
        for agent_name, result in agent_results.items():
            agents.append(agent_name)
            value = result.get(metric, 0)
            if isinstance(value, str) and '%' in value:
                value = float(value.rstrip('%'))
            elif isinstance(value, str):
                try:
                    value = float(value)
                except ValueError:
                    value = 0
            values.append(value)
        
        fig.add_trace(go.Bar(
            x=agents,
            y=values,
            name=metric.replace('_', ' ').title()
        ))
    
    fig.update_layout(
        title=title or "Multi-Metric Agent Comparison",
        barmode="group",
        hovermode="x unified",
        xaxis_title="Agent",
        yaxis_title="Value"
    )
    
    return fig


def create_delta_comparison_chart(
    deltas: Dict[str, Dict[str, Any]],
    metric: str = "pass_rate_delta",
    title: Optional[str] = None
) -> go.Figure:
    """
    Create bar chart showing deltas (differences) from baseline.
    
    Args:
        deltas: Dict mapping comparison pairs to delta dicts
        metric: Delta metric to display
        title: Chart title
        
    Returns:
        Plotly Figure object
    """
    comparisons = []
    values = []
    colors = []
    
    for comparison, delta_info in deltas.items():
        # Extract agent names from comparison key (baseline__variant)
        if "__" in comparison:
            variant = comparison.split("__")[1]
        else:
            variant = comparison
        
        comparisons.append(variant)
        value = delta_info.get(metric, 0)
        
        if isinstance(value, str) and '%' in value:
            value = float(value.rstrip('%+'))
        elif isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                value = 0
        
        values.append(value)
        # Color based on positive/negative delta
        colors.append("green" if value > 0 else "darkgray" if value < 0 else "gray")
    
    df = pd.DataFrame({
        "Agent": comparisons,
        metric: values,
        "color": colors
    })
    
    fig = px.bar(
        df,
        x="Agent",
        y=metric,
        title=title or f"{metric.replace('_', ' ').title()} vs Baseline",
        labels={metric: metric.replace('_', ' ').title()},
        color="color",
        color_discrete_map={"green": "#2ecc71", "darkgray": "#555555", "gray": "#95a5a6"}
    )
    
    fig.update_layout(
        hovermode="x unified",
        showlegend=False,
    )
    
    return fig


def create_failure_pattern_pie_chart(
    patterns: Dict[str, int],
    title: Optional[str] = None,
    max_slices: int = 10
) -> go.Figure:
    """
    Create pie chart of failure patterns.
    
    Args:
        patterns: Dict mapping pattern names to counts
        title: Chart title
        max_slices: Maximum number of slices to show
        
    Returns:
        Plotly Figure object
    """
    # Sort and limit to top N patterns
    sorted_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)
    if len(sorted_patterns) > max_slices:
        sorted_patterns = sorted_patterns[:max_slices]
    
    labels, values = zip(*sorted_patterns)
    
    fig = px.pie(
        values=values,
        names=labels,
        title=title or "Failure Pattern Distribution",
    )
    
    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>"
    )
    
    return fig


def create_category_distribution_chart(
    categories: Dict[str, Dict[str, Any]],
    title: Optional[str] = None
) -> go.Figure:
    """
    Create bar chart of failure categories by count.
    
    Args:
        categories: Dict mapping category names to info dicts (with 'count' key)
        title: Chart title
        
    Returns:
        Plotly Figure object
    """
    cat_names = []
    counts = []
    
    for cat_name, cat_info in categories.items():
        cat_names.append(cat_name)
        counts.append(cat_info.get('count', 0))
    
    df = pd.DataFrame({
        "Category": cat_names,
        "Count": counts
    })
    
    # Sort by count
    df = df.sort_values("Count", ascending=False)
    
    fig = px.bar(
        df,
        x="Category",
        y="Count",
        title=title or "Failure Categories",
        color="Count",
        color_continuous_scale="Viridis"
    )
    
    fig.update_layout(
        hovermode="x unified",
        xaxis_tickangle=-45
    )
    
    return fig


def create_cost_breakdown_chart(
    agent_costs: Dict[str, Dict[str, Any]],
    cost_metric: str = "total_cost",
    title: Optional[str] = None
) -> go.Figure:
    """
    Create bar chart comparing costs across agents.
    
    Args:
        agent_costs: Dict mapping agent names to cost dicts
        cost_metric: Cost metric to display (total_cost, cost_per_success, etc.)
        title: Chart title
        
    Returns:
        Plotly Figure object
    """
    agents = []
    costs = []
    
    for agent_name, cost_info in agent_costs.items():
        agents.append(agent_name)
        cost = cost_info.get(cost_metric, 0)
        
        if isinstance(cost, str) and '$' in cost:
            cost = float(cost.replace('$', ''))
        elif isinstance(cost, str):
            try:
                cost = float(cost)
            except ValueError:
                cost = 0
        
        costs.append(cost)
    
    df = pd.DataFrame({
        "Agent": agents,
        cost_metric: costs
    })
    
    # Sort by cost
    df = df.sort_values(cost_metric, ascending=False)
    
    fig = px.bar(
        df,
        x="Agent",
        y=cost_metric,
        title=title or f"{cost_metric.replace('_', ' ').title()} by Agent",
        color="Agent",
        hover_data={cost_metric: ":.2f"}
    )
    
    fig.update_layout(
        hovermode="x unified",
        showlegend=False
    )
    
    return fig


def create_token_comparison_chart(
    agent_costs: Dict[str, Dict[str, Any]],
    title: Optional[str] = None
) -> go.Figure:
    """
    Create grouped bar chart comparing input and output tokens.
    
    Args:
        agent_costs: Dict mapping agent names to cost dicts
        title: Chart title
        
    Returns:
        Plotly Figure object
    """
    agents = []
    input_tokens = []
    output_tokens = []
    
    for agent_name, cost_info in agent_costs.items():
        agents.append(agent_name)
        
        input_val = cost_info.get('input_tokens', 0)
        output_val = cost_info.get('output_tokens', 0)
        
        # Parse string values
        if isinstance(input_val, str):
            input_val = float(input_val.replace(',', ''))
        if isinstance(output_val, str):
            output_val = float(output_val.replace(',', ''))
        
        input_tokens.append(input_val)
        output_tokens.append(output_val)
    
    df = pd.DataFrame({
        "Agent": agents,
        "Input Tokens": input_tokens,
        "Output Tokens": output_tokens
    })
    
    fig = px.bar(
        df,
        x="Agent",
        y=["Input Tokens", "Output Tokens"],
        title=title or "Token Usage by Agent",
        barmode="group",
        labels={"value": "Tokens", "variable": "Token Type"}
    )
    
    fig.update_layout(
        hovermode="x unified",
    )
    
    return fig


def create_effect_size_chart(
    effect_sizes: Dict[str, Dict[str, Any]],
    title: Optional[str] = None
) -> go.Figure:
    """
    Create horizontal bar chart of effect sizes.
    
    Args:
        effect_sizes: Dict mapping metrics to effect size dicts
        title: Chart title
        
    Returns:
        Plotly Figure object
    """
    metrics = []
    values = []
    magnitudes = []
    colors_map = {
        "negligible": "#95a5a6",
        "small": "#3498db",
        "medium": "#666666",
        "large": "#555555",
        "very_large": "#444444"
    }
    
    for metric, effects in effect_sizes.items():
        for comparison, effect_info in effects.items():
            if isinstance(effect_info, dict):
                metrics.append(f"{metric}\nvs {comparison}")
                value = effect_info.get('value', 0)
                magnitude = effect_info.get('magnitude', 'negligible')
                
                if isinstance(value, str):
                    value = float(value)
                
                values.append(abs(value))
                magnitudes.append(magnitude)
    
    df = pd.DataFrame({
        "Metric": metrics,
        "Effect Size": values,
        "Magnitude": magnitudes
    })
    
    colors = [colors_map.get(m, "#95a5a6") for m in df["Magnitude"]]
    
    fig = px.bar(
        df,
        y="Metric",
        x="Effect Size",
        orientation="h",
        title=title or "Effect Size Analysis",
        color="Magnitude",
        color_discrete_map=colors_map,
        hover_data={"Effect Size": ":.4f"}
    )
    
    fig.update_layout(
        hovermode="y unified",
    )
    
    return fig


def create_trend_line_chart(
    agent_trends: Dict[str, Dict[str, Any]],
    metric: str,
    experiment_ids: List[str],
    title: Optional[str] = None
) -> go.Figure:
    """
    Create line chart showing metric trends over experiments.
    
    Args:
        agent_trends: Dict mapping agent names to metric trends
        metric: Metric name to plot
        experiment_ids: Ordered list of experiment IDs
        title: Chart title
        
    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    
    for agent_name, trends in agent_trends.items():
        if metric in trends:
            metric_trend = trends[metric]
            
            # Extract values - assume they're stored as start/end or as list
            start = metric_trend.get('start_value', 0)
            end = metric_trend.get('end_value', 0)
            
            # For simplicity, use start and end (full timeseries would need different data structure)
            y_values = [start, end]
            x_values = [experiment_ids[0], experiment_ids[-1]] if len(experiment_ids) > 1 else experiment_ids
            
            fig.add_trace(go.Scatter(
                x=x_values,
                y=y_values,
                mode="lines+markers",
                name=agent_name,
                hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>" + metric + ": %{y:.4f}<extra></extra>"
            ))
    
    fig.update_layout(
        title=title or f"{metric.replace('_', ' ').title()} Trends",
        xaxis_title="Experiment",
        yaxis_title=metric.replace('_', ' ').title(),
        hovermode="x unified"
    )
    
    return fig


def create_difficulty_correlation_chart(
    difficulty_data: Dict[str, Dict[str, Any]],
    metric: str = "failure_rate",
    title: Optional[str] = None
) -> go.Figure:
    """
    Create bar chart showing correlation between difficulty and a metric.
    
    Args:
        difficulty_data: Dict mapping difficulty levels to metric dicts
        metric: Metric to display (failure_rate, avg_duration, etc.)
        title: Chart title
        
    Returns:
        Plotly Figure object
    """
    difficulties = []
    values = []
    
    # Define order for difficulty levels
    difficulty_order = ["easy", "medium", "hard", "expert"]
    
    for diff in difficulty_order:
        if diff in difficulty_data:
            difficulties.append(diff.title())
            value = difficulty_data[diff].get(metric, 0)
            
            if isinstance(value, str) and '%' in value:
                value = float(value.rstrip('%'))
            elif isinstance(value, str):
                try:
                    value = float(value)
                except ValueError:
                    value = 0
            
            values.append(value)
    
    df = pd.DataFrame({
        "Difficulty": difficulties,
        metric: values
    })
    
    fig = px.bar(
        df,
        x="Difficulty",
        y=metric,
        title=title or f"{metric.replace('_', ' ').title()} by Difficulty",
        color=metric,
        color_continuous_scale="RdYlGn_r"
    )
    
    fig.update_layout(
        hovermode="x unified",
    )
    
    return fig


def create_anomaly_scatter_chart(
    anomalies: List[Dict[str, Any]],
    experiment_ids: List[str],
    title: Optional[str] = None
) -> go.Figure:
    """
    Create scatter plot highlighting anomalies in time series.
    
    Args:
        anomalies: List of anomaly dicts with experiment_id, metric, severity
        experiment_ids: List of experiment IDs for x-axis
        title: Chart title
        
    Returns:
        Plotly Figure object
    """
    if not anomalies:
        # Return empty chart if no anomalies
        fig = go.Figure()
        fig.add_annotation(text="No anomalies detected")
        return fig
    
    experiments = []
    metrics = []
    severities = []
    descriptions = []
    
    severity_colors = {
        "low": "#3498db",
        "medium": "#666666",
        "high": "#555555"
    }
    
    for anomaly in anomalies:
        exp_id = anomaly.get("experiment_id", "unknown")
        
        # Try to match experiment ID to index
        try:
            exp_idx = experiment_ids.index(exp_id)
        except (ValueError, IndexError):
            exp_idx = 0
        
        experiments.append(exp_id)
        metrics.append(anomaly.get("metric", "unknown"))
        severity = anomaly.get("severity", "medium")
        severities.append(severity)
        descriptions.append(anomaly.get("description", ""))
    
    df = pd.DataFrame({
        "Experiment": experiments,
        "Metric": metrics,
        "Severity": severities,
        "Description": descriptions
    })
    
    fig = px.scatter(
        df,
        x="Experiment",
        y="Metric",
        color="Severity",
        size=[5]*len(df),  # Constant size
        title=title or "Detected Anomalies",
        color_discrete_map=severity_colors,
        hover_data={"Description": True, "Severity": True}
    )
    
    fig.update_layout(
        hovermode="closest",
    )
    
    return fig


def create_precision_recall_chart(
    ir_results: Dict[str, Dict[str, Any]],
    title: Optional[str] = None
) -> go.Figure:
    """
    Create scatter plot of precision vs recall for IR tools.
    
    Args:
        ir_results: Dict mapping IR tool names to metric dicts
        title: Chart title
        
    Returns:
        Plotly Figure object
    """
    tools = []
    precisions = []
    recalls = []
    
    for tool_name, metrics in ir_results.items():
        tools.append(tool_name.replace("_", " ").title())
        precisions.append(metrics.get('precision_at_k', 0))
        recalls.append(metrics.get('recall_at_k', 0))
    
    df = pd.DataFrame({
        "IR Tool": tools,
        "Precision@K": precisions,
        "Recall@K": recalls
    })
    
    fig = px.scatter(
        df,
        x="Recall@K",
        y="Precision@K",
        text="IR Tool",
        title=title or "Precision vs Recall by IR Tool",
        size_max=50,
        hover_data={"IR Tool": True, "Precision@K": ":.3f", "Recall@K": ":.3f"}
    )
    
    fig.update_traces(textposition='top center')
    fig.update_layout(
        hovermode="closest",
        xaxis_title="Recall@K",
        yaxis_title="Precision@K",
    )
    
    return fig


def create_ir_impact_chart(
    ir_impact: Dict[str, Any],
    title: Optional[str] = None
) -> go.Figure:
    """
    Create bar chart showing IR tool impact on agent success rate.
    
    Args:
        ir_impact: Dict with agents and their IR tool results
        title: Chart title
        
    Returns:
        Plotly Figure object
    """
    agents = []
    success_rates = []
    
    agent_data = ir_impact.get("agents", {})
    for agent_name, metrics in agent_data.items():
        agents.append(agent_name)
        success_rates.append(metrics.get('success_rate', 0) * 100)
    
    df = pd.DataFrame({
        "Agent": agents,
        "Success Rate (%)": success_rates
    })
    
    fig = px.bar(
        df,
        x="Agent",
        y="Success Rate (%)",
        title=title or "IR Tool Impact on Agent Success Rate",
        color="Agent",
        hover_data={"Success Rate (%)": ":.1f"}
    )
    
    fig.update_layout(
        hovermode="x unified",
        showlegend=False,
    )
    
    return fig


def create_mrr_ndcg_chart(
    ir_results: Dict[str, Dict[str, Any]],
    title: Optional[str] = None
) -> go.Figure:
    """
    Create bar chart comparing MRR and NDCG metrics across IR tools.
    
    Args:
        ir_results: Dict mapping IR tool names to metric dicts
        title: Chart title
        
    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    
    tools = [tool.replace("_", " ").title() for tool in ir_results.keys()]
    mrr_values = [ir_results[tool].get('mrr', 0) for tool in ir_results.keys()]
    ndcg_values = [ir_results[tool].get('ndcg', 0) for tool in ir_results.keys()]
    
    fig.add_trace(go.Bar(
        x=tools,
        y=mrr_values,
        name="MRR",
        hovertemplate="%{x}<br>MRR: %{y:.3f}<extra></extra>"
    ))
    
    fig.add_trace(go.Bar(
        x=tools,
        y=ndcg_values,
        name="NDCG",
        hovertemplate="%{x}<br>NDCG: %{y:.3f}<extra></extra>"
    ))
    
    fig.update_layout(
        title=title or "MRR vs NDCG by IR Tool",
        xaxis_title="IR Tool",
        yaxis_title="Score",
        barmode="group",
        hovermode="x unified",
    )
    
    return fig
