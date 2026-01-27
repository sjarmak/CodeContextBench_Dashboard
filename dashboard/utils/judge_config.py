"""
Judge configuration data model and file I/O.

Manages LLM judge templates with system prompt, scoring dimensions,
model settings, and persistence to configs/judge_templates/.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default configs directory relative to project root
JUDGE_TEMPLATES_DIR = "configs/judge_templates"
ACTIVE_CONFIG_FILENAME = "active_config.json"

# Available Anthropic models for judge evaluation
AVAILABLE_MODELS = (
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
)

DEFAULT_SYSTEM_PROMPT = (
    "You are an expert code reviewer and evaluator. "
    "Evaluate the agent's solution based on the provided scoring dimensions. "
    "For each dimension, assign a score from 1 to 5 and provide a brief justification."
)


@dataclass(frozen=True)
class ScoringCriterion:
    """Description for a single score level within a dimension."""

    level: int  # 1-5
    description: str


@dataclass(frozen=True)
class ScoringDimension:
    """A single scoring dimension with name, weight, and per-level criteria."""

    name: str
    weight: float  # 0.0 - 1.0
    criteria: tuple[ScoringCriterion, ...]  # one per score level (1-5)


@dataclass(frozen=True)
class JudgeConfig:
    """Complete LLM judge configuration."""

    system_prompt: str
    dimensions: tuple[ScoringDimension, ...]
    model: str
    temperature: float
    max_tokens: int


def default_dimensions() -> tuple[ScoringDimension, ...]:
    """Return the default scoring dimensions."""
    return (
        ScoringDimension(
            name="Correctness",
            weight=0.4,
            criteria=(
                ScoringCriterion(1, "Solution does not address the issue"),
                ScoringCriterion(2, "Solution attempts but is largely incorrect"),
                ScoringCriterion(3, "Solution partially addresses the issue"),
                ScoringCriterion(4, "Solution mostly correct with minor issues"),
                ScoringCriterion(5, "Solution fully and correctly addresses the issue"),
            ),
        ),
        ScoringDimension(
            name="Code Quality",
            weight=0.3,
            criteria=(
                ScoringCriterion(1, "Code is incorrect or harmful"),
                ScoringCriterion(2, "Code has significant issues"),
                ScoringCriterion(3, "Code is acceptable with some issues"),
                ScoringCriterion(4, "Code is good with minor improvements possible"),
                ScoringCriterion(5, "Code is excellent and well-implemented"),
            ),
        ),
        ScoringDimension(
            name="Completeness",
            weight=0.3,
            criteria=(
                ScoringCriterion(1, "No requirements are met"),
                ScoringCriterion(2, "Few requirements are met"),
                ScoringCriterion(3, "Some requirements are met"),
                ScoringCriterion(4, "Most requirements are met"),
                ScoringCriterion(5, "All requirements are fully met"),
            ),
        ),
    )


def default_config() -> JudgeConfig:
    """Return a default JudgeConfig."""
    return JudgeConfig(
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        dimensions=default_dimensions(),
        model=AVAILABLE_MODELS[0],
        temperature=0.0,
        max_tokens=4096,
    )


def _dimension_to_dict(dim: ScoringDimension) -> dict:
    """Convert a ScoringDimension to a serializable dict."""
    return {
        "name": dim.name,
        "weight": dim.weight,
        "criteria": [
            {"level": c.level, "description": c.description}
            for c in dim.criteria
        ],
    }


def _dict_to_dimension(data: dict) -> ScoringDimension:
    """Convert a dict to a ScoringDimension."""
    criteria_list = data.get("criteria", [])
    criteria = tuple(
        ScoringCriterion(
            level=c.get("level", i + 1),
            description=c.get("description", ""),
        )
        for i, c in enumerate(criteria_list)
    )
    return ScoringDimension(
        name=data.get("name", ""),
        weight=float(data.get("weight", 0.5)),
        criteria=criteria,
    )


def config_to_dict(config: JudgeConfig) -> dict:
    """Serialize a JudgeConfig to a JSON-compatible dict.

    Args:
        config: JudgeConfig to serialize

    Returns:
        Dict suitable for JSON serialization
    """
    return {
        "system_prompt": config.system_prompt,
        "dimensions": [_dimension_to_dict(d) for d in config.dimensions],
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }


def dict_to_config(data: dict) -> JudgeConfig:
    """Deserialize a dict into a JudgeConfig.

    Args:
        data: Dict from JSON parsing

    Returns:
        JudgeConfig instance
    """
    dimensions = tuple(
        _dict_to_dimension(d) for d in data.get("dimensions", [])
    )
    return JudgeConfig(
        system_prompt=data.get("system_prompt", DEFAULT_SYSTEM_PROMPT),
        dimensions=dimensions if dimensions else default_dimensions(),
        model=data.get("model", AVAILABLE_MODELS[0]),
        temperature=float(data.get("temperature", 0.0)),
        max_tokens=int(data.get("max_tokens", 4096)),
    )


def _get_templates_dir(project_root: Path) -> Path:
    """Get the judge templates directory path."""
    return project_root / JUDGE_TEMPLATES_DIR


def save_config(
    config: JudgeConfig,
    project_root: Path,
    filename: str = ACTIVE_CONFIG_FILENAME,
) -> Path:
    """Save a JudgeConfig to a JSON file.

    Creates the templates directory if it doesn't exist.

    Args:
        config: JudgeConfig to save
        project_root: Project root directory
        filename: Filename to save as (default: active_config.json)

    Returns:
        Path to the saved file
    """
    templates_dir = _get_templates_dir(project_root)
    templates_dir.mkdir(parents=True, exist_ok=True)

    file_path = templates_dir / filename
    data = config_to_dict(config)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved judge config to {file_path}")
    except OSError as e:
        logger.error(f"Failed to save judge config: {e}")
        raise

    return file_path


def load_config(
    project_root: Path,
    filename: str = ACTIVE_CONFIG_FILENAME,
) -> JudgeConfig:
    """Load a JudgeConfig from a JSON file.

    Returns the default config if the file doesn't exist or is malformed.

    Args:
        project_root: Project root directory
        filename: Filename to load (default: active_config.json)

    Returns:
        JudgeConfig instance
    """
    file_path = _get_templates_dir(project_root) / filename

    if not file_path.exists():
        logger.info(f"No config file at {file_path}, using defaults")
        return default_config()

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return dict_to_config(data)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load config from {file_path}: {e}")
        return default_config()


def list_templates(project_root: Path) -> list[str]:
    """List all saved template filenames.

    Args:
        project_root: Project root directory

    Returns:
        List of template filenames (sorted alphabetically)
    """
    templates_dir = _get_templates_dir(project_root)
    if not templates_dir.exists():
        return []

    return sorted(
        f.name
        for f in templates_dir.iterdir()
        if f.is_file() and f.suffix == ".json"
    )


def delete_template(
    project_root: Path,
    filename: str,
) -> bool:
    """Delete a template file.

    Args:
        project_root: Project root directory
        filename: Template filename to delete

    Returns:
        True if deleted, False if file not found
    """
    file_path = _get_templates_dir(project_root) / filename

    if not file_path.exists():
        return False

    try:
        file_path.unlink()
        logger.info(f"Deleted template {file_path}")
        return True
    except OSError as e:
        logger.error(f"Failed to delete template: {e}")
        return False


def add_dimension(
    config: JudgeConfig,
    dimension: ScoringDimension,
) -> JudgeConfig:
    """Return a new config with an additional dimension.

    Args:
        config: Existing JudgeConfig
        dimension: New dimension to add

    Returns:
        New JudgeConfig with the dimension appended
    """
    return JudgeConfig(
        system_prompt=config.system_prompt,
        dimensions=(*config.dimensions, dimension),
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )


def remove_dimension(
    config: JudgeConfig,
    index: int,
) -> JudgeConfig:
    """Return a new config with a dimension removed by index.

    Args:
        config: Existing JudgeConfig
        index: Index of the dimension to remove

    Returns:
        New JudgeConfig without the specified dimension
    """
    if index < 0 or index >= len(config.dimensions):
        return config

    remaining = tuple(
        d for i, d in enumerate(config.dimensions) if i != index
    )
    return JudgeConfig(
        system_prompt=config.system_prompt,
        dimensions=remaining,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )


def update_dimension(
    config: JudgeConfig,
    index: int,
    dimension: ScoringDimension,
) -> JudgeConfig:
    """Return a new config with a dimension replaced at the given index.

    Args:
        config: Existing JudgeConfig
        index: Index of the dimension to replace
        dimension: New dimension to insert

    Returns:
        New JudgeConfig with the updated dimension
    """
    if index < 0 or index >= len(config.dimensions):
        return config

    updated = tuple(
        dimension if i == index else d
        for i, d in enumerate(config.dimensions)
    )
    return JudgeConfig(
        system_prompt=config.system_prompt,
        dimensions=updated,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
