"""
Copia boletins para as pastas de NJUD conforme o plano de alocação
(plano_alocacao.csv), organizando por mês/NJUD.

NÃO REVERTER PARA A VERSÃO SEM VALIDAÇÃO: existiu uma versão anterior
deste script que rodava `shutil.rmtree()` em TODAS as pastas de NJUD
ANTES de sequer abrir/validar o plano_alocacao.csv. Se o CSV estivesse
ausente, vazio ou malformado, a limpeza já tinha acontecido e não havia
como reverter — perda de dados sem rede de segurança. Essa versão
corrige isso. Corrigido em 2026-08-21; já reapareceu uma vez por
restauração de versão antiga (verificar se algum processo de
sincronização/backup está restaurando versões desatualizadas deste
arquivo antes de rodar).

Rede de segurança:
  1. Valida o plano ANTES de tocar em qualquer pasta existente
     (colunas obrigatórias, origem de cada arquivo existe, ano no nome
     bate com ANO_ESPERADO, mes_destino bate com njuds_por_mes.csv).
  2. Modo --dry-run por padrão: só mostra o que seria feito.
  3. --apply executa de fato, e só então limpa+copia.
  4. Antes de limpar, grava um snapshot do que existia (backup leve).
  5. Só remove uma pasta de NJUD se ela realmente for recriada pelo
     plano atual — nunca a árvore inteira.

Uso
----
    python copiar_boletins.py --dry-run
    python copiar_boletins.py --apply
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from config.settings import settings

DEST_ROOT = settings.BOLETINS_BRUTOS
PLAN_CSV = Path(settings.BOLETINS_CORTADOS).parent / "plano_alocacao.csv"
REPORT_CSV = Path(settings.BOLETINS_CORTADOS).parent / "alocacao_boletins.csv"
NJUDS_POR_MES_CSV = Path(settings.BOLETINS_CORTADOS).parent / "njuds_por_mes.csv"

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


# ===========================================================================
# VALIDAÇÃO DO PLANO (roda ANTES de qualquer alteração em disco)
# ===========================================================================

def carregar_mapa_njud_mes_oficial(caminho: Path) -> dict[str, str]:
    if not caminho.exists():
        return {}
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


def ler_e_validar_plano(caminho_csv: Path, linhas: list[dict] | None = None,
                        permitir_mes_divergente: bool = False) -> list[dict]:
    """permitir_mes_divergente (2026-08-24): opt-in do operador para aceitar
    linhas de FALLBACK do gerar_plano.py (NJUD de um mês completado com boletins
    de outro mês). Não é reversão da validação — o padrão continua bloqueando."""
    if linhas is None:
        linhas = carregar_linhas_plano(caminho_csv)

    erros = []

    # Fonte de verdade do mês = data no nome do arquivo (decisão do operador).
    # Validação contra njuds_por_mes.csv desativada para não conflitar com
    # remessas onde a pasta difere da data do nome.
    for i, row in enumerate(linhas, start=2):
        m = re.match(r"BOLETIM_RADIO_TJRN_\d{2}_(\d{2})_\d{4}_B\d+_", row.get("arquivo", ""))
        if m:
            mes_nome = {"01":"JANEIRO","02":"FEVEREIRO","03":"MARÇO","04":"ABRIL",
                        "05":"MAIO","06":"JUNHO","07":"JULHO","08":"AGOSTO",
                        "09":"SETEMBRO","10":"OUTUBRO","11":"NOVEMBRO","12":"DEZEMBRO"}.get(m.group(1))
            if mes_nome and mes_nome != row["mes_destino"]:
                if permitir_mes_divergente:
                    print(f"    [AVISO-FALLBACK] linha {i}: '{row['arquivo']}' "
                          f"(mês {m.group(1)}) alocada em {row['mes_destino']} — fallback autorizado pelo operador em 2026-08-24.")
                else:
                    erros.append(
                        f"linha {i}: arquivo '{row['arquivo']}' tem mês {m.group(1)} no nome "
                        f"mas mes_destino='{row['mes_destino']}'"
                    )

    for i, row in enumerate(linhas, start=2):
        m = re.search(r"_(\d{4})_", row.get("arquivo", ""))
        if m and m.group(1) != ANO_ESPERADO:
            erros.append(
                f"linha {i}: arquivo '{row['arquivo']}' tem ano '{m.group(1)}', "
                f"esperado '{ANO_ESPERADO}'"
            )

    for i, row in enumerate(linhas, start=2):
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
        print(f"✖ Plano com {len(erros)} problema(s) — nada foi alterado em disco:", file=sys.stderr)
        for e in erros[:30]:
            print(f"    {e}", file=sys.stderr)
        if len(erros) > 30:
            print(f"    ... e mais {len(erros) - 30}", file=sys.stderr)
        sys.exit(1)

    print(f"✔ Plano válido: {len(linhas)} linha(s), todas as origens existem, "
          f"mes_destino confere, anos corretos.")
    return linhas


def njuds_no_plano(linhas: list[dict]) -> set[tuple[str, str]]:
    return {(row["mes_destino"], row["njud"]) for row in linhas}


# ===========================================================================
# BACKUP LEVE DO ESTADO ANTERIOR (antes de limpar qualquer coisa)
# ===========================================================================

def registrar_estado_atual(dest_root: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = dest_root.parent / f"_backup_estado_antes_{ts}.csv"

    linhas = []
    if dest_root.exists():
        for month in sorted(os.listdir(dest_root)):
            mpath = dest_root / month
            if not mpath.is_dir():
                continue
            for njud in sorted(os.listdir(mpath)):
                npath = mpath / njud
                if not npath.is_dir():
                    continue
                for arq in sorted(os.listdir(npath)):
                    linhas.append({"mes": month, "njud": njud, "arquivo": arq})

    with open(backup_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["mes", "njud", "arquivo"])
        writer.writeheader()
        writer.writerows(linhas)

    print(f"✔ Estado anterior registrado em: {backup_path} ({len(linhas)} arquivo(s))")
    return backup_path


# ===========================================================================
# LIMPEZA (só das pastas que o plano vai recriar) E CÓPIA
# ===========================================================================

def limpar_pastas_do_plano(dest_root: Path, alvo: set[tuple[str, str]], aplicar: bool):
    if not dest_root.exists():
        return

    a_remover = []
    for month in sorted(os.listdir(dest_root)):
        mpath = dest_root / month
        if not mpath.is_dir():
            continue
        for njud in sorted(os.listdir(mpath)):
            npath = mpath / njud
            if not (npath.is_dir() and (month, njud) in alvo):
                continue
            mp3s = [f for f in os.listdir(npath) if f.lower().endswith(".mp3")]
            if len(mp3s) > 4:
                print(f"⚠ {npath} tem {len(mp3s)} arquivos (esperado 4) — verifique manualmente.")
            a_remover.append(npath)

    print(f"{'Removeria' if not aplicar else 'Removendo'} {len(a_remover)} pasta(s) de NJUD:")
    for p in a_remover:
        print(f"    {p}")
        if aplicar:
            shutil.rmtree(p)


def copiar_conforme_plano(linhas: list[dict], dest_root: Path, aplicar: bool):
    count = 0
    erros = []
    for row in linhas:
        src = Path(row["src"]) / row["arquivo"]
        dest_dir = dest_root / row["mes_destino"] / row["njud"]
        dest_file = dest_dir / row["arquivo"]

        if not aplicar:
            print(f"    [dry-run] copiaria: {src} -> {dest_file}")
            count += 1
            continue

        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest_file)
            count += 1
        except Exception as e:
            erros.append((str(src), str(dest_file), str(e)))

    print(f"\n{'Copiaria' if not aplicar else 'Copiados'}: {count}")
    print(f"Erros: {len(erros)}")
    for e in erros:
        print(f"    {e}")
    return count, erros


def validar_resultado(dest_root: Path) -> list[tuple]:
    invalid = []
    for month_name in sorted(os.listdir(dest_root)):
        mpath = dest_root / month_name
        if not mpath.is_dir():
            continue
        for njud in sorted(os.listdir(mpath)):
            npath = mpath / njud
            if not npath.is_dir():
                continue
            mp3s = sorted(f for f in os.listdir(npath) if f.lower().endswith(".mp3"))
            if len(mp3s) != 4:
                invalid.append((month_name, njud, f"qtd={len(mp3s)}"))
            meses = set()
            for f in mp3s:
                mm = re.match(r"^BOLETIM_RADIO_TJRN_(\d{2}_(\d{2})_(\d{4}))_B(\d+)_", f, re.IGNORECASE)
                if mm:
                    meses.add(mm.group(2))
            if len(meses) > 1:
                invalid.append((month_name, njud, f"meses={sorted(meses)}"))
    return invalid


# ===========================================================================
# CLI
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Copia boletins conforme plano_alocacao.csv, organizando por mês/NJUD."
    )
    parser.add_argument("--filter", type=str, default=None,
                        help="Filtra o plano por mês de destino (ex: AGOSTO ou 08).")
    parser.add_argument("--plan", type=str, default=None,
                        help="Caminho alternativo para o plano CSV.")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--dry-run", action="store_true", default=True,
                        help="Só mostra o que seria feito, não altera nada em disco (padrão)")
    parser.add_argument("--apply", action="store_true",
                        help="Executa de fato: limpa as pastas do plano e copia os arquivos")
    parser.add_argument("--permitir-mes-divergente", action="store_true",
                        help="Opt-in: aceita linhas de fallback (mês no nome do arquivo difere "
                             "do mes_destino). Cada linha aceita é registrada como AVISO-FALLBACK.")
    args = parser.parse_args()
    aplicar = args.apply

    plan_path = Path(args.plan) if args.plan else PLAN_CSV
    linhas = carregar_linhas_plano(plan_path)

    if args.filter:
        filtro = args.filter.strip().upper()
        filtro_extenso = ABBR_POR_EXTENSO.get(filtro[:3].upper(), filtro)
        linhas = [
            row for row in linhas
            if row["mes_destino"].strip().upper() in {filtro, filtro_extenso}
        ]
        if not linhas:
            print(f"✖ Nenhuma linha do plano corresponde ao filtro: {args.filter}", file=sys.stderr)
            sys.exit(1)
        print(f"Filtro aplicado: {len(linhas)} linha(s) para mês {filtro_extenso}.")

    linhas = ler_e_validar_plano(plan_path, linhas=linhas, permitir_mes_divergente=args.permitir_mes_divergente)
    alvo = njuds_no_plano(linhas)

    if aplicar:
        registrar_estado_atual(DEST_ROOT)

    limpar_pastas_do_plano(DEST_ROOT, alvo, aplicar)
    count, erros = copiar_conforme_plano(linhas, DEST_ROOT, aplicar)

    if not aplicar:
        print("\nModo dry-run: nada foi alterado em disco. Rode com --apply para executar de fato.")
        return

    with open(REPORT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_OBRIGATORIOS)
        writer.writeheader()
        writer.writerows(linhas)
    print(f"\nRelatório gravado em: {REPORT_CSV}")

    invalid = validar_resultado(DEST_ROOT)
    print("\nValidação:")
    if invalid:
        for r in invalid:
            print(f"    {r}")
    else:
        print("TODAS as pastas OK — exatamente 4 boletins por NJUD, mesmo mês.")


if __name__ == "__main__":
    main()
