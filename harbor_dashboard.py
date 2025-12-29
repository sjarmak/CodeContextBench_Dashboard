#!/usr/bin/env python3
"""
Harbor Evaluations Dashboard

Standalone app for running and viewing Harbor evaluations with different MCP configurations.
"""

import streamlit as st
import subprocess
import json
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import time
from threading import Thread
from queue import Queue

# Configuration
PROJECT_ROOT = Path(__file__).parent
HARBOR_JOBS_DIR = PROJECT_ROOT / "harbor_jobs" / "jobs"
BENCHMARKS_DIR = PROJECT_ROOT / "benchmarks"

# Benchmark to local directory mapping
BENCHMARK_PATHS = {
    "hello-world@head": "hello_world_test",
    "swebench-verified@1.0": "swebench_pro/tasks",
    "swebenchpro@1.0": "swebench_pro/tasks",
    "aider-polyglot@1.0": "github_mined",
    "ir-sdlc-multi-repo@1.0": "dependeval_benchmark",
}

def get_available_tasks(dataset_name: str) -> list:
    """Discover available tasks for a dataset."""
    benchmark_dir = BENCHMARK_PATHS.get(dataset_name)
    if not benchmark_dir:
        return []
    
    full_path = BENCHMARKS_DIR / benchmark_dir
    if not full_path.exists():
        return []
    
    tasks = []
    # Look for task directories (exclude common non-task directories)
    exclude_dirs = {'.', '..', '__pycache__', '.git', 'jobs', 'template', '.DS_Store'}
    
    for item in sorted(full_path.iterdir()):
        if item.is_dir() and not item.name.startswith('.') and item.name not in exclude_dirs:
            tasks.append(item.name)
    
    return sorted(tasks)

# Load credentials from .env.local
def load_env():
    env_file = PROJECT_ROOT / ".env.local"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

load_env()

