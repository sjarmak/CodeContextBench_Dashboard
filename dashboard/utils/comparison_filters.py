"""
Comparison filter functions for cross-config task data.

Provides pure-function filters that return new dicts without modifying
input data (immutable pattern). Supports filtering by benchmark,
category, difficulty, size bucket, error severity, and search strategy.
"""

from typing import Optional, Sequence


def _get_size_bucket(task: dict) -> Optional[str]:
    """Classify a task into a size bucket based on input_tokens.

    Buckets:
        small  – < 300_000 tokens
        medium – 300_000 .. 1_000_000 tokens
        large  – > 1_000_000 tokens

    Falls back to None when no token data is available.
    """
    tokens = task.get("input_tokens")
    if tokens is None:
        return None
    if tokens < 300_000:
        return "small"
    if tokens <= 1_000_000:
        return "medium"
    return "large"


def _matches(value: Optional[str], allowed: Optional[Sequence[str]]) -> bool:
    """Return True when *value* passes a multi-value OR filter.

    If *allowed* is None or empty the filter is inactive (everything passes).
    """
    if not allowed:
        return True
    return value in allowed


def _get_error_severity(task: dict) -> Optional[str]:
    """Extract error severity from a task's error_fingerprint field.

    error_fingerprint is a dict with keys: fingerprint_id, label, severity.
    Returns None when there is no error.
    """
    fp = task.get("error_fingerprint")
    if not fp or not isinstance(fp, dict):
        return None
    return fp.get("severity")


def _get_search_strategy_type(task: dict) -> Optional[str]:
    """Extract or infer search_strategy_type from task metrics.

    If the field exists directly, use it. Otherwise infer from
    search call counts (keyword, nls, deepsearch).
    """
    direct = task.get("search_strategy_type")
    if direct is not None:
        return direct

    keyword = task.get("search_calls_keyword") or 0
    nls = task.get("search_calls_nls") or 0
    deepsearch = task.get("search_calls_deepsearch") or 0
    total = keyword + nls + deepsearch

    if total == 0:
        return None

    if deepsearch > 0 and keyword == 0 and nls == 0:
        return "deepsearch_heavy"
    if deepsearch == 0 and keyword > 0 and nls == 0:
        return "keyword_only"
    if deepsearch == 0 and nls > 0:
        return "nls_focused"
    return "mixed"


def filter_comparison_tasks(
    tasks: dict[str, dict[str, Optional[dict]]],
    *,
    benchmark: Optional[Sequence[str]] = None,
    category: Optional[Sequence[str]] = None,
    difficulty: Optional[Sequence[str]] = None,
    sdlc_phase: Optional[Sequence[str]] = None,
    size_bucket: Optional[str] = None,
    error_severity: Optional[Sequence[str]] = None,
    search_strategy_type: Optional[Sequence[str]] = None,
) -> dict[str, dict[str, Optional[dict]]]:
    """Filter comparison task data across multiple dimensions.

    All filter parameters are optional — ``None`` means no filter on that
    dimension.  Filters are combined with AND across dimensions and OR
    within multi-value dimensions.

    Args:
        tasks: Comparison dict ``{task_id: {config: metrics_or_None}}``.
        benchmark: Allowed benchmark names (OR).
        category: Allowed category values (OR).
        difficulty: Allowed difficulty values (OR).
        sdlc_phase: Allowed SDLC phase values (OR).
        size_bucket: Single size bucket — ``"small"``, ``"medium"``, or
            ``"large"``.
        error_severity: Allowed error severity values (OR).
        search_strategy_type: Allowed strategy types (OR).

    Returns:
        A **new** dict containing only the tasks that pass all active
        filters.  The input ``tasks`` dict is never mutated.
    """
    # Fast path — no filters active
    if all(
        f is None
        for f in (benchmark, category, difficulty, sdlc_phase, size_bucket,
                  error_severity, search_strategy_type)
    ):
        return tasks

    filtered: dict[str, dict[str, Optional[dict]]] = {}

    for task_id, configs in tasks.items():
        # We need at least one non-None config to evaluate filter fields.
        # Pick the first available metrics dict.
        representative: Optional[dict] = None
        for cfg_metrics in configs.values():
            if cfg_metrics is not None:
                representative = cfg_metrics
                break

        if representative is None:
            # No data at all — skip this task
            continue

        # Apply each dimension filter (AND across dimensions)
        if not _matches(representative.get("benchmark"), benchmark):
            continue
        if not _matches(representative.get("category"), category):
            continue
        if not _matches(representative.get("difficulty"), difficulty):
            continue
        if not _matches(representative.get("sdlc_phase"), sdlc_phase):
            continue

        # Size bucket filter
        if size_bucket is not None:
            task_bucket = _get_size_bucket(representative)
            if task_bucket != size_bucket:
                continue

        # Error severity filter — check across ALL configs
        if error_severity is not None:
            has_matching_severity = False
            for cfg_metrics in configs.values():
                if cfg_metrics is not None:
                    sev = _get_error_severity(cfg_metrics)
                    # Include "no_error" pseudo-value for tasks without errors
                    effective = sev if sev is not None else "no_error"
                    if effective in error_severity:
                        has_matching_severity = True
                        break
            if not has_matching_severity:
                continue

        # Search strategy filter — check across ALL configs
        if search_strategy_type is not None:
            has_matching_strategy = False
            for cfg_metrics in configs.values():
                if cfg_metrics is not None:
                    strategy = _get_search_strategy_type(cfg_metrics)
                    if strategy is not None and strategy in search_strategy_type:
                        has_matching_strategy = True
                        break
            if not has_matching_strategy:
                continue

        filtered[task_id] = configs

    return filtered
