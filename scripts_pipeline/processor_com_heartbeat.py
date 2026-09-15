#!/usr/bin/env python3
"""DEPRECADO — não é mais um caminho de execução válido.

Use: run_dispatcher.sh (src/pipeline/dispatcher.py) + verificação manual via
'tasklist | findstr dispatcher'

Motivo: REGRAS_ORQUESTRACAO.md (YAGNI) já proibiu explicitamente contra
heartbeat system/monitor/watchdog quando 'tasklist | findstr' resolve. Este
script contraria a própria política documentada no projeto.

Original arquivado em .trash/2026-09-14_deprecados_orquestradores/
para referência histórica. Ver ARQUITETURA_ALVO_2026-09-14.md, seção 1.1.
"""
import sys

print(
    "\n[DEPRECADO] processor_com_heartbeat.py não é mais o caminho canônico de execução.\n"
    "Use: run_dispatcher.sh (src/pipeline/dispatcher.py) + verificação manual via "
    "'tasklist | findstr dispatcher'\n"
    "Motivo: REGRAS_ORQUESTRACAO.md (YAGNI) já proibiu explicitamente contra "
    "heartbeat system/monitor/watchdog quando 'tasklist | findstr' resolve. Este "
    "script contraria a própria política documentada no projeto.\n"
    "Original arquivado em .trash/2026-09-14_deprecados_orquestradores/\n"
    "Ver ARQUITETURA_ALVO_2026-09-14.md, seção 1.1.\n",
    file=sys.stderr,
)
sys.exit(1)
