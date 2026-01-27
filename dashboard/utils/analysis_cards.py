"""
Analysis Hub card components for card-based navigation.

Provides:
- AnalysisCard dataclass for card configuration
- Status detection for each analysis type
- Card rendering as a styled HTML card with icon, title, description, and status badge
- Grid rendering for 2x3 card layout
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import streamlit as st


@dataclass(frozen=True)
class AnalysisCard:
    """Configuration for a single analysis card."""

    card_id: str
    title: str
    icon: str
    description: str
    page_name: str
    status_key: str


# Card definitions for the 6 analysis types
ANALYSIS_CARDS: tuple[AnalysisCard, ...] = (
    AnalysisCard(
        card_id="statistical",
        title="Statistical Analysis",
        icon="📊",
        description="Significance testing, effect sizes, and confidence intervals",
        page_name="Statistical Analysis",
        status_key="statistical_results",
    ),
    AnalysisCard(
        card_id="comparison",
        title="Comparison Analysis",
        icon="⚖️",
        description="Compare agent performance metrics across experiments",
        page_name="Comparison Analysis",
        status_key="comparison_results",
    ),
    AnalysisCard(
        card_id="timeseries",
        title="Time Series",
        icon="📈",
        description="Track metric trends, anomalies, and improvement rates",
        page_name="Time-Series Analysis",
        status_key="timeseries_results",
    ),
    AnalysisCard(
        card_id="cost",
        title="Cost Analysis",
        icon="💰",
        description="Token usage, cost per success, and efficiency metrics",
        page_name="Cost Analysis",
        status_key="cost_results",
    ),
    AnalysisCard(
        card_id="failure",
        title="Failure Analysis",
        icon="🔍",
        description="Failure patterns, error categories, and root causes",
        page_name="Failure Analysis",
        status_key="failure_results",
    ),
    AnalysisCard(
        card_id="llm_judge",
        title="LLM Judge",
        icon="🧑‍⚖️",
        description="LLM-based evaluation, rubric editing, and A/B comparison",
        page_name="LLM Judge",
        status_key="llm_judge_results",
    ),
)


def check_results_available(status_key: str, project_root: Optional[Path] = None) -> bool:
    """
    Check if results are available for a given analysis type.

    Checks session state for cached results and filesystem for persisted results.

    Args:
        status_key: The session state key to check for results.
        project_root: Optional project root path for filesystem checks.

    Returns:
        True if results are available, False otherwise.
    """
    if st.session_state.get(status_key):
        return True

    if project_root is None:
        return False

    result_checks = {
        "statistical_results": _check_db_has_experiments,
        "comparison_results": _check_db_has_experiments,
        "timeseries_results": _check_db_has_experiments,
        "cost_results": _check_db_has_experiments,
        "failure_results": _check_db_has_experiments,
        "llm_judge_results": _check_judge_results_exist,
    }

    checker = result_checks.get(status_key)
    if checker is not None:
        return checker(project_root)

    return False


def _check_db_has_experiments(project_root: Path) -> bool:
    """Check if the metrics database has experiments loaded."""
    loader = st.session_state.get("analysis_loader")
    if loader is None:
        return False
    try:
        experiments = loader.list_experiments()
        return len(experiments) > 0
    except Exception:
        return False


def _check_judge_results_exist(project_root: Path) -> bool:
    """Check if LLM judge results exist on disk."""
    judge_dir = project_root / "data" / "judge_results"
    if not judge_dir.exists():
        return False
    json_files = list(judge_dir.glob("*.json"))
    return len(json_files) > 0


def _render_status_badge(has_results: bool) -> str:
    """
    Render an HTML status badge.

    Args:
        has_results: Whether results are available.

    Returns:
        HTML string for the status badge.
    """
    if has_results:
        return (
            '<span style="background: #2ca02c; color: white; padding: 2px 8px; '
            'border-radius: 12px; font-size: 0.75em;">Results Available</span>'
        )
    return (
        '<span style="background: #888; color: white; padding: 2px 8px; '
        'border-radius: 12px; font-size: 0.75em;">No Results</span>'
    )


def render_analysis_card(
    card: AnalysisCard,
    has_results: bool,
    session_key: str = "current_page",
) -> None:
    """
    Render a single analysis card with icon, title, description, status, and button.

    Args:
        card: The AnalysisCard configuration.
        has_results: Whether results are available for this card.
        session_key: The session state key for page navigation.
    """
    badge_html = _render_status_badge(has_results)
    border_color = "#2ca02c" if has_results else "#ddd"

    card_html = f"""
    <div style="
        border: 1px solid {border_color};
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 8px;
        background: white;
        min-height: 140px;
    ">
        <div style="font-size: 1.8em; margin-bottom: 4px;">{card.icon}</div>
        <div style="font-size: 1.1em; font-weight: 600; margin-bottom: 4px;">{card.title}</div>
        <div style="font-size: 0.85em; color: #666; margin-bottom: 8px;">{card.description}</div>
        <div>{badge_html}</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

    if st.button(
        "Configure & Run",
        key=f"analysis_card_{card.card_id}",
        use_container_width=True,
    ):
        st.session_state[session_key] = card.page_name
        st.rerun()


def render_analysis_card_grid(
    project_root: Optional[Path] = None,
    session_key: str = "current_page",
) -> None:
    """
    Render the 2x3 grid of analysis cards.

    Args:
        project_root: Optional project root path for result status checks.
        session_key: The session state key for page navigation.
    """
    cards = ANALYSIS_CARDS
    rows = [cards[i : i + 3] for i in range(0, len(cards), 3)]

    for row in rows:
        cols = st.columns(len(row))
        for col, card in zip(cols, row):
            with col:
                has_results = check_results_available(card.status_key, project_root)
                render_analysis_card(card, has_results, session_key)
