#!/usr/bin/env python3
"""DEPRECADO — não é mais um caminho de execução válido.

Use: scripts_pipeline/rodar_tudo_giro.sh

Motivo: Escopo fixo em janeiro/2026, já vencido. rodar_tudo_giro.sh cobre
jan-ago/2026 via executar_programa.py, cadeia real confirmada em
ARQUITETURA_REAL.md.

Original arquivado em .trash/2026-09-14_deprecados_orquestradores/
para referência histórica. Ver ARQUITETURA_ALVO_2026-09-14.md, seção 1.1.
"""
import sys

print(
    "\n[DEPRECADO] orquestrador_giro_jan2026.py não é mais o caminho canônico de execução.\n"
    "Use: scripts_pipeline/rodar_tudo_giro.sh\n"
    "Motivo: Escopo fixo em janeiro/2026, já vencido. rodar_tudo_giro.sh cobre "
    "jan-ago/2026 via executar_programa.py, cadeia real confirmada em "
    "ARQUITETURA_REAL.md.\n"
    "Original arquivado em .trash/2026-09-14_deprecados_orquestradores/\n"
    "Ver ARQUITETURA_ALVO_2026-09-14.md, seção 1.1.\n",
    file=sys.stderr,
)
sys.exit(1)
