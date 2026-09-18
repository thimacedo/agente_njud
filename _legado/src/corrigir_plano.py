#!/usr/bin/env python3
"""Wrapper de compatibilidade: use plan/fixer.py."""
import warnings
warnings.warn(
    "corrigir_plano.py está depreciado; migre para plan/fixer.py.",
    DeprecationWarning,
)
from plan.fixer import *  # noqa: F401,F403
