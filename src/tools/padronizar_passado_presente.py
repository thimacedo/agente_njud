#!/usr/bin/env python3
"""Localiza arquivos existentes nas pastas-alvo, renomeia para NJUD_<prog>_<data>.mp3 e gera relatório real."""
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

# Carregar CSV e filtrar passado/presente até 2026-08-29
with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = [r for r in reader if r.get("Data_Formatada") and r.get("Programa_Projetado")]

rows_passado = []
for row in rows:
    try:
        dt = datetime.strptime(row["Data_Formatada"], "%d/%m/%Y")
        if dt <= datetime(2026, 8, 29):
            rows_passado.append(row)
    except ValueError:
        continue

print(f"Programas passado/presente: {len(rows_passado)}")

# Mapeamentos
num_para_data = {}
data_para_num = {}
for row in rows_passado:
    data = row["Data_Formatada"]
    num = int(float(row["Programa_Projetado"]))
    num_para_data[num] = data
    data_para_num[data] = num

# Padrões de nome
PATTERN_NJUD = re.compile(r"^NJUD_(\d+)_(\d{2}-\d{2}-\d{4})\.mp3$", re.IGNORECASE)
PATTERN_BOLETIM = re.compile(r"^BOLETIM_RADIO_TJRN_\d{2}_(\d{2})_(\d{2})_(\d{4})_.*\.mp3$", re.IGNORECASE)

# Coletar arquivos existentes
arquivos_por_pasta = {}
todos_arquivos = []
for pasta in PASTAS_ALVO:
    if not pasta.exists():
        continue
    arquivos = list(pasta.rglob("*.mp3"))
    arquivos_por_pasta[pasta] = arquivos
    todos_arquivos.extend(arquivos)

print(f"Total arquivos .mp3 nas pastas-alvo: {len(todos_arquivos)}")

# Classificar
no_padrao_njud = []
no_padrao_boletim = []
outros = []

for f in todos_arquivos:
    if PATTERN_NJUD.match(f.name):
        no_padrao_njud.append(f)
    elif PATTERN_BOLETIM.match(f.name):
        no_padrao_boletim.append(f)
    else:
        outros.append(f)

print(f"Já no padrão NJUD: {len(no_padrao_njud)}")
print(f"No padrão BOLETIM_RADIO_TJRN: {len(no_padrao_boletim)}")
print(f"Outros formatos: {len(outros)}")

# Renomear BOLETIM -> NJUD usando CSV
renomeados = []
duplicatas = []
erros = []
ignorados = []

# Primeiro, marcar todos os NJUD existentes como ocupados
nomes_ocupados = {f.name for f in no_padrao_njud}

for f in no_padrao_boletim:
    m = PATTERN_BOLETIM.match(f.name)
    if not m:
        ignorados.append((f, "BOLETIM sem match"))
        continue
    
    dia, mes, ano = m.group(1), m.group(2), m.group(3)
    data_str = f"{dia}/{mes}/{ano}"
    
    # Buscar número do programa para essa data
    num_prog = data_para_num.get(data_str)
    if num_prog is None:
        ignorados.append((f, f"Data {data_str} sem programa no CSV"))
        continue
    
    novo_nome = f"NJUD_{num_prog}_{dia}-{mes}-{ano}.mp3"
    
    # Verificar duplicata
    if novo_nome in nomes_ocupados:
        duplicatas.append((f, novo_nome, "Nome já existe"))
        continue
    
    # Renomear
    destino = f.parent / novo_nome
    try:
        f.rename(destino)
        renomeados.append((f, destino))
        nomes_ocupados.add(novo_nome)
    except Exception as e:
        erros.append((f, str(e)))

print(f"\nRenomeados: {len(renomeados)}")
print(f"Duplicatas: {len(duplicatas)}")
print(f"Erros: {len(erros)}")
print(f"Ignorados: {len(ignorados)}")

# Gerar relatório
report_path = LOGS / "relatorio_padronizacao_passado_presente.csv"
with open(report_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["arquivo_origem", "arquivo_destino", "status", "observacao"])
    for orig, dest in renomeados:
        writer.writerow([orig.name, dest.name, "renomeado", ""])
    for f, nome, obs in duplicatas:
        writer.writerow([f.name, nome, "duplicata", obs])
    for f, e in erros:
        writer.writerow([f.name, "", "erro", e])
    for f, obs in ignorados:
        writer.writerow([f.name, "", "ignorado", obs])

print(f"\nRelatório: {report_path}")
print("Amostra renomeados:")
for orig, dest in renomeados[:10]:
    print(f"  {orig.name} -> {dest.name}")
