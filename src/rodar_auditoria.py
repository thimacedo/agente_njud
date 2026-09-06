#!/usr/bin/env python3
"""Wrapper de compatibilidade: use audit/integrity.py."""
import warnings
warnings.warn(
    "rodar_auditoria.py está depreciado; migre para audit/integrity.py.",
    DeprecationWarning,
)
from audit.integrity import *  # noqa: F401,F403
