"""Tests for judge configuration data model and file I/O."""

import json
from pathlib import Path

import pytest

from dashboard.utils.judge_config import (
    ACTIVE_CONFIG_FILENAME,
    AVAILABLE_MODELS,
    DEFAULT_SYSTEM_PROMPT,
    JUDGE_TEMPLATES_DIR,
    JudgeConfig,
    ScoringCriterion,
    ScoringDimension,
    add_dimension,
    config_to_dict,
    default_config,
    default_dimensions,
    delete_template,
    dict_to_config,
    list_templates,
    load_config,
    remove_dimension,
    save_config,
    update_dimension,
)


# ---- ScoringCriterion tests ----


class TestScoringCriterion:
    def test_creation(self):
        c = ScoringCriterion(level=3, description="Partially addresses")
        assert c.level == 3
        assert c.description == "Partially addresses"

    def test_frozen(self):
        c = ScoringCriterion(level=1, description="Poor")
        with pytest.raises(AttributeError):
            c.level = 2  # type: ignore[misc]


# ---- ScoringDimension tests ----


class TestScoringDimension:
    def test_creation(self):
        criteria = (
            ScoringCriterion(1, "Bad"),
            ScoringCriterion(2, "OK"),
        )
        dim = ScoringDimension(name="Quality", weight=0.5, criteria=criteria)
        assert dim.name == "Quality"
        assert dim.weight == 0.5
        assert len(dim.criteria) == 2

    def test_frozen(self):
        dim = ScoringDimension(name="X", weight=0.3, criteria=())
        with pytest.raises(AttributeError):
            dim.name = "Y"  # type: ignore[misc]


# ---- JudgeConfig tests ----


class TestJudgeConfig:
    def test_creation(self):
        config = JudgeConfig(
            system_prompt="Test prompt",
            dimensions=(),
            model="claude-haiku-4-5-20251001",
            temperature=0.5,
            max_tokens=2048,
        )
        assert config.system_prompt == "Test prompt"
        assert config.model == "claude-haiku-4-5-20251001"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048

    def test_frozen(self):
        config = JudgeConfig(
            system_prompt="X",
            dimensions=(),
            model="m",
            temperature=0.0,
            max_tokens=1000,
        )
        with pytest.raises(AttributeError):
            config.temperature = 0.5  # type: ignore[misc]


# ---- default_config tests ----


class TestDefaultConfig:
    def test_returns_judge_config(self):
        config = default_config()
        assert isinstance(config, JudgeConfig)

    def test_has_system_prompt(self):
        config = default_config()
        assert config.system_prompt == DEFAULT_SYSTEM_PROMPT
        assert len(config.system_prompt) > 0

    def test_has_dimensions(self):
        config = default_config()
        assert len(config.dimensions) >= 2

    def test_dimensions_have_criteria(self):
        config = default_config()
        for dim in config.dimensions:
            assert len(dim.criteria) == 5
            for c in dim.criteria:
                assert 1 <= c.level <= 5
                assert len(c.description) > 0

    def test_has_valid_model(self):
        config = default_config()
        assert config.model in AVAILABLE_MODELS

    def test_default_temperature(self):
        config = default_config()
        assert config.temperature == 0.0

    def test_default_max_tokens(self):
        config = default_config()
        assert config.max_tokens == 4096

    def test_dimension_weights_sum(self):
        config = default_config()
        total_weight = sum(d.weight for d in config.dimensions)
        assert total_weight > 0


# ---- default_dimensions tests ----


class TestDefaultDimensions:
    def test_returns_tuple(self):
        dims = default_dimensions()
        assert isinstance(dims, tuple)

    def test_has_multiple_dimensions(self):
        dims = default_dimensions()
        assert len(dims) >= 2

    def test_each_dimension_has_name(self):
        dims = default_dimensions()
        for dim in dims:
            assert len(dim.name) > 0

    def test_each_dimension_has_criteria(self):
        dims = default_dimensions()
        for dim in dims:
            assert len(dim.criteria) == 5


# ---- config_to_dict tests ----


class TestConfigToDict:
    def test_serializes_all_fields(self):
        config = default_config()
        data = config_to_dict(config)
        assert "system_prompt" in data
        assert "dimensions" in data
        assert "model" in data
        assert "temperature" in data
        assert "max_tokens" in data

    def test_dimensions_are_list_of_dicts(self):
        config = default_config()
        data = config_to_dict(config)
        assert isinstance(data["dimensions"], list)
        for dim in data["dimensions"]:
            assert "name" in dim
            assert "weight" in dim
            assert "criteria" in dim

    def test_criteria_are_list_of_dicts(self):
        config = default_config()
        data = config_to_dict(config)
        for dim in data["dimensions"]:
            for criterion in dim["criteria"]:
                assert "level" in criterion
                assert "description" in criterion

    def test_is_json_serializable(self):
        config = default_config()
        data = config_to_dict(config)
        json_str = json.dumps(data)
        assert len(json_str) > 0

    def test_empty_dimensions(self):
        config = JudgeConfig(
            system_prompt="X",
            dimensions=(),
            model="m",
            temperature=0.0,
            max_tokens=1000,
        )
        data = config_to_dict(config)
        assert data["dimensions"] == []


