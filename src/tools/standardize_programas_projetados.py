#!/usr/bin/env python3
"""Corrige números de NJUD usando dias_uteis_programas_projetado_do_ultimo.csv."""
import csv
import re
from pathlib import Path
from datetime import datetime

CSV_PATH = Path(r"C:\Users\THIAGO\AppData\Local\hermes\profiles\divisor\attachments\dias_uteis_programas_projetado_do_ultimo.csv")
ROOT = Path(r"F:/Projetos/DIVISOR")
LOG_PATH = ROOT / "logs" / "padronizacao_programas_projetados.log"
REPORT_PATH = ROOT / "logs" / "padronizacao_programas_projetados_relatorio.csv"

PASTAS_ALVO = [
    ROOT / "data" / "processed" / "JORNAIS_DIVIDIDOS",
    ROOT / "data" / "output",
    ROOT / "data" / "processed" / "JORNAIS_DIVIDIDOS_JUN_JUL_AGO_2026",
]

PATTERN = re.compile(r"^NJUD_(\d+)_(\d{2}-\d{2}-\d{4})\.mp3$", re.IGNORECASE)


def carregar_csv():
    mapa = {}
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data_str = row["Data_Formatada"].strip()
            projeto_str = row["Programa_Projetado"].strip()
            try:
                dt = datetime.strptime(data_str, "%d/%m/%Y")
                if projeto_str:
                    mapa[dt.strftime("%d-%m-%Y")] = int(projeto_str)
            except ValueError:
                continue
    return mapa


def gerar_relatorio(correcoes, sem_proj, conflitos):
    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["arquivo_original", "data", "num_atual", "num_projetado", "motivo"])
        for nome_arq, data_str, num_atual, num_projetado, motivo in correcoes:
            writer.writerow([nome_arq, data_str, num_atual, num_projetado, motivo])
        for nome_arq, data_str, num_atual, num_projetado, motivo in sem_proj:
            writer.writerow([nome_arq, data_str, num_atual, num_projetado or "", motivo])
        for nome_arq, data_str, num_atual, num_projetado, motivo in conflitos:
            writer.writerow([nome_arq, data_str, num_atual, num_projetado or "", motivo])
    print(f"Relatório CSV: {REPORT_PATH}")


def main():
    mapa = carregar_csv()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    arquivos = []
    for pasta in PASTAS_ALVO:
        if pasta.exists():
            arquivos.extend(pasta.rglob("NJUD_*_*.mp3"))

    log_file = open(LOG_PATH, "w", encoding="utf-8")
    log_file.write(f"# Padronização por Programa_Projetado - {datetime.now().isoformat()}\n")
    log_file.write(f"# CSV: {CSV_PATH}\n")
    log_file.write(f"# Pastas: {', '.join(str(p) for p in PASTAS_ALVO)}\n")
    log_file.write(f"# Total arquivos encontrados: {len(arquivos)}\n\n")

    correcoes = []
    sem_proj = []
    conflitos = []
    renomeados = 0
    ignorados = 0

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
            log_file.write(f"SEM_PROJETADO {nome} (data {data_str} sem entrada no CSV)\n")
            sem_proj.append((nome, data_str, num_atual, None, "sem entrada no CSV"))
            continue

        num_projetado = mapa[data_str]
        if num_atual == num_projetado:
            log_file.write(f"OK {nome}\n")
            continue

        novo_nome = f"NJUD_{num_projetado:04d}_{data_str}.mp3"
        novo_caminho = arq.with_name(novo_nome)

        if novo_caminho.exists():
            log_file.write(f"CONFLITO {nome} -> {novo_nome} (destino já existe)\n")
            conflitos.append((nome, data_str, num_atual, num_projetado, "destino já existe"))
            continue

        try:
            arq.rename(novo_caminho)
            log_file.write(f"RENOMEADO {nome} -> {novo_nome}\n")
            correcoes.append((nome, data_str, num_atual, num_projetado, "renomeado"))
            renomeados += 1
        except Exception as e:
            log_file.write(f"ERRO {nome} -> {e}\n")
            conflitos.append((nome, data_str, num_atual, num_projetado, str(e)))

    log_file.write(f"\n# Resumo:\n")
    log_file.write(f"# Renomeados: {renomeados}\n")
    log_file.write(f"# Ignorados (formato): {ignorados}\n")
    log_file.write(f"# Sem projeto: {len(sem_proj)}\n")
    log_file.write(f"# Conflitos: {len(conflitos)}\n")
    log_file.close()

    gerar_relatorio(correcoes, sem_proj, conflitos)

    print(f"Renomeados: {renomeados}")
    print(f"Ignorados (formato): {ignorados}")
    print(f"Sem projeto: {len(sem_proj)}")
    print(f"Conflitos: {len(conflitos)}")
    print(f"Log: {LOG_PATH}")


if __name__ == "__main__":
    main()
