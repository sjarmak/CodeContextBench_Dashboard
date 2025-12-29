"""
Evaluation Runner

Run evaluations with:
- Agent selection
- Task selection
- Live progress monitoring
- Pause/resume capability
- Log streaming
"""

import streamlit as st
from pathlib import Path
import sys
import os
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from benchmark.database import BenchmarkRegistry, RunManager, TaskManager, AgentRegistry
from benchmark.run_orchestrator import create_evaluation_run, get_orchestrator
from benchmark.harbor_datasets import get_harbor_dataset_instances
import pandas as pd


def show_run_configuration():
    """Show run configuration form."""
    st.subheader("Configure Evaluation Run")

    # Benchmark selection
    benchmarks = BenchmarkRegistry.list_all()
    if not benchmarks:
        st.error("No benchmarks registered. Please add benchmarks first.")
        return None

    benchmark_names = [b["name"] for b in benchmarks]
    # Default to SWE-bench Verified if available
    default_bench_idx = 0
    if "SWE-bench Verified" in benchmark_names:
        default_bench_idx = benchmark_names.index("SWE-bench Verified")
    
    selected_benchmark_name = st.selectbox(
        "Select Benchmark", 
        benchmark_names, 
        index=default_bench_idx,
        key="eval_benchmark_selector"
    )

    selected_benchmark = next(b for b in benchmarks if b["name"] == selected_benchmark_name)
    
    # Clear selected tasks if benchmark changed
    prev_benchmark = st.session_state.get("eval_prev_benchmark")
    if prev_benchmark != selected_benchmark_name:
        st.session_state["eval_selected_tasks"] = []
        st.session_state["eval_prev_benchmark"] = selected_benchmark_name

    # Check if this is a Harbor dataset
    is_harbor_dataset = selected_benchmark.get("adapter_type") == "harbor_dataset"

    # Get benchmark tasks
    if is_harbor_dataset:
        # For Harbor datasets, load instance list from HuggingFace
        st.markdown("#### Instance Selection")
        st.info(f"**Harbor Dataset:** {selected_benchmark['name']}")

        # Load instance IDs
        with st.spinner("Loading instances from HuggingFace..."):
            try:
                tasks = get_harbor_dataset_instances(selected_benchmark['folder_name'])
                st.success(f"Loaded {len(tasks)} instances")
            except Exception as e:
                st.error(f"Failed to load instances: {e}")
                return None

        # Task selection UI
        st.markdown("#### Task Selection")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Select All Tasks"):
                st.session_state["eval_selected_tasks"] = tasks
                st.rerun()

        with col2:
            if st.button("Clear Selection"):
                st.session_state["eval_selected_tasks"] = []
                st.rerun()

        # Filter defaults to only include valid options for this benchmark
        stored_tasks = st.session_state.get("eval_selected_tasks", [])
        valid_defaults = [t for t in stored_tasks if t in tasks]
        
        selected_tasks = st.multiselect(
            "Tasks to Run",
            tasks,
            default=valid_defaults,
            key="task_selection_multiselect"
        )

        st.session_state["eval_selected_tasks"] = selected_tasks

        if not selected_tasks:
            st.warning("Please select at least one task")
            return None

        st.write(f"**Selected: {len(selected_tasks)} tasks**")
    else:
        # Local benchmark - enumerate from folder
        benchmark_path = Path("benchmarks") / selected_benchmark["folder_name"]
        tasks = []

        if benchmark_path.exists():
            for task_dir in sorted(benchmark_path.iterdir()):
                if task_dir.is_dir() and (task_dir / "task.toml").exists():
                    tasks.append(task_dir.name)

        if not tasks:
            st.warning("No tasks found in selected benchmark")
            return None

        # Task selection
        st.markdown("#### Task Selection")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Select All Tasks"):
                st.session_state["eval_selected_tasks"] = tasks
                st.rerun()

        with col2:
            if st.button("Clear Selection"):
                st.session_state["eval_selected_tasks"] = []
                st.rerun()

        # Filter defaults to only include valid options for this benchmark
        stored_tasks = st.session_state.get("eval_selected_tasks", [])
        valid_defaults = [t for t in stored_tasks if t in tasks]
        
        selected_tasks = st.multiselect(
            "Tasks to Run",
            tasks,
            default=valid_defaults,
            key="task_selection_multiselect"
        )

        st.session_state["eval_selected_tasks"] = selected_tasks

        if not selected_tasks:
            st.warning("Please select at least one task")
            return None

        st.write(f"**Selected: {len(selected_tasks)} tasks**")

    # Agent selection
    st.markdown("#### Agent Configuration")

    # Single agent: BaselineClaudeCodeAgent with MCP configuration options
    st.info("**Agent:** BaselineClaudeCodeAgent (Harbor's generic Claude Code + configurable MCP)")

    # MCP Type Selection
    mcp_type = st.radio(
        "MCP Configuration",
        options=["None (Pure Baseline)", "Sourcegraph MCP", "Deep Search MCP"],
        help="""
        Select MCP configuration for the BaselineClaudeCodeAgent:
        - **None**: Pure baseline with no MCP (local tools only)
        - **Sourcegraph MCP**: Full Sourcegraph code intelligence (keyword, NLS, Deep Search)
        - **Deep Search MCP**: Deep Search semantic search only

        This allows clean A/B/C testing of MCP impact on the same agent harness.
        """
    )

    # Map selection to environment variable value
    mcp_env_value = {
        "None (Pure Baseline)": "none",
        "Sourcegraph MCP": "sourcegraph",
        "Deep Search MCP": "deepsearch"
    }[mcp_type]

    # Store in session state for later use
    st.session_state["baseline_mcp_type"] = mcp_env_value

    # Single agent import path
    agent_import_path = "agents.claude_baseline_agent:BaselineClaudeCodeAgent"

    # Display what will be created based on MCP selection
    with st.expander("Configuration Details"):
        if mcp_env_value == "none":
            st.markdown("""
            **Pure Baseline (No MCP)**
            - No MCP configuration
            - Local tools only: Bash, Read, Edit, Write, Grep, Glob
            - Baseline for measuring MCP impact
            """)
        elif mcp_env_value == "sourcegraph":
            st.markdown("""
            **Sourcegraph MCP (Full Code Intelligence)**
            - MCP endpoint: `{SOURCEGRAPH_URL}/.api/mcp/v1`
            - Tools available:
              - `sg_keyword_search` - Exact string matching
              - `sg_nls_search` - Natural language search
              - `sg_deepsearch` - Deep semantic search
              - `sg_read_file` - Read indexed files
            - CLAUDE.md instructs agent to use MCP tools first
            - Requires: `SOURCEGRAPH_URL` and `SOURCEGRAPH_ACCESS_TOKEN`
            """)
        elif mcp_env_value == "deepsearch":
            st.markdown("""
            **Deep Search MCP (Semantic Search Only)**
            - MCP endpoint: `{SOURCEGRAPH_URL}/.api/mcp/deepsearch`
            - Tools available:
              - `deepsearch` - Deep semantic code understanding
            - Focused configuration for testing Deep Search impact
            - Requires: `SOURCEGRAPH_URL` and `SOURCEGRAPH_ACCESS_TOKEN`
            """)

    selected_agents = [agent_import_path]

    # Configuration
    st.markdown("#### Run Configuration")

    col1, col2 = st.columns(2)

    with col1:
        concurrency = st.number_input(
            "Concurrency (tasks in parallel)",
            min_value=1,
            max_value=10,
            value=1
        )

    with col2:
        timeout = st.number_input(
            "Timeout per task (seconds)",
            min_value=60,
            max_value=3600,
            value=600
        )

    force_rebuild = st.checkbox(
        "Force Rebuild Environment (advanced)",
        value=False,
        help="""
        Force build environment from Dockerfile instead of using pre-built images.

        **When to use:**
        - You modified a benchmark's Dockerfile
        - You added new system dependencies
        - Debugging environment issues

        **Usually NOT needed** because:
        - Daytona creates fresh cloud VMs each time
        - Pre-built images work fine for most runs
        - BaselineClaudeCodeAgent doesn't change the environment
        """
    )

    # Create run button
    st.markdown("---")

    if st.button("Start Evaluation Run", type="primary"):
        try:
            import subprocess
            import sys
            project_root = Path.cwd()
            sys.path.insert(0, str(project_root / "dashboard"))
            from utils.run_tracker import RunTracker

            # Get MCP type from session state
            mcp_type_env = st.session_state.get("baseline_mcp_type", "none")

            # 1. Create the run record in DB
            run_id = create_evaluation_run(
                benchmark_name=selected_benchmark["name"],
                agents=selected_agents,
                task_selection=selected_tasks,
                concurrency=concurrency,
                config={
                    "timeout": timeout,
                    "env": {
                        "BASELINE_MCP_TYPE": mcp_type_env
                    }
                }
            )

            # 2. Prepare the CLI command
            # Pass force rebuild flag if checked
            force_flag = "--force-build" if force_rebuild else ""
            # CRITICAL: Quote the run_id because it can contain spaces (e.g. "SWE-bench Verified")
            # Use sys.executable to ensure we use the same python environment
            command = f'{sys.executable} scripts/run_evaluation.py --run-id "{run_id}" {force_flag}'
            
            # 3. Initialize run tracker and detached log file
            tracker = RunTracker(project_root / ".dashboard_runs")
            log_file = tracker.tracker_dir / f"{run_id}.log"
            
            # 4. Launch as detached background process
            log_fd = open(log_file, "w", buffering=1)

            # Set up environment with unbuffered output for real-time streaming
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            process = subprocess.Popen(
                command,
                shell=True,
                cwd=project_root,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                text=True,
                env=env
            )

            # 5. Register with tracker
            # Create descriptive agent name based on MCP configuration
            agent_display_name = f"BaselineClaudeCode ({mcp_type})"

            tracker.register_run(
                run_id=run_id,
                run_type="evaluation",
                pid=process.pid,
                command=command,
                benchmark_name=selected_benchmark["name"],
                agent_name=agent_display_name
            )

            st.session_state["current_run_id"] = run_id
            st.success(f"Evaluation started in background! Run ID: `{run_id}`")
            st.info("Navigate to the **'Current Runs'** tab to monitor progress and view live logs.")
            
        except Exception as e:
            st.error(f"Failed to create run: {e}")
            import traceback
            st.code(traceback.format_exc())

    return None


