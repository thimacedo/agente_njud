#!/usr/bin/env python3
"""Wrapper de compatibilidade: use audit/summaries.py."""
import warnings
warnings.warn(
    "resumo_metodos.py está depreciado; migre para audit/summaries.py.",
    DeprecationWarning,
)
from audit.summaries import *  # noqa: F401,F403
