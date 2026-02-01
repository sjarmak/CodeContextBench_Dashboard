"""IR-SDLC Analysis View - Evaluate IR tool impact on agent performance."""

import streamlit as st
import pandas as pd
from typing import Dict, Any

from dashboard.utils.view_base import ViewBase
from dashboard.utils.result_extractors import extract_ir_metrics
from dashboard.utils.visualizations import (
    create_agent_comparison_bar_chart,
    create_precision_recall_chart,
    create_ir_impact_chart,
    create_mrr_ndcg_chart,
)
from dashboard.utils.common_components import display_summary_card


class IRASDLCAnalysisView(ViewBase):
    """Analysis view for IR-SDLC (Information Retrieval SDLC) metrics."""
    
    def __init__(self):
        super().__init__("IR-SDLC Analysis", "ir_sdlc")
        self.baseline_ir_tool = "none"
        self.comparison_ir_tools = []
    
    @property
    def title(self) -> str:
        return "IR-SDLC Analysis"
    
    @property
    def subtitle(self) -> str:
        return "**Evaluate Information Retrieval tool impact on agent performance**"
    
    def configure_sidebar(self):
        """Configure IR-specific sidebar options."""
        st.markdown("**IR Tool Configuration**")
        
        self.baseline_ir_tool = st.selectbox(
            "Baseline IR Tool",
            ["none", "keyword_search", "deepsearch", "deepsearch_focused"],
            help="Reference IR tool to compare against"
        )
        
        available_tools = ["keyword_search", "deepsearch", "deepsearch_focused"]
        self.comparison_ir_tools = st.multiselect(
            "Compare Against",
            available_tools,
            default=available_tools,
            help="Which IR tools to include in comparison"
        )
    
    def load_analysis(self):
        """Load IR-SDLC analysis from loader."""
        return self.loader.load_ir_analysis(
            self.experiment_id,
            baseline_agent=self.baseline_ir_tool,
        )
    
    def extract_metrics(self, result) -> Dict[str, Any]:
        """Extract IR metrics into filterable format."""
        return extract_ir_metrics(result)
    
    def render_main_content(self, data: Dict[str, Any]):
        """Render IR-SDLC-specific content."""
        
        # Summary metrics
        st.subheader("IR Metrics Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            display_summary_card(
                "Baseline IR Tool",
                self.baseline_ir_tool.replace("_", " ").title(),
                color="blue"
            )
        
        with col2:
            display_summary_card(
                "Comparison Tools",
                str(len(self.comparison_ir_tools)),
                color="blue"
            )
        
        with col3:
            avg_precision = data.get("avg_precision_at_k", 0)
            display_summary_card(
                "Avg Precision@K",
                f"{avg_precision:.3f}",
                color="green" if avg_precision > 0.5 else "orange"
            )
        
        with col4:
            avg_recall = data.get("avg_recall_at_k", 0)
            display_summary_card(
                "Avg Recall@K",
                f"{avg_recall:.3f}",
                color="green" if avg_recall > 0.5 else "orange"
            )
        
        st.markdown("---")
        
        # IR Tool Performance Metrics Table
        st.subheader("IR Tool Performance Comparison")
        try:
            ir_results = data.get("ir_tool_results", {})
            if ir_results:
                table_data = []
                for tool, metrics in ir_results.items():
                    table_data.append({
                        "IR Tool": tool.replace("_", " ").title(),
                        "Precision@K": f"{metrics.get('precision_at_k', 0):.3f}",
                        "Recall@K": f"{metrics.get('recall_at_k', 0):.3f}",
                        "MRR": f"{metrics.get('mrr', 0):.3f}",
                        "NDCG": f"{metrics.get('ndcg', 0):.3f}",
                        "Avg Rank": f"{metrics.get('avg_rank', 0):.1f}",
                    })
                
                metrics_df = pd.DataFrame(table_data)
                st.dataframe(metrics_df, use_container_width=True, hide_index=True)
            else:
                st.info("No IR tool results available for this experiment.")
        except Exception as e:
            st.warning(f"Could not display IR metrics table: {e}")
        
        st.markdown("---")
        
        # IR Tool Visualizations
        st.subheader("IR Tool Analysis")
        
        try:
            ir_results = data.get("ir_tool_results", {})
            if ir_results:
                col1, col2 = st.columns(2)
                
                with col1:
                    try:
                        precision_recall_chart = create_precision_recall_chart(
                            ir_results,
                            title="Precision vs Recall"
                        )
                        st.plotly_chart(precision_recall_chart, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Could not render precision/recall chart: {e}")
                
                with col2:
                    try:
                        mrr_ndcg_chart = create_mrr_ndcg_chart(
                            ir_results,
                            title="MRR vs NDCG Comparison"
                        )
                        st.plotly_chart(mrr_ndcg_chart, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Could not render MRR/NDCG chart: {e}")
        except Exception as e:
            st.warning(f"Could not render IR visualizations: {e}")
        
        st.markdown("---")
        
        # IR Impact on Agent Performance
        st.subheader("IR Tool Impact on Agent Success")
        try:
            ir_impact = data.get("ir_impact", {})
            if ir_impact and ir_impact.get("agents"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    try:
                        impact_chart = create_ir_impact_chart(
                            ir_impact,
                            title="Success Rate by IR Tool"
                        )
                        st.plotly_chart(impact_chart, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Could not render impact chart: {e}")
                
                with col2:
                    st.markdown("""
                    **Interpretation**:
                    - **Precision@K**: Fraction of top-K results that are relevant
                    - **Recall@K**: Fraction of all relevant results in top-K
                    - **MRR**: Mean Reciprocal Rank - position of first relevant result
                    - **NDCG**: Normalized Discounted Cumulative Gain - ranking quality
                    - **Avg Rank**: Average position of relevant results
                    """)
            else:
                st.info("No IR impact data available.")
        except Exception as e:
            st.warning(f"Could not render IR impact section: {e}")
        
        st.markdown("---")
        
        # Correlation Analysis
        st.subheader("IR Metrics Correlation Analysis")
        try:
            correlation = data.get("correlation_analysis", {})
            if correlation:
                corr_data = []
                for metric_pair, corr_value in correlation.items():
                    corr_data.append({
                        "Metric Pair": metric_pair,
                        "Correlation": f"{corr_value:.3f}"
                    })
                
                if corr_data:
                    corr_df = pd.DataFrame(corr_data)
                    st.dataframe(corr_df, use_container_width=True, hide_index=True)
            else:
                st.info("No correlation analysis available.")
        except Exception as e:
            st.warning(f"Could not display correlation analysis: {e}")
        
        st.markdown("---")
        
        # Detailed Metrics
        st.subheader("Detailed IR Metrics")
        try:
            detailed = data.get("detailed_metrics", {})
            if detailed:
                for metric_name, metric_data in detailed.items():
                    with st.expander(f"({metric_name}"):
                        if isinstance(metric_data, dict):
                            metric_df = pd.DataFrame([metric_data])
                            st.dataframe(metric_df, use_container_width=True)
                        else:
                            st.write(metric_data)
            else:
                st.info("No detailed metrics available.")
        except Exception as e:
            st.warning(f"Could not display detailed metrics: {e}")
        
        st.markdown("---")
        
        # Reference Information
        st.subheader("IR-SDLC Metrics Reference")
        st.markdown("""
        ### Information Retrieval Metrics
        
        **Precision@K**: Among the top K retrieved documents, what fraction are relevant?
        - Formula: (# relevant in top K) / K
        - Higher is better
        
        **Recall@K**: What fraction of all relevant documents appear in top K?
        - Formula: (# relevant in top K) / (total # relevant)
        - Higher is better
        
        **Mean Reciprocal Rank (MRR)**: Average position of first relevant result
        - Formula: 1/rank of first relevant result
        - Higher is better (closer to 1.0 = better)
        
        **Normalized Discounted Cumulative Gain (NDCG)**: Quality-aware ranking metric
        - Accounts for position and relevance
        - Normalized to 0-1 scale
        - Higher is better
        
        ### Interpretation Guide
        
        - **Good IR Tool**: Precision > 0.7, Recall > 0.6, NDCG > 0.7
        - **Avg IR Tool**: Precision 0.5-0.7, Recall 0.4-0.6, NDCG 0.5-0.7
        - **Poor IR Tool**: Precision < 0.5, Recall < 0.4, NDCG < 0.5
        """)


def show_ir_analysis():
    """Main entry point for IR-SDLC analysis view."""
    view = IRASDLCAnalysisView()
    view.run()
