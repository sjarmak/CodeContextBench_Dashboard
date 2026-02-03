"""Prompt template loader and renderer for the unified LLM judge.

Loads YAML-based prompt templates with placeholder validation and rendering.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass(frozen=True)
class PromptTemplate:
    """A prompt template with system and user prompts containing {placeholders}."""

    name: str
    version: str
    system_prompt: str
    user_prompt_template: str
    output_format_spec: str
    example_output: Optional[str] = None


def _extract_placeholders(template: str) -> set[str]:
    """Extract all {placeholder} names from a template string."""
    return set(re.findall(r"\{(\w+)\}", template))


def load_template(path: str | Path) -> PromptTemplate:
    """Load a prompt template from a YAML file.

    Args:
        path: Path to the YAML template file.

    Returns:
        A validated PromptTemplate instance.

    Raises:
        FileNotFoundError: If the template file does not exist.
        ValueError: If required fields are missing or template is invalid.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Template file not found: {path}")

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Template file must contain a YAML mapping: {path}")

    required_fields = ["name", "version", "system_prompt", "user_prompt_template", "output_format_spec"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise ValueError(f"Template missing required fields: {', '.join(missing)}")

    placeholders = _extract_placeholders(data["user_prompt_template"])
    if not placeholders:
        raise ValueError(
            f"Template '{data['name']}' user_prompt_template contains no placeholders. "
            "Templates must include at least one {{placeholder}}."
        )

    return PromptTemplate(
        name=data["name"],
        version=data["version"],
        system_prompt=data["system_prompt"],
        user_prompt_template=data["user_prompt_template"],
        output_format_spec=data["output_format_spec"],
        example_output=data.get("example_output"),
    )


def render(template: PromptTemplate, **kwargs: str) -> str:
    """Render a prompt template by substituting placeholders.

    Args:
        template: The PromptTemplate to render.
        **kwargs: Values for each placeholder in the user_prompt_template.

    Returns:
        The rendered user prompt string.

    Raises:
        KeyError: If a required placeholder value is not provided.
    """
    required = _extract_placeholders(template.user_prompt_template)
    provided = set(kwargs.keys())
    missing = required - provided
    if missing:
        raise KeyError(
            f"Missing values for placeholders: {', '.join(sorted(missing))}. "
            f"Template '{template.name}' requires: {', '.join(sorted(required))}"
        )

    return template.user_prompt_template.format(**kwargs)
