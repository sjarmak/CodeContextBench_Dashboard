"""
Judge configuration data model and file I/O.

Manages LLM judge templates with system prompt, scoring dimensions,
model settings, and persistence to configs/judge_templates/.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

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


@dataclass(frozen=True)
class TemplateInfo:
    """Metadata about a saved template."""

    name: str
    filename: str
    model: str
    created_at: str  # ISO format datetime string


def save_template(
    config: JudgeConfig,
    project_root: Path,
    template_name: str,
) -> Path:
    """Save a JudgeConfig as a named template with metadata.

    Creates the templates directory if it doesn't exist.
    The template name is sanitized to produce a valid filename.

    Args:
        config: JudgeConfig to save
        project_root: Project root directory
        template_name: Human-readable name for the template

    Returns:
        Path to the saved file
    """
    filename = _sanitize_template_name(template_name)
    data = {
        **config_to_dict(config),
        "_template_name": template_name,
        "_created_at": datetime.now(timezone.utc).isoformat(),
    }

    templates_dir = _get_templates_dir(project_root)
    templates_dir.mkdir(parents=True, exist_ok=True)

    file_path = templates_dir / filename
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved template '{template_name}' to {file_path}")
    except OSError as e:
        logger.error(f"Failed to save template: {e}")
        raise

    return file_path


def _sanitize_template_name(name: str) -> str:
    """Convert a template name to a valid filename.

    Replaces spaces and non-alphanumeric characters with underscores,
    lowercases, and appends .json.

    Args:
        name: Human-readable template name

    Returns:
        Sanitized filename with .json extension
    """
    sanitized = "".join(
        c if c.isalnum() or c in ("-", "_") else "_"
        for c in name.strip().lower()
    )
    sanitized = sanitized.strip("_") or "unnamed"
    return f"{sanitized}.json"


def load_template_info(
    project_root: Path,
    filename: str,
) -> TemplateInfo | None:
    """Load template metadata from a JSON file.

    Args:
        project_root: Project root directory
        filename: Template filename

    Returns:
        TemplateInfo or None if file not found or malformed
    """
    file_path = _get_templates_dir(project_root) / filename

    if not file_path.exists():
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        name = data.get("_template_name", filename.replace(".json", ""))
        created_at = data.get("_created_at", "")
        model = data.get("model", "unknown")

        return TemplateInfo(
            name=name,
            filename=filename,
            model=model,
            created_at=created_at,
        )
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load template info from {file_path}: {e}")
        return None


def list_template_infos(project_root: Path) -> list[TemplateInfo]:
    """List all saved templates with metadata.

    Args:
        project_root: Project root directory

    Returns:
        List of TemplateInfo sorted by name
    """
    filenames = list_templates(project_root)
    infos: list[TemplateInfo] = []
    for filename in filenames:
        info = load_template_info(project_root, filename)
        if info is not None:
            infos = [*infos, info]
    return infos


def duplicate_template(
    project_root: Path,
    source_filename: str,
    new_name: str | None = None,
) -> Path | None:
    """Duplicate a template file with '-copy' suffix.

    Args:
        project_root: Project root directory
        source_filename: Filename of template to duplicate
        new_name: Optional new template name. Defaults to original name + '-copy'.

    Returns:
        Path to the new file, or None if source not found
    """
    source_path = _get_templates_dir(project_root) / source_filename

    if not source_path.exists():
        return None

    try:
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        original_name = data.get(
            "_template_name",
            source_filename.replace(".json", ""),
        )
        copy_name = new_name if new_name else f"{original_name}-copy"

        data = {
            **data,
            "_template_name": copy_name,
            "_created_at": datetime.now(timezone.utc).isoformat(),
        }

        copy_filename = _sanitize_template_name(copy_name)
        copy_path = _get_templates_dir(project_root) / copy_filename

        with open(copy_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Duplicated template '{original_name}' as '{copy_name}'")
        return copy_path

    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to duplicate template: {e}")
        return None


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
