#!/usr/bin/env python3
"""Wrapper de compatibilidade: use sync/drive.py."""
import warnings
warnings.warn(
    "sincronizar_drive.py está depreciado; migre para sync/drive.py.",
    DeprecationWarning,
)
from sync.drive import *  # noqa: F401,F403