# Page config with custom styling
st.set_page_config(
    page_title="Sourcegraph Evaluations",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for greyscale, modern look
st.markdown("""
<style>
    /* Remove default streamlit colors */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 4px;
        background-color: #f0f0f0;
        color: #333;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: #333;
        color: #fff;
    }
    
    /* Metrics styling */
    .metric-container {
        background-color: #fafafa;
        padding: 16px;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    
    /* Code blocks */
    .stCodeBlock {
        background-color: #1a1a1a !important;
        color: #e0e0e0 !important;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #333;
        color: white;
        border-radius: 4px;
        border: none;
        font-weight: 500;
    }
    .stButton > button:hover {
        background-color: #555;
    }
    
    /* Text styling */
    h1, h2, h3 {
        color: #1a1a1a;
    }
</style>
""", unsafe_allow_html=True)

st.title("Sourcegraph Evaluations")

# ============================================================================
# SIDEBAR
# ============================================================================

with st.sidebar:
    st.markdown("## Configuration")
    
    # Agent selection
    agent = st.radio(
        "Agent Configuration",
        [
            ("Baseline", "baseline"),
            ("Sourcegraph MCP", "sourcegraph"),
            ("Deep Search MCP", "deepsearch"),
        ],
        format_func=lambda x: x[0]
    )
    agent_name = agent[1]
    
    # Model selection
    model = st.selectbox(
        "Model",
        [
            ("Haiku (Fast)", "anthropic/claude-haiku-4-5"),
            ("Sonnet (Balanced)", "anthropic/claude-sonnet-4-20250514"),
            ("Opus (Capable)", "anthropic/claude-opus-4-1"),
        ],
        format_func=lambda x: x[0]
    )
    model_name = model[1]
    
    # Dataset selection
    dataset = st.selectbox(
        "Dataset",
        [
            ("Hello World", "hello-world@head"),
            ("SWE-Bench Verified", "swebench-verified@1.0"),
            ("SWE-Bench Pro", "swebenchpro@1.0"),
            ("Aider Polyglot", "aider-polyglot@1.0"),
            ("IR-SDLC Multi-Repo", "ir-sdlc-multi-repo@1.0"),
        ],
        format_func=lambda x: x[0]
    )
    dataset_name = dataset[1]
    
    # Task selection
    available_tasks = get_available_tasks(dataset_name)
    task_mode = st.radio(
        "Task Selection",
        ["Full Benchmark", "Single Task"],
        horizontal=True
    )
    
    selected_task = None
    if task_mode == "Single Task":
        if available_tasks:
            st.markdown(f"**{len(available_tasks)} tasks available**")
            
            # For large task lists, add search filter
            if len(available_tasks) > 50:
                task_search = st.text_input(
                    "Search tasks",
                    placeholder="Type to filter (e.g., django, bug, fix)...",
                    key="task_search"
                )
                filtered_tasks = [t for t in available_tasks if task_search.lower() in t.lower()] if task_search else available_tasks
                
                if task_search and not filtered_tasks:
                    st.warning(f"No tasks match '{task_search}'")
                    selected_task = None
                else:
                    st.markdown(f"**{len(filtered_tasks)} tasks**" if task_search else "")
                    selected_task = st.selectbox(
                        "Select Task",
                        filtered_tasks,
                        key="task_select"
                    )
            else:
                selected_task = st.selectbox(
                    "Select Task",
                    available_tasks,
                    key="task_select"
                )
        else:
            st.warning("No tasks found for this dataset")
    
    # Advanced options
    with st.expander("Advanced Options"):
        n_concurrent = st.slider("Concurrent Trials", 1, 16, 2)
        timeout_mult = st.slider("Timeout Multiplier", 0.5, 5.0, 1.0, 0.5)
        n_attempts = st.slider("Attempts", 1, 3, 1)


# ============================================================================
# MAIN TABS
# ============================================================================

tab1, tab2, tab3 = st.tabs(["Run", "Results", "Compare"])

# ============================================================================
# TAB 1: RUN
# ============================================================================

with tab1:
    st.markdown("### Start Evaluation")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown(f"""
        **Configuration:**
        - Agent: `{agent[0]}`
        - Model: `{model[0]}`
        - Dataset: `{dataset[0]}`
        """)
    
    with col2:
        if st.button("START", use_container_width=True, key="run_btn"):
            # Verify credentials
            if agent_name in ["sourcegraph", "deepsearch"]:
                if not os.getenv("SOURCEGRAPH_ACCESS_TOKEN") or not os.getenv("SOURCEGRAPH_URL"):
                    st.error("Missing Sourcegraph credentials in .env.local")
                    st.stop()
            
            if not os.getenv("ANTHROPIC_API_KEY"):
                st.error("Missing ANTHROPIC_API_KEY in .env.local")
                st.stop()
            
            # Build command
            cmd = [
                "harbor", "run",
                "--dataset", dataset_name,
                "--agent", "openhands",
                "--model", model_name,
                "--n-concurrent", str(n_concurrent),
                "--timeout-multiplier", str(timeout_mult),
                "--n-attempts", str(n_attempts),
                "--jobs-dir", str(HARBOR_JOBS_DIR.parent),
            ]
            
            if selected_task:
                cmd.extend(["--task-name", selected_task])
            
            # Build environment
            env = os.environ.copy()
            
            # Add MCP config if needed
            if agent_name == "sourcegraph":
                sg_url = os.getenv("SOURCEGRAPH_URL", "").rstrip("/")
                sg_token = os.getenv("SOURCEGRAPH_ACCESS_TOKEN")
                mcp_cfg = {
                    "sourcegraph": {
                        "command": "mcp-remote",
                        "env": {
                            "MCP_REMOTE_URL": f"{sg_url}/.mcp/transport",
                            "MCP_REMOTE_AUTH_HEADER": f"Authorization: token {sg_token}"
                        }
                    }
                }
                env["OPENHANDS_MCP_SERVERS"] = json.dumps(mcp_cfg)
            
            elif agent_name == "deepsearch":
                sg_url = os.getenv("SOURCEGRAPH_URL", "").rstrip("/")
                sg_token = os.getenv("SOURCEGRAPH_ACCESS_TOKEN")
                mcp_cfg = {
                    "deepsearch": {
                        "command": "mcp-remote",
                        "env": {
                            "MCP_REMOTE_URL": f"{sg_url}/.mcp/deepsearch",
                            "MCP_REMOTE_AUTH_HEADER": f"Authorization: token {sg_token}"
                        }
                    }
                }
                env["OPENHANDS_MCP_SERVERS"] = json.dumps(mcp_cfg)
            
            # Run with real-time logs
            st.markdown("### Execution Logs")
            log_container = st.container()
            status_text = st.empty()
            
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                    cwd=str(PROJECT_ROOT),
                    bufsize=1
                )
                
                log_lines = []
                with log_container:
                    log_display = st.code("", language="")
                
                # Stream logs in real time
                for line in iter(process.stdout.readline, ''):
                    if line:
                        log_lines.append(line.rstrip())
                        # Display last 20 lines
                        with log_container:
                            log_display.code('\n'.join(log_lines[-20:]), language="")
                        time.sleep(0.01)  # Small delay for UI update
                
                returncode = process.wait()
                
                if returncode == 0:
                    status_text.success("Evaluation completed successfully")
                else:
                    status_text.error(f"Evaluation failed with exit code {returncode}")
                    with log_container:
                        log_display.code('\n'.join(log_lines[-50:]), language="")
                
            except Exception as e:
                st.error(f"Error: {e}")


