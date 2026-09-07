#!/usr/bin/env python3
"""Wrapper de compatibilidade: use audit/individual_cuts.py."""
import warnings
warnings.warn(
    "analisar_cortes_individuais.py está depreciado; migre para audit/individual_cuts.py.",
    DeprecationWarning,
)
from audit.individual_cuts import *  # noqa: F401,F403
