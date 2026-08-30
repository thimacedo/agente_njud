#!/usr/bin/env python3
"""Auditoria completa de duplicatas e padronização NJUD em pastas-alvo."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import hashlib
import re
import shutil
from datetime import datetime
from collections import defaultdict

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

# Patterns
PATTERN_NJUD = re.compile(r"^NJUD_(\d+)_(\d{2}-\d{2}-\d{4})\.mp3$", re.IGNORECASE)
PATTERN_BOLETIM = re.compile(r"^BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_", re.IGNORECASE)


def file_hash(path: Path, block_size: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            h.update(block)
    return h.hexdigest()


def load_csv():
    rows = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def filter_passado_presente(rows):
    result = []
    for row in rows:
        try:
            data_dt = datetime.strptime(row["Data_Formatada"], "%d/%m/%Y")
            if data_dt <= datetime(2026, 8, 29):
                result.append(row)
        except:
            continue
    return result


def build_mappings(rows):
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
            except:
                continue
    return num_para_data, data_para_num


def scan_files(pastas):
    njud_files = []
    boletim_files = []
    outros = []

    for pasta in pastas:
        if not pasta.exists():
            continue
        for f in pasta.rglob("*.mp3"):
            m_njud = PATTERN_NJUD.match(f.name)
            m_boletim = PATTERN_BOLETIM.match(f.name)
            if m_njud:
                num = int(m_njud.group(1))
                data_nome = m_njud.group(2)
                njud_files.append((f, num, data_nome))
            elif m_boletim:
                dia, mes, ano = m_boletim.groups()
                data_str = f"{dia}/{mes}/{ano}"
                boletim_files.append((f, data_str))
            else:
                outros.append(f)

    return njud_files, boletim_files, outros


def detect_duplicates_by_hash(files):
    hashes = defaultdict(list)
    for path, *_ in files:
        try:
            h = file_hash(path)
            hashes[h].append(path)
        except Exception as e:
            print(f"Erro ao hash {path}: {e}")
    
    duplicatas = []
    for h, paths in hashes.items():
        if len(paths) > 1:
            duplicatas.append((h, paths))
    return duplicatas


def main():
    print("=== AUDITORIA COMPLETA PASTAS-ALVO ===\n")

    # Load data
    rows = load_csv()
    rows_passado = filter_passado_presente(rows)
    num_para_data, data_para_num = build_mappings(rows_passado)

    print(f"Programas passado/presente: {len(rows_passado)}")

    # Scan files
    njud_files, boletim_files, outros = scan_files(PASTAS_ALVO)
    print(f"Arquivos NJUD_*: {len(njud_files)}")
    print(f"Arquivos BOLETIM_RADIO_TJRN*: {len(boletim_files)}")
    print(f"Outros: {len(outros)}\n")

    # Detect NJUD duplicates
    njud_dups = detect_duplicates_by_hash(njud_files)
    print(f"Duplicatas NJUD_*: {len(njud_dups)}")

    # Detect BOLETIM duplicates
    boletim_dups = detect_duplicates_by_hash(boletim_files)
    print(f"Duplicatas BOLETIM_RADIO_TJRN*: {len(boletim_dups)}\n")

    # Check BOLETIM -> NJUD mapping
    boletim_mapeaveis = []
    boletim_sem_data = []
    boletim_sem_num = []

    for path, data_str in boletim_files:
        num = data_para_num.get(data_str)
        if num:
            boletim_mapeaveis.append((path, data_str, num))
        else:
            if data_str == "SEM_DATA":
                boletim_sem_data.append(path)
            else:
                boletim_sem_num.append((path, data_str))

    print(f"BOLETIMs mapeáveis: {len(boletim_mapeaveis)}")
    print(f"BOLETIMs sem data: {len(boletim_sem_data)}")
    print(f"BOLETIMs sem número no CSV: {len(boletim_sem_num)}\n")

    # Check if NJUD target already exists for mapeaveis
    njud_existentes = {num for _, num, _ in njud_files}
    conflitos = []
    nao_mapeaveis = []

    for path, data_str, num in boletim_mapeaveis:
        if num in njud_existentes:
            conflitos.append((path, data_str, num))
        else:
            nao_mapeaveis.append((path, data_str, num))

    print(f"BOLETIMs prontos para renomear: {len(nao_mapeaveis)}")
    print(f"BOLETIMs com conflito (NJUD já existe): {len(conflitos)}\n")

    # Generate reports
    report_dir = LOGS
    report_dir.mkdir(parents=True, exist_ok=True)

    # Report 1: NJUD duplicates
    with open(report_dir / "relatorio_duplicatas_njud.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["hash", "arquivo1", "arquivo2", "status"])
        for h, paths in njud_dups:
            writer.writerow([h, str(paths[0]), str(paths[1]) if len(paths) > 1 else "", "duplicata"])

    # Report 2: BOLETIM duplicates
    with open(report_dir / "relatorio_duplicatas_boletim.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["hash", "arquivo1", "arquivo2", "status"])
        for h, paths in boletim_dups:
            writer.writerow([h, str(paths[0]), str(paths[1]) if len(paths) > 1 else "", "duplicata"])

    # Report 3: BOLETIM mapping analysis
    with open(report_dir / "relatorio_boletins_mapeaveis.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["arquivo", "data", "num_projetado", "status"])
        for path, data_str, num in nao_mapeaveis:
            writer.writerow([str(path), data_str, num, "pronto_renomear"])
        for path, data_str, num in conflitos:
            writer.writerow([str(path), data_str, num, "conflito_njud_existe"])

    print("Relatórios gerados:")
    print(f"  - {report_dir / 'relatorio_duplicatas_njud.csv'}")
    print(f"  - {report_dir / 'relatorio_duplicatas_boletim.csv'}")
    print(f"  - {report_dir / 'relatorio_boletins_mapeaveis.csv'}")

    # Summary
    print("\n=== RESUMO ===")
    print(f"Total NJUD_*: {len(njud_files)}")
    print(f"Total BOLETIM_RADIO_TJRN*: {len(boletim_files)}")
    print(f"Duplicatas NJUD: {len(njud_dups)}")
    print(f"Duplicatas BOLETIM: {len(boletim_dups)}")
    print(f"BOLETIMs prontos para renomear: {len(nao_mapeaveis)}")
    print(f"BOLETIMs em conflito: {len(conflitos)}")
    print(f"BOLETIMs sem número no CSV: {len(boletim_sem_num)}")


if __name__ == "__main__":
    main()
