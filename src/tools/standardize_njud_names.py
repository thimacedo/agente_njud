#!/usr/bin/env python3
"""Padroniza nomes de arquivos NJUD_<NUM>_<DATA>.mp3 usando NJUDS_VALIDOS.csv."""
import csv
import re
from pathlib import Path
from datetime import datetime

CSV_PATH = Path(r"C:\Users\THIAGO\AppData\Local\hermes\profiles\divisor\attachments\NJUDS_VALIDOS.csv")
ROOT = Path(r"F:/Projetos/DIVISOR")
LOG_PATH = ROOT / "logs" / "padronizacao_njuds.log"

PATTERN = re.compile(r"^NJUD_(\d+)_(\d{2}-\d{2}-\d{4})\.mp3$", re.IGNORECASE)


def carregar_csv():
    mapa = {}
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data_str = row["Data_Formatada"].strip()
            correto = row["Correto"].strip()
            try:
                dt = datetime.strptime(data_str, "%d/%m/%Y")
                if correto:
                    mapa[dt.strftime("%d-%m-%Y")] = int(correto)
            except ValueError:
                continue
    return mapa


def processar():
    mapa = carregar_csv()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(LOG_PATH, "w", encoding="utf-8")

    arquivos = list(ROOT.rglob("NJUD_*_*.mp3"))
    log_file.write(f"# Padronização NJUD - {datetime.now().isoformat()}\n")
    log_file.write(f"# CSV: {CSV_PATH}\n")
    log_file.write(f"# Total arquivos encontrados: {len(arquivos)}\n\n")

    renomeados = 0
    ignorados = 0
    sem_csv = 0
    erros = 0

    for arq in arquivos:
        nome = arq.name
        m = PATTERN.match(nome)
        if not m:
            log_file.write(f"IGNORADO (formato) {arq}\n")
            ignorados += 1
            continue

        num_atual = int(m.group(1))
        data_str = m.group(2)

        if data_str not in mapa:
            log_file.write(f"SEM_CSV {nome} (data {data_str} não encontrada no CSV)\n")
            sem_csv += 1
            continue

        num_esperado = mapa[data_str]
        if num_atual == num_esperado:
            log_file.write(f"OK {nome}\n")
            continue

        novo_nome = f"NJUD_{num_esperado:04d}_{data_str}.mp3"
        novo_caminho = arq.with_name(novo_nome)

        try:
            if novo_caminho.exists():
                log_file.write(f"CONFLITO {nome} -> {novo_nome} (destino já existe)\n")
                erros += 1
                continue

            arq.rename(novo_caminho)
            log_file.write(f"RENOMEADO {nome} -> {novo_nome}\n")
            renomeados += 1
        except Exception as e:
            log_file.write(f"ERRO {nome} -> {e}\n")
            erros += 1

    log_file.write(f"\n# Resumo:\n")
    log_file.write(f"# Renomeados: {renomeados}\n")
    log_file.write(f"# Ignorados (formato): {ignorados}\n")
    log_file.write(f"# Sem entrada no CSV: {sem_csv}\n")
    log_file.write(f"# Erros: {erros}\n")
    log_file.close()

    print(f"Renomeados: {renomeados}")
    print(f"Ignorados (formato): {ignorados}")
    print(f"Sem entrada no CSV: {sem_csv}")
    print(f"Erros: {erros}")
    print(f"Log: {LOG_PATH}")


if __name__ == "__main__":
    processar()