# ---- dict_to_config tests ----


class TestDictToConfig:
    def test_roundtrip(self):
        original = default_config()
        data = config_to_dict(original)
        restored = dict_to_config(data)
        assert restored.system_prompt == original.system_prompt
        assert restored.model == original.model
        assert restored.temperature == original.temperature
        assert restored.max_tokens == original.max_tokens
        assert len(restored.dimensions) == len(original.dimensions)

    def test_roundtrip_preserves_dimension_names(self):
        original = default_config()
        data = config_to_dict(original)
        restored = dict_to_config(data)
        for orig_dim, rest_dim in zip(original.dimensions, restored.dimensions):
            assert orig_dim.name == rest_dim.name

    def test_roundtrip_preserves_criteria(self):
        original = default_config()
        data = config_to_dict(original)
        restored = dict_to_config(data)
        for orig_dim, rest_dim in zip(original.dimensions, restored.dimensions):
            assert len(orig_dim.criteria) == len(rest_dim.criteria)
            for orig_c, rest_c in zip(orig_dim.criteria, rest_dim.criteria):
                assert orig_c.level == rest_c.level
                assert orig_c.description == rest_c.description

    def test_missing_fields_use_defaults(self):
        data = {}
        config = dict_to_config(data)
        assert config.system_prompt == DEFAULT_SYSTEM_PROMPT
        assert config.model == AVAILABLE_MODELS[0]
        assert config.temperature == 0.0
        assert config.max_tokens == 4096
        assert len(config.dimensions) >= 2  # defaults

    def test_empty_dimensions_uses_defaults(self):
        data = {"dimensions": []}
        config = dict_to_config(data)
        assert len(config.dimensions) >= 2  # defaults

    def test_partial_dimension_data(self):
        data = {
            "dimensions": [
                {"name": "Test"},
            ]
        }
        config = dict_to_config(data)
        assert len(config.dimensions) == 1
        assert config.dimensions[0].name == "Test"
        assert config.dimensions[0].weight == 0.5  # default

    def test_custom_model(self):
        data = {"model": "claude-opus-4-20250514"}
        config = dict_to_config(data)
        assert config.model == "claude-opus-4-20250514"


# ---- save_config / load_config tests ----


class TestSaveAndLoadConfig:
    def test_save_creates_file(self, tmp_path: Path):
        config = default_config()
        saved_path = save_config(config, tmp_path)
        assert saved_path.exists()
        assert saved_path.name == ACTIVE_CONFIG_FILENAME

    def test_save_creates_directory(self, tmp_path: Path):
        config = default_config()
        save_config(config, tmp_path)
        templates_dir = tmp_path / JUDGE_TEMPLATES_DIR
        assert templates_dir.exists()

    def test_load_returns_saved_config(self, tmp_path: Path):
        original = JudgeConfig(
            system_prompt="Custom prompt",
            dimensions=(
                ScoringDimension(
                    name="Custom",
                    weight=0.7,
                    criteria=(ScoringCriterion(1, "Low"), ScoringCriterion(2, "High")),
                ),
            ),
            model="claude-opus-4-20250514",
            temperature=0.3,
            max_tokens=8192,
        )
        save_config(original, tmp_path)
        loaded = load_config(tmp_path)

        assert loaded.system_prompt == "Custom prompt"
        assert loaded.model == "claude-opus-4-20250514"
        assert loaded.temperature == 0.3
        assert loaded.max_tokens == 8192
        assert len(loaded.dimensions) == 1
        assert loaded.dimensions[0].name == "Custom"

    def test_load_missing_file_returns_default(self, tmp_path: Path):
        config = load_config(tmp_path)
        assert config.system_prompt == DEFAULT_SYSTEM_PROMPT

    def test_load_malformed_json_returns_default(self, tmp_path: Path):
        templates_dir = tmp_path / JUDGE_TEMPLATES_DIR
        templates_dir.mkdir(parents=True)
        bad_file = templates_dir / ACTIVE_CONFIG_FILENAME
        bad_file.write_text("not json!", encoding="utf-8")

        config = load_config(tmp_path)
        assert config.system_prompt == DEFAULT_SYSTEM_PROMPT

    def test_save_custom_filename(self, tmp_path: Path):
        config = default_config()
        saved_path = save_config(config, tmp_path, "my_template.json")
        assert saved_path.name == "my_template.json"
        assert saved_path.exists()

    def test_load_custom_filename(self, tmp_path: Path):
        config = JudgeConfig(
            system_prompt="Named template",
            dimensions=(),
            model="claude-haiku-4-5-20251001",
            temperature=0.1,
            max_tokens=2048,
        )
        save_config(config, tmp_path, "named.json")
        loaded = load_config(tmp_path, "named.json")
        assert loaded.system_prompt == "Named template"

    def test_save_overwrites_existing(self, tmp_path: Path):
        config1 = JudgeConfig(
            system_prompt="First",
            dimensions=(),
            model="m",
            temperature=0.0,
            max_tokens=1000,
        )
        config2 = JudgeConfig(
            system_prompt="Second",
            dimensions=(),
            model="m",
            temperature=0.0,
            max_tokens=1000,
        )
        save_config(config1, tmp_path)
        save_config(config2, tmp_path)
        loaded = load_config(tmp_path)
        assert loaded.system_prompt == "Second"

    def test_saved_file_is_valid_json(self, tmp_path: Path):
        config = default_config()
        saved_path = save_config(config, tmp_path)
        with open(saved_path) as f:
            data = json.load(f)
        assert "system_prompt" in data
        assert "dimensions" in data


