#!/usr/bin/env python3
"""Wrapper de compatibilidade: use pipeline/dispatcher.py."""
import warnings
warnings.warn(
    "dispatcher_paralelo.py está depreciado; migre para pipeline/dispatcher.py.",
    DeprecationWarning,
)
from pipeline.dispatcher import *  # noqa: F401,F403
