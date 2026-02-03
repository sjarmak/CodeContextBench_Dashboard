"""Tests for the prompt template loader and renderer."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest
import yaml

# --- Together SDK mock setup (needed because src.judge.__init__ imports backends) ---
if "together" not in sys.modules:
    _together_module = ModuleType("together")
    _together_error = ModuleType("together.error")

    class _MockTogetherRateLimitError(Exception):
        pass

    _together_error.RateLimitError = _MockTogetherRateLimitError  # type: ignore[attr-defined]
    _together_module.error = _together_error  # type: ignore[attr-defined]
    _together_module.AsyncTogether = MagicMock  # type: ignore[attr-defined]
    sys.modules["together"] = _together_module
    sys.modules["together.error"] = _together_error

from src.judge.prompts.loader import PromptTemplate, load_template, render


# ---------- PromptTemplate dataclass tests ----------


class TestPromptTemplate:
    """Tests for the PromptTemplate frozen dataclass."""

    def test_construction(self):
        tpl = PromptTemplate(
            name="test",
            version="1.0",
            system_prompt="You are a judge.",
            user_prompt_template="Evaluate {task_description}",
            output_format_spec='{"score": 0.0}',
        )
        assert tpl.name == "test"
        assert tpl.version == "1.0"
        assert tpl.example_output is None

    def test_construction_with_example(self):
        tpl = PromptTemplate(
            name="test",
            version="1.0",
            system_prompt="system",
            user_prompt_template="Evaluate {task}",
            output_format_spec="spec",
            example_output='{"example": true}',
        )
        assert tpl.example_output == '{"example": true}'

    def test_immutability(self):
        tpl = PromptTemplate(
            name="test",
            version="1.0",
            system_prompt="system",
            user_prompt_template="Evaluate {task}",
            output_format_spec="spec",
        )
        with pytest.raises(AttributeError):
            tpl.name = "changed"


# ---------- load_template tests ----------


class TestLoadTemplate:
    """Tests for the load_template function."""

    def _write_yaml(self, data: dict, path: Path) -> Path:
        filepath = path / "template.yaml"
        with open(filepath, "w") as f:
            yaml.dump(data, f)
        return filepath

    def _valid_data(self) -> dict:
        return {
            "name": "test_template",
            "version": "1.0",
            "system_prompt": "You are a judge.",
            "user_prompt_template": "Evaluate {task_description} with {dimensions}",
            "output_format_spec": '{"score": 0.0}',
        }

    def test_load_valid_template(self, tmp_path):
        filepath = self._write_yaml(self._valid_data(), tmp_path)
        tpl = load_template(filepath)
        assert tpl.name == "test_template"
        assert tpl.version == "1.0"
        assert "{task_description}" in tpl.user_prompt_template
        assert tpl.example_output is None

    def test_load_with_example_output(self, tmp_path):
        data = self._valid_data()
        data["example_output"] = '{"example": true}'
        filepath = self._write_yaml(data, tmp_path)
        tpl = load_template(filepath)
        assert tpl.example_output == '{"example": true}'

    def test_load_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="Template file not found"):
            load_template("/nonexistent/template.yaml")

    def test_load_missing_required_fields(self, tmp_path):
        data = {"name": "incomplete", "version": "1.0"}
        filepath = self._write_yaml(data, tmp_path)
        with pytest.raises(ValueError, match="missing required fields"):
            load_template(filepath)

    def test_load_not_a_mapping(self, tmp_path):
        filepath = tmp_path / "template.yaml"
        with open(filepath, "w") as f:
            f.write("- item1\n- item2\n")
        with pytest.raises(ValueError, match="must contain a YAML mapping"):
            load_template(filepath)

    def test_load_no_placeholders_raises(self, tmp_path):
        data = self._valid_data()
        data["user_prompt_template"] = "This has no placeholders at all."
        filepath = self._write_yaml(data, tmp_path)
        with pytest.raises(ValueError, match="contains no placeholders"):
            load_template(filepath)

    def test_load_accepts_string_path(self, tmp_path):
        filepath = self._write_yaml(self._valid_data(), tmp_path)
        tpl = load_template(str(filepath))
        assert tpl.name == "test_template"


# ---------- render tests ----------


class TestRender:
    """Tests for the render function."""

    def _make_template(self, user_prompt: str) -> PromptTemplate:
        return PromptTemplate(
            name="test",
            version="1.0",
            system_prompt="system",
            user_prompt_template=user_prompt,
            output_format_spec="spec",
        )

    def test_render_basic(self):
        tpl = self._make_template("Task: {task_description}, Dims: {dimensions}")
        result = render(tpl, task_description="Fix bug", dimensions="Correctness")
        assert result == "Task: Fix bug, Dims: Correctness"

    def test_render_single_placeholder(self):
        tpl = self._make_template("Evaluate: {task}")
        result = render(tpl, task="implement feature")
        assert result == "Evaluate: implement feature"

    def test_render_missing_placeholder_raises(self):
        tpl = self._make_template("Task: {task_description}, Dims: {dimensions}")
        with pytest.raises(KeyError, match="Missing values for placeholders"):
            render(tpl, task_description="Fix bug")

    def test_render_extra_kwargs_allowed(self):
        tpl = self._make_template("Task: {task}")
        result = render(tpl, task="test", extra="ignored")
        assert result == "Task: test"

    def test_render_multiline_template(self):
        tpl = self._make_template("## Task\n{task}\n\n## Output\n{output}")
        result = render(tpl, task="Fix bug", output="Done")
        assert "## Task\nFix bug\n\n## Output\nDone" == result

    def test_render_preserves_non_placeholder_braces(self):
        tpl = self._make_template("JSON: {{\"key\": \"val\"}} and {task}")
        result = render(tpl, task="test")
        assert result == 'JSON: {"key": "val"} and test'


# ---------- Default template loading tests ----------


class TestDefaultTemplates:
    """Tests for loading the 5 default YAML templates."""

    TEMPLATES_DIR = Path(__file__).parent.parent / "configs" / "judge_prompts"

    EXPECTED_TEMPLATES = [
        ("pairwise_simultaneous.yaml", {"task_description", "dimensions", "outputs", "output_format"}),
        ("pairwise_roundrobin.yaml", {"task_description", "dimensions", "output_a", "output_b", "output_format"}),
        ("direct_review.yaml", {"task_description", "dimensions", "agent_output", "code_changes", "output_format"}),
        ("reference_correctness.yaml", {"task_description", "reference_answer", "context_files", "agent_output", "output_format"}),
        ("reference_completeness.yaml", {"task_description", "evaluation_criteria", "agent_output", "output_format"}),
    ]

    def test_all_templates_exist(self):
        for filename, _ in self.EXPECTED_TEMPLATES:
            path = self.TEMPLATES_DIR / filename
            assert path.exists(), f"Missing template: {filename}"

    @pytest.mark.parametrize("filename,expected_placeholders", EXPECTED_TEMPLATES)
    def test_template_loads_successfully(self, filename, expected_placeholders):
        tpl = load_template(self.TEMPLATES_DIR / filename)
        assert isinstance(tpl, PromptTemplate)
        assert tpl.version == "1.0"

    @pytest.mark.parametrize("filename,expected_placeholders", EXPECTED_TEMPLATES)
    def test_template_has_expected_placeholders(self, filename, expected_placeholders):
        tpl = load_template(self.TEMPLATES_DIR / filename)
        import re
        actual = set(re.findall(r"\{(\w+)\}", tpl.user_prompt_template))
        assert expected_placeholders.issubset(actual), (
            f"Template {filename} missing placeholders: {expected_placeholders - actual}"
        )

    @pytest.mark.parametrize("filename,expected_placeholders", EXPECTED_TEMPLATES)
    def test_template_has_anti_bias_instructions(self, filename, expected_placeholders):
        tpl = load_template(self.TEMPLATES_DIR / filename)
        system = tpl.system_prompt.lower()
        assert "bias" in system or "verbosity" in system or "longer" in system, (
            f"Template {filename} system_prompt missing anti-bias instructions"
        )

    @pytest.mark.parametrize("filename,expected_placeholders", EXPECTED_TEMPLATES)
    def test_template_requests_json_output(self, filename, expected_placeholders):
        tpl = load_template(self.TEMPLATES_DIR / filename)
        user = tpl.user_prompt_template.lower()
        assert "json" in user, (
            f"Template {filename} should request JSON output in user prompt"
        )

    @pytest.mark.parametrize("filename,expected_placeholders", EXPECTED_TEMPLATES)
    def test_template_requests_chain_of_thought(self, filename, expected_placeholders):
        tpl = load_template(self.TEMPLATES_DIR / filename)
        system = tpl.system_prompt.lower()
        assert "chain-of-thought" in system or "chain of thought" in system or "reasoning" in system, (
            f"Template {filename} should request chain-of-thought reasoning"
        )


# ---------- Import tests ----------


class TestImports:
    """Tests that public API is accessible from the package."""

    def test_import_from_prompts_package(self):
        from src.judge.prompts import PromptTemplate, load_template, render
        assert PromptTemplate is not None
        assert callable(load_template)
        assert callable(render)
