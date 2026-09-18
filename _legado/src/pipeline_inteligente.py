#!/usr/bin/env python3
"""Wrapper de compatibilidade: use orchestration/intelligent.py."""
import warnings
warnings.warn(
    "pipeline_inteligente.py está depreciado; migre para orchestration/intelligent.py.",
    DeprecationWarning,
)
from orchestration.intelligent import *  # noqa: F401,F403
