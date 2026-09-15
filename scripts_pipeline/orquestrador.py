#!/usr/bin/env python3
"""DEPRECADO — não é mais um caminho de execução válido.

Use: src/orchestration/safe_runner.py (via scripts_pipeline/njud/orquestrador.sh)

Motivo: O próprio docstring deste arquivo já declarava LEGACY, apontando
safe_runner.py como ativo. Caminhos hardcoded, log fora do padrão namespaced.

Original arquivado em .trash/2026-09-14_deprecados_orquestradores/orquestrador.py
para referência histórica. Ver ARQUITETURA_ALVO_2026-09-14.md, seção 1.1.
"""
import sys

print(
    "\n[DEPRECADO] orquestrador.py não é mais o caminho canônico de execução.\n"
    "Use: src/orchestration/safe_runner.py (via scripts_pipeline/njud/orquestrador.sh)\n"
    "Motivo: O próprio docstring deste arquivo já declarava LEGACY, apontando "
    "safe_runner.py como ativo. Caminhos hardcoded, log fora do padrão namespaced.\n"
    "Original arquivado em .trash/2026-09-14_deprecados_orquestradores/\n"
    "Ver ARQUITETURA_ALVO_2026-09-14.md, seção 1.1.\n",
    file=sys.stderr,
)
sys.exit(1)
