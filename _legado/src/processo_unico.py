#!/usr/bin/env python3
"""Wrapper de compatibilidade: use pipeline/single_process.py."""
import warnings
warnings.warn(
    "processo_unico.py está depreciado; migre para pipeline/single_process.py.",
    DeprecationWarning,
)
from pipeline.single_process import *  # noqa: F401,F403
