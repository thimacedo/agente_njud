#!/usr/bin/env python3
"""Status da produção PRODUCAO_2026 — linha única máquina-legível para o monitor."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(r"F:\Projetos\DIVISOR\data\processed\PRODUCAO_2026")
ESTADO = BASE / "estado_por_arquivo"
FINAL = BASE / "JORNAIS_FINAL"
TOTAL = 552

ok = esgotado = erro = processando = 0
if ESTADO.is_dir():
    for f in ESTADO.glob("*.json"):
        try:
            st = json.loads(f.read_text(encoding="utf-8")).get("status")
        except Exception:
            continue
        if st in ("OK", "ESGOTADO_ACEITO"):
            ok += 1
        elif st == "ESGOTADO":
            esgotado += 1
        elif st in ("ERRO", "FALHA"):
            erro += 1
        else:
            processando += 1

jornais = len(list(FINAL.glob("*.mp3"))) if FINAL.is_dir() else 0

if jornais > 0:
    fase = "MONTAGEM_CONCLUIDA" if ok + esgotado >= TOTAL else "MONTAGEM_INICIOU"
elif ok + esgotado >= TOTAL:
    fase = "CORTES_CONCLUIDOS_SEM_MONTAGEM"
else:
    fase = "CORTANDO"

print(
    f"FASE={fase} cortes_ok={ok}/{TOTAL} esgotado={esgotado} "
    f"erro={erro} processando={processando} jornais_final={jornais}"
)
sys.exit(0)
