#!/usr/bin/env python3
"""Wrapper de compatibilidade: use plan/generator.py."""
import warnings
warnings.warn(
    "gerar_plano.py está depreciado; migre para plan/generator.py.",
    DeprecationWarning,
)
from plan.generator import *  # noqa: F401,F403
