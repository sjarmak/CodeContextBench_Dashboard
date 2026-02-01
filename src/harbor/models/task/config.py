"""Task configuration model for Harbor benchmark framework."""

import sys
from typing import Any, Dict

# tomllib is Python 3.11+, fall back to tomli for older versions
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        # Fallback: basic TOML parsing for simple cases
        tomllib = None


class TaskConfig:
    """Configuration for a Harbor benchmark task."""

    def __init__(self, metadata: Dict[str, Any] = None, **kwargs):
        """Initialize task configuration.

        Args:
            metadata: Task metadata dictionary.
            **kwargs: Additional configuration fields.
        """
        self.metadata = metadata if metadata is not None else {}
        self._config = kwargs

    @classmethod
    def model_validate_toml(cls, toml_content: str) -> "TaskConfig":
        """Parse a TaskConfig from TOML content.

        Args:
            toml_content: TOML string to parse.

        Returns:
            TaskConfig instance.
        """
        if tomllib is not None:
            data = tomllib.loads(toml_content)
        else:
            # Basic fallback TOML parser for simple configs
            data = cls._parse_simple_toml(toml_content)
        metadata = data.pop("metadata", {})
        return cls(metadata=metadata, **data)

    @staticmethod
    def _parse_simple_toml(content: str) -> Dict[str, Any]:
        """Basic TOML parser for simple configurations.

        Only handles basic sections and key-value pairs.
        For full TOML support, install tomli package.
        """
        import re
        result: Dict[str, Any] = {}
        current_section = None

        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Section header
            section_match = re.match(r"\[([^\]]+)\]", line)
            if section_match:
                current_section = section_match.group(1)
                result[current_section] = {}
                continue

            # Key-value pair
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Parse value
                if value.startswith('"') and value.endswith('"'):
                    parsed_value = value[1:-1]
                elif value.startswith("[") and value.endswith("]"):
                    # Simple list parsing
                    inner = value[1:-1]
                    if inner:
                        items = [v.strip().strip('"') for v in inner.split(",")]
                        parsed_value = items
                    else:
                        parsed_value = []
                elif value.lower() in ("true", "false"):
                    parsed_value = value.lower() == "true"
                else:
                    try:
                        parsed_value = int(value)
                    except ValueError:
                        try:
                            parsed_value = float(value)
                        except ValueError:
                            parsed_value = value

                if current_section:
                    result[current_section][key] = parsed_value
                else:
                    result[key] = parsed_value

        return result

    def model_dump_toml(self) -> str:
        """Serialize the configuration to TOML format.

        Returns:
            TOML string representation.
        """
        lines = []

        # Write metadata section
        if self.metadata:
            lines.append("[metadata]")
            for key, value in self.metadata.items():
                if isinstance(value, str):
                    lines.append(f'{key} = "{value}"')
                elif isinstance(value, bool):
                    lines.append(f"{key} = {str(value).lower()}")
                elif isinstance(value, (int, float)):
                    lines.append(f"{key} = {value}")
                elif isinstance(value, list):
                    formatted = ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in value)
                    lines.append(f"{key} = [{formatted}]")
            lines.append("")

        # Write other sections
        for section, content in self._config.items():
            if section == "metadata":
                continue
            if isinstance(content, dict):
                lines.append(f"[{section}]")
                for key, value in content.items():
                    if isinstance(value, str):
                        lines.append(f'{key} = "{value}"')
                    elif isinstance(value, bool):
                        lines.append(f"{key} = {str(value).lower()}")
                    elif isinstance(value, (int, float)):
                        lines.append(f"{key} = {value}")
                    elif isinstance(value, list):
                        formatted = ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in value)
                        lines.append(f"{key} = [{formatted}]")
                lines.append("")

        return "\n".join(lines)
