#!/usr/bin/env python3
"""
Corrigir Plano — TJRN
=======================

Corrige dois problemas confirmados em plano_alocacao.csv:
  1. mes_destino divergente do mês oficial do NJUD (fonte: njuds_por_mes.csv)
  2. Ano errado no nome do arquivo de áudio (ex: 2027/2028 onde deveria ser 2026)

Rede de segurança:
  - --dry-run por padrão
  - --apply renomeia arquivos físicos no Drive e reescreve o CSV
  - Log de auditoria em _logs_correcao/
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

from config.settings import settings

PLANO_CSV = Path(settings.BOLETINS_CORTADOS).parent / "plano_alocacao.csv"
NJUDS_POR_MES_CSV = Path(settings.BOLETINS_CORTADOS).parent / "njuds_por_mes.csv"
LOG_DIR = Path(settings.LOGS_DIR) / "correcoes"

ANO_CORRETO = "2026"

ABBR_POR_EXTENSO = {
    "JAN": "JANEIRO", "FEV": "FEVEREIRO", "MAR": "MARÇO", "ABR": "ABRIL",
    "MAI": "MAIO", "JUN": "JUNHO", "JUL": "JULHO", "AGO": "AGOSTO",
    "SET": "SETEMBRO", "OUT": "OUTUBRO", "NOV": "NOVEMBRO", "DEZ": "DEZEMBRO",
}


def normalizar_njud(valor: str) -> str:
    return valor.strip().replace("NJUD ", "").replace("NJUD_", "")


def carregar_mapa_njud_mes_oficial(caminho: Path) -> dict[str, str]:
    mapa = {}
    with open(caminho, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            abbr = row["mes"].split("-")[1].strip()
            mes_extenso = ABBR_POR_EXTENSO.get(abbr)
            if not mes_extenso:
                continue
            for njud in row["njuds"].split(";"):
                mapa[normalizar_njud(njud)] = mes_extenso
    return mapa


_PADRAO_ANO_NO_NOME = re.compile(r"_(20\d{2})_")


def corrigir_ano_no_texto(texto: str) -> tuple[str, bool]:
    def _sub(m):
        return f"_{ANO_CORRETO}_"
    novo = _PADRAO_ANO_NO_NOME.sub(_sub, texto)
    return novo, novo != texto


def analisar_plano(linhas: list[dict], mapa_oficial: dict[str, str]) -> list[dict]:
    correcoes = []
    for i, row in enumerate(linhas):
        mudancas = {}
        mes_oficial = mapa_oficial.get(row["njud"])
        if mes_oficial and mes_oficial != row["mes_destino"]:
            mudancas["mes_destino"] = (row["mes_destino"], mes_oficial)
        arquivo_corrigido, mudou_arquivo = corrigir_ano_no_texto(row["arquivo"])
        if mudou_arquivo:
            mudancas["arquivo"] = (row["arquivo"], arquivo_corrigido)
        data_corrigida, mudou_data = corrigir_ano_no_texto(row["data"])
        if mudou_data:
            mudancas["data"] = (row["data"], data_corrigida)
        if mudancas:
            correcoes.append({"indice": i, "row": row, "mudancas": mudancas})
    return correcoes


def aplicar_correcoes(
    linhas: list[dict], correcoes: list[dict], aplicar: bool
) -> tuple[list[dict], list[str]]:
    erros = []
    registro_log = []
    log_dir = LOG_DIR
    if aplicar:
        log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"correcao_{ts}.csv"

    for c in correcoes:
        row = c["row"]
        mudancas = c["mudancas"]
        if "arquivo" in mudancas:
            nome_antigo, nome_novo = mudancas["arquivo"]
            origem = Path(row["src"]) / nome_antigo
            destino = Path(row["src"]) / nome_novo
            # REGRA DE OPERAÇÃO: NENHUM processo pode escrever/renomear no
            # Drive H: (decisão do operador, 2026-08-24). Correções de nome
            # são registradas no log; o arquivo físico não é tocado.
            if str(origem).lower().startswith("h:"):
                erros.append(
                    f"NJUD {row['njud']}: renomeação no Drive bloqueada por política "
                    f"(somente leitura): {origem}"
                )
            elif not origem.exists():
                if not destino.exists():
                    erros.append(f"NJUD {row['njud']}: origem não encontrada: {origem}")
                    continue
            elif aplicar:
                origem.rename(destino)
            registro_log.append({
                "njud": row["njud"], "campo": "arquivo",
                "antes": nome_antigo, "depois": nome_novo,
            })
            row["arquivo"] = nome_novo
        if "data" in mudancas:
            antes, depois = mudancas["data"]
            registro_log.append({
                "njud": row["njud"], "campo": "data",
                "antes": antes, "depois": depois,
            })
            row["data"] = depois
        if "mes_destino" in mudancas:
            antes, depois = mudancas["mes_destino"]
            registro_log.append({
                "njud": row["njud"], "campo": "mes_destino",
                "antes": antes, "depois": depois,
            })
            row["mes_destino"] = depois

    if aplicar and registro_log:
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["njud", "campo", "antes", "depois"])
            writer.writeheader()
            writer.writerows(registro_log)
        print(f"\n✔ Log de correções gravado em: {log_path}")
    return linhas, erros


def main():
    parser = argparse.ArgumentParser(description="Corrige mes_destino e ano errado em plano_alocacao.csv.")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--dry-run", action="store_true", default=True,
                        help="Só mostra as correções propostas (padrão)")
    grupo.add_argument("--apply", action="store_true",
                        help="Aplica de fato: renomeia arquivos físicos e reescreve o CSV")
    args = parser.parse_args()
    aplicar = args.apply

    if not PLANO_CSV.exists():
        print(f"✖ Plano não encontrado: {PLANO_CSV}", file=sys.stderr)
        sys.exit(1)

    with open(PLANO_CSV, newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    campos = list(linhas[0].keys()) if linhas else []

    mapa_oficial = carregar_mapa_njud_mes_oficial(NJUDS_POR_MES_CSV)
    correcoes = analisar_plano(linhas, mapa_oficial)

    if not correcoes:
        print("Nenhuma correção necessária — plano já está consistente.")
        return

    print(f"{len(correcoes)} linha(s) do plano precisam de correção:\n")
    for c in correcoes:
        row = c["row"]
        print(f"  NJUD {row['njud']} — {row['arquivo']}")
        for campo, (antes, depois) in c["mudancas"].items():
            print(f"      {campo}: '{antes}' -> '{depois}'")

    linhas_corrigidas, erros = aplicar_correcoes(linhas, correcoes, aplicar)

    if erros:
        print(f"\n⚠ {len(erros)} erro(s) durante a correção (linhas puladas):")
        for e in erros:
            print(f"    {e}")

    if not aplicar:
        print("\nModo dry-run: nada foi alterado. Rode com --apply para executar de fato.")
        return

    with open(PLANO_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas_corrigidas)
    print(f"\n✔ {PLANO_CSV} reescrito com as correções.")
    print("\nPróximo passo: rode copiar_boletins.py --dry-run para conferir.")


if __name__ == "__main__":
    main()
