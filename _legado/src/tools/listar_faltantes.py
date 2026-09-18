#!/usr/bin/env python3
"""Diagnóstico de programas (jornais NJUD) faltantes em JORNAIS_FINAL.

A demanda é o conjunto de NJUDs únicos do plano de alocação (um jornal por
NJUD). Compara com o inventário real da pasta de saída, aceitando cobertura
tanto pela numeração oficial quanto pela antiga (mesma data).

Uso:
    python src/tools/listar_faltantes.py
Saída:
    data/output/_logs/programas_faltantes_2026.csv
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import settings  # noqa: E402

BASE = Path(settings.BASE_DIR)
DATA_DIR = BASE / "data"
PLANO_LOCAL = DATA_DIR / "plano_alocacao_local.csv"
PLANO_CANONICO = DATA_DIR / "plano_alocacao.csv"
JORNAIS_FINAL = Path(settings.JORNAIS_MONTADOS)
OUT_CSV = Path(settings.DIR_OUTPUT) / "_logs" / "programas_faltantes_2026.csv"

RE_ARQ = re.compile(r"^NJUD_(\d+)_(\d{2}-\d{2}-\d{4})(_INCOMPLETO)?\.mp3$", re.IGNORECASE)


def caminho_plano() -> Path:
    return PLANO_LOCAL if PLANO_LOCAL.exists() else PLANO_CANONICO


def carregar_demanda() -> list[dict]:
    """Um jornal por NJUD; data esperada = moda das datas dos boletins."""
    por_njud: dict[str, dict] = {}
    with open(caminho_plano(), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            njud_num = row["njud"].strip().replace("NJUD", "").strip()
            data_iso = row["data"].strip().replace("_", "-")
            item = por_njud.setdefault(njud_num, {
                "njud": njud_num, "mes": row["mes_destino"].strip(),
                "datas": Counter(),
            })
            item["datas"][data_iso] += 1
    demanda = []
    for item in por_njud.values():
        demanda.append({
            "njud": item["njud"],
            "mes": item["mes"],
            "data": item["datas"].most_common(1)[0][0],
        })
    return sorted(demanda, key=lambda x: int(x["njud"]))


def inventariar_saida() -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    por_numero: dict[str, list[dict]] = {}
    por_data: dict[str, list[dict]] = {}
    if not JORNAIS_FINAL.exists():
        return por_numero, por_data
    for arq in JORNAIS_FINAL.iterdir():
        m = RE_ARQ.match(arq.name)
        if not m:
            continue
        numero, data, incompleto = m.group(1), m.group(2), bool(m.group(3))
        info = {"arquivo": arq.name, "incompleto": incompleto}
        por_numero.setdefault(numero, []).append(info)
        por_data.setdefault(data, []).append(info)
    return por_numero, por_data


def classificar(njud: str, data: str, por_numero: dict, por_data: dict) -> str:
    oficiais = por_numero.get(njud, [])
    if oficiais:
        if any(not a["incompleto"] for a in oficiais):
            return "OK"
        return "INCOMPLETO"
    antigos = por_data.get(data, [])
    if antigos:
        if any(not a["incompleto"] for a in antigos):
            return "COBERTO_NUM_ANTIGA"
        return "INCOMPLETO_NUM_ANTIGA"
    return "FALTANTE"


def main() -> int:
    demanda = carregar_demanda()
    por_numero, por_data = inventariar_saida()

    linhas = []
    resumo: Counter = Counter()
    for item in demanda:
        status = classificar(item["njud"], item["data"], por_numero, por_data)
        resumo[status] += 1
        linhas.append({**item, "status": status})

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["njud", "data", "mes", "status"])
        writer.writeheader()
        writer.writerows(linhas)

    print(f"Demanda: {len(demanda)} jornais (plano: {caminho_plano().name})")
    print(f"Saída: {JORNAIS_FINAL}")
    print(f"Relatório: {OUT_CSV}\n")
    print("Resumo por status:")
    for status in ["FALTANTE", "INCOMPLETO", "COBERTO_NUM_ANTIGA",
                   "INCOMPLETO_NUM_ANTIGA", "OK"]:
        print(f"  {status:22s} {resumo.get(status, 0):4d}")
    print("\nPendências (faltante/incompleto) por mês:")
    por_mes = Counter(x["mes"] for x in linhas if x["status"] not in
                      ("OK", "COBERTO_NUM_ANTIGA"))
    for mes, qtd in sorted(por_mes.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {mes:10s} {qtd:4d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
