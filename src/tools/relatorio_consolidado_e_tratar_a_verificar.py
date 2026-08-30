import csv
import json
import shutil
import re
from pathlib import Path
from datetime import datetime

BASE = Path(r"F:\Projetos\DIVISOR")
OUTPUT = BASE / "data" / "output"
A_VERIFICAR = OUTPUT / "_a_verificar"
JORNAIS_DIVIDIDOS = BASE / "data" / "processed" / "JORNAIS_DIVIDIDOS"
LOGS = OUTPUT / "_logs"
CSV_PROGRAMAS = Path(r"C:/Users/THIAGO/AppData/Local/hermes/profiles/divisor/attachments/dias_uteis_programas_projetado_do_ultimo.csv")

# Ensure log dir exists
LOGS.mkdir(parents=True, exist_ok=True)

# Load program projections
mapa_programas = {}
with open(CSV_PROGRAMAS, newline='', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        try:
            dt = datetime.strptime(row['Data_Formatada'].strip(), '%d/%m/%Y')
            proj = row['Programa_Projetado'].strip()
            if proj:
                mapa_programas[dt.strftime('%d-%m-%Y')] = int(proj)
        except Exception:
            pass

# Pattern for NJUD files
pat = re.compile(r'^NJUD_(\d+)_(\d{2}-\d{2}-\d{4})\.mp3$', re.IGNORECASE)

# Month folder mapping
MES_MAP = {
    '01': '01 - JAN - 26', '02': '02 - FEV - 26', '03': '03 - MAR - 26',
    '04': '04 - ABR - 26', '05': '05 - MAI - 26', '06': '06 - JUN - 26',
    '07': '07 - JUL - 26', '08': '08 - AGO - 26', '09': '09 - SET - 26',
    '10': '10 - OUT - 26', '11': '11 - NOV - 26', '12': '12 - DEZ - 26',
}

def destino_mes(data_str):
    dd, mm, yyyy = data_str.split('-')
    return MES_MAP.get(mm)

# Collect pending/report data from multiple production roots
production_roots = [
    JORNAIS_DIVIDIDOS,
    BASE / "data" / "processed" / "JORNAIS_DIVIDIDOS_JUN_JUL_AGO_2026",
    OUTPUT / "JORNAIS_FINAL",
    OUTPUT / "fila_refacao_quarentena",
]

pending_items = []
all_njud = []

for root in production_roots:
    if not root.exists():
        continue
    for mp3 in root.rglob("NJUD_*_*.mp3"):
        m = pat.match(mp3.name)
        if not m:
            continue
        num = int(m.group(1))
        data = m.group(2)
        esperado = mapa_programas.get(data)
        status = 'ok' if esperado and num == esperado else ('sem_csv' if not esperado else 'divergente')
        if status != 'ok':
            pending_items.append({
                'arquivo': mp3.name,
                'caminho': str(mp3),
                'data': data,
                'njud_atual': num,
                'njud_esperado': esperado,
                'status': status,
                'pasta': str(root)
            })
        all_njud.append((mp3.name, data, num, esperado, status, str(root)))

# Report for _a_verificar
a_verificar_report = []
if A_VERIFICAR.exists():
    for mp3 in sorted(A_VERIFICAR.rglob("NJUD_*_*.mp3")):
        m = pat.match(mp3.name)
        if not m:
            continue
        num = int(m.group(1))
        data = m.group(2)
        esperado = mapa_programas.get(data)
        status = 'ok' if esperado and num == esperado else ('sem_csv' if not esperado else 'divergente')
        a_verificar_report.append({
            'arquivo': mp3.name,
            'caminho': str(mp3),
            'data': data,
            'njud_atual': num,
            'njud_esperado': esperado,
            'status': status,
            'pasta': '_a_verificar'
        })

# Write consolidated report
report_path = LOGS / "relatorio_consolidado_final.csv"
with open(report_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['arquivo','caminho','data','njud_atual','njud_esperado','status','pasta'])
    writer.writeheader()
    for row in pending_items + a_verificar_report:
        writer.writerow(row)

# Summary
summary = {
    'pending_producao': len(pending_items),
    'a_verificar_total': len(a_verificar_report),
    'a_verificar_ok': sum(1 for r in a_verificar_report if r['status']=='ok'),
    'a_verificar_sem_csv': sum(1 for r in a_verificar_report if r['status']=='sem_csv'),
    'a_verificar_divergente': sum(1 for r in a_verificar_report if r['status']=='divergente'),
}
summary_path = LOGS / "relatorio_consolidado_resumo.json"
with open(summary_path, 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2)

print(f"Relatório consolidado: {report_path}")
print(f"Resumo: {summary_path}")
print(json.dumps(summary, indent=2))

# Process _a_verificar: move OK files to production folders, log others
if A_VERIFICAR.exists():
    movidos = 0
    conflitos = 0
    sem_destino = 0
    sem_csv_guardados = []
    for item in a_verificar_report:
        src = Path(item['caminho'])
        data = item['data']
        mes_destino = destino_mes(data)
        if not mes_destino:
            sem_destino += 1
            continue
        if item['status'] == 'ok':
            dst_dir = JORNAIS_DIVIDIDOS / mes_destino
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = dst_dir / src.name
            if dst.exists():
                conflitos += 1
            else:
                shutil.move(str(src), str(dst))
                movidos += 1
        elif item['status'] == 'sem_csv':
            sem_csv_guardados.append(src.name)
            # Move to sem_csv quarantine within _a_verificar
            quarentena = A_VERIFICAR / "_sem_csv"
            quarentena.mkdir(exist_ok=True)
            shutil.move(str(src), str(quarentena / src.name))
        else:
            # divergente: leave in place for manual review
            pass

    print(f"\nTratamento _a_verificar:")
    print(f"  Movidos para produção: {movidos}")
    print(f"  Conflitos: {conflitos}")
    print(f"  Sem destino: {sem_destino}")
    print(f"  Sem CSV (guardados em _a_verificar/_sem_csv): {len(sem_csv_guardados)}")
    if sem_csv_guardados:
        print("  Arquivos sem CSV:", sem_csv_guardados)
