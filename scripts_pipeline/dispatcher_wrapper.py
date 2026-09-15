#!/usr/bin/env python3
"""DEPRECADO — não é mais um caminho de execução válido.

Use: run_dispatcher.sh (src/pipeline/dispatcher.py) + verificação manual via
R2 de REGRAS_ORQUESTRACAO.md

Motivo: Auto-restart em loop com heartbeat próprio, escopado a um lote histórico
(NJUD 1909-1927, 1936-1945). Mesma contradição de YAGNI do item anterior:
reinicio automático sem confirmar com o orquestrador viola R5 (subagente não
reiniciar processos sozinho).

Original arquivado em .trash/2026-09-14_deprecados_orquestradores/
para referência histórica. Ver ARQUITETURA_ALVO_2026-09-14.md, seção 1.1.
"""
import sys

print(
    "\n[DEPRECADO] dispatcher_wrapper.py não é mais o caminho canônico de execução.\n"
    "Use: run_dispatcher.sh (src/pipeline/dispatcher.py) + verificação manual via "
    "R2 de REGRAS_ORQUESTRACAO.md\n"
    "Motivo: Auto-restart em loop com heartbeat próprio, escopado a um lote histórico "
    "(NJUD 1909-1927, 1936-1945). Mesma contradição de YAGNI do item anterior: "
    "reinicio automático sem confirmar com o orquestrador viola R5 (subagente não "
    "reiniciar processos sozinho).\n"
    "Original arquivado em .trash/2026-09-14_deprecados_orquestradores/\n"
    "Ver ARQUITETURA_ALVO_2026-09-14.md, seção 1.1.\n",
    file=sys.stderr,
)
sys.exit(1)
