"""
Run Trigger Interface

Provides UI to trigger:
- Benchmark lifecycle pipeline
- Profile runs
- Postprocess evaluation
"""

import streamlit as st
from pathlib import Path
import subprocess
import json
from typing import Optional


def run_command(command: str, cwd: Optional[Path] = None) -> tuple[int, str, str]:
    """
    Run a shell command and return results.

    Returns:
        (exit_code, stdout, stderr)
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out after 5 minutes"
    except Exception as e:
        return -1, "", str(e)


def show_benchmark_lifecycle_trigger():
    """UI for triggering benchmark lifecycle pipeline."""
    st.subheader("Benchmark Lifecycle Pipeline")

    st.markdown(
        """
    Run the benchmark lifecycle pipeline to:
    - Refresh benchmark adapters
    - Regenerate tasks
    - Validate with Harbor
    - Generate MANIFEST.json
    """
    )

    # Get project root
    project_root = st.session_state.get("project_root", Path.cwd())

    # Benchmark selector
    benchmarks_dir = project_root / "benchmarks"
    if benchmarks_dir.exists():
        benchmark_dirs = [
            d.name
            for d in benchmarks_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
        benchmark_dirs = sorted(benchmark_dirs)
    else:
        benchmark_dirs = []

    selected_benchmarks = st.multiselect(
        "Select Benchmarks (leave empty for all)", benchmark_dirs
    )

    dry_run = st.checkbox("Dry Run (preview commands only)", value=True)

    if st.button("Run Lifecycle Pipeline", key="lifecycle_run"):
        # Build command
        cmd_parts = ["python scripts/benchmark_lifecycle.py"]

        if selected_benchmarks:
            cmd_parts.append(f"--benchmarks {' '.join(selected_benchmarks)}")

        if dry_run:
            cmd_parts.append("--dry-run")

        command = " ".join(cmd_parts)

        st.info(f"Running: `{command}`")

        with st.spinner("Running..."):
            exit_code, stdout, stderr = run_command(command, cwd=project_root)

        if exit_code == 0:
            st.success("Pipeline completed successfully!")
        else:
            st.error(f"Pipeline failed with exit code {exit_code}")

        if stdout:
            st.text_area("Output", stdout, height=300)

        if stderr:
            st.text_area("Errors", stderr, height=200)


def show_profile_runner_trigger():
    """UI for triggering profile runs."""
    st.subheader("Profile Runner")

    st.markdown(
        """
    Run benchmark profiles with agent matrices:
    - Select profiles to run
    - Launch Harbor with multiple agents
    - Generate PROFILE_MANIFEST.json
    """
    )

    # Get project root
    project_root = st.session_state.get("project_root", Path.cwd())

    # Load profiles from config
    profiles_config = project_root / "configs" / "benchmark_profiles.yaml"

    if not profiles_config.exists():
        st.warning(f"Profiles config not found: {profiles_config}")
        return

    st.info(f"Using config: `{profiles_config}`")

    # Parse YAML to get available profiles
    import yaml
    try:
        with open(profiles_config) as f:
            config = yaml.safe_load(f)
            available_profiles = list(config.get("profiles", {}).keys())

        if not available_profiles:
            st.warning("No profiles found in config")
            profile_name = st.text_input("Profile Name (manual entry)")
        else:
            # Show dropdown with available profiles
            profile_name = st.selectbox(
                "Select Profile",
                available_profiles,
                help="Profile defined in configs/benchmark_profiles.yaml"
            )

            # Show profile description if available
            if profile_name:
                profile_desc = config["profiles"][profile_name].get("description", "")
                if profile_desc:
                    st.caption(f"{profile_desc}")

    except Exception as e:
        st.error(f"Error loading profiles: {e}")
        profile_name = st.text_input("Profile Name (e.g., repoqa_smoke)")

    dry_run = st.checkbox("Dry Run (preview commands only)", value=True, key="profile_dry")

    if st.button("Run Profile", key="profile_run"):
        cmd_parts = ["python", "scripts/benchmark_profile_runner.py"]

        if profile_name:
            cmd_parts.extend(["--profiles", profile_name])

        if dry_run:
            cmd_parts.append("--dry-run")

        command = " ".join(cmd_parts)

        st.info(f"Running: `{command}`")

        with st.spinner("Running..."):
            exit_code, stdout, stderr = run_command(command, cwd=project_root)

        if exit_code == 0:
            st.success("Profile run completed!")
        else:
            st.error(f"Profile run failed with exit code {exit_code}")

        if stdout:
            st.text_area("Output", stdout, height=300, key="profile_stdout")

        if stderr:
            st.text_area("Errors", stderr, height=200, key="profile_stderr")


def show_postprocess_trigger():
    """UI for triggering postprocess evaluation."""
    st.subheader("Post-Process Evaluation")

    st.markdown(
        """
    Post-process an experiment:
    - Extract metrics from Harbor results
    - Run LLM judge evaluation
    - Generate evaluation_report.json and REPORT.md
    """
    )

    # Get project root
    project_root = st.session_state.get("project_root", Path.cwd())
    jobs_dir = project_root / "jobs"

    if not jobs_dir.exists():
        st.warning(f"Jobs directory not found: {jobs_dir}")
        return

    # Experiment selector
    exp_dirs = [
        d.name
        for d in sorted(jobs_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
        if d.is_dir() and not d.name.startswith(".")
    ]

    selected_exp = st.selectbox("Select Experiment", exp_dirs)

    # Options
    col1, col2 = st.columns(2)

    with col1:
        benchmark_id = st.text_input("Benchmark ID (optional)", placeholder="repoqa")

    with col2:
        profile_name = st.text_input("Profile Name (optional)", placeholder="repoqa_smoke")

    run_judge = st.checkbox("Run LLM Judge (requires ANTHROPIC_API_KEY)", value=False)

    if run_judge:
        judge_model = st.selectbox(
            "Judge Model",
            [
                "claude-haiku-4-5-20251001",
                "claude-sonnet-4-5-20250929",
                "claude-opus-4-5-20251101",
            ],
        )
    else:
        judge_model = "claude-haiku-4-5-20251001"

    if st.button("Run Post-Process", key="postprocess_run"):
        if not selected_exp:
            st.error("Please select an experiment")
            return

        exp_path = jobs_dir / selected_exp

        cmd_parts = [f"python scripts/postprocess_experiment.py {exp_path}"]

        if benchmark_id:
            cmd_parts.append(f"--benchmark {benchmark_id}")

        if profile_name:
            cmd_parts.append(f"--profile {profile_name}")

        if run_judge:
            cmd_parts.append("--judge")
            cmd_parts.append(f"--judge-model {judge_model}")

        command = " ".join(cmd_parts)

        st.info(f"Running: `{command}`")

        with st.spinner("Running post-process..."):
            exit_code, stdout, stderr = run_command(command, cwd=project_root)

        if exit_code == 0:
            st.success("Post-processing completed!")

            # Check for outputs
            report_json = exp_path / "evaluation_report.json"
            report_md = exp_path / "REPORT.md"

            if report_json.exists():
                st.success(f"Generated: {report_json}")

            if report_md.exists():
                st.success(f"Generated: {report_md}")

        else:
            st.error(f"Post-processing failed with exit code {exit_code}")

        if stdout:
            st.text_area("Output", stdout, height=300, key="postprocess_stdout")

        if stderr:
            st.text_area("Errors", stderr, height=200, key="postprocess_stderr")


def show_run_triggers():
    """Main run triggers page."""
    st.title("Run Benchmarks")
    st.markdown("Launch benchmark lifecycle, profile runs, or evaluation pipelines.")

    st.warning(
        "These operations can take significant time and resources. "
        "Use dry-run mode first to preview commands."
    )

    st.markdown("---")

    # Tabs for different trigger types
    tab1, tab2, tab3 = st.tabs(
        ["Benchmark Lifecycle", "Profile Runner", "Post-Process"]
    )

    with tab1:
        show_benchmark_lifecycle_trigger()

    with tab2:
        show_profile_runner_trigger()

    with tab3:
        show_postprocess_trigger()


if __name__ == "__main__":
    show_run_triggers()
