#!/usr/bin/env python3
"""Auditoria e redistribuição de programas passado/presente até 2026-08-29."""
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

if not CSV_PATH.exists():
    print(f"CSV não encontrado: {CSV_PATH}")
    sys.exit(1)

# Carregar CSV
with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Filtrar passado/presente até 2026-08-29
rows_passado = []
for row in rows:
    data_str = row.get("Data_Formatada", "")
    try:
        data_dt = datetime.strptime(data_str, "%d/%m/%Y")
        if data_dt <= datetime(2026, 8, 29):
            rows_passado.append(row)
    except ValueError:
        continue

print(f"Total programas passado/presente: {len(rows_passado)}")

# Mapeamentos
num_para_data = {}
data_para_num = {}
for row in rows_passado:
    data = row["Data_Formatada"]
    num = row.get("Programa_Projetado", "")
    if data and num:
        try:
            num_int = int(float(num))
            num_para_data[num_int] = data
            data_para_num[data] = num_int
        except ValueError:
            continue

# Padrão de nome canônico
PATTERN = re.compile(r"^NJUD_(\d+)_(\d{2}-\d{2}-\d{4})\.mp3$", re.IGNORECASE)

# Mapear arquivos existentes nas pastas-alvo
existentes_por_num = {}
existentes_por_data = {}
todos_existentes = set()

for pasta in PASTAS_ALVO:
    if not pasta.exists():
        continue
    for f in pasta.glob("*.mp3"):
        m = PATTERN.match(f.name)
        if m:
            num = int(m.group(1))
            data_nome = m.group(2)
            existentes_por_num[num] = f
            existentes_por_data[data_nome] = f
            todos_existentes.add(f.name)

# Identificar duplicatas e faltantes
duplicatas = []
faltantes = []

for num, data in num_para_data.items():
    nome_esperado = f"NJUD_{num}_{data.replace('/', '-')}.mp3"
    if nome_esperado in todos_existentes:
        # Verificar se há duplicata
        count = sum(1 for n in todos_existentes if n == nome_esperado)
        if count > 1:
            duplicatas.append((num, data, nome_esperado))
    else:
        faltantes.append((num, data, nome_esperado))

print(f"Arquivos esperados: {len(num_para_data)}")
print(f"Existentes no padrão: {len(todos_existentes)}")
print(f"Duplicatas: {len(duplicatas)}")
print(f"Faltantes: {len(faltantes)}")

# Gerar relatório
report_path = LOGS / "relatorio_passado_presente.csv"
with open(report_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["num_programa", "data", "nome_esperado", "status"])
    for num, data, nome in faltantes[:20]:
        writer.writerow([num, data, nome, "faltante"])
    for num, data, nome in duplicatas[:20]:
        writer.writerow([num, data, nome, "duplicata"])

print(f"Relatório: {report_path}")
print(f"Faltantes (amostra): {len(faltantes)}")
for num, data, nome in faltantes[:5]:
    print(f"  {data} -> {nome}")
