#!/usr/bin/env python3
"""Setup script for CodeContextBench."""

from setuptools import setup, find_packages

setup(
    name="codecontextbench",
    version="0.1.0",
    description="Benchmark for evaluating coding agents with Sourcegraph code intelligence",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "harbor-cli",  # Harbor framework for agent orchestration
        "toml",        # Task manifest parsing
        "pyyaml",      # Config files
        "jsonschema",  # Task specification validation
    ],
    extras_require={
        "dev": [
            "pytest",
            "black",
            "mypy",
        ],
    },
    entry_points={
        "console_scripts": [
            "ccb-run=runners.harbor_benchmark:main",
        ],
    },
)
