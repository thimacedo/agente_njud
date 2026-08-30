#!/usr/bin/env python3
"""Gera relatório de arquivos órfãos no Drive (presentes no Drive, ausentes em JORNAIS_FINAL)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import settings

ROOT = Path(settings.BASE_DIR)
OUTPUT = ROOT / "data" / "output"
JORNAIS_FINAL = OUTPUT / "JORNAIS_FINAL"
LOGS = OUTPUT / "_logs"
RELATORIO = LOGS / "relatorio_orfaos_drive.csv"

import re

PATTERN = re.compile(r"^NJUD_\d+_\d{2}-\d{2}-\d{4}\.mp3$", re.IGNORECASE)

DRIVE_ROOT = Path(r"H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/02_JORNAIS_NJUD/03_AUDIOS_RADIO")

if not DRIVE_ROOT.exists():
    print(f"Drive indisponível: {DRIVE_ROOT}")
    sys.exit(0)

local_names = {p.name for p in JORNAIS_FINAL.glob("*.mp3") if PATTERN.match(p.name)}
drive_files = [p for p in DRIVE_ROOT.rglob("*.mp3") if PATTERN.match(p.name)]

orfãos = []
for p in drive_files:
    nome = p.name
    if nome not in local_names:
        orfãos.append((nome, str(p.parent.relative_to(DRIVE_ROOT)), "orfao", "Presente no Drive, ausente em JORNAIS_FINAL"))

LOGS.mkdir(parents=True, exist_ok=True)
with open(RELATORIO, "w", newline="", encoding="utf-8") as f:
    import csv
    writer = csv.writer(f)
    writer.writerow(["arquivo", "pasta_drive", "status", "observacao"])
    for nome, pasta, status, obs in orfãos:
        writer.writerow([nome, pasta, status, obs])

print(f"Relatório de órfãos gerado em: {RELATORIO}")
print(f"Total órfãos: {len(orfãos)}")