# ============================================================================
# TAB 2: RESULTS
# ============================================================================

with tab2:
    if not HARBOR_JOBS_DIR.exists():
        st.info("No evaluations yet. Run one in the Run tab.")
    else:
        job_dirs = sorted(HARBOR_JOBS_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not job_dirs:
            st.info("No evaluations found.")
        else:
            # Job selector
            job_id = st.selectbox("Select Job", [j.name for j in job_dirs])
            job_path = HARBOR_JOBS_DIR / job_id
            
            # Load result
            result_file = job_path / "result.json"
            if result_file.exists():
                with open(result_file) as f:
                    result = json.load(f)
                
                # Summary metrics
                st.markdown("### Summary")
                col1, col2, col3, col4 = st.columns(4)
                
                stats = result.get("stats", {})
                n_trials = stats.get("n_trials", 0)
                n_errors = stats.get("n_errors", 0)
                
                with col1:
                    st.metric("Trials", n_trials)
                with col2:
                    st.metric("Errors", n_errors)
                with col3:
                    success_rate = f"{((n_trials - n_errors) / n_trials * 100):.0f}%" if n_trials > 0 else "N/A"
                    st.metric("Success Rate", success_rate)
                with col4:
                    st.metric("Job ID", job_id[:8])
                
                # Trial results
                st.markdown("### Trial Results")
                
                trials = []
                trial_data_map = {}
                
                for trial_dir in sorted(job_path.glob("*__*")):
                    trial_file = trial_dir / "result.json"
                    if trial_file.exists():
                        with open(trial_file) as f:
                            t = json.load(f)
                        
                        exec_time = 0
                        if t.get("started_at") and t.get("finished_at"):
                            s = datetime.fromisoformat(t["started_at"])
                            e = datetime.fromisoformat(t["finished_at"])
                            exec_time = (e - s).total_seconds()
                        
                        reward = t.get("verifier_result", {}).get("rewards", {}).get("reward", 0)
                        input_tokens = t.get("agent_result", {}).get("n_input_tokens", 0)
                        output_tokens = t.get("agent_result", {}).get("n_output_tokens", 0)
                        total_tokens = input_tokens + output_tokens
                        cost = t.get("agent_result", {}).get("cost_usd", 0)
                        cache_tokens = t.get("agent_result", {}).get("n_cache_tokens", 0)
                        
                        task_name = t.get("task_name", "")
                        trials.append({
                            "Task": task_name,
                            "Status": "Pass" if reward > 0 else "Fail",
                            "Input Tokens": f"{input_tokens:,}",
                            "Output Tokens": f"{output_tokens:,}",
                            "Total Tokens": f"{total_tokens:,}",
                            "Cost": f"${cost:.4f}",
                            "Time": f"{exec_time:.0f}s"
                        })
                        
                        trial_data_map[task_name] = {
                            "full_result": t,
                            "exec_time": exec_time,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "cache_tokens": cache_tokens,
                            "cost": cost
                        }
                
                if trials:
                    df = pd.DataFrame(trials)
                    
                    # Display table with selectable rows
                    selected_trial = st.selectbox(
                        "View full trace for trial:",
                        options=[t["Task"] for t in trials],
                        key="trial_selector"
                    )
                    
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    
                    # Display full trace for selected trial
                    if selected_trial and selected_trial in trial_data_map:
                        st.markdown("### Full Trace and Metrics")
                        
                        trial_info = trial_data_map[selected_trial]
                        full_result = trial_info["full_result"]
                        
                        # Detailed metrics
                        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                        
                        with metric_col1:
                            st.metric("Input Tokens", f"{trial_info['input_tokens']:,}")
                        with metric_col2:
                            st.metric("Output Tokens", f"{trial_info['output_tokens']:,}")
                        with metric_col3:
                            st.metric("Cache Tokens", f"{trial_info['cache_tokens']:,}")
                        with metric_col4:
                            st.metric("Cost (USD)", f"${trial_info['cost']:.4f}")
                        
                        # Execution timeline
                        st.markdown("### Execution Timeline")
                        time_col1, time_col2, time_col3, time_col4 = st.columns(4)
                        
                        env_setup = full_result.get("environment_setup", {})
                        agent_setup = full_result.get("agent_setup", {})
                        agent_exec = full_result.get("agent_execution", {})
                        verifier = full_result.get("verifier", {})
                        
                        def calc_duration(start, end):
                            if start and end:
                                s = datetime.fromisoformat(start)
                                e = datetime.fromisoformat(end)
                                return (e - s).total_seconds()
                            return 0
                        
                        env_time = calc_duration(env_setup.get("started_at"), env_setup.get("finished_at"))
                        agent_setup_time = calc_duration(agent_setup.get("started_at"), agent_setup.get("finished_at"))
                        exec_time = calc_duration(agent_exec.get("started_at"), agent_exec.get("finished_at"))
                        verify_time = calc_duration(verifier.get("started_at"), verifier.get("finished_at"))
                        
                        with time_col1:
                            st.metric("Environment Setup", f"{env_time:.1f}s")
                        with time_col2:
                            st.metric("Agent Setup", f"{agent_setup_time:.1f}s")
                        with time_col3:
                            st.metric("Execution", f"{exec_time:.1f}s")
                        with time_col4:
                            st.metric("Verification", f"{verify_time:.1f}s")
                        
                        # Raw JSON trace
                        st.markdown("### Raw Result JSON")
                        with st.expander("View complete result.json"):
                            st.json(full_result)
                        
                        # Agent trajectory - search for matching trial directory
                        trajectory_file = None
                        for trial_dir in job_path.glob("*__*"):
                            if trial_dir.name.startswith(selected_trial.split("__")[0] if "__" in selected_trial else selected_trial):
                                traj_path = trial_dir / "agent" / "trajectory.json"
                                if traj_path.exists():
                                    trajectory_file = traj_path
                                    break
                        
                        if trajectory_file and trajectory_file.exists():
                            st.markdown("### Agent Trajectory")
                            try:
                                with open(trajectory_file) as f:
                                    trajectory = json.load(f)
                                
                                # Show trajectory stats
                                traj_col1, traj_col2, traj_col3 = st.columns(3)
                                
                                with traj_col1:
                                    tool_calls = [a for a in trajectory.get("actions", []) if a.get("type") == "tool"]
                                    st.metric("Tool Calls", len(tool_calls))
                                
                                with traj_col2:
                                    actions = trajectory.get("actions", [])
                                    st.metric("Total Actions", len(actions))
                                
                                with traj_col3:
                                    st.metric("Agent", trajectory.get("agent", {}).get("name", "unknown"))
                                
                                with st.expander("View full agent trajectory.json"):
                                    st.json(trajectory)
                            except json.JSONDecodeError:
                                st.error("Failed to parse trajectory.json")
                        else:
                            st.info("No trajectory data available for this trial")
                    
                    # Stats
                    st.markdown("### Statistics")
                    col1, col2, col3 = st.columns(3)
                    
                    passed = sum(1 for t in trials if t["Status"] == "Pass")
                    total_cost = sum(float(trial_data_map[t["Task"]]["cost"]) for t in trials)
                    avg_tokens = sum(int(t["Total Tokens"].replace(",", "")) for t in trials) / len(trials)
                    
                    with col1:
                        st.metric("Pass Rate", f"{passed}/{len(trials)}")
                    with col2:
                        st.metric("Total Cost", f"${total_cost:.2f}")
                    with col3:
                        st.metric("Avg Tokens", f"{avg_tokens:,.0f}")


# ============================================================================
# TAB 3: COMPARE
# ============================================================================

with tab3:
    if not HARBOR_JOBS_DIR.exists() or not list(HARBOR_JOBS_DIR.glob("*")):
        st.info("No evaluations to compare yet.")
    else:
        st.markdown("### Cross-Evaluation Comparison")
        
        job_dirs = sorted(HARBOR_JOBS_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]
        
        all_data = []
        for job_dir in job_dirs:
            for trial_dir in sorted(job_dir.glob("*__*")):
                trial_file = trial_dir / "result.json"
                if trial_file.exists():
                    with open(trial_file) as f:
                        t = json.load(f)
                    
                    reward = t.get("verifier_result", {}).get("rewards", {}).get("reward", 0)
                    cost = t.get("agent_result", {}).get("cost_usd", 0)
                    tokens = (t.get("agent_result", {}).get("n_input_tokens", 0) +
                             t.get("agent_result", {}).get("n_output_tokens", 0))
                    model = t.get("agent_info", {}).get("model_info", {}).get("name", "")
                    
                    all_data.append({
                        "Job": job_dir.name[:10],
                        "Task": t.get("task_name", ""),
                        "Model": model,
                        "Status": "Pass" if reward > 0 else "Fail",
                        "Cost": cost,
                        "Tokens": tokens,
                    })
        
        if all_data:
            df = pd.DataFrame(all_data)
            
            # Model comparison
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### By Model")
                model_stats = df.groupby("Model").agg({
                    "Status": lambda x: sum(x == "Pass") / len(x),
                    "Cost": "sum",
                    "Tokens": "mean",
                }).round(2)
                model_stats.columns = ["Pass Rate", "Total Cost", "Avg Tokens"]
                st.dataframe(model_stats)
            
            with col2:
                st.markdown("#### Success Rate by Task")
                task_success = df.groupby("Task").apply(
                    lambda x: sum(x["Status"] == "Pass") / len(x)
                ).round(2).sort_values(ascending=False)
                st.dataframe(task_success)
            
            # Overall stats
            st.markdown("#### Overall")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Trials", len(df))
            with col2:
                st.metric("Pass Rate", f"{sum(df['Status'] == 'Pass') / len(df):.1%}")
            with col3:
                st.metric("Total Cost", f"${df['Cost'].sum():.2f}")


# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    creds_ok = bool(os.getenv("ANTHROPIC_API_KEY"))
    if creds_ok:
        st.success("Credentials loaded")
    else:
        st.error("Missing credentials")

with col2:
    st.caption(f"Jobs: {HARBOR_JOBS_DIR.parent if HARBOR_JOBS_DIR.exists() else 'none'}")


if __name__ == "__main__":
    pass
