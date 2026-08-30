#!/usr/bin/env python3
"""Wrapper de compatibilidade: use orchestration/journal_pipeline.py."""
import warnings
warnings.warn(
    "pipeline_jornal.py está depreciado; migre para orchestration/journal_pipeline.py.",
    DeprecationWarning,
)
from orchestration.journal_pipeline import *  # noqa: F401,F403
