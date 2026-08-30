#!/usr/bin/env python3
"""Move arquivos órfãos do Drive para uma pasta de arquivo morto local."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from config.settings import Settings
    settings = Settings()
    DRIVE_ROOT = Path(r"H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/02_JORNAIS_NJUD/03_AUDIOS_RADIO")
except Exception:
    DRIVE_ROOT = Path(r"H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/02_JORNAIS_NJUD/03_AUDIOS_RADIO")

import csv
import shutil
from datetime import datetime

RELATORIO = Path("F:/Projetos/DIVISOR/data/output/_logs/relatorio_orfaos_drive.csv")
PASTA_ARQUIVO_MORTO = DRIVE_ROOT / "_arquivo_morto"
LOG_ARQUIVO_MORTO = Path("F:/Projetos/DIVISOR/logs/mover_orfaos_drive.log")

if not DRIVE_ROOT.exists():
    print(f"Drive indisponível: {DRIVE_ROOT}")
    sys.exit(0)

if not RELATORIO.exists():
    print(f"Relatório de órfãos não encontrado: {RELATORIO}")
    sys.exit(1)

PASTA_ARQUIVO_MORTO.mkdir(parents=True, exist_ok=True)
LOG_ARQUIVO_MORTO.parent.mkdir(parents=True, exist_ok=True)

linhas = []
with open(RELATORIO, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        linhas.append(row)

movidos = 0
erros = 0
ignorados = 0
log = []

log.append(f"[{datetime.now().isoformat()}] Iniciando movimentação de órfãos para arquivo morto")
log.append(f"Relatório: {RELATORIO}")
log.append(f"Destino: {PASTA_ARQUIVO_MORTO}")
log.append("")

for row in linhas:
    arquivo = row.get("arquivo")
    pasta_drive = row.get("pasta_drive")
    if not arquivo or not pasta_drive:
        ignorados += 1
        continue

    origem = DRIVE_ROOT / pasta_drive / arquivo
    if not origem.exists():
        log.append(f"IGNORADO (origem não existe): {origem}")
        ignorados += 1
        continue

    destino = PASTA_ARQUIVO_MORTO / pasta_drive / arquivo
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            destino = PASTA_ARQUIVO_MORTO / pasta_drive / f"duplicado_{datetime.now().strftime('%H%M%S')}_{arquivo}"
        shutil.move(str(origem), str(destino))
        log.append(f"MOVIDO: {origem} -> {destino}")
        movidos += 1
    except Exception as e:
        log.append(f"ERRO: {origem} -> {e}")
        erros += 1

log.append("")
log.append(f"Concluído: movidos={movidos}, erros={erros}, ignorados={ignorados}")

LOG_ARQUIVO_MORTO.write_text("\n".join(log), encoding="utf-8")
print("\n".join(log[-5:]))
print(f"\nLog completo em: {LOG_ARQUIVO_MORTO}")
print(f"Arquivo morto: {PASTA_ARQUIVO_MORTO}")
