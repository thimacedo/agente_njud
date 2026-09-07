#!/usr/bin/env python3
"""Wrapper de compatibilidade: use orchestration/safe_runner.py."""
import warnings
warnings.warn(
    "run_pipeline_safe_v2.py está depreciado; migre para orchestration/safe_runner.py.",
    DeprecationWarning,
)
from orchestration.safe_runner import *  # noqa: F401,F403
