#!/usr/bin/env python3
"""Wrapper de compatibilidade: use audit/integrity_report.py."""
import warnings
warnings.warn(
    "relatorio_audit.py está depreciado; migre para audit/integrity_report.py.",
    DeprecationWarning,
)
from audit.integrity_report import *  # noqa: F401,F403
