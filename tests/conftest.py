#!/usr/bin/env python3
"""
conftest.py — Config de testes pytest para o pipeline DIVISOR.
"""
import sys
from pathlib import Path

# Adicionar scripts_pipeline ao path para imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts_pipeline"))
sys.path.insert(0, str(PROJECT_ROOT))
