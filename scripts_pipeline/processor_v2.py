#!/usr/bin/env python3
"""DEPRECADO — não é mais um caminho de execução válido.

Use: run_dispatcher.sh (src/pipeline/dispatcher.py)

Motivo: Versão ad-hoc anterior à v3, mesma família de script de lote único.
Não superado formalmente antes (v2 e v3 coexistiam).

Original arquivado em .trash/2026-09-14_deprecados_orquestradores/processor_v2.py
para referência histórica. Ver ARQUITETURA_ALVO_2026-09-14.md, seção 1.1.
"""
import sys

print(
    "\n[DEPRECADO] processor_v2.py não é mais o caminho canônico de execução.\n"
    "Use: run_dispatcher.sh (src/pipeline/dispatcher.py)\n"
    "Motivo: Versão ad-hoc anterior à v3, mesma família de script de lote único. "
    "Não superado formalmente antes (v2 e v3 coexistiam).\n"
    "Original arquivado em .trash/2026-09-14_deprecados_orquestradores/\n"
    "Ver ARQUITETURA_ALVO_2026-09-14.md, seção 1.1.\n",
    file=sys.stderr,
)
sys.exit(1)
