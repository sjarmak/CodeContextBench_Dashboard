"""
Agent Label Standardization

Maps directory names to canonical labels for consistent display
across the dashboard.
"""

# Directory name -> canonical label
AGENT_LABEL_MAP: dict[str, str] = {
    "baseline": "baseline",
    "sourcegraph": "sourcegraph_no_ds",
    "sourcegraph_hybrid": "sourcegraph_no_ds",
    "deepsearch": "sourcegraph_full",
    "mcp": "sourcegraph_full",
}

# Canonical label -> human-readable display name
AGENT_DISPLAY_NAMES: dict[str, str] = {
    "baseline": "Baseline",
    "sourcegraph_no_ds": "Sourcegraph (no Deep Search)",
    "sourcegraph_full": "Sourcegraph (Full)",
}


def resolve_agent_label(dir_name: str) -> str:
    """Resolve a directory name to its canonical agent label.

    Falls back to the dir_name itself if not in the mapping.
    """
    return AGENT_LABEL_MAP.get(dir_name, dir_name)


def display_name(label: str) -> str:
    """Get human-readable display name for a canonical label or dir name.

    Resolves through the label map first, then looks up display name.
    Falls back to title-casing the input.
    """
    canonical = AGENT_LABEL_MAP.get(label, label)
    return AGENT_DISPLAY_NAMES.get(canonical, canonical.replace("_", " ").title())
