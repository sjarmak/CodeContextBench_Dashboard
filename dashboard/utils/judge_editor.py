"""
LLM judge prompt and rubric editor UI component.

Renders Streamlit widgets for editing the judge system prompt,
scoring dimensions (name, weight, per-level criteria), model
selection, temperature, and max_tokens. Saves configuration
to configs/judge_templates/active_config.json.
"""

import logging
from pathlib import Path

import streamlit as st

from dashboard.utils.judge_config import (
    AVAILABLE_MODELS,
    JudgeConfig,
    ScoringCriterion,
    ScoringDimension,
    add_dimension,
    config_to_dict,
    default_config,
    dict_to_config,
    load_config,
    remove_dimension,
    save_config,
)

logger = logging.getLogger(__name__)

SESSION_KEY_PREFIX = "judge_editor"


def _session_key(suffix: str) -> str:
    """Build a session state key for the editor."""
    return f"{SESSION_KEY_PREFIX}_{suffix}"


def _config_to_session_state(config: JudgeConfig) -> None:
    """Populate Streamlit session state from a JudgeConfig.

    Stores the config as a mutable dict in session state so widgets
    can read and write values during the editing session.

    Args:
        config: JudgeConfig to load into session state
    """
    state = config_to_dict(config)
    st.session_state[_session_key("data")] = state
    st.session_state[_session_key("initialized")] = True


def _session_state_to_config() -> JudgeConfig:
    """Read the current editor session state and produce a JudgeConfig.

    Returns:
        JudgeConfig built from session state values
    """
    data = st.session_state.get(_session_key("data"), {})
    if not data:
        return default_config()
    return dict_to_config(data)


def _ensure_initialized(project_root: Path) -> None:
    """Load config into session state if not already initialized."""
    if not st.session_state.get(_session_key("initialized"), False):
        config = load_config(project_root)
        _config_to_session_state(config)


def _render_system_prompt() -> None:
    """Render the system prompt text area."""
    data = st.session_state[_session_key("data")]

    st.markdown("### System Prompt")
    new_prompt = st.text_area(
        "System prompt for the LLM judge",
        value=data.get("system_prompt", ""),
        height=200,
        key=_session_key("system_prompt_input"),
        label_visibility="collapsed",
    )
    data["system_prompt"] = new_prompt


def _render_model_settings() -> None:
    """Render model selection, temperature, and max_tokens controls."""
    data = st.session_state[_session_key("data")]

    st.markdown("### Model Settings")
    col_model, col_temp, col_tokens = st.columns([2, 1, 1])

    with col_model:
        current_model = data.get("model", AVAILABLE_MODELS[0])
        model_index = 0
        if current_model in AVAILABLE_MODELS:
            model_index = AVAILABLE_MODELS.index(current_model)

        selected_model = st.selectbox(
            "Model",
            AVAILABLE_MODELS,
            index=model_index,
            key=_session_key("model_select"),
        )
        data["model"] = selected_model

    with col_temp:
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=float(data.get("temperature", 0.0)),
            step=0.1,
            key=_session_key("temperature_slider"),
        )
        data["temperature"] = temperature

    with col_tokens:
        max_tokens = st.number_input(
            "Max tokens",
            min_value=256,
            max_value=32768,
            value=int(data.get("max_tokens", 4096)),
            step=256,
            key=_session_key("max_tokens_input"),
        )
        data["max_tokens"] = max_tokens


def _render_dimension_row(dim_data: dict, index: int) -> bool:
    """Render a single dimension row with name, weight, criteria, and delete.

    Args:
        dim_data: Dict with name, weight, criteria keys
        index: Index in the dimensions list

    Returns:
        True if the dimension should be deleted
    """
    should_delete = False

    col_name, col_weight, col_delete = st.columns([3, 2, 1])

    with col_name:
        new_name = st.text_input(
            "Dimension name",
            value=dim_data.get("name", ""),
            key=_session_key(f"dim_name_{index}"),
            label_visibility="collapsed",
            placeholder="Dimension name",
        )
        dim_data["name"] = new_name

    with col_weight:
        new_weight = st.slider(
            "Weight",
            min_value=0.0,
            max_value=1.0,
            value=float(dim_data.get("weight", 0.5)),
            step=0.05,
            key=_session_key(f"dim_weight_{index}"),
        )
        dim_data["weight"] = new_weight

    with col_delete:
        st.markdown("")
        st.markdown("")
        if st.button(
            "Delete",
            key=_session_key(f"dim_delete_{index}"),
            type="secondary",
        ):
            should_delete = True

    # Per-level criteria (1-5)
    criteria = dim_data.get("criteria", [])
    # Ensure 5 levels exist
    while len(criteria) < 5:
        criteria = [*criteria, {"level": len(criteria) + 1, "description": ""}]
    dim_data["criteria"] = criteria

    with st.expander(f"Score criteria (1-5)", expanded=False):
        for level_idx, criterion in enumerate(criteria[:5]):
            level_num = criterion.get("level", level_idx + 1)
            new_desc = st.text_input(
                f"Score {level_num}",
                value=criterion.get("description", ""),
                key=_session_key(f"dim_{index}_level_{level_num}"),
            )
            criteria[level_idx] = {"level": level_num, "description": new_desc}

    return should_delete


def _render_dimensions() -> None:
    """Render the full scoring dimensions editor."""
    data = st.session_state[_session_key("data")]

    st.markdown("### Scoring Dimensions")
    st.caption("Name | Weight (0-1) | Delete")

    dimensions = data.get("dimensions", [])
    indices_to_delete: list[int] = []

    for i, dim in enumerate(dimensions):
        if _render_dimension_row(dim, i):
            indices_to_delete = [*indices_to_delete, i]
        if i < len(dimensions) - 1:
            st.markdown("---")

    # Process deletions (reverse order to preserve indices)
    if indices_to_delete:
        remaining = [
            d for idx, d in enumerate(dimensions) if idx not in indices_to_delete
        ]
        data["dimensions"] = remaining
        st.rerun()

    # Add dimension button
    st.markdown("")
    if st.button(
        "Add Dimension",
        key=_session_key("add_dimension"),
        type="secondary",
    ):
        new_dim = {
            "name": "",
            "weight": 0.5,
            "criteria": [
                {"level": i + 1, "description": ""} for i in range(5)
            ],
        }
        data["dimensions"] = [*dimensions, new_dim]
        st.rerun()


def _render_save_button(project_root: Path) -> None:
    """Render the save button and handle saving."""
    st.markdown("---")

    if st.button(
        "Save Configuration",
        key=_session_key("save_button"),
        type="primary",
    ):
        config = _session_state_to_config()
        try:
            saved_path = save_config(config, project_root)
            st.success(f"Configuration saved to {saved_path}")
        except OSError as e:
            st.error(f"Failed to save configuration: {e}")


def render_judge_editor(project_root: Path) -> None:
    """Render the full LLM judge prompt and rubric editor.

    This is the main entry point for the editor UI. It loads the
    current config from disk (or defaults), renders editable widgets,
    and provides a save button.

    Args:
        project_root: Path to the project root directory
    """
    _ensure_initialized(project_root)

    _render_system_prompt()
    st.markdown("---")
    _render_model_settings()
    st.markdown("---")
    _render_dimensions()
    _render_save_button(project_root)
