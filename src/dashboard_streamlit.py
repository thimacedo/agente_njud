#!/usr/bin/env python3
"""
Dashboard mínimo do pipeline DIVISOR.

Mostra, em tempo real, o estado dos arquivos a partir de
data/processed/JORNAIS_DIVIDIDOS/estado_por_arquivo/*.json.

Uso:
    streamlit run src/dashboard_streamlit.py
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="DIVISOR — Pipeline", layout="wide")
st.title("DIVISOR — Dashboard do Pipeline")

PASTA_ESTADO = Path("F:/Projetos/DIVISOR/data/processed/JORNAIS_DIVIDIDOS/estado_por_arquivo")


@st.cache_data(ttl=10)
def carregar_estado() -> list[dict]:
    if not PASTA_ESTADO.is_dir():
        return []
    registros = []
    for p in PASTA_ESTADO.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        registros.append({
            "arquivo": d.get("arquivo", p.stem),
            "njud": d.get("njud", "?"),
            "status": d.get("status", "PENDENTE"),
            "estrategia": d.get("estrategia", ""),
            "tentativas": d.get("tentativas", 0),
            "erro": d.get("erro", ""),
        })
    return registros


registros = carregar_estado()

if not registros:
    st.warning("Nenhum estado encontrado em:\n\n" + str(PASTA_ESTADO))
    st.stop()

status_counts: dict[str, int] = {}
for r in registros:
    status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

ok = sum(qtd for status, qtd in status_counts.items() if status in ("OK", "ESGOTADO_ACEITO"))
pendentes = status_counts.get("PENDENTE", 0)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total", len(registros))
with col2:
    st.metric("Concluídos", ok)
with col3:
    st.metric("Pendentes", pendentes)

st.subheader("Distribuição por status")
st.bar_chart(status_counts)

st.subheader("Por NJUD")
njud_summary: dict[str, dict[str, int]] = {}
for r in registros:
    njud = r["njud"]
    njud_summary.setdefault(njud, {})
    njud_summary[njud][r["status"]] = njud_summary[njud].get(r["status"], 0) + 1

linhas = []
for njud, counts in sorted(njud_summary.items()):
    linha = {"njud": njud, **counts}
    linhas.append(linha)

if linhas:
    st.dataframe(linhas, use_container_width=True)

st.subheader("Arquivos em erro")
erros = [r for r in registros if r["status"] == "ERRO"]
if not erros:
    st.success("Sem ERROs no momento.")
else:
    st.dataframe(
        [
            {
                "arquivo": r["arquivo"],
                "njud": r["njud"],
                "estrategia": r["estrategia"],
                "erro": r["erro"],
            }
            for r in erros
        ],
        use_container_width=True,
    )
