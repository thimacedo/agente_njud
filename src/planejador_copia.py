#!/usr/bin/env python3
"""
Planejador de cópias em JSON + workspace temporário.

Gera um plano JSON com os arquivos que serão usados pelo pipeline,
copia apenas esses arquivos para uma pasta temporária e permite
limpar automaticamente ao final para não ocupar o HD.

Uso:
    python planejador_copia.py --plan data/plano_alocacao.csv --out-plan data/plano_copia.json
    python planejador_copia.py --exec-plan data/plano_copia.json --workspace data/workspace_temp
    python planejador_copia.py --cleanup --workspace data/workspace_temp
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import csv

DEST_ROOT = Path(r"F:\Projetos\DIVISOR\JORNAIS")
PLAN_CSV = Path(r"F:\Projetos\DIVISOR\data\plano_alocacao.csv")
REPORT_CSV = Path(r"F:\Projetos\DIVISOR\data\alocacao_boletins.csv")
NJUDS_POR_MES_CSV = Path(r"F:\Projetos\DIVISOR\data\njuds_por_mes.csv")

CAMPOS_OBRIGATORIOS = ["mes_destino", "njud", "arquivo", "data", "boletim",
                        "retranca", "entidade", "bloqueado", "src"]
ANO_ESPERADO = "2026"
ABBR_POR_EXTENSO = {
    "JAN": "JANEIRO", "FEV": "FEVEREIRO", "MAR": "MARÇO", "ABR": "ABRIL",
    "MAI": "MAIO", "JUN": "JUNHO", "JUL": "JULHO", "AGO": "AGOSTO",
    "SET": "SETEMBRO", "OUT": "OUTUBRO", "NOV": "NOVEMBRO", "DEZ": "DEZEMBRO",
}


def normalizar_njud(valor: str) -> str:
    return valor.strip().replace("NJUD ", "").replace("NJUD_", "")


def carregar_linhas_plano(caminho_csv: Path) -> list[dict]:
    if not caminho_csv.exists():
        print(f"✖ Plano não encontrado: {caminho_csv}", file=sys.stderr)
        sys.exit(1)
    with open(caminho_csv, newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    if not linhas:
        print(f"✖ Plano vazio: {caminho_csv}", file=sys.stderr)
        sys.exit(1)
    faltando = set(CAMPOS_OBRIGATORIOS) - set(linhas[0].keys())
    if faltando:
        print(f"✖ Plano sem as colunas obrigatórias: {sorted(faltando)}", file=sys.stderr)
        sys.exit(1)
    return linhas


def validar_plano(linhas: list[dict], permitir_mes_divergente: bool = False) -> list[dict]:
    erros = []
    for i, row in enumerate(linhas, start=2):
        m = re.match(r"BOLETIM_RADIO_TJRN_\d{2}_(\d{2})_\d{4}_B\d+_", row.get("arquivo", ""))
        if m:
            mes_nome = {"01": "JANEIRO", "02": "FEVEREIRO", "03": "MARÇO", "04": "ABRIL",
                        "05": "MAIO", "06": "JUNHO", "07": "JULHO", "08": "AGOSTO",
                        "09": "SETEMBRO", "10": "OUTUBRO", "11": "NOVEMBRO", "12": "DEZEMBRO"}.get(m.group(1))
            if mes_nome and mes_nome != row["mes_destino"]:
                if permitir_mes_divergente:
                    arquivo_nome = row["arquivo"]
                    print(
                        "    [AVISO-FALLBACK] linha "
                        + str(i)
                        + ": '"
                        + arquivo_nome
                        + "' (mês "
                        + m.group(1)
                        + ") alocada em "
                        + row["mes_destino"]
                        + " — fallback autorizado."
                    )
                else:
                    arquivo_nome = row["arquivo"]
                    erros.append(
                        "linha "
                        + str(i)
                        + ": arquivo '"
                        + arquivo_nome
                        + "' tem mês "
                        + m.group(1)
                        + " no nome mas mes_destino='"
                        + row["mes_destino"]
                        + "'"
                    )

        m = re.search(r"_(\d{4})_", row.get("arquivo", ""))
        if m and m.group(1) != ANO_ESPERADO:
            erros.append(
                f"linha {i}: arquivo '{row['arquivo']}' tem ano '{m.group(1)}', "
                f"esperado '{ANO_ESPERADO}'"
            )

        if not row.get("arquivo", "").strip():
            erros.append(f"linha {i}: 'arquivo' vazio")
            continue
        if not row.get("src", "").strip():
            erros.append(f"linha {i}: 'src' vazio")
            continue
        caminho_origem = Path(row["src"]) / row["arquivo"]
        if not caminho_origem.exists():
            erros.append(f"linha {i}: origem não existe: {caminho_origem}")

    if erros:
        print(f"✖ Plano com {len(erros)} problema(s):", file=sys.stderr)
        for e in erros[:30]:
            print(f"    {e}", file=sys.stderr)
        if len(erros) > 30:
            print(f"    ... e mais {len(erros) - 30}", file=sys.stderr)
        sys.exit(1)

    print(f"✔ Plano válido: {len(linhas)} linha(s).")
    return linhas


def gerar_plano_json(linhas: list[dict], saida: Path, permitir_mes_divergente: bool = False) -> Path:
    validar_plano(linhas, permitir_mes_divergente=permitir_mes_divergente)
    plano = {
        "gerado_em": datetime.now().isoformat(),
        "total": len(linhas),
        "entradas": [],
    }
    for row in linhas:
        src = Path(row["src"]) / row["arquivo"]
        destino_relativo = Path(row["mes_destino"]) / row["njud"] / row["arquivo"]
        plano["entradas"].append({
            "arquivo": row["arquivo"],
            "src": str(src),
            "destino_relativo": str(destino_relativo),
            "mes_destino": row["mes_destino"],
            "njud": row["njud"],
            "data": row.get("data", ""),
            "boletim": row.get("boletim", ""),
            "retranca": row.get("retranca", ""),
            "entidade": row.get("entidade", ""),
            "bloqueado": row.get("bloqueado", ""),
        })
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(plano, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✔ Plano JSON gravado em: {saida}")
    return saida


def copiar_para_workspace(plano_json: Path, workspace: Path, dry_run: bool = True) -> Path:
    plano = json.loads(plano_json.read_text(encoding="utf-8"))
    workspace.mkdir(parents=True, exist_ok=True)
    registros = []
    for item in plano.get("entradas", []):
        src = Path(item["src"])
        dest = workspace / item["destino_relativo"]
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        registros.append({
            "arquivo": item["arquivo"],
            "src": str(src),
            "workspace": str(dest),
            "njud": item["njud"],
            "mes_destino": item["mes_destino"],
        })
    manifest = workspace / "manifest.json"
    manifest.write_text(
        json.dumps({"plano": str(plano_json), "entradas": registros}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"{'[dry-run]' if dry_run else '[apply]'} workspace={workspace} itens={len(registros)}")
    return manifest


def limpar_workspace(workspace: Path, confirmar: bool = True) -> None:
    if not workspace.exists():
        print(f"✖ Workspace não existe: {workspace}")
        return
    manifest = workspace / "manifest.json"
    if not manifest.exists():
        print(f"✖ Manifest não encontrado em {workspace}; limpeza abortada.")
        return
    if confirmar:
        resp = input(f"Apagar workspace temporário '{workspace}'? [s/N]: ").strip().lower()
        if resp != "s":
            print("Limpeza cancelada.")
            return
    shutil.rmtree(workspace, ignore_errors=True)
    print(f"✔ Workspace removido: {workspace}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Planejador JSON + workspace temporário para cópias seletivas.")
    parser.add_argument("--plan", type=str, default=str(PLAN_CSV), help="Caminho do plano CSV")
    parser.add_argument("--out-plan", type=str, default=str(Path("data/plano_copia.json")), help="Saída do plano JSON")
    parser.add_argument("--exec-plan", type=str, default=None, help="Executa cópias a partir de um plano JSON")
    parser.add_argument("--workspace", type=str, default=str(Path("data/workspace_temp")), help="Workspace temporário")
    parser.add_argument("--apply", action="store_true", help="Copia de fato para o workspace")
    parser.add_argument("--cleanup", action="store_true", help="Remove o workspace temporário")
    parser.add_argument("--no-confirm", action="store_true", help="Limpeza sem confirmação")
    parser.add_argument("--permitir-mes-divergente", action="store_true", help="Aceita fallback de mês")
    args = parser.parse_args()

    if args.cleanup:
        limpar_workspace(Path(args.workspace), confirmar=not args.no_confirm)
        return

    if args.exec_plan:
        copiar_para_workspace(Path(args.exec_plan), Path(args.workspace), dry_run=not args.apply)
        return

    plan_path = Path(args.plan)
    linhas = carregar_linhas_plano(plan_path)
    saida = Path(args.out_plan)
    gerar_plano_json(linhas, saida, permitir_mes_divergente=args.permitir_mes_divergente)


if __name__ == "__main__":
    main()