# ---- list_templates tests ----


class TestListTemplates:
    def test_empty_directory(self, tmp_path: Path):
        result = list_templates(tmp_path)
        assert result == []

    def test_nonexistent_directory(self, tmp_path: Path):
        result = list_templates(tmp_path / "nonexistent")
        assert result == []

    def test_lists_json_files(self, tmp_path: Path):
        config = default_config()
        save_config(config, tmp_path, "a.json")
        save_config(config, tmp_path, "b.json")
        result = list_templates(tmp_path)
        assert "a.json" in result
        assert "b.json" in result

    def test_sorted_alphabetically(self, tmp_path: Path):
        config = default_config()
        save_config(config, tmp_path, "z.json")
        save_config(config, tmp_path, "a.json")
        result = list_templates(tmp_path)
        assert result == sorted(result)

    def test_ignores_non_json_files(self, tmp_path: Path):
        templates_dir = tmp_path / JUDGE_TEMPLATES_DIR
        templates_dir.mkdir(parents=True)
        (templates_dir / "readme.txt").write_text("info")
        (templates_dir / "valid.json").write_text("{}")
        result = list_templates(tmp_path)
        assert result == ["valid.json"]


# ---- delete_template tests ----


class TestDeleteTemplate:
    def test_deletes_existing_file(self, tmp_path: Path):
        config = default_config()
        save_config(config, tmp_path, "to_delete.json")
        result = delete_template(tmp_path, "to_delete.json")
        assert result is True
        assert "to_delete.json" not in list_templates(tmp_path)

    def test_returns_false_for_missing_file(self, tmp_path: Path):
        result = delete_template(tmp_path, "nonexistent.json")
        assert result is False

    def test_does_not_affect_other_files(self, tmp_path: Path):
        config = default_config()
        save_config(config, tmp_path, "keep.json")
        save_config(config, tmp_path, "remove.json")
        delete_template(tmp_path, "remove.json")
        assert "keep.json" in list_templates(tmp_path)


# ---- add_dimension tests ----


class TestAddDimension:
    def test_adds_dimension(self):
        config = JudgeConfig(
            system_prompt="P",
            dimensions=(),
            model="m",
            temperature=0.0,
            max_tokens=1000,
        )
        new_dim = ScoringDimension(name="New", weight=0.5, criteria=())
        result = add_dimension(config, new_dim)
        assert len(result.dimensions) == 1
        assert result.dimensions[0].name == "New"

    def test_preserves_existing_dimensions(self):
        existing = ScoringDimension(name="Existing", weight=0.3, criteria=())
        config = JudgeConfig(
            system_prompt="P",
            dimensions=(existing,),
            model="m",
            temperature=0.0,
            max_tokens=1000,
        )
        new_dim = ScoringDimension(name="New", weight=0.5, criteria=())
        result = add_dimension(config, new_dim)
        assert len(result.dimensions) == 2
        assert result.dimensions[0].name == "Existing"
        assert result.dimensions[1].name == "New"

    def test_preserves_other_config_fields(self):
        config = JudgeConfig(
            system_prompt="Custom",
            dimensions=(),
            model="claude-opus-4-20250514",
            temperature=0.7,
            max_tokens=8192,
        )
        new_dim = ScoringDimension(name="X", weight=0.1, criteria=())
        result = add_dimension(config, new_dim)
        assert result.system_prompt == "Custom"
        assert result.model == "claude-opus-4-20250514"
        assert result.temperature == 0.7
        assert result.max_tokens == 8192


