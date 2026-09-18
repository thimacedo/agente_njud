#!/usr/bin/env python3
"""Wrapper de compatibilidade: use pipeline/monitor.py."""
import warnings
warnings.warn(
    "monitor_tempo_real.py está depreciado; migre para pipeline/monitor.py.",
    DeprecationWarning,
)
from pipeline.monitor import *  # noqa: F401,F403
