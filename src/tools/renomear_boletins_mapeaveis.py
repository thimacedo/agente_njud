#!/usr/bin/env python3
"""Etapa 2: Renomeação de boletins mapeáveis sem conflito para NJUD_<num>_<data>.mp3."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import re
import shutil
from datetime import datetime

try:
    from config.settings import Settings
    settings = Settings()
    BASE = Path(settings.BASE_DIR)
except Exception:
    BASE = Path("F:/Projetos/DIVISOR")

LOGS = BASE / "logs"
REPORT = LOGS / "relatorio_boletins_mapeaveis.csv"
OUTPUT = BASE / "data/output"
OUTPUT.mkdir(parents=True, exist_ok=True)
LOG_RENAME = LOGS / "renomeacao_boletins.log"


def main():
    print("=== ETAPA 2: RENOMEAÇÃO DE BOLETINS MAPEÁVEIS ===\n")
    LOG_RENAME.parent.mkdir(parents=True, exist_ok=True)
    log_lines = []
    log_lines.append(f"[{datetime.now().isoformat()}] Iniciando renomeação de boletins")

    if not REPORT.exists():
        print(f"Relatório não encontrado: {REPORT}")
        sys.exit(1)

    rows = []
    with open(REPORT, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    # Filtrar apenas pronto_renomear
    alvos = [r for r in rows if r.get("status") == "pronto_renomear"]
    print(f"Boletins prontos para renomear: {len(alvos)}")

    renomeados = 0
    erros = 0
    ignorados = 0

    for row in alvos:
        arquivo_origem = Path(row.get("arquivo", ""))
        data_str = row.get("data", "")
        num = row.get("num_projetado", "")

        if not arquivo_origem.exists() or not data_str or not num:
            log_lines.append(f"IGNORADO: {arquivo_origem} (dados incompletos)")
            ignorados += 1
            continue

        try:
            num_int = int(float(num))
            data_nome = data_str.replace("/", "-")
            nome_novo = f"NJUD_{num_int}_{data_nome}.mp3"
            destino = OUTPUT / nome_novo

            # Copiar para destino
            shutil.copy2(arquivo_origem, destino)
            log_lines.append(f"RENOMEADO: {arquivo_origem.name} -> {nome_novo}")
            renomeados += 1
        except Exception as e:
            log_lines.append(f"ERRO: {arquivo_origem} -> {e}")
            erros += 1

    log_lines.append(f"Concluído: renomeados={renomeados}, erros={erros}, ignorados={ignorados}")
    LOG_RENAME.write_text("\n".join(log_lines), encoding="utf-8")
    print(f"\nRenomeados: {renomeados}")
    print(f"Erros: {erros}")
    print(f"Ignorados: {ignorados}")
    print(f"Log: {LOG_RENAME}")


if __name__ == "__main__":
    main()
