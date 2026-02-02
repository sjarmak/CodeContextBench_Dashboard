"""
Benchmark-to-SDLC phase mapping.

Maps benchmark names to Software Development Life Cycle phases
from Table 2 of the CodeContextBench paper.

Functions:
    get_sdlc_phases: Map a benchmark name to its SDLC phases.
    get_benchmark_name: Extract benchmark name from a task path.
"""

from __future__ import annotations

from pathlib import PurePosixPath

# Static mapping from benchmark name patterns to SDLC phases.
# Keys are lowercase substrings matched against the benchmark name.
# Values are tuples of SDLC phases for immutability.
BENCHMARK_SDLC_MAP: dict[str, tuple[str, ...]] = {
    "kubernetes-docs": ("Documentation",),
    "ccb-kubernetes-docs": ("Documentation",),
    "pytorch-issues": ("Implementation",),
    "ccb-pytorch-issues": ("Implementation",),
    "crossrepo": ("Implementation", "Maintenance"),
    "ccb-crossrepo": ("Implementation", "Maintenance"),
    "largerepo": ("Implementation",),
    "ccb-largerepo": ("Implementation",),
    "swe-bench-pro": ("Implementation", "Testing"),
    "swe-bench": ("Implementation", "Testing"),
    "locobench": ("Implementation", "Code Review"),
    "repoqa": ("Requirements",),
    "di-bench": ("Maintenance",),
    "swe-perf": ("Implementation", "Testing"),
    "dependeval": ("Maintenance",),
    "the-agent-company": ("Multiple",),
    "tac": ("Multiple",),
    "big_code_mcp": ("Implementation",),
    "big-code": ("Implementation",),
    "github_mined": ("Implementation",),
    "tac_mcp_value": ("Multiple",),
}


def get_sdlc_phases(benchmark_name: str) -> list[str]:
    """Map a benchmark name to its SDLC phases.

    Uses fuzzy matching: checks if any known benchmark pattern
    is a substring of the provided benchmark name (case-insensitive).
    Returns matches from longest pattern first to prefer more specific matches.

    Args:
        benchmark_name: The benchmark name to look up.

    Returns:
        List of SDLC phase strings. Returns ["Unknown"] if no match found.
    """
    if not benchmark_name:
        return ["Unknown"]

    name_lower = benchmark_name.lower().strip()

    # Sort patterns by length descending so more specific patterns match first
    sorted_patterns = sorted(BENCHMARK_SDLC_MAP.keys(), key=len, reverse=True)

    for pattern in sorted_patterns:
        if pattern in name_lower:
            return list(BENCHMARK_SDLC_MAP[pattern])

    return ["Unknown"]


def get_benchmark_name(task_path: str) -> str:
    """Extract benchmark name from a task path.

    Looks for the segment immediately after "benchmarks/" in the path.
    Handles both forward and backward slashes.

    Args:
        task_path: A file path string containing a benchmarks segment,
            e.g. "benchmarks/big_code_mcp/big-code-k8s-001".

    Returns:
        The benchmark name string, or "unknown" if not found.
    """
    if not task_path:
        return "unknown"

    # Normalize to forward slashes
    normalized = task_path.replace("\\", "/")
    parts = PurePosixPath(normalized).parts

    if "benchmarks" in parts:
        idx = parts.index("benchmarks")
        if idx + 1 < len(parts):
            return parts[idx + 1]

    return "unknown"
