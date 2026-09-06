#!/usr/bin/env python3
"""Wrapper de compatibilidade: use plan/allocator.py."""
import warnings
warnings.warn(
    "planejador_copia.py está depreciado; migre para plan/allocator.py.",
    DeprecationWarning,
)
from plan.allocator import *  # noqa: F401,F403
