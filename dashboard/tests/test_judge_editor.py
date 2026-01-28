"""Tests for LLM judge prompt and rubric editor UI component."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from dashboard.utils.judge_config import (
    ACTIVE_CONFIG_FILENAME,
    AVAILABLE_MODELS,
    DEFAULT_SYSTEM_PROMPT,
    JudgeConfig,
    ScoringCriterion,
    ScoringDimension,
    config_to_dict,
    default_config,
    save_config,
)
from dashboard.utils.judge_editor import (
    SESSION_KEY_PREFIX,
    _config_to_session_state,
    _ensure_initialized,
    _render_dimension_row,
    _render_dimensions,
    _render_model_settings,
    _render_save_button,
    _render_system_prompt,
    _session_key,
    _session_state_to_config,
    render_judge_editor,
)


# ---- _session_key tests ----


class TestSessionKey:
    def test_builds_key_with_prefix(self):
        key = _session_key("data")
        assert key == f"{SESSION_KEY_PREFIX}_data"

    def test_different_suffixes(self):
        key1 = _session_key("data")
        key2 = _session_key("initialized")
        assert key1 != key2

    def test_preserves_suffix(self):
        key = _session_key("system_prompt_input")
        assert key.endswith("system_prompt_input")

    def test_prefix_is_consistent(self):
        key = _session_key("anything")
        assert key.startswith(SESSION_KEY_PREFIX)


# ---- _config_to_session_state tests ----


class TestConfigToSessionState:
    @patch("dashboard.utils.judge_editor.st")
    def test_stores_data_dict(self, mock_st):
        mock_st.session_state = {}
        config = default_config()
        _config_to_session_state(config)

        data_key = _session_key("data")
        assert data_key in mock_st.session_state
        assert isinstance(mock_st.session_state[data_key], dict)

    @patch("dashboard.utils.judge_editor.st")
    def test_sets_initialized_flag(self, mock_st):
        mock_st.session_state = {}
        config = default_config()
        _config_to_session_state(config)

        init_key = _session_key("initialized")
        assert mock_st.session_state[init_key] is True

    @patch("dashboard.utils.judge_editor.st")
    def test_preserves_system_prompt(self, mock_st):
        mock_st.session_state = {}
        config = JudgeConfig(
            system_prompt="Custom prompt",
            dimensions=(),
            model="claude-haiku-4-5-20251001",
            temperature=0.0,
            max_tokens=4096,
        )
        _config_to_session_state(config)

        data = mock_st.session_state[_session_key("data")]
        assert data["system_prompt"] == "Custom prompt"

    @patch("dashboard.utils.judge_editor.st")
    def test_preserves_model(self, mock_st):
        mock_st.session_state = {}
        config = JudgeConfig(
            system_prompt="P",
            dimensions=(),
            model="claude-opus-4-20250514",
            temperature=0.5,
            max_tokens=8192,
        )
        _config_to_session_state(config)

        data = mock_st.session_state[_session_key("data")]
        assert data["model"] == "claude-opus-4-20250514"
        assert data["temperature"] == 0.5
        assert data["max_tokens"] == 8192

    @patch("dashboard.utils.judge_editor.st")
    def test_serializes_dimensions(self, mock_st):
        mock_st.session_state = {}
        config = default_config()
        _config_to_session_state(config)

        data = mock_st.session_state[_session_key("data")]
        assert isinstance(data["dimensions"], list)
        assert len(data["dimensions"]) == len(config.dimensions)
        for dim_dict in data["dimensions"]:
            assert "name" in dim_dict
            assert "weight" in dim_dict
            assert "criteria" in dim_dict


# ---- _session_state_to_config tests ----


class TestSessionStateToConfig:
    @patch("dashboard.utils.judge_editor.st")
    def test_returns_default_when_no_data(self, mock_st):
        mock_st.session_state = {}
        config = _session_state_to_config()
        assert config.system_prompt == DEFAULT_SYSTEM_PROMPT

    @patch("dashboard.utils.judge_editor.st")
    def test_returns_default_when_empty_data(self, mock_st):
        mock_st.session_state = {_session_key("data"): {}}
        config = _session_state_to_config()
        assert config.system_prompt == DEFAULT_SYSTEM_PROMPT

    @patch("dashboard.utils.judge_editor.st")
    def test_roundtrip_with_config(self, mock_st):
        mock_st.session_state = {}
        original = JudgeConfig(
            system_prompt="Test prompt",
            dimensions=(
                ScoringDimension(
                    name="Quality",
                    weight=0.7,
                    criteria=(
                        ScoringCriterion(1, "Poor"),
                        ScoringCriterion(2, "OK"),
                    ),
                ),
            ),
            model="claude-opus-4-20250514",
            temperature=0.3,
            max_tokens=2048,
        )
        _config_to_session_state(original)
        restored = _session_state_to_config()

        assert restored.system_prompt == "Test prompt"
        assert restored.model == "claude-opus-4-20250514"
        assert restored.temperature == 0.3
        assert restored.max_tokens == 2048
        assert len(restored.dimensions) == 1
        assert restored.dimensions[0].name == "Quality"

    @patch("dashboard.utils.judge_editor.st")
    def test_restores_dimension_criteria(self, mock_st):
        mock_st.session_state = {}
        original = default_config()
        _config_to_session_state(original)
        restored = _session_state_to_config()

        for orig_dim, rest_dim in zip(original.dimensions, restored.dimensions):
            assert len(orig_dim.criteria) == len(rest_dim.criteria)
            for orig_c, rest_c in zip(orig_dim.criteria, rest_dim.criteria):
                assert orig_c.level == rest_c.level
                assert orig_c.description == rest_c.description


# ---- _ensure_initialized tests ----


class TestEnsureInitialized:
    @patch("dashboard.utils.judge_editor.load_config")
    @patch("dashboard.utils.judge_editor.st")
    def test_loads_config_on_first_call(self, mock_st, mock_load):
        mock_st.session_state = {}
        mock_load.return_value = default_config()

        _ensure_initialized(Path("/fake"))

        mock_load.assert_called_once_with(Path("/fake"))
        assert mock_st.session_state[_session_key("initialized")] is True

    @patch("dashboard.utils.judge_editor.load_config")
    @patch("dashboard.utils.judge_editor.st")
    def test_skips_if_already_initialized(self, mock_st, mock_load):
        mock_st.session_state = {_session_key("initialized"): True}

        _ensure_initialized(Path("/fake"))

        mock_load.assert_not_called()

    @patch("dashboard.utils.judge_editor.load_config")
    @patch("dashboard.utils.judge_editor.st")
    def test_stores_loaded_config_data(self, mock_st, mock_load):
        mock_st.session_state = {}
        custom = JudgeConfig(
            system_prompt="Loaded prompt",
            dimensions=(),
            model="claude-haiku-4-5-20251001",
            temperature=0.1,
            max_tokens=1024,
        )
        mock_load.return_value = custom

        _ensure_initialized(Path("/fake"))

        data = mock_st.session_state[_session_key("data")]
        assert data["system_prompt"] == "Loaded prompt"
        assert data["temperature"] == 0.1


# ---- _render_system_prompt tests ----


class TestRenderSystemPrompt:
    @patch("dashboard.utils.judge_editor.st")
    def test_renders_markdown_header(self, mock_st):
        mock_st.session_state = {
            _session_key("data"): {"system_prompt": "Test prompt"}
        }
        mock_st.text_area.return_value = "Test prompt"

        _render_system_prompt()

        mock_st.markdown.assert_called_with("### System Prompt")

    @patch("dashboard.utils.judge_editor.st")
    def test_renders_text_area(self, mock_st):
        mock_st.session_state = {
            _session_key("data"): {"system_prompt": "Current prompt"}
        }
        mock_st.text_area.return_value = "Current prompt"

        _render_system_prompt()

        mock_st.text_area.assert_called_once()
        call_kwargs = mock_st.text_area.call_args
        assert call_kwargs[1]["value"] == "Current prompt"
        assert call_kwargs[1]["height"] == 200

    @patch("dashboard.utils.judge_editor.st")
    def test_updates_session_state_on_change(self, mock_st):
        data = {"system_prompt": "Old prompt"}
        mock_st.session_state = {_session_key("data"): data}
        mock_st.text_area.return_value = "New prompt"

        _render_system_prompt()

        assert data["system_prompt"] == "New prompt"


# ---- _render_model_settings tests ----


class TestRenderModelSettings:
    @patch("dashboard.utils.judge_editor.st")
    def test_renders_markdown_header(self, mock_st):
        data = {
            "model": AVAILABLE_MODELS[0],
            "temperature": 0.0,
            "max_tokens": 4096,
        }
        mock_st.session_state = {_session_key("data"): data}
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_st.selectbox.return_value = AVAILABLE_MODELS[0]
        mock_st.slider.return_value = 0.0
        mock_st.number_input.return_value = 4096

        _render_model_settings()

        mock_st.markdown.assert_any_call("### Model Settings")

    @patch("dashboard.utils.judge_editor.st")
    def test_creates_three_columns(self, mock_st):
        data = {
            "model": AVAILABLE_MODELS[0],
            "temperature": 0.0,
            "max_tokens": 4096,
        }
        mock_st.session_state = {_session_key("data"): data}
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_st.selectbox.return_value = AVAILABLE_MODELS[0]
        mock_st.slider.return_value = 0.0
        mock_st.number_input.return_value = 4096

        _render_model_settings()

        mock_st.columns.assert_called_with([2, 1, 1])

    @patch("dashboard.utils.judge_editor.st")
    def test_renders_model_selectbox(self, mock_st):
        data = {
            "model": AVAILABLE_MODELS[0],
            "temperature": 0.0,
            "max_tokens": 4096,
        }
        mock_st.session_state = {_session_key("data"): data}
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_st.selectbox.return_value = AVAILABLE_MODELS[1]
        mock_st.slider.return_value = 0.0
        mock_st.number_input.return_value = 4096

        _render_model_settings()

        mock_st.selectbox.assert_called_once()
        call_args = mock_st.selectbox.call_args
        assert call_args[0][0] == "Model"
        assert call_args[0][1] == AVAILABLE_MODELS

    @patch("dashboard.utils.judge_editor.st")
    def test_updates_model_in_data(self, mock_st):
        data = {
            "model": AVAILABLE_MODELS[0],
            "temperature": 0.0,
            "max_tokens": 4096,
        }
        mock_st.session_state = {_session_key("data"): data}
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_st.selectbox.return_value = "claude-opus-4-20250514"
        mock_st.slider.return_value = 0.5
        mock_st.number_input.return_value = 8192

        _render_model_settings()

        assert data["model"] == "claude-opus-4-20250514"
        assert data["temperature"] == 0.5
        assert data["max_tokens"] == 8192

    @patch("dashboard.utils.judge_editor.st")
    def test_temperature_slider_range(self, mock_st):
        data = {
            "model": AVAILABLE_MODELS[0],
            "temperature": 0.3,
            "max_tokens": 4096,
        }
        mock_st.session_state = {_session_key("data"): data}
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_st.selectbox.return_value = AVAILABLE_MODELS[0]
        mock_st.slider.return_value = 0.3
        mock_st.number_input.return_value = 4096

        _render_model_settings()

        slider_call = mock_st.slider.call_args
        assert slider_call[1]["min_value"] == 0.0
        assert slider_call[1]["max_value"] == 1.0
        assert slider_call[1]["step"] == 0.1

    @patch("dashboard.utils.judge_editor.st")
    def test_max_tokens_input_range(self, mock_st):
        data = {
            "model": AVAILABLE_MODELS[0],
            "temperature": 0.0,
            "max_tokens": 4096,
        }
        mock_st.session_state = {_session_key("data"): data}
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_st.selectbox.return_value = AVAILABLE_MODELS[0]
        mock_st.slider.return_value = 0.0
        mock_st.number_input.return_value = 4096

        _render_model_settings()

        input_call = mock_st.number_input.call_args
        assert input_call[1]["min_value"] == 256
        assert input_call[1]["max_value"] == 32768
        assert input_call[1]["step"] == 256


# ---- _render_dimension_row tests ----


class TestRenderDimensionRow:
    @patch("dashboard.utils.judge_editor.st")
    def test_renders_name_input(self, mock_st):
        dim_data = {
            "name": "Correctness",
            "weight": 0.5,
            "criteria": [{"level": i + 1, "description": f"Level {i + 1}"} for i in range(5)],
        }
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_st.text_input.return_value = "Correctness"
        mock_st.slider.return_value = 0.5
        mock_st.button.return_value = False
        mock_st.expander.return_value.__enter__ = MagicMock()
        mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)

        result = _render_dimension_row(dim_data, 0)

        assert result is False  # no delete
        mock_st.text_input.assert_called()

    @patch("dashboard.utils.judge_editor.st")
    def test_returns_true_on_delete(self, mock_st):
        dim_data = {
            "name": "Quality",
            "weight": 0.3,
            "criteria": [{"level": i + 1, "description": ""} for i in range(5)],
        }
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_st.text_input.return_value = "Quality"
        mock_st.slider.return_value = 0.3
        mock_st.button.return_value = True  # delete clicked
        mock_st.expander.return_value.__enter__ = MagicMock()
        mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)

        result = _render_dimension_row(dim_data, 0)

        assert result is True

    @patch("dashboard.utils.judge_editor.st")
    def test_ensures_five_criteria_levels(self, mock_st):
        dim_data = {
            "name": "Test",
            "weight": 0.5,
            "criteria": [{"level": 1, "description": "One"}],  # only 1 criterion
        }
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_st.text_input.return_value = "Test"
        mock_st.slider.return_value = 0.5
        mock_st.button.return_value = False
        mock_st.expander.return_value.__enter__ = MagicMock()
        mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)

        _render_dimension_row(dim_data, 0)

        assert len(dim_data["criteria"]) >= 5

    @patch("dashboard.utils.judge_editor.st")
    def test_updates_name_from_input(self, mock_st):
        dim_data = {
            "name": "Old Name",
            "weight": 0.5,
            "criteria": [{"level": i + 1, "description": ""} for i in range(5)],
        }
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_st.text_input.return_value = "New Name"
        mock_st.slider.return_value = 0.5
        mock_st.button.return_value = False
        mock_st.expander.return_value.__enter__ = MagicMock()
        mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)

        _render_dimension_row(dim_data, 0)

        assert dim_data["name"] == "New Name"

    @patch("dashboard.utils.judge_editor.st")
    def test_updates_weight_from_slider(self, mock_st):
        dim_data = {
            "name": "Test",
            "weight": 0.3,
            "criteria": [{"level": i + 1, "description": ""} for i in range(5)],
        }
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_st.text_input.return_value = "Test"
        mock_st.slider.return_value = 0.8
        mock_st.button.return_value = False
        mock_st.expander.return_value.__enter__ = MagicMock()
        mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)

        _render_dimension_row(dim_data, 0)

        assert dim_data["weight"] == 0.8

    @patch("dashboard.utils.judge_editor.st")
    def test_weight_slider_range(self, mock_st):
        dim_data = {
            "name": "Test",
            "weight": 0.5,
            "criteria": [{"level": i + 1, "description": ""} for i in range(5)],
        }
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_st.text_input.return_value = "Test"
        mock_st.slider.return_value = 0.5
        mock_st.button.return_value = False
        mock_st.expander.return_value.__enter__ = MagicMock()
        mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)

        _render_dimension_row(dim_data, 0)

        slider_call = mock_st.slider.call_args
        assert slider_call[1]["min_value"] == 0.0
        assert slider_call[1]["max_value"] == 1.0


# ---- _render_dimensions tests ----


class TestRenderDimensions:
    @patch("dashboard.utils.judge_editor._render_dimension_row")
    @patch("dashboard.utils.judge_editor.st")
    def test_renders_all_dimensions(self, mock_st, mock_render_row):
        data = {
            "dimensions": [
                {"name": "A", "weight": 0.3, "criteria": []},
                {"name": "B", "weight": 0.7, "criteria": []},
            ]
        }
        mock_st.session_state = {_session_key("data"): data}
        mock_render_row.return_value = False
        mock_st.button.return_value = False

        _render_dimensions()

        assert mock_render_row.call_count == 2

    @patch("dashboard.utils.judge_editor._render_dimension_row")
    @patch("dashboard.utils.judge_editor.st")
    def test_add_dimension_button_exists(self, mock_st, mock_render_row):
        data = {"dimensions": []}
        mock_st.session_state = {_session_key("data"): data}
        mock_render_row.return_value = False
        mock_st.button.return_value = False

        _render_dimensions()

        # Check that Add Dimension button was created
        button_calls = [c for c in mock_st.button.call_args_list]
        add_calls = [
            c for c in button_calls
            if c[0][0] == "Add Dimension" or c[1].get("key", "").endswith("add_dimension")
        ]
        assert len(add_calls) == 1

    @patch("dashboard.utils.judge_editor._render_dimension_row")
    @patch("dashboard.utils.judge_editor.st")
    def test_add_dimension_adds_to_list(self, mock_st, mock_render_row):
        data = {"dimensions": [{"name": "Existing", "weight": 0.5, "criteria": []}]}
        mock_st.session_state = {_session_key("data"): data}
        mock_render_row.return_value = False

        # Make the Add Dimension button return True
        def button_side_effect(label, **kwargs):
            if kwargs.get("key", "").endswith("add_dimension"):
                return True
            return False

        mock_st.button.side_effect = button_side_effect

        _render_dimensions()

        assert len(data["dimensions"]) == 2
        assert data["dimensions"][1]["name"] == ""
        assert data["dimensions"][1]["weight"] == 0.5
        mock_st.rerun.assert_called_once()

    @patch("dashboard.utils.judge_editor._render_dimension_row")
    @patch("dashboard.utils.judge_editor.st")
    def test_delete_dimension_removes_from_list(self, mock_st, mock_render_row):
        data = {
            "dimensions": [
                {"name": "A", "weight": 0.3, "criteria": []},
                {"name": "B", "weight": 0.7, "criteria": []},
            ]
        }
        mock_st.session_state = {_session_key("data"): data}
        mock_st.button.return_value = False

        # First dimension returns True (delete), second returns False
        mock_render_row.side_effect = [True, False]

        _render_dimensions()

        assert len(data["dimensions"]) == 1
        assert data["dimensions"][0]["name"] == "B"
        mock_st.rerun.assert_called_once()

    @patch("dashboard.utils.judge_editor._render_dimension_row")
    @patch("dashboard.utils.judge_editor.st")
    def test_renders_section_header(self, mock_st, mock_render_row):
        data = {"dimensions": []}
        mock_st.session_state = {_session_key("data"): data}
        mock_render_row.return_value = False
        mock_st.button.return_value = False

        _render_dimensions()

        mock_st.markdown.assert_any_call("### Scoring Dimensions")


# ---- _render_save_button tests ----


class TestRenderSaveButton:
    @patch("dashboard.utils.judge_editor.save_config")
    @patch("dashboard.utils.judge_editor.st")
    def test_renders_save_button(self, mock_st, mock_save):
        mock_st.session_state = {
            _session_key("data"): config_to_dict(default_config())
        }
        mock_st.button.return_value = False

        _render_save_button(Path("/fake"))

        mock_st.button.assert_called_once()
        call_kwargs = mock_st.button.call_args[1]
        assert call_kwargs["type"] == "primary"

    @patch("dashboard.utils.judge_editor.save_config")
    @patch("dashboard.utils.judge_editor.st")
    def test_saves_on_click(self, mock_st, mock_save):
        mock_st.session_state = {
            _session_key("data"): config_to_dict(default_config())
        }
        mock_st.button.return_value = True
        mock_save.return_value = Path("/fake/configs/judge_templates/active_config.json")

        _render_save_button(Path("/fake"))

        mock_save.assert_called_once()
        saved_config = mock_save.call_args[0][0]
        assert isinstance(saved_config, JudgeConfig)
        assert mock_save.call_args[0][1] == Path("/fake")

    @patch("dashboard.utils.judge_editor.save_config")
    @patch("dashboard.utils.judge_editor.st")
    def test_shows_success_on_save(self, mock_st, mock_save):
        mock_st.session_state = {
            _session_key("data"): config_to_dict(default_config())
        }
        mock_st.button.return_value = True
        mock_save.return_value = Path("/fake/active_config.json")

        _render_save_button(Path("/fake"))

        mock_st.success.assert_called_once()

    @patch("dashboard.utils.judge_editor.save_config")
    @patch("dashboard.utils.judge_editor.st")
    def test_shows_error_on_failure(self, mock_st, mock_save):
        mock_st.session_state = {
            _session_key("data"): config_to_dict(default_config())
        }
        mock_st.button.return_value = True
        mock_save.side_effect = OSError("Disk full")

        _render_save_button(Path("/fake"))

        mock_st.error.assert_called_once()
        assert "Disk full" in mock_st.error.call_args[0][0]

    @patch("dashboard.utils.judge_editor.save_config")
    @patch("dashboard.utils.judge_editor.st")
    def test_no_save_when_not_clicked(self, mock_st, mock_save):
        mock_st.session_state = {
            _session_key("data"): config_to_dict(default_config())
        }
        mock_st.button.return_value = False

        _render_save_button(Path("/fake"))

        mock_save.assert_not_called()

    @patch("dashboard.utils.judge_editor.save_config")
    @patch("dashboard.utils.judge_editor.st")
    def test_save_writes_to_active_config(self, mock_st, mock_save):
        mock_st.session_state = {
            _session_key("data"): config_to_dict(default_config())
        }
        mock_st.button.return_value = True
        mock_save.return_value = Path("/fake/active_config.json")

        _render_save_button(Path("/fake"))

        # save_config is called with project_root, which defaults to active_config.json
        mock_save.assert_called_once()


# ---- render_judge_editor tests ----


class TestRenderJudgeEditor:
    @patch("dashboard.utils.judge_editor._render_save_button")
    @patch("dashboard.utils.judge_editor._render_dimensions")
    @patch("dashboard.utils.judge_editor._render_model_settings")
    @patch("dashboard.utils.judge_editor._render_system_prompt")
    @patch("dashboard.utils.judge_editor._ensure_initialized")
    @patch("dashboard.utils.judge_editor.st")
    def test_calls_all_render_functions(
        self, mock_st, mock_init, mock_prompt, mock_model, mock_dims, mock_save
    ):
        render_judge_editor(Path("/fake"))

        mock_init.assert_called_once_with(Path("/fake"))
        mock_prompt.assert_called_once()
        mock_model.assert_called_once()
        mock_dims.assert_called_once()
        mock_save.assert_called_once_with(Path("/fake"))

    @patch("dashboard.utils.judge_editor._render_save_button")
    @patch("dashboard.utils.judge_editor._render_dimensions")
    @patch("dashboard.utils.judge_editor._render_model_settings")
    @patch("dashboard.utils.judge_editor._render_system_prompt")
    @patch("dashboard.utils.judge_editor._ensure_initialized")
    @patch("dashboard.utils.judge_editor.st")
    def test_renders_separators(
        self, mock_st, mock_init, mock_prompt, mock_model, mock_dims, mock_save
    ):
        render_judge_editor(Path("/fake"))

        separator_calls = [
            c for c in mock_st.markdown.call_args_list if c[0][0] == "---"
        ]
        assert len(separator_calls) >= 2

    @patch("dashboard.utils.judge_editor._render_save_button")
    @patch("dashboard.utils.judge_editor._render_dimensions")
    @patch("dashboard.utils.judge_editor._render_model_settings")
    @patch("dashboard.utils.judge_editor._render_system_prompt")
    @patch("dashboard.utils.judge_editor._ensure_initialized")
    @patch("dashboard.utils.judge_editor.st")
    def test_initialization_happens_first(
        self, mock_st, mock_init, mock_prompt, mock_model, mock_dims, mock_save
    ):
        call_order = []
        mock_init.side_effect = lambda p: call_order.append("init")
        mock_prompt.side_effect = lambda: call_order.append("prompt")
        mock_model.side_effect = lambda: call_order.append("model")
        mock_dims.side_effect = lambda: call_order.append("dims")
        mock_save.side_effect = lambda p: call_order.append("save")

        render_judge_editor(Path("/fake"))

        assert call_order[0] == "init"
        assert "prompt" in call_order
        assert "model" in call_order
        assert "dims" in call_order
        assert "save" in call_order


# ---- Integration tests ----


class TestEditorIntegration:
    @patch("dashboard.utils.judge_editor.st")
    def test_full_config_to_session_and_back(self, mock_st):
        """Test that a config can be stored in session state and restored."""
        mock_st.session_state = {}

        config = JudgeConfig(
            system_prompt="Evaluate code quality thoroughly",
            dimensions=(
                ScoringDimension(
                    name="Correctness",
                    weight=0.4,
                    criteria=(
                        ScoringCriterion(1, "Completely wrong"),
                        ScoringCriterion(2, "Mostly wrong"),
                        ScoringCriterion(3, "Partially correct"),
                        ScoringCriterion(4, "Mostly correct"),
                        ScoringCriterion(5, "Fully correct"),
                    ),
                ),
                ScoringDimension(
                    name="Quality",
                    weight=0.3,
                    criteria=(
                        ScoringCriterion(1, "Poor"),
                        ScoringCriterion(2, "Below average"),
                        ScoringCriterion(3, "Average"),
                        ScoringCriterion(4, "Good"),
                        ScoringCriterion(5, "Excellent"),
                    ),
                ),
            ),
            model="claude-sonnet-4-20250514",
            temperature=0.2,
            max_tokens=6000,
        )

        _config_to_session_state(config)
        restored = _session_state_to_config()

        assert restored.system_prompt == config.system_prompt
        assert restored.model == config.model
        assert restored.temperature == config.temperature
        assert restored.max_tokens == config.max_tokens
        assert len(restored.dimensions) == 2
        assert restored.dimensions[0].name == "Correctness"
        assert restored.dimensions[1].name == "Quality"
        assert len(restored.dimensions[0].criteria) == 5
        assert restored.dimensions[0].criteria[0].description == "Completely wrong"

    @patch("dashboard.utils.judge_editor.st")
    def test_session_data_is_mutable_dict(self, mock_st):
        """Verify session state data is a mutable dict for widget updates."""
        mock_st.session_state = {}
        config = default_config()
        _config_to_session_state(config)

        data = mock_st.session_state[_session_key("data")]
        assert isinstance(data, dict)

        # Should be mutable (not frozen)
        data["system_prompt"] = "Modified"
        assert data["system_prompt"] == "Modified"

        data["dimensions"].append({"name": "New", "weight": 0.5, "criteria": []})
        assert len(data["dimensions"]) == len(config.dimensions) + 1

    def test_save_config_integration(self, tmp_path: Path):
        """Test that editor config can be saved and reloaded."""
        from dashboard.utils.judge_config import load_config

        config = JudgeConfig(
            system_prompt="Integration test prompt",
            dimensions=(
                ScoringDimension(
                    name="Test Dim",
                    weight=0.6,
                    criteria=(
                        ScoringCriterion(1, "Bad"),
                        ScoringCriterion(2, "OK"),
                        ScoringCriterion(3, "Good"),
                        ScoringCriterion(4, "Very good"),
                        ScoringCriterion(5, "Excellent"),
                    ),
                ),
            ),
            model="claude-opus-4-20250514",
            temperature=0.1,
            max_tokens=2048,
        )

        saved_path = save_config(config, tmp_path)
        assert saved_path.exists()
        assert saved_path.name == ACTIVE_CONFIG_FILENAME

        loaded = load_config(tmp_path)
        assert loaded.system_prompt == "Integration test prompt"
        assert loaded.model == "claude-opus-4-20250514"
        assert len(loaded.dimensions) == 1
        assert loaded.dimensions[0].name == "Test Dim"
        assert loaded.dimensions[0].weight == 0.6
        assert len(loaded.dimensions[0].criteria) == 5

    def test_save_config_creates_templates_dir(self, tmp_path: Path):
        """Test that save_config creates the configs/judge_templates/ directory."""
        config = default_config()
        save_config(config, tmp_path)

        templates_dir = tmp_path / "configs" / "judge_templates"
        assert templates_dir.exists()
        assert (templates_dir / ACTIVE_CONFIG_FILENAME).exists()

    def test_saved_json_structure(self, tmp_path: Path):
        """Verify the saved JSON has the expected structure."""
        config = JudgeConfig(
            system_prompt="Structured test",
            dimensions=(
                ScoringDimension(
                    name="Dim1",
                    weight=0.5,
                    criteria=(ScoringCriterion(1, "Low"), ScoringCriterion(2, "High")),
                ),
            ),
            model="claude-haiku-4-5-20251001",
            temperature=0.0,
            max_tokens=4096,
        )
        saved_path = save_config(config, tmp_path)

        with open(saved_path) as f:
            data = json.load(f)

        assert data["system_prompt"] == "Structured test"
        assert data["model"] == "claude-haiku-4-5-20251001"
        assert data["temperature"] == 0.0
        assert data["max_tokens"] == 4096
        assert len(data["dimensions"]) == 1
        assert data["dimensions"][0]["name"] == "Dim1"
        assert data["dimensions"][0]["weight"] == 0.5
        assert len(data["dimensions"][0]["criteria"]) == 2
        assert data["dimensions"][0]["criteria"][0]["level"] == 1
        assert data["dimensions"][0]["criteria"][0]["description"] == "Low"


# ---- Tab integration in analysis_llm_judge ----


class TestTabIntegration:
    """Verify that the editor is accessible as Tab 3 in the LLM Judge view."""

    @patch("dashboard.views.analysis_llm_judge.show_rubric_config")
    @patch("dashboard.views.analysis_llm_judge.show_reports_view")
    @patch("dashboard.views.analysis_llm_judge.show_evaluation_config")
    @patch("dashboard.views.analysis_llm_judge.render_judge_editor")
    @patch("dashboard.views.analysis_llm_judge.st")
    def test_editor_tab_exists(
        self, mock_st, mock_editor, mock_eval, mock_reports, mock_rubric
    ):
        mock_st.session_state = {
            "judge_config": {
                "model": "claude-haiku-4-5-20251001",
                "selected_dimensions": ["correctness"],
                "custom_rubrics": {},
            },
            "project_root": Path("/fake"),
        }
        mock_st.tabs.return_value = [MagicMock() for _ in range(4)]
        for tab in mock_st.tabs.return_value:
            tab.__enter__ = MagicMock(return_value=tab)
            tab.__exit__ = MagicMock(return_value=False)

        from dashboard.views.analysis_llm_judge import show_llm_judge

        show_llm_judge()

        # Verify tabs include the editor
        tab_labels = mock_st.tabs.call_args[0][0]
        assert "Prompt & Rubric Editor" in tab_labels

        # Verify render_judge_editor was called
        mock_editor.assert_called_once()
