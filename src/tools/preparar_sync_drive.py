#!/usr/bin/env python3
"""Localiza jornais montados e copia para JORNAIS_FINAL, depois sincroniza com Drive."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import settings

ROOT = Path(settings.BASE_DIR)
OUTPUT = ROOT / "data" / "output"
JORNAIS_FINAL = OUTPUT / "JORNAIS_FINAL"
LOGS = OUTPUT / "_logs"

import shutil
import re

PATTERN = re.compile(r"^NJUD_\d+_\d{2}-\d{2}-\d{4}\.mp3$", re.IGNORECASE)

# Pastas que podem conter jornais montados
PASTAS_ORIGEM = [
    ROOT / "data" / "processed" / "JORNAIS_DIVIDIDOS" / "JORNAIS_FINAL",
    ROOT / "data" / "processed" / "JORNAIS_DIVIDIDOS_JUN_JUL_AGO_2026",
    ROOT / "data" / "output" / "fila_refacao_quarentena",
    ROOT / "data" / "output",
]

JORNAIS_FINAL.mkdir(parents=True, exist_ok=True)

copiados = 0
ignorados = 0
for pasta in PASTAS_ORIGEM:
    if not pasta.exists():
        continue
    for f in pasta.rglob("*.mp3"):
        if not PATTERN.match(f.name):
            ignorados += 1
            continue
        dst = JORNAIS_FINAL / f.name
        if not dst.exists():
            shutil.copy2(f, dst)
            copiados += 1

print(f"Copiados para JORNAIS_FINAL: {copiados}")
print(f"Ignorados (nome fora do padrão): {ignorados}")

total_final = sum(1 for _ in JORNAIS_FINAL.glob("*.mp3"))
print(f"Total em JORNAIS_FINAL: {total_final}")
