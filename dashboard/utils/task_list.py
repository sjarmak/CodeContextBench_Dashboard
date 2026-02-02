"""
Task list component with inline metrics, filtering, and sorting.

Provides:
- Unified task data normalization from different experiment formats
- Task metadata parsing (language, task type, difficulty from task ID)
- Multi-criteria filtering (status, language, task type, difficulty, text search)
- Configurable sorting
- Paired mode side-by-side status columns
- Row selection via Streamlit session state
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import streamlit as st

logger = logging.getLogger(__name__)

# --- Task ID parsing patterns ---

# SWE-Bench: instance_{org}__{repo}-{hash} or instance_{org}__{repo}__{hash}
SWEBENCH_PATTERN = re.compile(
    r"^instance_(?P<org>[^_]+)__(?P<repo>[^_-]+)[-_](?P<hash>.+)$",
    re.IGNORECASE,
)

# Known languages for detection
KNOWN_LANGUAGES = {
    "python", "typescript", "javascript", "go", "rust",
    "cpp", "c", "java", "csharp", "ruby", "php", "swift",
    "kotlin", "scala", "haskell", "elixir", "clojure",
}

# Known difficulty levels
KNOWN_DIFFICULTIES = {"easy", "medium", "hard", "expert", "beginner", "advanced"}


def _format_language_display(language: str) -> str:
    """Format language name for display (e.g., cpp -> C++, csharp -> C#)."""
    lang_lower = language.lower()

    # Special cases
    if lang_lower == "cpp":
        return "C++"
    elif lang_lower == "csharp":
        return "C#"
    elif lang_lower == "javascript":
        return "JavaScript"
    elif lang_lower == "typescript":
        return "TypeScript"
    elif lang_lower == "golang":
        return "Go"

    # Default: capitalize
    return language.capitalize()

# Known task categories
KNOWN_TASK_CATEGORIES = {
    "cross_file_refactoring", "architectural_understanding", "bug_investigation",
    "bugfix", "refactor", "feature", "test", "documentation", "api",
}


@dataclass(frozen=True)
class TaskMetadata:
    """Parsed metadata extracted from a task ID."""

    language: str
    task_type: str
    difficulty: str


def parse_task_metadata(task_id: str) -> TaskMetadata:
    """
    Parse language, task type, and difficulty from a task ID string.

    Supports LoCoBench format:
      {language}_{domain...}_{complexity}_{num}_{task_category...}_{difficulty}_{variant}

    Examples:
      typescript_system_monitoring_expert_061_cross_file_refactoring_expert_01
      rust_web_social_expert_073_architectural_understanding_expert_01

    Also supports SWE-Bench ID formats.

    Args:
        task_id: The task identifier string

    Returns:
        TaskMetadata with extracted or default fields
    """
    if not task_id:
        return TaskMetadata(language="Unknown", task_type="Unknown", difficulty="Unknown")

    # Try SWE-Bench pattern first
    match = SWEBENCH_PATTERN.match(task_id)
    if match:
        org = match.group("org").lower()
        repo = match.group("repo").lower()

        # Determine language based on known repos
        language = "Python"  # Default for SWE-Bench
        typescript_orgs = {"protonmail"}
        typescript_repos = {"webclients"}
        if org in typescript_orgs or repo in typescript_repos:
            language = "TypeScript"

        return TaskMetadata(
            language=language,
            task_type="SWE-Bench",
            difficulty="Unknown",
        )

    # Parse LoCoBench-style IDs by analyzing parts
    parts = task_id.lower().split("_")

    if len(parts) < 3:
        return TaskMetadata(language="Unknown", task_type="Unknown", difficulty="Unknown")

    # Extract language (first part if it's a known language)
    language = "Unknown"
    if parts[0] in KNOWN_LANGUAGES:
        language = _format_language_display(parts[0])

    # Find the 3-digit number as a pivot point
    num_index = -1
    for i, part in enumerate(parts):
        if part.isdigit() and len(part) == 3:
            num_index = i
            break

    # Extract difficulty (typically second-to-last part, should be a known difficulty)
    difficulty = "Unknown"
    if len(parts) >= 2:
        # Check second-to-last part
        if parts[-2] in KNOWN_DIFFICULTIES:
            difficulty = parts[-2].capitalize()
        # Also check the part right before the number (complexity level)
        elif num_index > 0 and parts[num_index - 1] in KNOWN_DIFFICULTIES:
            difficulty = parts[num_index - 1].capitalize()

    # Extract task type (parts between number and difficulty)
    task_type = "Unknown"
    if num_index > 0 and num_index < len(parts) - 2:
        # Task category is between number+1 and second-to-last
        task_parts = parts[num_index + 1 : -2]
        if task_parts:
            task_type = " ".join(task_parts).title()
            # Also try to match known categories
            task_category_str = "_".join(task_parts)
            if task_category_str in KNOWN_TASK_CATEGORIES:
                task_type = task_category_str.replace("_", " ").title()

    return TaskMetadata(
        language=language,
        task_type=task_type,
        difficulty=difficulty,
    )


def _compute_duration_seconds(task: dict) -> Optional[float]:
    """Compute duration in seconds from task timing fields."""
    started = task.get("started_at", "")
    finished = task.get("finished_at", "")
    if started and finished:
        try:
            from datetime import datetime

            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
            return (end_dt - start_dt).total_seconds()
        except (ValueError, TypeError):
            pass

    # Fall back to execution_time field
    exec_time = task.get("execution_time")
    if exec_time is not None and exec_time != 0:
        return float(exec_time)

    return None


def _determine_status(task: dict) -> str:
    """Determine display status from task data."""
    status = task.get("status", "unknown")
    reward = task.get("reward")

    if status == "error":
        return "error"

    if reward is not None and reward != "N/A":
        try:
            return "pass" if float(reward) > 0 else "fail"
        except (ValueError, TypeError):
            pass

    if status == "completed":
        return "pass"

    return status


def _compute_token_count(task: dict) -> Optional[int]:
    """Compute total token count from task data."""
    input_tokens = task.get("input_tokens")
    output_tokens = task.get("output_tokens")
    total_tokens = task.get("total_tokens")

    if total_tokens is not None and total_tokens != "N/A":
        try:
            return int(total_tokens)
        except (ValueError, TypeError):
            pass

    if input_tokens is not None and output_tokens is not None:
        try:
            return int(input_tokens) + int(output_tokens)
        except (ValueError, TypeError):
            pass

    return None


@dataclass(frozen=True)
class NormalizedTask:
    """Uniform task representation for display and filtering."""

    task_id: str
    status: str
    language: str
    task_type: str
    difficulty: str
    duration_seconds: Optional[float]
    token_count: Optional[int]
    reward: Optional[float]
    instance_dir: Optional[Path]
    raw: dict


def normalize_task(task: dict) -> NormalizedTask:
    """
    Normalize a task dict from any experiment format into a uniform structure.

    Handles both paired mode tasks (from _scan_paired_mode_tasks) and
    single experiment tasks (from load_external_tasks).

    Language, task_type, and difficulty are extracted from:
    1. Database fields (task_language, task_category, task_difficulty) if present
    2. Fallback to parsing from task_id pattern
    """
    task_id = task.get("task_name", task.get("task_id", "unknown"))

    # First try to get metadata from database fields
    db_language = task.get("task_language")
    db_category = task.get("task_category")
    db_difficulty = task.get("task_difficulty")

    # Use database values if present and not "unknown", otherwise parse from task_id
    if db_language and db_language.lower() != "unknown":
        language = _format_language_display(db_language)
    else:
        parsed = parse_task_metadata(task_id)
        language = parsed.language

    if db_category and db_category.lower() != "unknown":
        task_type = db_category.replace("_", " ").title()
    else:
        parsed = parse_task_metadata(task_id)
        task_type = parsed.task_type

    if db_difficulty and db_difficulty.lower() != "unknown":
        difficulty = db_difficulty.capitalize()
    else:
        parsed = parse_task_metadata(task_id)
        difficulty = parsed.difficulty

    reward_val = task.get("reward")
    reward_float: Optional[float] = None
    if reward_val is not None and reward_val != "N/A":
        try:
            reward_float = float(reward_val)
        except (ValueError, TypeError):
            pass

    instance_dir = task.get("instance_dir")
    if instance_dir is not None and not isinstance(instance_dir, Path):
        instance_dir = Path(instance_dir)

    return NormalizedTask(
        task_id=task_id,
        status=_determine_status(task),
        language=language,
        task_type=task_type,
        difficulty=difficulty,
        duration_seconds=_compute_duration_seconds(task),
        token_count=_compute_token_count(task),
        reward=reward_float,
        instance_dir=instance_dir,
        raw=task,
    )


def normalize_tasks(tasks: list[dict]) -> list[NormalizedTask]:
    """Normalize a list of task dicts into uniform NormalizedTask list."""
    return [normalize_task(t) for t in tasks]


# --- Filtering ---


@dataclass(frozen=True)
class TaskFilter:
    """Filter criteria for task list."""

    statuses: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    task_types: tuple[str, ...] = ()
    difficulty: str = ""
    search_text: str = ""


def filter_tasks(
    tasks: list[NormalizedTask], task_filter: TaskFilter
) -> list[NormalizedTask]:
    """
    Apply filter criteria to a list of normalized tasks.

    All active filters are combined with AND logic.
    """
    filtered = list(tasks)

    if task_filter.statuses:
        filtered = [t for t in filtered if t.status in task_filter.statuses]

    if task_filter.languages:
        filtered = [t for t in filtered if t.language in task_filter.languages]

    if task_filter.task_types:
        filtered = [t for t in filtered if t.task_type in task_filter.task_types]

    if task_filter.difficulty:
        filtered = [
            t for t in filtered if t.difficulty == task_filter.difficulty
        ]

    if task_filter.search_text:
        search_lower = task_filter.search_text.lower()
        filtered = [
            t for t in filtered if search_lower in t.task_id.lower()
        ]

    return filtered


# --- Sorting ---

SORT_OPTIONS = {
    "Name": lambda t: t.task_id.lower(),
    "Duration": lambda t: t.duration_seconds if t.duration_seconds is not None else float("inf"),
    "Token Count": lambda t: t.token_count if t.token_count is not None else float("inf"),
    "Reward": lambda t: t.reward if t.reward is not None else -1.0,
    "Status": lambda t: t.status,
}


def sort_tasks(
    tasks: list[NormalizedTask],
    sort_key: str,
    descending: bool = False,
) -> list[NormalizedTask]:
    """Sort normalized tasks by the given key."""
    key_func = SORT_OPTIONS.get(sort_key, SORT_OPTIONS["Name"])
    return sorted(tasks, key=key_func, reverse=descending)


# --- Unique values extraction ---


def _unique_values(
    tasks: list[NormalizedTask], attr: str
) -> list[str]:
    """Extract sorted unique values for a given attribute."""
    values = sorted({getattr(t, attr) for t in tasks})
    return values


# --- Status badge ---

_STATUS_BADGES = {
    "pass": "Pass",
    "fail": "Fail",
    "error": "Error",
}


def _status_badge(status: str) -> str:
    return _STATUS_BADGES.get(status, status)


# --- Format helpers ---


def _format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


def _format_tokens(count: Optional[int]) -> str:
    if count is None:
        return "N/A"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


def _format_reward(reward: Optional[float]) -> str:
    if reward is None:
        return "N/A"
    return f"{reward:.4f}"


# --- Streamlit rendering ---


def _render_filter_sidebar(
    tasks: list[NormalizedTask],
    key_prefix: str,
) -> TaskFilter:
    """Render filter sidebar controls and return the current filter state."""
    statuses = _unique_values(tasks, "status")
    languages = _unique_values(tasks, "language")
    task_types = _unique_values(tasks, "task_type")
    difficulties = _unique_values(tasks, "difficulty")

    selected_statuses = st.multiselect(
        "Status",
        statuses,
        key=f"{key_prefix}_status_filter",
    )

    selected_languages = st.multiselect(
        "Language",
        languages,
        key=f"{key_prefix}_language_filter",
    )

    selected_task_types = st.multiselect(
        "Task Type",
        task_types,
        key=f"{key_prefix}_task_type_filter",
    )

    selected_difficulty = st.selectbox(
        "Difficulty",
        [""] + difficulties,
        format_func=lambda d: "All" if d == "" else d,
        key=f"{key_prefix}_difficulty_filter",
    )

    search_text = st.text_input(
        "Search by task ID",
        key=f"{key_prefix}_search",
    )

    return TaskFilter(
        statuses=tuple(selected_statuses),
        languages=tuple(selected_languages),
        task_types=tuple(selected_task_types),
        difficulty=selected_difficulty or "",
        search_text=search_text,
    )


def _render_sort_controls(key_prefix: str) -> tuple[str, bool]:
    """Render sort controls and return (sort_key, descending)."""
    col1, col2 = st.columns([3, 1])

    with col1:
        sort_key = st.selectbox(
            "Sort by",
            list(SORT_OPTIONS.keys()),
            key=f"{key_prefix}_sort_key",
        )

    with col2:
        descending = st.checkbox(
            "Desc",
            value=True,
            key=f"{key_prefix}_sort_desc",
        )

    return sort_key or "Name", descending


def _shorten_task_id(task_id: str) -> str:
    """Shorten a task ID for table display.

    SWE-bench IDs like 'instance_ansible__ansible-4c5ce5a1...' become 'ansible/ansible'.
    Other IDs are truncated to 40 chars.
    """
    match = SWEBENCH_PATTERN.match(task_id)
    if match:
        return f"{match.group('org')}/{match.group('repo')}"
    if len(task_id) > 40:
        return task_id[:40]
    return task_id


def _build_table_rows(tasks: list[NormalizedTask]) -> list[dict]:
    """Build display table rows from normalized tasks."""
    return [
        {
            "Task": _shorten_task_id(t.task_id),
            "Status": _status_badge(t.status),
            "Lang": t.language,
            "Duration": _format_duration(t.duration_seconds),
            "Tokens": _format_tokens(t.token_count),
            "Reward": _format_reward(t.reward),
        }
        for t in tasks
    ]


def _build_paired_table_rows(
    baseline_tasks: list[NormalizedTask],
    variant_tasks: list[NormalizedTask],
) -> list[dict]:
    """
    Build paired comparison table rows with side-by-side status columns.

    Matches tasks by task_id between baseline and variant lists.
    """
    baseline_map = {t.task_id: t for t in baseline_tasks}
    variant_map = {t.task_id: t for t in variant_tasks}

    all_ids = sorted(set(baseline_map.keys()) | set(variant_map.keys()))

    rows: list[dict] = []
    for task_id in all_ids:
        b_task = baseline_map.get(task_id)
        v_task = variant_map.get(task_id)

        rows.append(
            {
                "Task": _shorten_task_id(task_id),
                "Base": _status_badge(b_task.status) if b_task else "N/A",
                "Var": _status_badge(v_task.status) if v_task else "N/A",
                "B Reward": _format_reward(b_task.reward) if b_task else "N/A",
                "V Reward": _format_reward(v_task.reward) if v_task else "N/A",
                "Lang": (b_task or v_task).language if (b_task or v_task) else "N/A",
            }
        )

    return rows


def render_task_list(
    tasks: list[dict],
    key_prefix: str = "task_list",
    paired_variant_tasks: Optional[list[dict]] = None,
) -> Optional[str]:
    """
    Render a full task list component with filters, sorting, and selection.

    Args:
        tasks: List of task dicts (baseline or single experiment)
        key_prefix: Unique key prefix for Streamlit widget state
        paired_variant_tasks: If provided, renders paired comparison mode
            with side-by-side columns for baseline (tasks) and variant

    Returns:
        The selected task_id, or None if no selection
    """
    normalized = normalize_tasks(tasks)

    if paired_variant_tasks is not None:
        normalized_variant = normalize_tasks(paired_variant_tasks)
    else:
        normalized_variant = None

    # All tasks for filter options (combine both if paired)
    all_for_filters = list(normalized)
    if normalized_variant:
        all_for_filters = [*all_for_filters, *normalized_variant]

    if not all_for_filters:
        st.info("No tasks found.")
        return None

    # --- Layout: sidebar filters + main content ---
    filter_col, main_col = st.columns([1, 3])

    with filter_col:
        st.markdown("**Filters**")
        task_filter = _render_filter_sidebar(all_for_filters, key_prefix)

    with main_col:
        # Sort controls
        sort_key, descending = _render_sort_controls(key_prefix)

        # Apply filters
        filtered = filter_tasks(normalized, task_filter)
        if normalized_variant is not None:
            filtered_variant = filter_tasks(normalized_variant, task_filter)
        else:
            filtered_variant = None

        # Apply sort
        filtered = sort_tasks(filtered, sort_key, descending)
        if filtered_variant is not None:
            filtered_variant = sort_tasks(filtered_variant, sort_key, descending)

        # Result count
        total_count = len(normalized)
        shown_count = len(filtered)
        st.caption(f"Showing {shown_count} of {total_count} tasks")

        # Render table
        if filtered_variant is not None:
            table_rows = _build_paired_table_rows(filtered, filtered_variant)
        else:
            table_rows = _build_table_rows(filtered)

        if table_rows:
            # Match table height to filter sidebar (~400px) so they align
            st.dataframe(table_rows, use_container_width=True, hide_index=True, height=400)
        else:
            st.info("No tasks match the current filters.")

        # Task selection
        task_ids = [t.task_id for t in filtered]
        if task_ids:
            selected_task_id = st.selectbox(
                "Select task for details",
                task_ids,
                key=f"{key_prefix}_task_select",
            )
            if selected_task_id:
                st.session_state["selected_task_id"] = selected_task_id
                return selected_task_id

    return None