# ---- remove_dimension tests ----


class TestRemoveDimension:
    def test_removes_dimension_at_index(self):
        dims = (
            ScoringDimension(name="A", weight=0.3, criteria=()),
            ScoringDimension(name="B", weight=0.5, criteria=()),
            ScoringDimension(name="C", weight=0.2, criteria=()),
        )
        config = JudgeConfig(
            system_prompt="P",
            dimensions=dims,
            model="m",
            temperature=0.0,
            max_tokens=1000,
        )
        result = remove_dimension(config, 1)
        assert len(result.dimensions) == 2
        assert result.dimensions[0].name == "A"
        assert result.dimensions[1].name == "C"

    def test_removes_first_dimension(self):
        dims = (
            ScoringDimension(name="A", weight=0.3, criteria=()),
            ScoringDimension(name="B", weight=0.7, criteria=()),
        )
        config = JudgeConfig(
            system_prompt="P",
            dimensions=dims,
            model="m",
            temperature=0.0,
            max_tokens=1000,
        )
        result = remove_dimension(config, 0)
        assert len(result.dimensions) == 1
        assert result.dimensions[0].name == "B"

    def test_removes_last_dimension(self):
        dims = (
            ScoringDimension(name="A", weight=0.3, criteria=()),
            ScoringDimension(name="B", weight=0.7, criteria=()),
        )
        config = JudgeConfig(
            system_prompt="P",
            dimensions=dims,
            model="m",
            temperature=0.0,
            max_tokens=1000,
        )
        result = remove_dimension(config, 1)
        assert len(result.dimensions) == 1
        assert result.dimensions[0].name == "A"

    def test_negative_index_returns_unchanged(self):
        config = default_config()
        result = remove_dimension(config, -1)
        assert len(result.dimensions) == len(config.dimensions)

    def test_out_of_bounds_index_returns_unchanged(self):
        config = default_config()
        result = remove_dimension(config, 999)
        assert len(result.dimensions) == len(config.dimensions)

    def test_preserves_other_config_fields(self):
        dims = (ScoringDimension(name="X", weight=0.5, criteria=()),)
        config = JudgeConfig(
            system_prompt="Keep",
            dimensions=dims,
            model="claude-opus-4-20250514",
            temperature=0.3,
            max_tokens=2048,
        )
        result = remove_dimension(config, 0)
        assert result.system_prompt == "Keep"
        assert result.model == "claude-opus-4-20250514"
        assert result.temperature == 0.3
        assert result.max_tokens == 2048


# ---- update_dimension tests ----


class TestUpdateDimension:
    def test_updates_dimension_at_index(self):
        dims = (
            ScoringDimension(name="Old", weight=0.3, criteria=()),
            ScoringDimension(name="Keep", weight=0.7, criteria=()),
        )
        config = JudgeConfig(
            system_prompt="P",
            dimensions=dims,
            model="m",
            temperature=0.0,
            max_tokens=1000,
        )
        new_dim = ScoringDimension(name="New", weight=0.8, criteria=())
        result = update_dimension(config, 0, new_dim)
        assert result.dimensions[0].name == "New"
        assert result.dimensions[0].weight == 0.8
        assert result.dimensions[1].name == "Keep"

    def test_negative_index_returns_unchanged(self):
        config = default_config()
        new_dim = ScoringDimension(name="X", weight=0.1, criteria=())
        result = update_dimension(config, -1, new_dim)
        assert result.dimensions == config.dimensions

    def test_out_of_bounds_returns_unchanged(self):
        config = default_config()
        new_dim = ScoringDimension(name="X", weight=0.1, criteria=())
        result = update_dimension(config, 999, new_dim)
        assert result.dimensions == config.dimensions

    def test_preserves_other_config_fields(self):
        dims = (ScoringDimension(name="X", weight=0.5, criteria=()),)
        config = JudgeConfig(
            system_prompt="Keep",
            dimensions=dims,
            model="m",
            temperature=0.9,
            max_tokens=512,
        )
        new_dim = ScoringDimension(name="Y", weight=0.2, criteria=())
        result = update_dimension(config, 0, new_dim)
        assert result.system_prompt == "Keep"
        assert result.temperature == 0.9
        assert result.max_tokens == 512


# ---- AVAILABLE_MODELS tests ----


class TestAvailableModels:
    def test_is_tuple(self):
        assert isinstance(AVAILABLE_MODELS, tuple)

    def test_has_models(self):
        assert len(AVAILABLE_MODELS) >= 2

    def test_all_strings(self):
        for model in AVAILABLE_MODELS:
            assert isinstance(model, str)
            assert len(model) > 0
