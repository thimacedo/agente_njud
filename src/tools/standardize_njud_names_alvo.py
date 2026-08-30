#!/usr/bin/env python3
"""Gera relatório CSV de conflitos/sem-CSV e repete padronização só em pastas-alvo."""
import csv
import re
from pathlib import Path
from datetime import datetime

CSV_PATH = Path(r"C:\Users\THIAGO\AppData\Local\hermes\profiles\divisor\attachments\NJUDS_VALIDOS.csv")
ROOT = Path(r"F:/Projetos/DIVISOR")
LOG_PATH = ROOT / "logs" / "padronizacao_njuds_pastas_alvo.log"
REPORT_PATH = ROOT / "logs" / "padronizacao_njuds_relatorio.csv"

PASTAS_ALVO = [
    ROOT / "data" / "processed" / "JORNAIS_DIVIDIDOS",
    ROOT / "data" / "output",
    ROOT / "data" / "processed" / "JORNAIS_DIVIDIDOS_JUN_JUL_AGO_2026",
]

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


def gerar_relatorio_csv(conflitos, sem_csv):
    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["arquivo_original", "data", "num_atual", "num_esperado", "motivo"])
        for nome_arq, data_str, num_atual, num_esperado, motivo in conflitos:
            writer.writerow([nome_arq, data_str, num_atual, num_esperado or "", motivo])
        for nome_arq, data_str, num_atual, num_esperado, motivo in sem_csv:
            writer.writerow([nome_arq, data_str, num_atual, num_esperado or "", motivo])
    print(f"Relatório CSV: {REPORT_PATH}")


def processar():
    mapa = carregar_csv()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(LOG_PATH, "w", encoding="utf-8")

    arquivos = []
    for pasta in PASTAS_ALVO:
        if pasta.exists():
            arquivos.extend(pasta.rglob("NJUD_*_*.mp3"))

    log_file.write(f"# Padronização NJUD (pastas-alvo) - {datetime.now().isoformat()}\n")
    log_file.write(f"# CSV: {CSV_PATH}\n")
    log_file.write(f"# Pastas: {', '.join(str(p) for p in PASTAS_ALVO)}\n")
    log_file.write(f"# Total arquivos encontrados: {len(arquivos)}\n\n")

    conflitos = []
    sem_csv = []
    renomeados = 0
    ignorados = 0
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
            sem_csv.append((nome, data_str, num_atual, None, "sem entrada no CSV"))
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
                conflitos.append((nome, data_str, num_atual, num_esperado, "destino já existe"))
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
    log_file.write(f"# Sem entrada no CSV: {len(sem_csv)}\n")
    log_file.write(f"# Conflitos: {len(conflitos)}\n")
    log_file.write(f"# Erros: {erros}\n")
    log_file.close()

    gerar_relatorio_csv(conflitos, sem_csv)

    print(f"Renomeados: {renomeados}")
    print(f"Ignorados (formato): {ignorados}")
    print(f"Sem entrada no CSV: {len(sem_csv)}")
    print(f"Conflitos: {len(conflitos)}")
    print(f"Erros: {erros}")
    print(f"Log: {LOG_PATH}")


if __name__ == "__main__":
    processar()
