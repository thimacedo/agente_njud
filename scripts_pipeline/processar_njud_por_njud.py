#!/usr/bin/env python3
"""DEPRECADO — não é mais um caminho de execução válido.

Use: run_dispatcher.sh (src/pipeline/dispatcher.py)

Motivo: Script ad-hoc de um lote específico (JORNAIS/ALVO), caminhos E:
hardcoded. Mesma responsabilidade do dispatcher.py, sem o estado persistido
dele.

Original arquivado em .trash/2026-09-14_deprecados_orquestradores/
para referência histórica. Ver ARQUITETURA_ALVO_2026-09-14.md, seção 1.1.
"""
import sys

print(
    "\n[DEPRECADO] processar_njud_por_njud.py não é mais o caminho canônico de execução.\n"
    "Use: run_dispatcher.sh (src/pipeline/dispatcher.py)\n"
    "Motivo: Script ad-hoc de um lote específico (JORNAIS/ALVO), caminhos E: "
    "hardcoded. Mesma responsabilidade do dispatcher.py, sem o estado persistido "
    "dele.\n"
    "Original arquivado em .trash/2026-09-14_deprecados_orquestradores/\n"
    "Ver ARQUITETURA_ALVO_2026-09-14.md, seção 1.1.\n",
    file=sys.stderr,
)
sys.exit(1)
