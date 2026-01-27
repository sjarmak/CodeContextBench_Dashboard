"""Tests for LLM judge template save, load, delete, and duplicate functionality."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from dashboard.utils.judge_config import (
    JudgeConfig,
    ScoringCriterion,
    ScoringDimension,
    TemplateInfo,
    _sanitize_template_name,
    config_to_dict,
    default_config,
    duplicate_template,
    list_template_infos,
    load_config,
    load_template_info,
    save_template,
)
from dashboard.utils.judge_template_manager import (
    SESSION_KEY_PREFIX,
    _format_created_at,
    _format_model_display,
    _handle_delete_confirm,
    _handle_delete_request,
    _handle_duplicate,
    _handle_load,
    _render_delete_confirmation,
    _render_template_row,
    _session_key,
    render_save_template_section,
    render_template_list,
    render_template_manager,
)


# ---- _sanitize_template_name tests ----


class TestSanitizeTemplateName:
    def test_basic_name(self):
        assert _sanitize_template_name("my template") == "my_template.json"

    def test_already_clean(self):
        assert _sanitize_template_name("clean-name") == "clean-name.json"

    def test_special_characters(self):
        result = _sanitize_template_name("Hello World! @#$%")
        assert result.endswith(".json")
        assert all(c.isalnum() or c in ("_", "-", ".") for c in result)

    def test_uppercase_lowered(self):
        assert _sanitize_template_name("My Template") == "my_template.json"

    def test_leading_trailing_spaces(self):
        result = _sanitize_template_name("  spaced  ")
        assert not result.startswith("_")

    def test_empty_name_becomes_unnamed(self):
        assert _sanitize_template_name("") == "unnamed.json"

    def test_whitespace_only_becomes_unnamed(self):
        assert _sanitize_template_name("   ") == "unnamed.json"

    def test_preserves_hyphens_and_underscores(self):
        assert _sanitize_template_name("my-config_v2") == "my-config_v2.json"


# ---- save_template tests ----


class TestSaveTemplate:
    def test_saves_config_with_metadata(self, tmp_path: Path):
        config = default_config()
        path = save_template(config, tmp_path, "Test Template")

        assert path.exists()
        with open(path) as f:
            data = json.load(f)

        assert data["_template_name"] == "Test Template"
        assert "_created_at" in data
        assert data["system_prompt"] == config.system_prompt
        assert data["model"] == config.model

    def test_filename_is_sanitized(self, tmp_path: Path):
        config = default_config()
        path = save_template(config, tmp_path, "My Cool Template!")

        # Trailing underscore from "!" is stripped by _sanitize_template_name
        assert path.name == "my_cool_template.json"

    def test_creates_templates_directory(self, tmp_path: Path):
        config = default_config()
        save_template(config, tmp_path, "new-template")

        templates_dir = tmp_path / "configs" / "judge_templates"
        assert templates_dir.exists()

    def test_preserves_all_config_fields(self, tmp_path: Path):
        config = JudgeConfig(
            system_prompt="Custom prompt",
            dimensions=(
                ScoringDimension(
                    name="Quality",
                    weight=0.7,
                    criteria=(
                        ScoringCriterion(1, "Bad"),
                        ScoringCriterion(2, "Good"),
                    ),
                ),
            ),
            model="claude-opus-4-20250514",
            temperature=0.5,
            max_tokens=8192,
        )
        path = save_template(config, tmp_path, "detailed")

        with open(path) as f:
            data = json.load(f)

        assert data["system_prompt"] == "Custom prompt"
        assert data["model"] == "claude-opus-4-20250514"
        assert data["temperature"] == 0.5
        assert data["max_tokens"] == 8192
        assert len(data["dimensions"]) == 1
        assert data["dimensions"][0]["name"] == "Quality"

    def test_can_load_saved_template(self, tmp_path: Path):
        original = default_config()
        save_template(original, tmp_path, "roundtrip")

        loaded = load_config(tmp_path, "roundtrip.json")
        assert loaded.system_prompt == original.system_prompt
        assert loaded.model == original.model


# ---- load_template_info tests ----


class TestLoadTemplateInfo:
    def test_loads_metadata(self, tmp_path: Path):
        config = default_config()
        save_template(config, tmp_path, "Info Test")

        info = load_template_info(tmp_path, "info_test.json")
        assert info is not None
        assert info.name == "Info Test"
        assert info.filename == "info_test.json"
        assert info.model == config.model
        assert info.created_at != ""

    def test_returns_none_for_missing_file(self, tmp_path: Path):
        info = load_template_info(tmp_path, "nonexistent.json")
        assert info is None

    def test_falls_back_to_filename_for_name(self, tmp_path: Path):
        templates_dir = tmp_path / "configs" / "judge_templates"
        templates_dir.mkdir(parents=True)
        file_path = templates_dir / "legacy.json"
        with open(file_path, "w") as f:
            json.dump(config_to_dict(default_config()), f)

        info = load_template_info(tmp_path, "legacy.json")
        assert info is not None
        assert info.name == "legacy"

    def test_handles_malformed_json(self, tmp_path: Path):
        templates_dir = tmp_path / "configs" / "judge_templates"
        templates_dir.mkdir(parents=True)
        file_path = templates_dir / "bad.json"
        file_path.write_text("not valid json{{{")

        info = load_template_info(tmp_path, "bad.json")
        assert info is None


# ---- list_template_infos tests ----


class TestListTemplateInfos:
    def test_lists_all_templates(self, tmp_path: Path):
        save_template(default_config(), tmp_path, "Alpha")
        save_template(default_config(), tmp_path, "Beta")

        infos = list_template_infos(tmp_path)
        assert len(infos) == 2
        names = [i.name for i in infos]
        assert "Alpha" in names
        assert "Beta" in names

    def test_empty_when_no_templates(self, tmp_path: Path):
        infos = list_template_infos(tmp_path)
        assert infos == []

    def test_skips_malformed_files(self, tmp_path: Path):
        save_template(default_config(), tmp_path, "Good")
        templates_dir = tmp_path / "configs" / "judge_templates"
        (templates_dir / "bad.json").write_text("invalid json")

        infos = list_template_infos(tmp_path)
        assert len(infos) == 1
        assert infos[0].name == "Good"

    def test_returns_sorted_by_name(self, tmp_path: Path):
        save_template(default_config(), tmp_path, "Zebra")
        save_template(default_config(), tmp_path, "Apple")

        infos = list_template_infos(tmp_path)
        filenames = [i.filename for i in infos]
        assert filenames == sorted(filenames)


# ---- duplicate_template tests ----


class TestDuplicateTemplate:
    def test_duplicates_with_copy_suffix(self, tmp_path: Path):
        save_template(default_config(), tmp_path, "Original")
        result = duplicate_template(tmp_path, "original.json")

        assert result is not None
        assert result.exists()

        with open(result) as f:
            data = json.load(f)
        assert data["_template_name"] == "Original-copy"

    def test_returns_none_for_missing_source(self, tmp_path: Path):
        result = duplicate_template(tmp_path, "missing.json")
        assert result is None

    def test_preserves_config_data(self, tmp_path: Path):
        config = JudgeConfig(
            system_prompt="Original prompt",
            dimensions=(),
            model="claude-opus-4-20250514",
            temperature=0.3,
            max_tokens=2048,
        )
        save_template(config, tmp_path, "Source")
        duplicate_template(tmp_path, "source.json")

        loaded = load_config(tmp_path, "source-copy.json")
        assert loaded.system_prompt == "Original prompt"
        assert loaded.model == "claude-opus-4-20250514"
        assert loaded.temperature == 0.3

    def test_custom_name_for_duplicate(self, tmp_path: Path):
        save_template(default_config(), tmp_path, "Original")
        result = duplicate_template(
            tmp_path, "original.json", new_name="My Custom Copy"
        )

        assert result is not None
        with open(result) as f:
            data = json.load(f)
        assert data["_template_name"] == "My Custom Copy"

    def test_updates_created_at(self, tmp_path: Path):
        save_template(default_config(), tmp_path, "Original")

        with open(tmp_path / "configs" / "judge_templates" / "original.json") as f:
            original_data = json.load(f)

        duplicate_template(tmp_path, "original.json")

        with open(tmp_path / "configs" / "judge_templates" / "original-copy.json") as f:
            copy_data = json.load(f)

        assert copy_data["_created_at"] != ""
        assert copy_data["_created_at"] >= original_data["_created_at"]


# ---- Template manager session key tests ----


class TestTemplateManagerSessionKey:
    def test_builds_key_with_prefix(self):
        key = _session_key("save_name")
        assert key == f"{SESSION_KEY_PREFIX}_save_name"

    def test_different_suffixes(self):
        key1 = _session_key("save_name")
        key2 = _session_key("save_button")
        assert key1 != key2


# ---- _format_created_at tests ----


class TestFormatCreatedAt:
    def test_formats_iso_date(self):
        result = _format_created_at("2026-01-27T10:30:00+00:00")
        assert result == "2026-01-27"

    def test_empty_string(self):
        assert _format_created_at("") == "Unknown"

    def test_short_string(self):
        result = _format_created_at("short")
        assert result == "short"


# ---- _format_model_display tests ----


class TestFormatModelDisplay:
    def test_haiku(self):
        assert _format_model_display("claude-haiku-4-5-20251001") == "Haiku"

    def test_sonnet(self):
        assert _format_model_display("claude-sonnet-4-20250514") == "Sonnet"

    def test_opus(self):
        assert _format_model_display("claude-opus-4-20250514") == "Opus"

    def test_unknown_model(self):
        result = _format_model_display("some-other-model-name-long")
        assert len(result) <= 20


# ---- render_save_template_section tests ----


class TestRenderSaveTemplateSection:
    @patch("dashboard.utils.judge_template_manager.save_template")
    @patch("dashboard.utils.judge_template_manager._session_state_to_config")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_renders_name_input(self, mock_st, mock_config, mock_save):
        mock_st.text_input.return_value = ""
        mock_st.button.return_value = False

        render_save_template_section(Path("/fake"))

        mock_st.text_input.assert_called_once()
        assert mock_st.text_input.call_args[1]["placeholder"] == "Enter a name for this template"

    @patch("dashboard.utils.judge_template_manager.save_template")
    @patch("dashboard.utils.judge_template_manager._session_state_to_config")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_saves_on_click_with_name(self, mock_st, mock_config, mock_save):
        mock_st.text_input.return_value = "My Template"
        mock_st.button.return_value = True
        mock_config.return_value = default_config()
        mock_save.return_value = Path("/fake/my_template.json")

        render_save_template_section(Path("/fake"))

        mock_save.assert_called_once()
        call_args = mock_save.call_args
        assert call_args[0][2] == "My Template"

    @patch("dashboard.utils.judge_template_manager.save_template")
    @patch("dashboard.utils.judge_template_manager._session_state_to_config")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_no_save_when_not_clicked(self, mock_st, mock_config, mock_save):
        mock_st.text_input.return_value = "Name"
        mock_st.button.return_value = False

        render_save_template_section(Path("/fake"))

        mock_save.assert_not_called()

    @patch("dashboard.utils.judge_template_manager.save_template")
    @patch("dashboard.utils.judge_template_manager._session_state_to_config")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_shows_error_on_save_failure(self, mock_st, mock_config, mock_save):
        mock_st.text_input.return_value = "Error Template"
        mock_st.button.return_value = True
        mock_config.return_value = default_config()
        mock_save.side_effect = OSError("Disk full")

        render_save_template_section(Path("/fake"))

        mock_st.error.assert_called_once()
        assert "Disk full" in mock_st.error.call_args[0][0]

    @patch("dashboard.utils.judge_template_manager.save_template")
    @patch("dashboard.utils.judge_template_manager._session_state_to_config")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_shows_success_on_save(self, mock_st, mock_config, mock_save):
        mock_st.text_input.return_value = "Good Template"
        mock_st.button.return_value = True
        mock_config.return_value = default_config()
        mock_save.return_value = Path("/fake/good_template.json")

        render_save_template_section(Path("/fake"))

        mock_st.success.assert_called_once()
        assert "Good Template" in mock_st.success.call_args[0][0]


# ---- _render_template_row tests ----


class TestRenderTemplateRow:
    @patch("dashboard.utils.judge_template_manager._handle_delete_request")
    @patch("dashboard.utils.judge_template_manager._handle_duplicate")
    @patch("dashboard.utils.judge_template_manager._handle_load")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_renders_name_and_metadata(self, mock_st, mock_load, mock_dup, mock_del):
        info = TemplateInfo(
            name="Test Template",
            filename="test.json",
            model="claude-haiku-4-5-20251001",
            created_at="2026-01-27T10:00:00",
        )
        mock_st.columns.return_value = (MagicMock(), MagicMock())
        inner_cols = (MagicMock(), MagicMock(), MagicMock())
        # Second columns call for buttons
        mock_st.columns.side_effect = [(MagicMock(), MagicMock()), inner_cols]
        mock_st.button.return_value = False

        _render_template_row(info, Path("/fake"), 0)

        mock_st.markdown.assert_any_call("**Test Template**")

    @patch("dashboard.utils.judge_template_manager._handle_load")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_load_button_triggers_load(self, mock_st, mock_load):
        info = TemplateInfo(
            name="Load Me",
            filename="load_me.json",
            model="claude-haiku-4-5-20251001",
            created_at="2026-01-27T10:00:00",
        )
        mock_st.columns.side_effect = [
            (MagicMock(), MagicMock()),
            (MagicMock(), MagicMock(), MagicMock()),
        ]
        # Load=True, Dup=False, Del=False
        mock_st.button.side_effect = [True, False, False]

        _render_template_row(info, Path("/fake"), 0)

        mock_load.assert_called_once_with(Path("/fake"), info)


# ---- _handle_load tests ----


class TestHandleLoad:
    @patch("dashboard.utils.judge_template_manager._config_to_session_state")
    @patch("dashboard.utils.judge_template_manager.load_config")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_loads_config_into_session(self, mock_st, mock_load, mock_to_state):
        info = TemplateInfo(
            name="Template",
            filename="template.json",
            model="claude-haiku-4-5-20251001",
            created_at="2026-01-27T10:00:00",
        )
        config = default_config()
        mock_load.return_value = config

        _handle_load(Path("/fake"), info)

        mock_load.assert_called_once_with(Path("/fake"), "template.json")
        mock_to_state.assert_called_once_with(config)
        mock_st.success.assert_called_once()
        mock_st.rerun.assert_called_once()


# ---- _handle_duplicate tests ----


class TestHandleDuplicate:
    @patch("dashboard.utils.judge_template_manager.duplicate_template")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_shows_success_on_duplicate(self, mock_st, mock_dup):
        info = TemplateInfo(
            name="Original",
            filename="original.json",
            model="claude-haiku-4-5-20251001",
            created_at="2026-01-27T10:00:00",
        )
        mock_dup.return_value = Path("/fake/original-copy.json")

        _handle_duplicate(Path("/fake"), info)

        mock_dup.assert_called_once_with(Path("/fake"), "original.json")
        mock_st.success.assert_called_once()
        mock_st.rerun.assert_called_once()

    @patch("dashboard.utils.judge_template_manager.duplicate_template")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_shows_error_on_failure(self, mock_st, mock_dup):
        info = TemplateInfo(
            name="Original",
            filename="original.json",
            model="claude-haiku-4-5-20251001",
            created_at="2026-01-27T10:00:00",
        )
        mock_dup.return_value = None

        _handle_duplicate(Path("/fake"), info)

        mock_st.error.assert_called_once()


# ---- _handle_delete_request tests ----


class TestHandleDeleteRequest:
    @patch("dashboard.utils.judge_template_manager.st")
    def test_sets_confirm_delete_state(self, mock_st):
        mock_st.session_state = {}

        _handle_delete_request(3)

        assert mock_st.session_state[_session_key("confirm_delete")] == 3


# ---- _handle_delete_confirm tests ----


class TestHandleDeleteConfirm:
    @patch("dashboard.utils.judge_template_manager.delete_template")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_deletes_and_clears_state(self, mock_st, mock_delete):
        mock_st.session_state = {_session_key("confirm_delete"): 0}
        mock_delete.return_value = True
        info = TemplateInfo(
            name="Delete Me",
            filename="delete_me.json",
            model="claude-haiku-4-5-20251001",
            created_at="2026-01-27T10:00:00",
        )

        _handle_delete_confirm(Path("/fake"), info)

        mock_delete.assert_called_once_with(Path("/fake"), "delete_me.json")
        mock_st.success.assert_called_once()
        assert _session_key("confirm_delete") not in mock_st.session_state
        mock_st.rerun.assert_called_once()

    @patch("dashboard.utils.judge_template_manager.delete_template")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_shows_error_on_failure(self, mock_st, mock_delete):
        mock_st.session_state = {_session_key("confirm_delete"): 0}
        mock_delete.return_value = False
        info = TemplateInfo(
            name="Stubborn",
            filename="stubborn.json",
            model="claude-haiku-4-5-20251001",
            created_at="2026-01-27T10:00:00",
        )

        _handle_delete_confirm(Path("/fake"), info)

        mock_st.error.assert_called_once()


# ---- render_template_list tests ----


class TestRenderTemplateList:
    @patch("dashboard.utils.judge_template_manager.list_template_infos")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_shows_info_when_empty(self, mock_st, mock_list):
        mock_st.session_state = {}
        mock_list.return_value = []

        render_template_list(Path("/fake"))

        mock_st.info.assert_called_once()
        assert "No saved templates" in mock_st.info.call_args[0][0]

    @patch("dashboard.utils.judge_template_manager._render_template_row")
    @patch("dashboard.utils.judge_template_manager.list_template_infos")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_renders_all_templates(self, mock_st, mock_list, mock_render_row):
        mock_st.session_state = {}
        infos = [
            TemplateInfo(
                name="A", filename="a.json",
                model="claude-haiku-4-5-20251001", created_at="2026-01-27",
            ),
            TemplateInfo(
                name="B", filename="b.json",
                model="claude-sonnet-4-20250514", created_at="2026-01-27",
            ),
        ]
        mock_list.return_value = infos

        render_template_list(Path("/fake"))

        assert mock_render_row.call_count == 2

    @patch("dashboard.utils.judge_template_manager._render_template_row")
    @patch("dashboard.utils.judge_template_manager._render_delete_confirmation")
    @patch("dashboard.utils.judge_template_manager.list_template_infos")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_shows_delete_confirmation_for_selected(
        self, mock_st, mock_list, mock_confirm, mock_row
    ):
        mock_st.session_state = {_session_key("confirm_delete"): 1}
        infos = [
            TemplateInfo(
                name="A", filename="a.json",
                model="claude-haiku-4-5-20251001", created_at="2026-01-27",
            ),
            TemplateInfo(
                name="B", filename="b.json",
                model="claude-sonnet-4-20250514", created_at="2026-01-27",
            ),
        ]
        mock_list.return_value = infos

        render_template_list(Path("/fake"))

        # First template renders normally, second shows confirmation
        mock_row.assert_called_once()
        mock_confirm.assert_called_once()

    @patch("dashboard.utils.judge_template_manager._render_template_row")
    @patch("dashboard.utils.judge_template_manager.list_template_infos")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_shows_count_caption(self, mock_st, mock_list, mock_render_row):
        mock_st.session_state = {}
        infos = [
            TemplateInfo(
                name="A", filename="a.json",
                model="claude-haiku-4-5-20251001", created_at="2026-01-27",
            ),
        ]
        mock_list.return_value = infos

        render_template_list(Path("/fake"))

        mock_st.caption.assert_any_call("1 template(s)")


# ---- render_delete_confirmation tests ----


class TestRenderDeleteConfirmation:
    @patch("dashboard.utils.judge_template_manager._handle_delete_confirm")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_shows_warning(self, mock_st, mock_confirm):
        info = TemplateInfo(
            name="Delete Me",
            filename="delete_me.json",
            model="claude-haiku-4-5-20251001",
            created_at="2026-01-27",
        )
        mock_st.columns.return_value = (MagicMock(), MagicMock())
        mock_st.button.return_value = False
        mock_st.session_state = {}

        _render_delete_confirmation(Path("/fake"), info, 0)

        mock_st.warning.assert_called_once()
        assert "Delete Me" in mock_st.warning.call_args[0][0]

    @patch("dashboard.utils.judge_template_manager._handle_delete_confirm")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_confirm_triggers_delete(self, mock_st, mock_confirm):
        info = TemplateInfo(
            name="Delete Me",
            filename="delete_me.json",
            model="claude-haiku-4-5-20251001",
            created_at="2026-01-27",
        )
        mock_st.columns.return_value = (MagicMock(), MagicMock())
        # Confirm=True, Cancel=False
        mock_st.button.side_effect = [True, False]
        mock_st.session_state = {}

        _render_delete_confirmation(Path("/fake"), info, 0)

        mock_confirm.assert_called_once_with(Path("/fake"), info)

    @patch("dashboard.utils.judge_template_manager._handle_delete_confirm")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_cancel_clears_state(self, mock_st, mock_confirm):
        info = TemplateInfo(
            name="Delete Me",
            filename="delete_me.json",
            model="claude-haiku-4-5-20251001",
            created_at="2026-01-27",
        )
        mock_st.columns.return_value = (MagicMock(), MagicMock())
        mock_st.session_state = {_session_key("confirm_delete"): 0}
        # Confirm=False, Cancel=True
        mock_st.button.side_effect = [False, True]

        _render_delete_confirmation(Path("/fake"), info, 0)

        assert _session_key("confirm_delete") not in mock_st.session_state
        mock_st.rerun.assert_called_once()


# ---- render_template_manager tests ----


class TestRenderTemplateManager:
    @patch("dashboard.utils.judge_template_manager.render_template_list")
    @patch("dashboard.utils.judge_template_manager.render_save_template_section")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_calls_both_sections(self, mock_st, mock_save, mock_list):
        render_template_manager(Path("/fake"))

        mock_save.assert_called_once_with(Path("/fake"))
        mock_list.assert_called_once_with(Path("/fake"))

    @patch("dashboard.utils.judge_template_manager.render_template_list")
    @patch("dashboard.utils.judge_template_manager.render_save_template_section")
    @patch("dashboard.utils.judge_template_manager.st")
    def test_renders_separator(self, mock_st, mock_save, mock_list):
        render_template_manager(Path("/fake"))

        mock_st.markdown.assert_any_call("---")


# ---- Integration tests ----


class TestTemplateManagerIntegration:
    def test_full_save_load_roundtrip(self, tmp_path: Path):
        """Save a template, list it, load it, and verify contents."""
        config = JudgeConfig(
            system_prompt="Integration test prompt",
            dimensions=(
                ScoringDimension(
                    name="Accuracy",
                    weight=0.6,
                    criteria=(
                        ScoringCriterion(1, "Inaccurate"),
                        ScoringCriterion(2, "Somewhat accurate"),
                        ScoringCriterion(3, "Accurate"),
                        ScoringCriterion(4, "Very accurate"),
                        ScoringCriterion(5, "Perfect"),
                    ),
                ),
            ),
            model="claude-sonnet-4-20250514",
            temperature=0.2,
            max_tokens=6000,
        )

        save_template(config, tmp_path, "Integration Test")

        infos = list_template_infos(tmp_path)
        assert len(infos) == 1
        assert infos[0].name == "Integration Test"
        assert infos[0].model == "claude-sonnet-4-20250514"

        loaded = load_config(tmp_path, infos[0].filename)
        assert loaded.system_prompt == "Integration test prompt"
        assert loaded.model == "claude-sonnet-4-20250514"
        assert loaded.temperature == 0.2
        assert len(loaded.dimensions) == 1
        assert loaded.dimensions[0].name == "Accuracy"

    def test_save_duplicate_delete_workflow(self, tmp_path: Path):
        """Test the full save -> duplicate -> delete workflow."""
        save_template(default_config(), tmp_path, "Original")

        infos = list_template_infos(tmp_path)
        assert len(infos) == 1

        duplicate_template(tmp_path, "original.json")

        infos = list_template_infos(tmp_path)
        assert len(infos) == 2
        names = {i.name for i in infos}
        assert "Original" in names
        assert "Original-copy" in names

        from dashboard.utils.judge_config import delete_template as del_tmpl

        del_tmpl(tmp_path, "original.json")

        infos = list_template_infos(tmp_path)
        assert len(infos) == 1
        assert infos[0].name == "Original-copy"

    def test_multiple_templates_with_different_configs(self, tmp_path: Path):
        """Save multiple templates with different configs and verify independence."""
        config_a = JudgeConfig(
            system_prompt="Prompt A",
            dimensions=(),
            model="claude-haiku-4-5-20251001",
            temperature=0.0,
            max_tokens=2048,
        )
        config_b = JudgeConfig(
            system_prompt="Prompt B",
            dimensions=(),
            model="claude-opus-4-20250514",
            temperature=0.9,
            max_tokens=16384,
        )

        save_template(config_a, tmp_path, "Template A")
        save_template(config_b, tmp_path, "Template B")

        loaded_a = load_config(tmp_path, "template_a.json")
        loaded_b = load_config(tmp_path, "template_b.json")

        assert loaded_a.system_prompt == "Prompt A"
        assert loaded_a.model == "claude-haiku-4-5-20251001"

        assert loaded_b.system_prompt == "Prompt B"
        assert loaded_b.model == "claude-opus-4-20250514"
        assert loaded_b.temperature == 0.9


# ---- Tab integration test ----


class TestTabIntegration:
    @patch("dashboard.views.analysis_llm_judge.render_human_alignment_tab")
    @patch("dashboard.views.analysis_llm_judge.render_ab_comparison_tab")
    @patch("dashboard.views.analysis_llm_judge.show_rubric_config")
    @patch("dashboard.views.analysis_llm_judge.show_reports_view")
    @patch("dashboard.views.analysis_llm_judge.show_evaluation_config")
    @patch("dashboard.views.analysis_llm_judge.render_template_manager")
    @patch("dashboard.views.analysis_llm_judge.render_judge_editor")
    @patch("dashboard.views.analysis_llm_judge.st")
    def test_template_manager_in_editor_tab(
        self, mock_st, mock_editor, mock_tmpl_mgr,
        mock_eval, mock_reports, mock_rubric,
        mock_ab, mock_human
    ):
        mock_st.session_state = {
            "judge_config": {
                "model": "claude-haiku-4-5-20251001",
                "selected_dimensions": ["correctness"],
                "custom_rubrics": {},
            },
            "project_root": Path("/fake"),
        }
        mock_st.tabs.return_value = [MagicMock() for _ in range(6)]
        for tab in mock_st.tabs.return_value:
            tab.__enter__ = MagicMock(return_value=tab)
            tab.__exit__ = MagicMock(return_value=False)

        from dashboard.views.analysis_llm_judge import show_llm_judge

        show_llm_judge()

        mock_editor.assert_called_once()
        mock_tmpl_mgr.assert_called_once()
