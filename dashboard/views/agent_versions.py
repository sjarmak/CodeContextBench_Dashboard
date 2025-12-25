"""
Agent Versions Manager

Manage agent configurations including:
- Model selection
- Prompt templates
- Tool configurations
- MCP settings
- Versioning for tracking changes
"""

import streamlit as st
from pathlib import Path
import sys
import uuid
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from benchmark.database import AgentRegistry
import pandas as pd


def show_agent_list():
    """Display list of agent versions."""
    st.subheader("Agent Versions")

    agents = AgentRegistry.list_all()

    if not agents:
        st.info("No agent versions registered. Create one to get started.")
        return

    # Create table
    data = []
    for agent in agents:
        data.append({
            "Version ID": agent["version_id"],
            "Name": agent["name"],
            "Model": agent["model"],
            "Import Path": agent["import_path"],
            "Created": agent.get("created_at", "")[:19] if agent.get("created_at") else "",
            "Active": "Yes" if agent.get("is_active") else "No",
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def show_create_agent():
    """Form to create new agent version."""
    st.subheader("Create New Agent Version")

    with st.form("create_agent_form"):
        name = st.text_input("Agent Name", placeholder="My Custom Agent")

        description = st.text_area(
            "Description",
            placeholder="Describe what makes this agent unique..."
        )

        # Model selection
        models = [
            "anthropic/claude-haiku-4-5-20251001",
            "anthropic/claude-sonnet-3-5-20250929",
            "anthropic/claude-opus-3-20240229",
        ]

        model = st.selectbox("Model", models)

        import_path = st.text_input(
            "Agent Import Path",
            placeholder="agents.my_agent:MyAgent"
        )

        # Advanced settings in expander
        with st.expander("Advanced Settings"):
            prompt_template = st.text_area(
                "Custom Prompt Template (optional)",
                placeholder="System prompt or template..."
            )

            st.markdown("**Tool Configuration (JSON)**")
            tools_config_text = st.text_area(
                "Tools Config",
                value='{}',
                height=100
            )

            st.markdown("**MCP Configuration (JSON)**")
            mcp_config_text = st.text_area(
                "MCP Config",
                value='{}',
                height=100
            )

        submitted = st.form_submit_button("Create Agent Version")

        if submitted:
            if not name or not import_path:
                st.error("Name and import path are required")
                return

            try:
                # Parse JSON configs
                import json
                tools_config = json.loads(tools_config_text) if tools_config_text else None
                mcp_config = json.loads(mcp_config_text) if mcp_config_text else None

                # Generate version ID
                version_id = f"{name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}"

                # Create agent
                agent_id = AgentRegistry.add(
                    version_id=version_id,
                    name=name,
                    model=model,
                    import_path=import_path,
                    description=description,
                    prompt_template=prompt_template if prompt_template else None,
                    tools_config=tools_config,
                    mcp_config=mcp_config,
                )

                st.success(f"Agent version created: {version_id}")

            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON configuration: {e}")
            except Exception as e:
                st.error(f"Failed to create agent: {e}")


def show_agent_details():
    """Show details of selected agent."""
    agents = AgentRegistry.list_all()

    if not agents:
        return

    version_ids = [a["version_id"] for a in agents]
    selected_version_id = st.selectbox("Select Agent Version", version_ids)

    if not selected_version_id:
        return

    agent = AgentRegistry.get(selected_version_id)

    if not agent:
        return

    st.subheader(f"Agent: {agent['name']}")

    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**Version ID:** `{agent['version_id']}`")
        st.write(f"**Model:** {agent['model']}")
        st.write(f"**Import Path:** `{agent['import_path']}`")

    with col2:
        st.write(f"**Created:** {agent.get('created_at', 'N/A')[:19]}")
        st.write(f"**Active:** {'Yes' if agent.get('is_active') else 'No'}")

    if agent.get("description"):
        st.markdown("**Description:**")
        st.write(agent["description"])

    # Show configs
    if agent.get("prompt_template"):
        with st.expander("Prompt Template"):
            st.code(agent["prompt_template"])

    if agent.get("tools_config"):
        with st.expander("Tools Configuration"):
            st.json(agent["tools_config"])

    if agent.get("mcp_config"):
        with st.expander("MCP Configuration"):
            st.json(agent["mcp_config"])

    # Actions
    col1, col2 = st.columns(2)

    with col1:
        if agent.get("is_active"):
            if st.button("Deactivate"):
                AgentRegistry.deactivate(selected_version_id)
                st.success("Agent deactivated")
                st.rerun()

    with col2:
        if st.button("Use in Evaluation"):
            st.info(f"Use import path in evaluation runner: {agent['import_path']}")


def show_agent_versions():
    """Main agent versions page."""
    st.title("Agent Versions Manager")
    st.write("Manage agent configurations and versions")

    tab1, tab2, tab3 = st.tabs(["Agent List", "Create New", "Details"])

    with tab1:
        show_agent_list()

    with tab2:
        show_create_agent()

    with tab3:
        show_agent_details()


if __name__ == "__main__":
    show_agent_versions()
