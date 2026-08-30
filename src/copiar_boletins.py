#!/usr/bin/env python3
"""Wrapper de compatibilidade: use sync/copy.py."""
import warnings
warnings.warn(
    "copiar_boletins.py está depreciado; migre para sync/copy.py.",
    DeprecationWarning,
)
from sync.copy import *  # noqa: F401,F403
