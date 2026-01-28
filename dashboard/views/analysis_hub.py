"""
Analysis Hub - Entry point for Phase 4 analysis components.

Provides:
- Auto-ingestion of results from external jobs directory
- Database connectivity status
- Experiment overview
- Card-based navigation to analysis components
- Quick-start workflow
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
        # Import ingest components
        from src.ingest.orchestrator import IngestionOrchestrator
        
        # Ensure data directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if we have results to ingest
        if not EXTERNAL_RUNS_DIR.exists():
            return False, f"External runs directory not found: {EXTERNAL_RUNS_DIR}"
        
        experiment_dirs = [
            d for d in EXTERNAL_RUNS_DIR.iterdir() 
            if d.is_dir() and not d.name.startswith('.') and (d / "result.json").exists()
        ]
        
        if not experiment_dirs:
            return False, "No experiments found in external runs directory"
        
        # Create orchestrator and ingest
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


def show_analysis_hub():
    """Display the Analysis Hub page."""
    
    st.title("Analysis Hub")
    st.markdown("**Comprehensive experiment analysis with Phase 4 components**")
    st.markdown("---")
    
    # Initialize analysis loader in session state
    project_root = st.session_state.get("project_root", Path(__file__).parent.parent.parent)
    db_path = project_root / "data" / "metrics.db"
    
    # Database status section
    st.subheader("1. Database Status")
    
    # Check if database exists, auto-ingest if not
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
                return
        
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
            return
    
    with col2:
        try:
            stats = loader.get_stats()
            if stats and 'harbor' in stats:
                task_count = stats['harbor'].get('total_tasks', 0)
                st.metric("Tasks Processed", task_count)
            else:
                st.metric("Tasks Processed", "N/A")
        except:
            st.metric("Tasks Processed", "N/A")
    
    with col3:
        try:
            experiments = loader.list_experiments()
            st.metric("Experiments", len(experiments))
        except:
            st.metric("Experiments", "N/A")
    
    # Re-ingest button
    st.markdown("")
    if st.button("🔄 Re-ingest Results", help="Re-scan external jobs directory and update database"):
        with st.spinner("Ingesting results..."):
            success, message = auto_ingest_if_needed(db_path, project_root)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)
    
    st.caption(f"📁 Results from: {EXTERNAL_RUNS_DIR}")
    
    st.markdown("---")
    
    # Experiment overview
    st.subheader("2. Available Experiments")
    
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
    
    # Analysis components card grid
    st.subheader("3. Analysis Components")
    st.caption("Click a card to configure and run the analysis.")

    render_analysis_card_grid(project_root=project_root)
    
    st.markdown("---")
    
    # Quick-start workflow
    st.subheader("4. Quick-Start Workflow")
    
    workflow_steps = [
        {
            "step": 1,
            "title": "Select Experiment",
            "description": "Choose an experiment from the list above",
            "action": "Use the sidebar to select an experiment"
        },
        {
            "step": 2,
            "title": "View Comparison",
            "description": "Compare agent performance metrics",
            "action": "Navigate to Comparison Analysis view"
        },
        {
            "step": 3,
            "title": "Check Significance",
            "description": "See which differences are statistically significant",
            "action": "Review Statistical Analysis view"
        },
        {
            "step": 4,
            "title": "Track Costs",
            "description": "Analyze API costs and efficiency",
            "action": "Open Cost Analysis view"
        },
        {
            "step": 5,
            "title": "Review Trends",
            "description": "Monitor improvements across experiments",
            "action": "Check Time-Series Analysis view"
        },
        {
            "step": 6,
            "title": "Export Results",
            "description": "Download analysis as JSON",
            "action": "Use export button in any view"
        }
    ]
    
    for step in workflow_steps:
        col1, col2, col3 = st.columns([1, 3, 3])
        
        with col1:
            st.markdown(f"**{step['step']}.**")
        
        with col2:
            st.markdown(f"**{step['title']}**")
            st.caption(step['description'])
        
        with col3:
            st.caption(f"→ {step['action']}")
    
    st.markdown("---")
    
    # Getting started
    st.subheader("5. Getting Started")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Run an Experiment**")
        st.code(
            "harbor run --path benchmarks/big_code_mcp/task \\\n"
            "  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent\n"
            "  --model anthropic/claude-haiku-4-5-20251001",
            language="bash"
        )
    
    with col2:
        st.markdown("**Ingest Results**")
        st.code(
            "ccb ingest exp001",
            language="bash"
        )
    
    st.markdown("**Analyze Results**")
    st.code(
        "ccb analyze compare exp001\n"
        "ccb analyze statistical exp001\n"
        "ccb analyze cost exp001",
        language="bash"
    )
    
    st.markdown("---")
    
    # Database management
    st.subheader("6. Database Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Refresh Database Connection"):
            st.session_state.analysis_loader = None
            try:
                loader = AnalysisLoader(db_path)
                st.session_state.analysis_loader = loader
                st.success("✓ Database refreshed")
            except Exception as e:
                st.error(f"Failed to refresh: {e}")
            st.rerun()
    
    with col2:
        if st.button("Clear Result Cache"):
            if hasattr(st.session_state.analysis_loader, 'clear_cache'):
                st.session_state.analysis_loader.clear_cache()
                st.success("✓ Cache cleared")
    
    st.markdown("---")
    
    # Documentation
    st.subheader("7. Documentation")
    
    st.markdown("""
    - **Phase 4 Statistical Testing**: Perform t-tests, chi-square tests, Mann-Whitney U tests
    - **Phase 4 Time-Series Analysis**: Track trends and anomalies across experiments
    - **Phase 4 Cost Analysis**: Monitor API costs and compute efficiency
    
    For detailed information, see:
    - `docs/PIPELINE_OVERVIEW.md` - Complete pipeline architecture
    - `docs/ANALYSIS_LAYER.md` - Analysis component details
    - `AGENTS.md` - Workflow and patterns
    """)
