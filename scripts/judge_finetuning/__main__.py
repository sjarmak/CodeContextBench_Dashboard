"""Entry point for running generate_preferences as a module.

Usage: python -m scripts.judge_finetuning.generate_preferences [args]
"""

from __future__ import annotations

import sys

from scripts.judge_finetuning.generate_preferences import main

sys.exit(main())
