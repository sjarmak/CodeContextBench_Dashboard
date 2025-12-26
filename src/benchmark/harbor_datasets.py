"""
Utility functions for working with Harbor pre-installed datasets.
"""
from typing import List, Optional
import streamlit as st
from datasets import load_dataset


# Cache dataset instance lists to avoid reloading
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_harbor_dataset_instances(dataset_name: str) -> List[str]:
    """
    Get list of instance IDs for a Harbor dataset.

    Args:
        dataset_name: Harbor dataset name (e.g., "swe_bench_verified")

    Returns:
        List of instance IDs
    """
    # Map Harbor dataset names to HuggingFace dataset paths
    dataset_mapping = {
        "swe-bench-verified@1.0": "princeton-nlp/SWE-bench_Verified",
        "swebench_verified": "princeton-nlp/SWE-bench_Verified",  # Old alias
        "swe_bench_verified": "princeton-nlp/SWE-bench_Verified",  # Old alias
        "swebench_lite": "princeton-nlp/SWE-bench_Lite",
        "swe_bench_lite": "princeton-nlp/SWE-bench_Lite",
        # Add more datasets as needed
    }

    hf_dataset_path = dataset_mapping.get(dataset_name)

    if not hf_dataset_path:
        raise ValueError(f"Unknown Harbor dataset: {dataset_name}")

    try:
        # Load dataset from HuggingFace
        ds = load_dataset(hf_dataset_path, split='test')

        # Extract instance IDs
        instance_ids = [item["instance_id"] for item in ds]

        return sorted(instance_ids)

    except Exception as e:
        raise RuntimeError(f"Failed to load dataset {dataset_name}: {e}")


def get_dataset_info(dataset_name: str) -> dict:
    """
    Get metadata about a Harbor dataset.

    Args:
        dataset_name: Harbor dataset name

    Returns:
        Dictionary with dataset metadata
    """
    info = {
        "swe_bench_verified": {
            "full_name": "SWE-bench Verified",
            "description": "500 validated GitHub issues requiring code modifications",
            "languages": ["Python"],
            "difficulty": "Hard",
            "avg_time_minutes": 20,
        },
        "swe_bench_lite": {
            "full_name": "SWE-bench Lite",
            "description": "300 lite GitHub issues for faster evaluation",
            "languages": ["Python"],
            "difficulty": "Medium-Hard",
            "avg_time_minutes": 15,
        },
    }

    return info.get(dataset_name, {})
