"""
LLM judge template save, load, delete, and duplicate UI component.

Renders a template list sidebar with management controls and a
save-as-template section for the editor. Templates are persisted
to configs/judge_templates/ as JSON files with metadata.
"""

import logging
from pathlib import Path

import streamlit as st

from dashboard.utils.judge_config import (
    TemplateInfo,
    delete_template,
    duplicate_template,
    list_template_infos,
    load_config,
    save_template,
)
from dashboard.utils.judge_editor import (
    _config_to_session_state,
    _session_state_to_config,
)

logger = logging.getLogger(__name__)

SESSION_KEY_PREFIX = "judge_template_mgr"


def _session_key(suffix: str) -> str:
    """Build a session state key for the template manager."""
    return f"{SESSION_KEY_PREFIX}_{suffix}"


def _format_created_at(iso_str: str) -> str:
    """Format an ISO datetime string for display.

    Args:
        iso_str: ISO format datetime string

    Returns:
        Formatted date string or 'Unknown' if parsing fails
    """
    if not iso_str:
        return "Unknown"
    try:
        return iso_str[:10]
    except (ValueError, IndexError):
        return "Unknown"


def _format_model_display(model: str) -> str:
    """Format a model identifier for compact display.

    Args:
        model: Full model identifier string

    Returns:
        Short model display name
    """
    if "haiku" in model:
        return "Haiku"
    if "sonnet" in model:
        return "Sonnet"
    if "opus" in model:
        return "Opus"
    return model[:20]


def render_save_template_section(project_root: Path) -> None:
    """Render the 'Save as Template' section with name input and save button.

    Args:
        project_root: Path to the project root directory
    """
    st.markdown("### Save as Template")

    template_name = st.text_input(
        "Template name",
        value="",
        key=_session_key("save_name"),
        placeholder="Enter a name for this template",
    )

    if st.button(
        "Save Template",
        key=_session_key("save_button"),
        type="primary",
        disabled=not template_name.strip(),
    ):
        if not template_name.strip():
            st.warning("Please enter a template name.")
            return

        config = _session_state_to_config()
        try:
            saved_path = save_template(config, project_root, template_name.strip())
            st.success(f"Template '{template_name.strip()}' saved to {saved_path.name}")
            st.rerun()
        except OSError as e:
            st.error(f"Failed to save template: {e}")


def _render_template_row(
    info: TemplateInfo,
    project_root: Path,
    index: int,
) -> None:
    """Render a single template row with metadata and action buttons.

    Args:
        info: Template metadata
        project_root: Project root directory
        index: Row index for unique widget keys
    """
    col_info, col_actions = st.columns([3, 2])

    with col_info:
        st.markdown(f"**{info.name}**")
        created = _format_created_at(info.created_at)
        model = _format_model_display(info.model)
        st.caption(f"Created: {created} | Model: {model}")

    with col_actions:
        btn_cols = st.columns(3)

        with btn_cols[0]:
            load_clicked = st.button(
                "Load",
                key=_session_key(f"load_{index}"),
                type="primary",
            )

        with btn_cols[1]:
            dup_clicked = st.button(
                "Duplicate",
                key=_session_key(f"dup_{index}"),
            )

        with btn_cols[2]:
            del_clicked = st.button(
                "Delete",
                key=_session_key(f"del_{index}"),
            )

    if load_clicked:
        _handle_load(project_root, info)

    if dup_clicked:
        _handle_duplicate(project_root, info)

    if del_clicked:
        _handle_delete_request(index)


def _handle_load(project_root: Path, info: TemplateInfo) -> None:
    """Load a template into the editor session state.

    Args:
        project_root: Project root directory
        info: Template metadata
    """
    config = load_config(project_root, info.filename)
    _config_to_session_state(config)
    st.success(f"Loaded template '{info.name}'")
    st.rerun()


def _handle_duplicate(project_root: Path, info: TemplateInfo) -> None:
    """Duplicate a template.

    Args:
        project_root: Project root directory
        info: Template metadata
    """
    result = duplicate_template(project_root, info.filename)
    if result is not None:
        st.success(f"Duplicated '{info.name}' as '{info.name}-copy'")
        st.rerun()
    else:
        st.error(f"Failed to duplicate template '{info.name}'")


def _handle_delete_request(index: int) -> None:
    """Set session state to show delete confirmation for a template.

    Args:
        index: Template index to confirm deletion for
    """
    st.session_state[_session_key("confirm_delete")] = index


def _handle_delete_confirm(
    project_root: Path,
    info: TemplateInfo,
) -> None:
    """Execute template deletion after confirmation.

    Args:
        project_root: Project root directory
        info: Template metadata
    """
    if delete_template(project_root, info.filename):
        st.success(f"Deleted template '{info.name}'")
        st.session_state.pop(_session_key("confirm_delete"), None)
        st.rerun()
    else:
        st.error(f"Failed to delete template '{info.name}'")


def render_template_list(project_root: Path) -> None:
    """Render the template list with load, delete, and duplicate actions.

    Args:
        project_root: Path to the project root directory
    """
    st.markdown("### Saved Templates")

    infos = list_template_infos(project_root)

    if not infos:
        st.info("No saved templates. Use 'Save as Template' above to create one.")
        return

    st.caption(f"{len(infos)} template(s)")

    confirm_delete_idx = st.session_state.get(_session_key("confirm_delete"))

    for i, info in enumerate(infos):
        if confirm_delete_idx == i:
            _render_delete_confirmation(project_root, info, i)
        else:
            _render_template_row(info, project_root, i)

        if i < len(infos) - 1:
            st.markdown("---")


def _render_delete_confirmation(
    project_root: Path,
    info: TemplateInfo,
    index: int,
) -> None:
    """Render a delete confirmation dialog for a template.

    Args:
        project_root: Project root directory
        info: Template metadata
        index: Template index
    """
    st.warning(f"Delete template '{info.name}'?")
    col_yes, col_no = st.columns(2)

    with col_yes:
        if st.button(
            "Confirm Delete",
            key=_session_key(f"confirm_yes_{index}"),
            type="primary",
        ):
            _handle_delete_confirm(project_root, info)

    with col_no:
        if st.button(
            "Cancel",
            key=_session_key(f"confirm_no_{index}"),
        ):
            st.session_state.pop(_session_key("confirm_delete"), None)
            st.rerun()


def render_template_manager(project_root: Path) -> None:
    """Render the full template management section.

    This is the main entry point for the template manager UI.
    It renders both the save-as-template section and the template list.

    Args:
        project_root: Path to the project root directory
    """
    render_save_template_section(project_root)
    st.markdown("---")
    render_template_list(project_root)