def show_run_monitoring():
    """Show live monitoring of current run."""
    run_id = st.session_state.get("current_run_id")

    if not run_id:
        st.info("No active run. Configure and start a run above.")
        return

    st.subheader(f"Monitoring Run: {run_id}")

    # Get orchestrator
    try:
        orchestrator = get_orchestrator(run_id)
    except Exception as e:
        st.error(f"Failed to get run: {e}")
        if st.button("Clear Run"):
            del st.session_state["current_run_id"]
            del st.session_state["show_monitoring"]
            st.rerun()
        return

    # Get progress
    progress = orchestrator.get_progress()

    # Show progress
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        status_label = progress["status"].capitalize()
        st.write(f"**Status:** {status_label}")

    with col2:
        st.write(f"**Progress:** {progress['completed']}/{progress['total_tasks']}")

    with col3:
        st.write(f"**Running:** {progress['running']}")

    with col4:
        st.write(f"**Pending:** {progress['pending']}")

    # Progress bar
    st.progress(progress['progress_pct'] / 100)

    # Control buttons
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if progress["status"] == "pending":
            if st.button("Start Run"):
                orchestrator.start()
                st.rerun()

    with col2:
        if progress["status"] == "running":
            if st.button("Pause Run"):
                orchestrator.pause()
                st.rerun()

    with col3:
        if progress["can_resume"]:
            if st.button("Resume Run"):
                orchestrator.resume()
                st.rerun()

    with col4:
        if progress["status"] in ("running", "paused"):
            if st.button("Stop Run"):
                orchestrator.stop()
                st.rerun()

    # Task details
    st.markdown("---")
    
    tasks = TaskManager.get_tasks(run_id)
    
    # Live Log Section for active task
    running_tasks = [t for t in tasks if t["status"] == "running"]
    if running_tasks:
        active_task = running_tasks[0]
        
        # Calculate elapsed time for active task
        import datetime
        started_at = active_task.get("started_at")
        elapsed_str = "Calculating..."
        if started_at:
            if isinstance(started_at, str):
                # Handle ISO format strings
                try:
                    start_dt = datetime.datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    elapsed = datetime.datetime.utcnow() - start_dt.replace(tzinfo=None)
                    elapsed_str = str(elapsed).split('.')[0]
                except:
                    pass
        
        st.markdown(f"#### Live Log: {active_task['task_name']} (Elapsed: {elapsed_str})")
        
        # Determine log path
        safe_agent_name = active_task["agent_name"].replace(":", "__").replace("/", "_")
        job_dir = Path(f"jobs/{run_id}")
        log_file = job_dir / f"{active_task['task_name']}_{safe_agent_name}_harbor.log"
        
        if log_file.exists():
            try:
                with open(log_file, "r") as f:
                    log_lines = f.readlines()
                    display_log = "".join(log_lines[-100:]) # Show last 100 lines
                    st.text_area("Harbor Output", display_log, height=300, key=f"live_log_{active_task['task_name']}")
                    st.caption(f"Log: `{log_file}` ({log_file.stat().st_size} bytes)")
            except Exception as e:
                st.error(f"Error reading log: {e}")
        else:
            st.info("Log file initializing...")
            # Debug: list directory if log missing
            if job_dir.exists():
                with st.expander("Debug: Job Directory Contents"):
                    st.write(f"Path: `{job_dir.absolute()}`")
                    files = list(job_dir.iterdir())
                    st.write([f.name for f in files])
            else:
                st.error(f"Job directory not found: `{job_dir}`")

    st.markdown("#### Task Status")

    if tasks:
        # Show tasks in a table
        task_data = []
        for task in tasks:
            task_data.append({
                "Task": task["task_name"],
                "Agent": task["agent_name"].split(":")[-1],
                "Status": task["status"],
                "Reward": task.get("reward", "N/A"),
                "Started": task.get("started_at", "")[:19] if task.get("started_at") else "",
            })

        df = pd.DataFrame(task_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Show detailed errors for failed tasks
        failed_tasks = [t for t in tasks if t["status"] == "failed"]
        if failed_tasks:
            st.markdown("#### Failed Task Details")
            for task in failed_tasks:
                with st.expander(f"Failure: {task['task_name']} ({task['agent_name'].split(':')[-1]})"):
                    if "error_message" in task and task["error_message"]:
                        st.code(task["error_message"], language="text")
                    else:
                        st.info("No error message captured.")


    # Auto-refresh if running or pending (for auto-start)
    # Use longer interval to reduce annoying page greying
    if progress["status"] in ("running", "pending"):
        import datetime
        now = datetime.datetime.now()
        st.caption(f"Last updated: {now.strftime('%H:%M:%S')} - Auto-refreshing every 5 seconds")
        time.sleep(5)
        st.rerun()

    # Completion actions
    if progress["status"] == "completed":
        st.success("Run completed!")

        if st.button("Generate Report"):
            st.session_state["generate_report_run_id"] = run_id
            st.info("Navigate to Report Generator page to generate report")

        if st.button("Clear Run"):
            del st.session_state["current_run_id"]
            del st.session_state["show_monitoring"]
            st.rerun()


def show_recent_runs():
    """Show list of recent runs."""
    st.subheader("Recent Runs")

    runs = RunManager.list_all()

    if not runs:
        st.info("No runs yet. Create a run to get started.")
        return

    # Show recent runs
    run_data = []
    for run in runs[:10]:  # Show last 10
        # Get benchmark name
        benchmark = BenchmarkRegistry.get(run["benchmark_id"])
        benchmark_name = benchmark["name"] if benchmark else "Unknown"

        run_data.append({
            "Run ID": run["run_id"],
            "Benchmark": benchmark_name,
            "Status": run["status"],
            "Agents": len(run.get("agents", [])),
            "Started": run.get("started_at", "")[:19] if run.get("started_at") else "N/A",
        })

    df = pd.DataFrame(run_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Select a run to monitor
    run_ids = [r["run_id"] for r in runs]
    selected_run_id = st.selectbox("Load Run", ["" ] + run_ids)

    if selected_run_id:
        if st.button("Load Selected Run"):
            st.session_state["current_run_id"] = selected_run_id
            st.session_state["show_monitoring"] = True
            st.rerun()


def show_profile_runner():
    """Run benchmark profiles (multiple agents on same tasks)."""

    # Check if we're monitoring a profile run
    if st.session_state.get("monitoring_profile"):
        show_profile_monitoring()
        return

    st.subheader("Benchmark Profile Runner")

    st.markdown("""
    Run benchmark profiles to test multiple agent variants on the same tasks.
    Profiles are defined in `configs/benchmark_profiles.yaml`.

    **The profile will run in the background** - you can monitor progress below.
    """ )

    # Get project root
    project_root = st.session_state.get("project_root", Path.cwd())
    profiles_config = project_root / "configs" / "benchmark_profiles.yaml"

    if not profiles_config.exists():
        st.error(f"Profiles config not found: {profiles_config}")
        return

    # Parse YAML to get available profiles
    import yaml
    try:
        with open(profiles_config) as f:
            config = yaml.safe_load(f)
            available_profiles = list(config.get("profiles", {}).keys())

        if not available_profiles:
            st.warning("No profiles found in config")
            return

        # Profile selection dropdown
        profile_name = st.selectbox(
            "Select Profile",
            available_profiles,
            help="Profile defined in configs/benchmark_profiles.yaml"
        )

        # Show profile description
        if profile_name:
            profile = config["profiles"][profile_name]
            desc = profile.get("description", "")
            if desc:
                st.info(f"{desc}")

            # Show profile details
            with st.expander("Profile Details"):
                st.json(profile)

        # Run options
        dry_run = st.checkbox("Dry Run (preview commands only)", value=True)

        # Run button
        if st.button("Start Profile Run", type="primary"):
            import subprocess
            import datetime
            import sys
            sys.path.insert(0, str(project_root / "dashboard"))
            from utils.run_tracker import RunTracker

            cmd_parts = ["python", "scripts/benchmark_profile_runner.py", "--profiles", profile_name]

            if dry_run:
                cmd_parts.append("--dry-run")

            command = " ".join(cmd_parts)

            st.info(f"Starting: `{command}`")

            try:
                # Initialize run tracker
                tracker = RunTracker(project_root / ".dashboard_runs")

                # Create log file
                run_id = f"profile_{profile_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
                log_file = tracker.tracker_dir / f"{run_id}.log"

                # Start process in background with output redirect
                # Open file without context manager so it stays open for subprocess
                log_fd = open(log_file, "w", buffering=1)  # Line buffering for real-time output
                process = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=project_root,
                    stdout=log_fd,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                # Note: log_fd will be closed when process exits or is garbage collected

                # Register with tracker
                tracker.register_run(
                    run_id=run_id,
                    run_type="profile",
                    pid=process.pid,
                    command=command,
                    profile_name=profile_name,
                    dry_run=dry_run
                )

                st.success(f"Profile started! Run ID: {run_id}")
                st.info("Navigate to 'Current Runs' tab to monitor progress")

                # Clear any existing monitoring state
                if "monitoring_profile" in st.session_state:
                    del st.session_state["monitoring_profile"]

                time.sleep(2)
                st.rerun()

            except Exception as e:
                st.error(f"Failed to start profile: {e}")
                import traceback
                st.code(traceback.format_exc())

    except Exception as e:
        st.error(f"Error loading profiles: {e}")
        import traceback
        st.code(traceback.format_exc())


def show_profile_monitoring():
    """Monitor running profile with live log streaming."""
    import datetime
    import re
    import select

    st.subheader("Profile Run Monitor")

    profile_name = st.session_state.get("profile_name", "Unknown")
    command = st.session_state.get("profile_command", "")
    start_time = st.session_state.get("profile_start_time")
    dry_run = st.session_state.get("profile_dry_run", False)
    process = st.session_state.get("profile_process")

    if not process:
        st.error("No process found in session state")
        if st.button("Back to Profile Runner"):
            st.session_state["monitoring_profile"] = False
            st.rerun()
        return

    # Check process status
    return_code = process.poll()

    # Calculate elapsed time
    if start_time:
        elapsed = datetime.datetime.now() - start_time
        elapsed_str = str(elapsed).split('.')[0]  # Remove microseconds
    else:
        elapsed_str = "Unknown"

    # Read available output and parse for current agent/task
    if "profile_output_buffer" not in st.session_state:
        st.session_state["profile_output_buffer"] = ""

    current_agent = "Starting..."
    current_task = "Initializing..."

    # Read new output (non-blocking)
    try:
        if return_code is None and process.stdout:
            # Use non-blocking read
            import fcntl
            import os
            fd = process.stdout.fileno()
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            try:
                new_output = process.stdout.read()
                if new_output:
                    st.session_state["profile_output_buffer"] += new_output
            except:
                pass  # No new data available

        # Parse output to find current agent and task
        output = st.session_state.get("profile_output_buffer", "")

        # Look for agent patterns
        agent_patterns = [
            r"Starting agent:\s*(\S+)",
            r"Agent:\s*(\S+)",
            r"Running agent:\s*(\S+)",
            r"--agent-import-path\s+(\S+)",
        ]
        for pattern in agent_patterns:
            matches = re.findall(pattern, output)
            if matches:
                agent_path = matches[-1]  # Get most recent
                # Extract class name
                if ":" in agent_path:
                    current_agent = agent_path.split(":")[-1]
                else:
                    current_agent = agent_path

        # Look for task patterns
        task_patterns = [
            r"on task:\s*(\S+)",
            r"Task:\s*(\S+)",
            r"Running task:\s*(\S+)",
            r"--path\s+\S+/(\S+)",
            r"instance[_-]([a-zA-Z0-9_-]+)",
        ]
        for pattern in task_patterns:
            matches = re.findall(pattern, output)
            if matches:
                task = matches[-1]
                # Truncate long task names
                if len(task) > 40:
                    current_task = task[:37] + "..."
                else:
                    current_task = task

    except Exception as e:
        # Fail silently for parsing errors
        pass

    # Display status with 4 columns
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Profile", profile_name)

    with col2:
        if return_code is None:
            st.metric("Status", "Running")
        elif return_code == 0:
            st.metric("Status", "Complete")
        else:
            st.metric("Status", f"Failed ({return_code})")

    with col3:
        st.metric("Current Agent", current_agent)

    with col4:
        st.metric("Current Task", current_task)

    # Show elapsed time prominently
    st.metric("Elapsed Time", elapsed_str)

    st.code(command, language="bash")

    if dry_run:
        st.info("🔍 Running in DRY RUN mode - no actual execution")

    # Show live log
    st.markdown("---")
    st.markdown("### Live Output Log")

    if return_code is None:
        # Still running - show live output
        output = st.session_state.get("profile_output_buffer", "")

        if output:
            # Show last 100 lines for performance
            lines = output.split('\n')
            display_lines = lines[-100:] if len(lines) > 100 else lines
            display_text = '\n'.join(display_lines)

            st.text_area(
                "Output (last 100 lines)",
                display_text,
                height=400,
                key="live_output"
            )

            # Show line count
            total_lines = len(lines)
            if total_lines > 100:
                st.caption(f"Showing last 100 of {total_lines} lines")
        else:
            st.info("Waiting for output... The process has started but hasn't produced output yet.")

        # Auto-refresh every 3 seconds for more responsive updates
        st.markdown("*Auto-refreshing every 3 seconds...*")
        time.sleep(3)
        st.rerun()

    else:
        # Process finished - show full output
        try:
            stdout, stderr = process.communicate(timeout=1)

            # Combine with buffered output
            full_output = st.session_state.get("profile_output_buffer", "")
            if stdout:
                full_output += "\n" + stdout

            if full_output:
                st.text_area(
                    "Complete Output",
                    full_output,
                    height=500,
                    key="final_output"
                )

            if stderr:
                st.subheader("Errors")
                st.code(stderr, language="bash")

            if return_code == 0:
                st.success(f"Profile '{profile_name}' completed successfully!")

                # Show results location
                project_root = st.session_state.get("project_root", Path.cwd())
                results_dir = project_root / "jobs" / "benchmark_profiles" / profile_name

                if results_dir.exists():
                    st.info(f"📁 Results: `{results_dir}`")

                    # List result directories
                    result_dirs = sorted(results_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
                    if result_dirs:
                        latest = result_dirs[0]
                        st.write(f"**Latest run:** `{latest.name}`")

                        # Show directory structure
                        with st.expander("View Results Structure"):
                            import os
                            for root, dirs, files in os.walk(latest):
                                level = root.replace(str(latest), '').count(os.sep)
                                indent = ' ' * 2 * level
                                st.text(f"{indent}{os.path.basename(root)}/")
                                subindent = ' ' * 2 * (level + 1)
                                for file in files[:20]:  # Limit to first 20 files
                                    st.text(f"{subindent}{file}")
            else:
                st.error(f"Profile failed with exit code {return_code}")

        except Exception as e:
            st.error(f"Error reading output: {e}")

        # Clear buffer on completion
        if "profile_output_buffer" in st.session_state:
            del st.session_state["profile_output_buffer"]

    # Control buttons
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Start New Profile Run"):
            # Clean up
            st.session_state["monitoring_profile"] = False
            del st.session_state["profile_process"]
            st.rerun()

    with col2:
        if return_code is None:
            if st.button("Stop Profile", type="secondary"):
                try:
                    process.terminate()
                    st.warning("Profile run terminated")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to stop: {e}")


def show_current_runs():
    """Show all current background runs with monitoring."""
    import sys
    from pathlib import Path

    project_root = st.session_state.get("project_root", Path.cwd())
    sys.path.insert(0, str(project_root / "dashboard"))
    from utils.run_tracker import RunTracker

    st.subheader("Current Background Runs")
    st.markdown("Monitor all running profile and benchmark evaluations")

    tracker = RunTracker(project_root / ".dashboard_runs")

    # Get all runs
    all_runs = tracker.list_runs()
    running_runs = [r for r in all_runs if r["status"] == "running"]
    completed_runs = [r for r in all_runs if r["status"] == "completed"]

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Running", len(running_runs))
    with col2:
        st.metric("Completed (Recent)", len(completed_runs[:10]))
    with col3:
        st.metric("Total Tracked", len(all_runs))

    st.markdown("---")

    # Show running runs
    if running_runs:
        st.markdown("### Active Runs")

        for run in running_runs:
            with st.expander(f"{run['profile_name'] or run['run_type']} - {run['run_id']}", expanded=True):
                # Show run details and monitoring
                show_run_monitor_compact(run, tracker)

    else:
        st.info("No active runs. Start a profile from the 'Profile Run' tab.")

    # Show recent completed runs
    if completed_runs:
        st.markdown("---")
        st.markdown("### Recently Completed")

        for run in completed_runs[:5]:  # Show last 5
            with st.expander(f"{run['profile_name'] or run['run_type']} - {run['run_id']}"):
                show_run_summary(run, tracker)

    # Cleanup button
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Cleanup Old Runs"):
            tracker.cleanup_completed(keep_recent=10)
            st.success("Cleaned up old completed runs")
            time.sleep(1)
            st.rerun()


def show_run_monitor_compact(run: dict, tracker):
    """Show compact monitoring view for a single run."""
    import datetime
    import re

    # Calculate elapsed time
    start_time = datetime.datetime.fromisoformat(run["start_time"])
    elapsed = datetime.datetime.now() - start_time
    elapsed_str = str(elapsed).split('.')[0]

    # Display metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**Status:** Running")
    with col2:
        st.write(f"**Elapsed:** {elapsed_str}")
    with col3:
        st.write(f"**PID:** {run['pid']}")

    # Debug info: Log file
    log_file = tracker.tracker_dir / f"{run['run_id']}.log"
    if log_file.exists():
        st.caption(f"Log: `{log_file.name}` ({log_file.stat().st_size} bytes)")
    else:
        st.error(f"Log file missing: {log_file}")

    # Get latest output for logs and parsing
    output = tracker.get_process_output(run["run_id"], tail_lines=50)

    # Parse for current agent/task
    current_agent = run.get("agent_name", "Starting...")
    current_task = run.get("benchmark_name", "Initializing...")

    # 1. Try to get more specific info from DB if possible
    from benchmark.database import RunManager, TaskManager
    run_db = RunManager.get(run["run_id"])
    if run_db:
        if run_db.get("agents"):
            db_agent = run_db["agents"][0].split(":")[-1]
            if db_agent:
                current_agent = db_agent
        
        # If multiple tasks, find the one that is currently running
        run_tasks = TaskManager.get_tasks(run["run_id"])
        running_tasks = [t for t in run_tasks if t["status"] == "running"]
        if running_tasks:
            current_task = running_tasks[0]["task_name"]
        elif run_db.get("task_selection"):
            current_task = run_db["task_selection"][0]

    # 2. Fallback to regex parsing if DB info is sparse
    if current_agent == "Starting..." or current_task == "Initializing...":
        if output:
            # Look for agent (new format with optional timestamp)
            agent_matches = re.findall(r"Starting agent:\s*([^\s]+)", output)
            if agent_matches:
                current_agent = agent_matches[-1]
            else:
                agent_matches = re.findall(r"--agent-import-path\s+(\S+)", output)
                if agent_matches:
                    agent_path = agent_matches[-1]
                    current_agent = agent_path.split(":")[-1] if ":" in agent_path else agent_path

            # Look for task (new format)
            task_matches = re.findall(r"on task:\s*([^\s]+)", output)
            if task_matches:
                current_task = task_matches[-1]
            else:
                task_matches = re.findall(r"instance[_-]([a-zA-Z0-9_-]+)", output)
                if task_matches:
                    current_task = task_matches[-1][:30] + "..." if len(task_matches[-1]) > 30 else task_matches[-1]

    st.write(f"**Agent:** {current_agent}")
    st.write(f"**Task:** {current_task}")

    # Show live log
    if output:
        # Add content hash to key to force Streamlit to update the widget
        import hashlib
        content_hash = hashlib.md5(output.encode()).hexdigest()[:8]

        st.text_area(
            "Live Output (last 50 lines)",
            output,
            height=300,
            key=f"output_{run['run_id']}_{content_hash}"
        )
        # Also show byte count to prove it's updating
        st.caption(f"Log size: {len(output)} chars | Last {len(output.split(chr(10)))} lines")
    else:
        st.info("Waiting for output...")

    # Control buttons
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🔄 Refresh Now", key=f"refresh_{run['run_id']}"):
            st.rerun()
    with col2:
        # Toggle auto-refresh
        auto_refresh_key = f"auto_refresh_{run['run_id']}"
        if auto_refresh_key not in st.session_state:
            st.session_state[auto_refresh_key] = True

        auto_refresh = st.checkbox(
            "Auto-refresh",
            value=st.session_state[auto_refresh_key],
            key=f"auto_refresh_checkbox_{run['run_id']}"
        )
        st.session_state[auto_refresh_key] = auto_refresh
    with col3:
        if st.button("Stop", key=f"stop_{run['run_id']}", type="secondary"):
            if tracker.terminate_run(run["run_id"]):
                st.warning("Run terminated")
                time.sleep(1)
                st.rerun()
    with col4:
        if st.button("Remove", key=f"remove_{run['run_id']}"):
            tracker.remove_run(run["run_id"])
            st.success("Run removed from tracking")
            time.sleep(1)
            st.rerun()

    # Auto-refresh if running and enabled
    auto_refresh_key = f"auto_refresh_{run['run_id']}"
    if run["status"] == "running" and st.session_state.get(auto_refresh_key, True):
        import datetime
        now = datetime.datetime.now()
        st.caption(f"Last updated: {now.strftime('%H:%M:%S')} - Auto-refreshing every 5 seconds")
        time.sleep(5)
        st.rerun()


def show_run_summary(run: dict, tracker):
    """Show summary of a completed run."""
    import datetime

    start_time = datetime.datetime.fromisoformat(run["start_time"])
    st.write(f"**Started:** {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    st.write(f"**Command:** `{run['command']}`")

    # Show final output excerpt
    output = tracker.get_process_output(run["run_id"], tail_lines=20)
    if output:
        with st.expander("View Output (last 20 lines)"):
            st.code(output)

    if st.button("Remove", key=f"remove_summary_{run['run_id']}"):
        tracker.remove_run(run["run_id"])
        st.success("Run removed")
        time.sleep(1)
        st.rerun()


def show_evaluation_runner():
    """Main evaluation runner page."""
    st.title("Evaluation Runner")
    st.write("Run and monitor benchmark evaluations")

    # Add tabs for single run, profile run, and current runs
    tab1, tab2, tab3 = st.tabs(["Single Run", "Profile Run", "Current Runs"])

    with tab1:
        # Show configuration form for single run
        show_run_configuration()

    with tab2:
        # Show profile runner
        show_profile_runner()

    with tab3:
        # Show current background runs
        show_current_runs()

    st.markdown("---")

    # Show recent runs
    show_recent_runs()


if __name__ == "__main__":
    show_evaluation_runner()