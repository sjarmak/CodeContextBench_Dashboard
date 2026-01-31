"""
Analysis Hub - Entry point for Phase 4 analysis components.

Provides:
- Auto-ingestion of results from external jobs directory
- Database connectivity status
- Tabbed interface embedding all analysis views:
  Overview, Comparison, Statistical, Time-Series, Cost, Failure
"""

import streamlit as st
from pathlib import Path
import os

from dashboard.utils.analysis_cards import render_analysis_card_grid
from dashboard.utils.analysis_loader import AnalysisLoader, DatabaseNotFoundError


# External runs directory - same as run_results
EXTERNAL_RUNS_DIR = Path(os.environ.get(
    "CCB_EXTERNAL_RUNS_DIR",
    os.path.expanduser("~/evals/custom_agents/agents/claudecode/runs")
))


def auto_ingest_if_needed(db_path: Path, project_root: Path) -> tuple[bool, str]:
    """
    Auto-ingest results from external jobs directory if database is missing or empty.

    Returns:
        Tuple of (success, message)
    """
    try:
        from src.ingest.orchestrator import IngestionOrchestrator

        db_path.parent.mkdir(parents=True, exist_ok=True)

        if not EXTERNAL_RUNS_DIR.exists():
            return False, f"External runs directory not found: {EXTERNAL_RUNS_DIR}"

        experiment_dirs = [
            d for d in EXTERNAL_RUNS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith('.') and (d / "result.json").exists()
        ]

        if not experiment_dirs:
            return False, "No experiments found in external runs directory"

        orchestrator = IngestionOrchestrator(
            db_path=db_path,
            results_dir=EXTERNAL_RUNS_DIR,
        )

        total_results = 0
        for exp_dir in experiment_dirs:
            try:
                stats = orchestrator.ingest_experiment(
                    experiment_id=exp_dir.name,
                    results_dir=exp_dir,
                )
                total_results += stats.get("results_processed", 0)
            except Exception as e:
                st.warning(f"Failed to ingest {exp_dir.name}: {e}")

        return True, f"Ingested {total_results} results from {len(experiment_dirs)} experiments"

    except ImportError as e:
        return False, f"Ingest module not available: {e}"
    except Exception as e:
        return False, f"Auto-ingest failed: {e}"


def _init_loader() -> bool:
    """Initialize analysis loader and database. Returns True if successful."""
    project_root = st.session_state.get("project_root", Path(__file__).parent.parent.parent)
    db_path = project_root / "data" / "metrics.db"

    db_exists = db_path.exists()

    col1, col2, col3 = st.columns(3)

    with col1:
        if not db_exists:
            st.info("Database not found. Auto-ingesting results...")
            success, message = auto_ingest_if_needed(db_path, project_root)
            if success:
                st.success(f"✓ {message}")
            else:
                st.warning(message)
                st.caption(f"Expected database at: {db_path}")
                return False

        try:
            loader = AnalysisLoader(db_path)
            st.session_state.analysis_loader = loader

            if loader.is_healthy():
                st.success("✓ Database Connected")
            else:
                st.error("✗ Database Unhealthy")
        except DatabaseNotFoundError:
            st.error("✗ Database Not Found")
            st.caption(f"Expected at: {db_path}")
            return False

    with col2:
        try:
            stats = loader.get_stats()
            if stats and 'harbor' in stats:
                task_count = stats['harbor'].get('total_tasks', 0)
                st.metric("Tasks Processed", task_count)
            else:
                st.metric("Tasks Processed", "N/A")
        except Exception:
            st.metric("Tasks Processed", "N/A")

    with col3:
        try:
            experiments = loader.list_experiments()
            st.metric("Experiments", len(experiments))
        except Exception:
            st.metric("Experiments", "N/A")

    if st.button("Re-ingest Results", help="Re-scan external jobs directory and update database"):
        with st.spinner("Ingesting results..."):
            success, message = auto_ingest_if_needed(db_path, project_root)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    st.caption(f"Results from: {EXTERNAL_RUNS_DIR}")
    return True


def _render_overview_tab():
    """Render the Overview tab with experiment list and analysis cards."""
    project_root = st.session_state.get("project_root", Path(__file__).parent.parent.parent)
    loader = st.session_state.get("analysis_loader")

    st.subheader("Available Experiments")

    try:
        experiments = loader.list_experiments()

        if experiments:
            exp_data = []
            for exp_id in experiments:
                try:
                    agents = loader.list_agents(exp_id)
                    exp_data.append({
                        "Experiment": exp_id,
                        "Agents": len(agents),
                        "Agent List": ", ".join(agents) if agents else "N/A"
                    })
                except Exception as e:
                    exp_data.append({
                        "Experiment": exp_id,
                        "Agents": "Error",
                        "Agent List": str(e)
                    })

            st.dataframe(exp_data, use_container_width=True, hide_index=True)
        else:
            st.info("No experiments found. Run `ccb ingest` to populate the database.")
    except Exception as e:
        st.error(f"Failed to load experiments: {e}")

    st.markdown("---")

    st.subheader("Analysis Components")
    st.caption("Use the tabs above to configure and run each analysis type.")
    render_analysis_card_grid(project_root=project_root, tab_mode=True)


def show_analysis_hub():
    """Display the Analysis Hub page with tabbed analysis views."""

    st.title("Analysis Hub")
    st.markdown("**Comprehensive experiment analysis with Phase 4 components**")
    st.markdown("---")

    if not _init_loader():
        return

    st.markdown("---")

    # Tabbed interface for all analysis views
    tab_overview, tab_comparison, tab_statistical, tab_timeseries, tab_cost, tab_failure = st.tabs([
        "Overview",
        "Comparison",
        "Statistical",
        "Time-Series",
        "Cost",
        "Failure",
    ])

    with tab_overview:
        _render_overview_tab()

    with tab_comparison:
        from dashboard.views.analysis_comparison import show_comparison_analysis
        show_comparison_analysis()

    with tab_statistical:
        from dashboard.views.analysis_statistical import show_statistical_analysis
        show_statistical_analysis()

    with tab_timeseries:
        from dashboard.views.analysis_timeseries import show_timeseries_analysis
        show_timeseries_analysis()

    with tab_cost:
        from dashboard.views.analysis_cost import show_cost_analysis
        show_cost_analysis()

    with tab_failure:
        from dashboard.views.analysis_failure import show_failure_analysis
        show_failure_analysis()
