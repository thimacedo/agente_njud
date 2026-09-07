#!/usr/bin/env python3
"""Teste de regressão: imports dos módulos canônicos."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

# Módulos canônicos
CANONICOS = [
    "divisor_boletins.audio",
    "divisor_boletins.deteccao",
    "divisor_boletins.calibracao",
    "divisor_boletins.montagem",
    "divisor_boletins.config",
    "divisor_boletins.log",
    "divisor_boletins.texto",
    "divisor_boletins.cli",
    "pipeline.single_process",
    "pipeline.dispatcher",
    "pipeline.monitor",
    "audit.individual_cuts",
    "audit.integrity",
    "audit.integrity_report",
    "audit.summaries",
    "sync.drive",
    "sync.copy",
    "plan.generator",
    "plan.allocator",
    "plan.fixer",
    "orchestration.safe_runner",
    "orchestration.intelligent",
    "orchestration.journal_pipeline",
    "config.settings",
    "utils.logger",
    "utils.validator",
    "utils.error_handler",
]

falhas = []
for mod in CANONICOS:
    try:
        __import__(mod)
        print(f"OK {mod}")
    except Exception as e:
        falhas.append((mod, str(e)))
        print(f"FAIL {mod}: {e}")

if falhas:
    print(f"\nFALHAS: {len(falhas)}")
    sys.exit(1)

print("\nTodos imports OK")
