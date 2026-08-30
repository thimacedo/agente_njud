#!/usr/bin/env python3
"""Etapa 3: Trata conflitos renomeando boletins cujo NJUD já existe, usando datas livres no CSV."""
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

CSV_PATH = BASE / "dias_uteis_programas_projetado_do_ultimo.csv"
LOGS = BASE / "logs"
REPORT = LOGS / "relatorio_boletins_mapeaveis.csv"
OUTPUT = BASE / "data/output"
OUTPUT.mkdir(parents=True, exist_ok=True)
LOG_CONFLITO = LOGS / "resolucao_conflitos.log"

if not CSV_PATH.exists() or not REPORT.exists():
    print("CSV ou relatório de mapeáveis não encontrado.")
    sys.exit(1)

# Carregar CSV completo
with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Mapear todas as datas úteis para número
todas_datas = []
num_para_data = {}
data_para_num = {}
for row in rows:
    data = row["Data_Formatada"]
    num = row.get("Programa_Projetado", "")
    if data and num:
        try:
            n = int(float(num))
            num_para_data[n] = data
            data_para_num[data] = n
            todas_datas.append(data)
        except:
            continue

# Carregar conflitos
conflitos = []
with open(REPORT, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get("status") == "conflito_njud_existe":
            conflitos.append(row)

print(f"Conflitos para tratar: {len(conflitos)}")

log_lines = []
log_lines.append(f"[{datetime.now().isoformat()}] Iniciando resolução de conflitos")
log_lines.append(f"Total conflitos: {len(conflitos)}")

resolvidos = 0
erros = 0
ignorados = 0

for row in conflitos:
    arquivo_origem = Path(row.get("arquivo", ""))
    data_str = row.get("data", "")
    num = row.get("num_projetado", "")

    if not arquivo_origem.exists() or not data_str or not num:
        log_lines.append(f"IGNORADO: dados incompletos")
        ignorados += 1
        continue

    try:
        num_int = int(float(num))
        idx = todas_datas.index(data_str) if data_str in todas_datas else -1
        if idx == -1:
            log_lines.append(f"IGNORADO (data não encontrada no CSV): {arquivo_origem}")
            ignorados += 1
            continue

        # Procurar próxima data livre
        livre_encontrada = False
        for offset in range(1, len(todas_datas) - idx):
            cand_data = todas_datas[idx + offset]
            cand_num = data_para_num.get(cand_data)
            if cand_num is None:
                continue
            cand_nome = f"NJUD_{cand_num}_{cand_data.replace('/', '-')}.mp3"
            cand_path = OUTPUT / cand_nome
            if not cand_path.exists():
                shutil.copy2(arquivo_origem, cand_path)
                log_lines.append(f"CONFLITO_RESOLVIDO: {arquivo_origem.name} -> {cand_nome}")
                resolvidos += 1
                livre_encontrada = True
                break

        if not livre_encontrada:
            log_lines.append(f"ERRO_CONFLITO_TOTAL: {arquivo_origem.name}")
            erros += 1
    except Exception as e:
        log_lines.append(f"ERRO: {arquivo_origem.name} -> {e}")
        erros += 1

log_lines.append(f"Concluído: resolvidos={resolvidos}, erros={erros}, ignorados={ignorados}")
LOG_CONFLITO.write_text("\n".join(log_lines), encoding="utf-8")
print(f"\nResolvidos: {resolvidos}")
print(f"Erros: {erros}")
print(f"Ignorados: {ignorados}")
print(f"Log: {LOG_CONFLITO}")
