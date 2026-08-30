#!/usr/bin/env python3
"""Etapa 4: Tratamento de boletins sem correspondência numérica no CSV."""
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
PASTAS_ALVO = [
    BASE / "data/processed/JORNAIS_DIVIDIDOS",
    BASE / "data/output",
    BASE / "data/processed/JORNAIS_DIVIDIDOS_JUN_JUL_AGO_2026",
]
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
REPORT_SEM_NUM = LOGS / "relatorio_boletins_sem_num.csv"
LOG_SEM_NUM = LOGS / "tratamento_sem_num.log"

if not CSV_PATH.exists():
    print("CSV não encontrado.")
    sys.exit(1)

# Carregar mapeamento data -> numero
with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

data_para_num = {}
for row in rows:
    data = row["Data_Formatada"]
    num = row.get("Programa_Projetado", "")
    if data and num:
        try:
            data_para_num[data] = int(float(num))
        except:
            data_para_num[data] = None
    else:
        data_para_num[data] = None

# Padrão BOLETIM
pattern_boletim = re.compile(r"^BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_", re.IGNORECASE)

# Escanear pastas-alvo
sem_num = []
for pasta in PASTAS_ALVO:
    if not pasta.exists():
        continue
    for f in pasta.rglob("*.mp3"):
        m = pattern_boletim.match(f.name)
        if m:
            dia, mes, ano = m.groups()
            data_str = f"{dia}/{mes}/{ano}"
            num = data_para_num.get(data_str)
            if num is None:
                sem_num.append((f, data_str))

print(f"Boletins sem número no CSV: {len(sem_num)}")

# Gerar relatório
with open(REPORT_SEM_NUM, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["arquivo", "pasta", "data", "status", "observacao"])
    for path, data_str in sem_num:
        writer.writerow([
            str(path),
            str(path.parent.relative_to(BASE)),
            data_str,
            "sem_num_csv",
            "Data existe no CSV mas sem Programa_Projetado"
        ])

# Mover para pasta de arquivo morto local
archive = BASE / "data/output/_arquivo_morto_local"
archive.mkdir(parents=True, exist_ok=True)

log_lines = []
log_lines.append(f"[{datetime.now().isoformat()}] Tratamento de boletins sem número no CSV")
log_lines.append(f"Total: {len(sem_num)}")

movidos = 0
erros = 0

for path, data_str in sem_num:
    destino = archive / path.parent.relative_to(BASE) / path.name
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            ts = datetime.now().strftime('%H%M%S')
            destino = archive / path.parent.relative_to(BASE) / f"semnum_{ts}_{path.name}"
        shutil.move(str(path), str(destino))
        log_lines.append(f"MOVIDO: {path} -> {destino}")
        movidos += 1
    except Exception as e:
        log_lines.append(f"ERRO: {path} -> {e}")
        erros += 1

log_lines.append(f"Concluído: movidos={movidos}, erros={erros}")
LOG_SEM_NUM.write_text("\n".join(log_lines), encoding="utf-8")

print(f"Movidos para arquivo morto local: {movidos}")
print(f"Erros: {erros}")
print(f"Relatório: {REPORT_SEM_NUM}")
print(f"Log: {LOG_SEM_NUM}")
