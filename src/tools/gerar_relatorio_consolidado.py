#!/usr/bin/env python3
"""Gera relatório consolidado final e trata arquivos de _a_verificar."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import settings

ROOT = Path(settings.BASE_DIR)
OUTPUT = ROOT / "data" / "output"
A_VERIFICAR = OUTPUT / "_a_verificar"
JORNAIS_FINAL = OUTPUT / "JORNAIS_FINAL"
LOGS = OUTPUT / "_logs"
CSV_VALIDOS = Path(r"C:\Users\THIAGO\AppData\Local\hermes\profiles\divisor\attachments\dias_uteis_programas_projetado_do_ultimo.csv")
RELATORIO = LOGS / "relatorio_consolidado_final.csv"
RELATORIO_A_VERIFICAR = LOGS / "relatorio_a_verificar.csv"

import csv
import re
from datetime import datetime

PATTERN = re.compile(r"^NJUD_(\d+)_(\d{2}-\d{2}-\d{4})\.mp3$", re.IGNORECASE)


def carregar_csv():
    mapa = {}
    if not CSV_VALIDOS.exists():
        return mapa
    with open(CSV_VALIDOS, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                dt = datetime.strptime(row["Data_Formatada"].strip(), "%d/%m/%Y")
                proj = row["Programa_Projetado"].strip()
                if proj:
                    mapa[dt.strftime("%d-%m-%Y")] = int(proj)
            except ValueError:
                continue
    return mapa


def analisar_arquivo(path: Path, mapa):
    m = PATTERN.match(path.name)
    if not m:
        return path.name, None, None, None, "formato_invalido"
    num = int(m.group(1))
    data = m.group(2)
    esperado = mapa.get(data)
    status = "ok" if esperado and num == esperado else ("sem_csv" if not esperado else "divergente")
    return path.name, data, num, esperado, status


def gerar_relatorio():
    mapa = carregar_csv()
    LOGS.mkdir(parents=True, exist_ok=True)

    # JORNAIS_FINAL
    jornais = []
    if JORNAIS_FINAL.exists():
        jornais = [p for p in JORNAIS_FINAL.glob("*.mp3") if PATTERN.match(p.name)]

    pendentes = []
    for arq in jornais:
        nome, data, num, esperado, status = analisar_arquivo(arq, mapa)
        if status != "ok":
            pendentes.append((nome, data, num, esperado, status))

    with open(RELATORIO, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["arquivo", "data", "num_atual", "num_esperado", "status"])
        for nome, data, num, esperado, status in pendentes:
            writer.writerow([nome, data, num, esperado or "", status])

    # _a_verificar
    a_verificar_items = []
    if A_VERIFICAR.exists():
        a_verificar_items = [p for p in A_VERIFICAR.glob("*.mp3") if PATTERN.match(p.name)]

    a_verificar_rows = []
    for arq in a_verificar_items:
        nome, data, num, esperado, status = analisar_arquivo(arq, mapa)
        a_verificar_rows.append((nome, data, num, esperado, status))

    with open(RELATORIO_A_VERIFICAR, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["arquivo", "data", "num_atual", "num_esperado", "status"])
        for nome, data, num, esperado, status in a_verificar_rows:
            writer.writerow([nome, data, num, esperado or "", status])

    return pendentes, a_verificar_rows


def mover_para_validacao(arq: Path, destino: Path):
    destino.parent.mkdir(parents=True, exist_ok=True)
    alvo = destino / arq.name
    if alvo.exists():
        stem = arq.stem
        suffix = arq.suffix
        i = 1
        while alvo.exists():
            alvo = destino / f"{stem}_{i}{suffix}"
            i += 1
    arq.rename(alvo)
    return alvo


def tratar_a_verificar(a_verificar_rows):
    pendente_dir = OUTPUT / "_a_verificar" / "pendentes"
    ok_dir = OUTPUT / "_a_verificar" / "ok"
    pendente_dir.mkdir(parents=True, exist_ok=True)
    ok_dir.mkdir(parents=True, exist_ok=True)

    movidos = 0
    for nome, data, num, esperado, status in a_verificar_rows:
        arq = A_VERIFICAR / nome
        if status == "ok":
            mover_para_validacao(arq, ok_dir)
        else:
            mover_para_validacao(arq, pendente_dir)
        movidos += 1
    return movidos


def main():
    pendentes, a_verificar_rows = gerar_relatorio()

    print("=== JORNAIS_FINAL ===")
    print(f"Pendentes reais: {len(pendentes)}")
    for nome, data, num, esperado, status in pendentes:
        print(f"  {nome}: {status}")

    print("\n=== _a_verificar ===")
    print(f"Arquivos: {len(a_verificar_rows)}")
    if a_verificar_rows:
        movidos = tratar_a_verificar(a_verificar_rows)
        print(f"Movidos para subpastas: {movidos}")
    else:
        print("Nenhum arquivo para tratar.")

    print(f"\nRelatório consolidado: {RELATORIO}")
    print(f"Relatório _a_verificar: {RELATORIO_A_VERIFICAR}")


if __name__ == "__main__":
    main()
