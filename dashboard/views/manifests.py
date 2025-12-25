"""
Benchmark Manifest Viewer

Displays benchmark MANIFEST.json files with:
- Dataset information and hashes
- Validation logs and breadcrumbs
- Environment fingerprints
- Artifact paths and creation commands
"""

import streamlit as st
from pathlib import Path
import json
from datetime import datetime
from typing import Optional, Dict, Any, List


def load_manifest(manifest_path: Path) -> Optional[Dict[str, Any]]:
    """Load MANIFEST.json file."""
    try:
        with open(manifest_path) as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Failed to load manifest: {e}")
        return None


def find_manifests(benchmarks_dir: Path) -> List[tuple[str, Path]]:
    """Find all MANIFEST.json files in benchmarks directory."""
    manifests = []
    for manifest_path in benchmarks_dir.rglob("MANIFEST.json"):
        # Get benchmark name from path
        benchmark_name = manifest_path.parent.name
        manifests.append((benchmark_name, manifest_path))
    return sorted(manifests)


def render_manifest_selector(benchmarks_dir: Path) -> Optional[Path]:
    """Render manifest selector and return selected path."""
    manifests = find_manifests(benchmarks_dir)

    if not manifests:
        st.warning("No MANIFEST.json files found in benchmarks directory.")
        return None

    benchmark_names = [name for name, _ in manifests]
    selected_name = st.selectbox("Select Benchmark", benchmark_names)

    if selected_name:
        for name, path in manifests:
            if name == selected_name:
                return path

    return None


def render_manifest_overview(manifest: Dict[str, Any]):
    """Render manifest overview section."""
    st.subheader("📋 Manifest Overview")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Benchmark ID", manifest.get("benchmark_id", "N/A"))

    with col2:
        generated_at = manifest.get("generated_at", "N/A")
        if generated_at != "N/A":
            try:
                dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
                generated_at = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            except:
                pass
        st.metric("Generated At", generated_at)

    with col3:
        pipeline = manifest.get("pipeline", {})
        st.metric("Pipeline Version", pipeline.get("version", "N/A"))

    st.markdown(f"**Description:** {manifest.get('description', 'No description')}")
    st.markdown(f"**Task Root:** `{manifest.get('task_root', 'N/A')}`")
    st.markdown(f"**Repo Commit:** `{manifest.get('repo_commit', 'N/A')}`")


def render_datasets(manifest: Dict[str, Any]):
    """Render datasets section."""
    st.subheader("💾 Datasets")

    datasets = manifest.get("datasets", [])

    if not datasets:
        st.info("No datasets listed in manifest.")
        return

    for i, dataset in enumerate(datasets):
        with st.expander(f"Dataset {i+1}: {Path(dataset.get('path', 'unknown')).name}"):
            st.markdown(f"**Path:** `{dataset.get('path', 'N/A')}`")
            st.markdown(f"**Exists:** {dataset.get('exists', False)}")
            st.markdown(f"**SHA-256:** `{dataset.get('sha256', 'N/A')}`")


def render_artifacts(manifest: Dict[str, Any]):
    """Render artifacts section."""
    st.subheader("📦 Artifacts")

    artifacts = manifest.get("artifacts", [])

    if not artifacts:
        st.info("No artifacts listed in manifest.")
        return

    for i, artifact in enumerate(artifacts):
        with st.expander(f"Artifact {i+1}: {Path(artifact.get('path', 'unknown')).name}"):
            st.markdown(f"**Path:** `{artifact.get('path', 'N/A')}`")
            st.markdown(f"**Type:** {artifact.get('type', 'N/A')}")
            st.markdown(f"**Exists:** {artifact.get('exists', False)}")


