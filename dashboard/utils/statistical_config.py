"""
GUI-driven statistical analysis configuration component.

Provides Streamlit UI for configuring and running statistical analysis:
- Experiment selection (multiselect)
- Task filtering
- Significance level input
- Test type selection (t-test, Mann-Whitney, chi-squared)
- Effect size threshold configuration
- Run analysis with inline results display
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.utils.common_components import (
    display_error_message,
    display_no_data_message,
    display_summary_card,
)


# Available test types for the selector
TEST_TYPES: tuple[tuple[str, str], ...] = (
    ("t-test", "Independent samples t-test (parametric)"),
    ("mann-whitney", "Mann-Whitney U test (non-parametric)"),
    ("chi-squared", "Chi-squared test (categorical)"),
)

# Available metrics for analysis
AVAILABLE_METRICS: tuple[str, ...] = (
    "pass_rate",
    "avg_duration_seconds",
    "avg_mcp_calls",
)

# Effect size interpretation thresholds
EFFECT_SIZE_THRESHOLDS: tuple[tuple[str, float], ...] = (
    ("negligible", 0.2),
    ("small", 0.5),
    ("medium", 0.8),
    ("large", float("inf")),
)


@dataclass(frozen=True)
class StatisticalConfig:
    """Immutable configuration for statistical analysis."""

    experiment_ids: tuple[str, ...] = ()
    baseline_agent: str = ""
    significance_level: float = 0.05
    test_types: tuple[str, ...] = ("t-test",)
    effect_size_threshold: float = 0.5
    selected_metrics: tuple[str, ...] = AVAILABLE_METRICS

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "experiment_ids": list(self.experiment_ids),
            "baseline_agent": self.baseline_agent,
            "significance_level": self.significance_level,
            "test_types": list(self.test_types),
            "effect_size_threshold": self.effect_size_threshold,
            "selected_metrics": list(self.selected_metrics),
        }


def _render_experiment_selector(
    loader,
    session_key: str = "stat_config",
) -> tuple[str, ...]:
    """Render experiment multiselect.

    Args:
        loader: AnalysisLoader instance
        session_key: Session state key prefix

    Returns:
        Tuple of selected experiment IDs
    """
    experiments = loader.list_experiments()
    if not experiments:
        st.warning("No experiments found in database.")
        return ()

    selected = st.multiselect(
        "Select Experiments",
        experiments,
        default=experiments[:1] if experiments else [],
        help="Choose one or more experiments to analyze",
        key=f"{session_key}_experiments",
    )
    return tuple(selected)


def _render_baseline_selector(
    loader,
    experiment_ids: tuple[str, ...],
    session_key: str = "stat_config",
) -> str:
    """Render baseline agent selector.

    Args:
        loader: AnalysisLoader instance
        experiment_ids: Selected experiment IDs
        session_key: Session state key prefix

    Returns:
        Selected baseline agent name
    """
    all_agents: list[str] = []
    for exp_id in experiment_ids:
        agents = loader.list_agents(exp_id)
        for agent in agents:
            if agent not in all_agents:
                all_agents.append(agent)

    if not all_agents:
        st.warning("No agents found for selected experiments.")
        return ""

    selected = st.selectbox(
        "Baseline Agent",
        all_agents,
        help="Agent to compare all others against",
        key=f"{session_key}_baseline",
    )
    return selected or ""


def _render_significance_level(
    session_key: str = "stat_config",
) -> float:
    """Render significance level input.

    Args:
        session_key: Session state key prefix

    Returns:
        Selected significance level (alpha)
    """
    return st.number_input(
        "Significance Level (alpha)",
        min_value=0.001,
        max_value=0.20,
        value=0.05,
        step=0.01,
        format="%.3f",
        help="P-value threshold for statistical significance (default: 0.05)",
        key=f"{session_key}_alpha",
    )


def _render_test_type_selector(
    session_key: str = "stat_config",
) -> tuple[str, ...]:
    """Render test type multiselect.

    Args:
        session_key: Session state key prefix

    Returns:
        Tuple of selected test type identifiers
    """
    test_options = [t[0] for t in TEST_TYPES]
    test_labels = {t[0]: f"{t[0]} - {t[1]}" for t in TEST_TYPES}

    selected = st.multiselect(
        "Test Types",
        test_options,
        default=["t-test"],
        format_func=lambda x: test_labels.get(x, x),
        help="Select statistical tests to run",
        key=f"{session_key}_test_types",
    )
    return tuple(selected) if selected else ("t-test",)


def _render_effect_size_threshold(
    session_key: str = "stat_config",
) -> float:
    """Render effect size threshold slider.

    Args:
        session_key: Session state key prefix

    Returns:
        Selected effect size threshold
    """
    return st.slider(
        "Effect Size Threshold",
        min_value=0.1,
        max_value=2.0,
        value=0.5,
        step=0.1,
        help="Minimum effect size to highlight (Cohen's d / h scale: 0.2=small, 0.5=medium, 0.8=large)",
        key=f"{session_key}_effect_threshold",
    )


def _render_metric_selector(
    session_key: str = "stat_config",
) -> tuple[str, ...]:
    """Render metric selector for analysis.

    Args:
        session_key: Session state key prefix

    Returns:
        Tuple of selected metric names
    """
    selected = st.multiselect(
        "Metrics to Analyze",
        list(AVAILABLE_METRICS),
        default=list(AVAILABLE_METRICS),
        help="Select which metrics to include in the analysis",
        key=f"{session_key}_metrics",
    )
    return tuple(selected) if selected else AVAILABLE_METRICS


def render_statistical_config(
    loader,
    session_key: str = "stat_config",
) -> Optional[StatisticalConfig]:
    """Render full statistical analysis configuration panel.

    Args:
        loader: AnalysisLoader instance
        session_key: Session state key prefix

    Returns:
        StatisticalConfig if valid configuration, None otherwise
    """
    st.subheader("Configuration")

    # Experiment selection
    experiment_ids = _render_experiment_selector(loader, session_key)
    if not experiment_ids:
        return None

    # Baseline agent
    baseline_agent = _render_baseline_selector(loader, experiment_ids, session_key)
    if not baseline_agent:
        return None

    st.markdown("---")
    st.subheader("Test Parameters")

    # Significance level
    significance_level = _render_significance_level(session_key)

    # Test type selection
    test_types = _render_test_type_selector(session_key)

    # Effect size threshold
    effect_size_threshold = _render_effect_size_threshold(session_key)

    st.markdown("---")
    st.subheader("Metrics")

    # Metric selection
    selected_metrics = _render_metric_selector(session_key)

    return StatisticalConfig(
        experiment_ids=experiment_ids,
        baseline_agent=baseline_agent,
        significance_level=significance_level,
        test_types=test_types,
        effect_size_threshold=effect_size_threshold,
        selected_metrics=selected_metrics,
    )


def _build_results_dataframe(
    analysis_result,
    alpha: float,
) -> pd.DataFrame:
    """Build a DataFrame from StatisticalAnalysisResult.

    Args:
        analysis_result: StatisticalAnalysisResult from the analyzer
        alpha: Significance threshold

    Returns:
        DataFrame with test results
    """
    rows: list[dict] = []

    if hasattr(analysis_result, "tests") and analysis_result.tests:
        for variant, variant_tests in analysis_result.tests.items():
            for metric_name, test in variant_tests.items():
                p_val = test.p_value
                is_sig = p_val < alpha
                effect_d = test.effect_size.cohens_d if test.effect_size.cohens_d is not None else 0.0
                effect_v = test.effect_size.cramers_v if test.effect_size.cramers_v is not None else 0.0
                effect_val = effect_d if abs(effect_d) > abs(effect_v) else effect_v

                rows.append({
                    "Variant": variant,
                    "Metric": metric_name,
                    "Baseline Mean": round(test.baseline_mean, 4),
                    "Variant Mean": round(test.variant_mean, 4),
                    "P-Value": round(p_val, 6),
                    "Significant": "Yes" if is_sig else "No",
                    "Effect Size": round(effect_val, 4),
                    "Effect Magnitude": test.effect_size.interpretation,
                    "Power": round(test.observed_power, 4),
                    "Baseline N": test.baseline_n,
                    "Variant N": test.variant_n,
                })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def _build_effect_size_chart(
    results_df: pd.DataFrame,
    effect_threshold: float,
) -> Optional[go.Figure]:
    """Build Plotly bar chart for effect sizes.

    Args:
        results_df: DataFrame with test results
        effect_threshold: Threshold line value

    Returns:
        Plotly Figure or None if no data
    """
    if results_df.empty:
        return None

    chart_df = results_df.copy()
    chart_df["Abs Effect Size"] = chart_df["Effect Size"].abs()
    chart_df["Label"] = chart_df["Variant"] + " / " + chart_df["Metric"]

    chart_df = chart_df.sort_values("Abs Effect Size", ascending=True)

    fig = px.bar(
        chart_df,
        x="Abs Effect Size",
        y="Label",
        orientation="h",
        color="Effect Magnitude",
        color_discrete_map={
            "negligible": "#999999",
            "small": "#ffb81c",
            "medium": "#ff6b6b",
            "large": "#d62728",
        },
        title="Effect Sizes by Metric and Variant",
    )

    fig.add_vline(
        x=effect_threshold,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Threshold ({effect_threshold})",
    )

    fig.update_layout(
        showlegend=True,
        height=max(300, len(chart_df) * 40 + 100),
        yaxis_title="",
        xaxis_title="Absolute Effect Size",
    )

    return fig


def _build_pvalue_chart(
    results_df: pd.DataFrame,
    alpha: float,
) -> Optional[go.Figure]:
    """Build Plotly bar chart for p-values.

    Args:
        results_df: DataFrame with test results
        alpha: Significance threshold

    Returns:
        Plotly Figure or None if no data
    """
    if results_df.empty:
        return None

    chart_df = results_df.copy()
    chart_df["Label"] = chart_df["Variant"] + " / " + chart_df["Metric"]
    chart_df["Color"] = chart_df["P-Value"].apply(
        lambda p: "Significant" if p < alpha else "Not Significant"
    )

    chart_df = chart_df.sort_values("P-Value", ascending=False)

    fig = px.bar(
        chart_df,
        x="P-Value",
        y="Label",
        orientation="h",
        color="Color",
        color_discrete_map={
            "Significant": "#2ca02c",
            "Not Significant": "#999999",
        },
        title="P-Values by Metric and Variant",
    )

    fig.add_vline(
        x=alpha,
        line_dash="dash",
        line_color="red",
        annotation_text=f"alpha = {alpha}",
    )

    fig.update_layout(
        showlegend=True,
        height=max(300, len(chart_df) * 40 + 100),
        yaxis_title="",
        xaxis_title="P-Value",
    )

    return fig


def _build_confidence_interval_chart(
    results_df: pd.DataFrame,
) -> Optional[go.Figure]:
    """Build Plotly chart showing baseline vs variant means with error indicators.

    Args:
        results_df: DataFrame with test results

    Returns:
        Plotly Figure or None if no data
    """
    if results_df.empty:
        return None

    chart_data: list[dict] = []
    for _, row in results_df.iterrows():
        label = f"{row['Variant']} / {row['Metric']}"
        chart_data.append({
            "Label": label,
            "Group": "Baseline",
            "Mean": row["Baseline Mean"],
        })
        chart_data.append({
            "Label": label,
            "Group": "Variant",
            "Mean": row["Variant Mean"],
        })

    if not chart_data:
        return None

    chart_df = pd.DataFrame(chart_data)

    fig = px.bar(
        chart_df,
        x="Mean",
        y="Label",
        color="Group",
        orientation="h",
        barmode="group",
        color_discrete_map={
            "Baseline": "#1f77b4",
            "Variant": "#ff7f0e",
        },
        title="Baseline vs Variant Means",
    )

    fig.update_layout(
        showlegend=True,
        height=max(300, len(results_df) * 50 + 100),
        yaxis_title="",
        xaxis_title="Mean Value",
    )

    return fig


def run_and_display_results(
    loader,
    config: StatisticalConfig,
    session_key: str = "stat_config",
) -> None:
    """Run statistical analysis and display results inline.

    Args:
        loader: AnalysisLoader instance
        config: StatisticalConfig with analysis parameters
        session_key: Session state key prefix
    """
    alpha = config.significance_level

    # Run analysis for each experiment
    all_results: list = []
    all_dfs: list[pd.DataFrame] = []

    for exp_id in config.experiment_ids:
        try:
            with st.spinner(f"Analyzing {exp_id}..."):
                result = loader.load_statistical(
                    exp_id,
                    baseline_agent=config.baseline_agent,
                    confidence_level=1.0 - alpha,
                )
                all_results.append(result)

                df = _build_results_dataframe(result, alpha)
                if not df.empty:
                    df = df.copy()
                    df.insert(0, "Experiment", exp_id)
                    all_dfs.append(df)

        except Exception as exc:
            display_error_message(f"Failed to analyze {exp_id}: {exc}")

    if not all_dfs:
        display_no_data_message("No statistical results produced. Check that experiments have data.")
        return

    combined_df = pd.concat(all_dfs, ignore_index=True)

    # Filter to selected metrics
    if config.selected_metrics:
        metric_set = set(config.selected_metrics)
        combined_df = combined_df[combined_df["Metric"].isin(metric_set)]

    if combined_df.empty:
        display_no_data_message("No results for selected metrics.")
        return

    # Store results in session state
    st.session_state[f"{session_key}_results"] = combined_df
    st.session_state[f"{session_key}_config_snapshot"] = config.to_dict()

    _render_results(combined_df, config, session_key)


def _render_results(
    combined_df: pd.DataFrame,
    config: StatisticalConfig,
    session_key: str = "stat_config",
) -> None:
    """Render analysis results inline.

    Args:
        combined_df: Combined results DataFrame
        config: Analysis configuration
        session_key: Session state key prefix
    """
    alpha = config.significance_level

    # Summary cards
    st.subheader("Analysis Summary")

    total_tests = len(combined_df)
    sig_count = int((combined_df["Significant"] == "Yes").sum())
    large_effects = int(
        combined_df["Effect Magnitude"].isin(["large"]).sum()
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        display_summary_card(
            "Total Tests",
            str(total_tests),
            f"{len(config.experiment_ids)} experiment(s)",
            color="blue",
        )
    with col2:
        display_summary_card(
            "Significant Tests",
            f"{sig_count}/{total_tests}",
            f"at alpha = {alpha}",
            color="green" if sig_count > 0 else "gray",
        )
    with col3:
        display_summary_card(
            "Large Effects",
            str(large_effects),
            "Practically significant",
            color="red" if large_effects > 0 else "gray",
        )
    with col4:
        display_summary_card(
            "Baseline Agent",
            config.baseline_agent,
            f"alpha = {alpha}",
            color="blue",
        )

    st.markdown("---")

    # P-values table
    st.subheader("P-Values Table")
    st.dataframe(
        combined_df[
            ["Experiment", "Variant", "Metric", "Baseline Mean", "Variant Mean",
             "P-Value", "Significant", "Baseline N", "Variant N"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")

    # Plotly charts
    st.subheader("Effect Size Analysis")

    effect_chart = _build_effect_size_chart(combined_df, config.effect_size_threshold)
    if effect_chart is not None:
        st.plotly_chart(effect_chart, use_container_width=True)
    else:
        display_no_data_message("No effect size data to chart")

    st.markdown("---")

    st.subheader("P-Value Distribution")

    pvalue_chart = _build_pvalue_chart(combined_df, alpha)
    if pvalue_chart is not None:
        st.plotly_chart(pvalue_chart, use_container_width=True)
    else:
        display_no_data_message("No p-value data to chart")

    st.markdown("---")

    st.subheader("Confidence Intervals (Baseline vs Variant Means)")

    ci_chart = _build_confidence_interval_chart(combined_df)
    if ci_chart is not None:
        st.plotly_chart(ci_chart, use_container_width=True)
    else:
        display_no_data_message("No confidence interval data to chart")

    st.markdown("---")

    # CSV export
    st.subheader("Export Results")

    csv_data = combined_df.to_csv(index=False)
    st.download_button(
        label="Download Results as CSV",
        data=csv_data,
        file_name="statistical_analysis_results.csv",
        mime="text/csv",
        key=f"{session_key}_export_csv",
    )