def render_creation_steps(manifest: Dict[str, Any]):
    """Render creation steps section."""
    st.subheader("🔨 Creation Steps")

    creation = manifest.get("creation", {})
    steps = creation.get("steps", [])

    if not steps:
        st.info("No creation steps in manifest.")
        return

    for i, step in enumerate(steps):
        status = step.get("status", "unknown")
        status_emoji = "✅" if status == "success" else "❌"

        with st.expander(f"{status_emoji} Step {i+1}: {step.get('name', 'Unnamed')}"):
            st.markdown(f"**Status:** {status}")
            st.markdown(f"**Exit Code:** {step.get('exit_code', 'N/A')}")

            command = step.get("command", "")
            if command:
                st.markdown("**Command:**")
                st.code(command, language="bash")

            log_path = step.get("log_path", "")
            if log_path and Path(log_path).exists():
                if st.button(f"View Log", key=f"creation_log_{i}"):
                    with open(log_path) as f:
                        log_content = f.read()
                    st.text_area("Log Output", log_content, height=300, key=f"log_content_{i}")


def render_validation_steps(manifest: Dict[str, Any]):
    """Render validation steps section."""
    st.subheader("✅ Validation Steps")

    validation = manifest.get("validation", {})
    steps = validation.get("steps", [])

    if not steps:
        st.info("No validation steps in manifest.")
        return

    for i, step in enumerate(steps):
        status = step.get("status", "unknown")
        status_emoji = "✅" if status == "success" else "❌"

        with st.expander(f"{status_emoji} Step {i+1}: {step.get('name', 'Unnamed')}"):
            st.markdown(f"**Status:** {status}")

            command = step.get("command", "")
            if command:
                st.markdown("**Command:**")
                st.code(command, language="bash")

            log_path = step.get("log_path", "")
            if log_path and Path(log_path).exists():
                if st.button(f"View Log", key=f"validation_log_{i}"):
                    with open(log_path) as f:
                        log_content = f.read()
                    st.text_area("Log Output", log_content, height=300, key=f"val_log_content_{i}")


def render_environment(manifest: Dict[str, Any]):
    """Render environment section."""
    st.subheader("🌍 Environment")

    env = manifest.get("environment", {})

    st.markdown(f"**Python:** {env.get('python', 'N/A')}")
    st.markdown(f"**Harbor:** {env.get('harbor', 'N/A')}")

    # Fingerprint
    st.markdown("**Environment Fingerprint:**")
    fingerprint = env.get("fingerprint", {})
    st.markdown(f"Combined Hash: `{fingerprint.get('combined_hash', 'N/A')}`")

    variables = fingerprint.get("variables", [])
    if variables:
        st.markdown("**Variables:**")
        for var in variables:
            is_set = "✅" if var.get("set", False) else "❌"
            st.markdown(f"- {is_set} `{var.get('name', 'unknown')}`: `{var.get('sha256', 'N/A')[:16]}...`")

    # Env files
    env_files = env.get("env_files", [])
    if env_files:
        st.markdown("**Environment Files:**")
        for ef in env_files:
            exists = "✅" if ef.get("exists", False) else "❌"
            st.markdown(f"- {exists} `{ef.get('path', 'unknown')}`: `{ef.get('sha256', 'N/A')[:16]}...`")


def show_manifest_viewer():
    """Main manifest viewer page."""
    st.title("📋 Benchmark Manifests")
    st.markdown("Browse benchmark configurations, datasets, and validation logs.")

    # Get project root
    project_root = st.session_state.get("project_root", Path.cwd())
    benchmarks_dir = project_root / "benchmarks"

    if not benchmarks_dir.exists():
        st.error(f"Benchmarks directory not found: {benchmarks_dir}")
        return

    # Manifest selector
    selected_path = render_manifest_selector(benchmarks_dir)

    if not selected_path:
        return

    # Load manifest
    manifest = load_manifest(selected_path)

    if not manifest:
        return

    st.markdown("---")

    # Render sections
    render_manifest_overview(manifest)
    st.markdown("---")

    render_datasets(manifest)
    st.markdown("---")

    render_artifacts(manifest)
    st.markdown("---")

    render_creation_steps(manifest)
    st.markdown("---")

    render_validation_steps(manifest)
    st.markdown("---")

    render_environment(manifest)

    # Raw JSON view
    st.markdown("---")
    if st.checkbox("Show Raw JSON"):
        st.json(manifest)


if __name__ == "__main__":
    show_manifest_viewer()
