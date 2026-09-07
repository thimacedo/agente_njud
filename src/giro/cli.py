# coding: utf-8
"""
CLI do módulo GIRO nas Comarcas — processamento de boletins e montagem.

Entrada:
    python -m giro <pasta_boletins> --saida <dir> [--mmss 0101] [--ano 2026]

Fluxo:
    1. Ler plano (data/plano_giro_<ano>.csv)
    2. Copiar boletins relevantes para data/processed/GIRO_COMARCAS/
    3. Para cada boletim:
       a. Transcrever com Whisper
       b. Extrair notas (LOC+OFF juntos, sem separação CABEÇA/CORPO)
       c. Filtrar geograficamente (filtro.py)
       d. Cortar nota e salvar em data/processed/GIRO_COMARCAS/<N>.mp3
       e. Persistir estado em estado_por_notas/*.json
    4. Montar programas com notas selecionadas (montagem.py)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

from .log import (
    configurar_logger,
    get_logger,
    log_aviso,
    log_debug,
    log_erro,
    log_info,
    log_programa_concluido,
)
from .config import DIR_PROCESSED, DIR_PLANOS, LOGS_DIR_GIRO
from .filtro import ClassificacaoGiro, ResultadoFiltro, filtrar_nota
from .utils import (
    gerar_plano,
    mes_dos_boletins,
    nome_corte_nota,
    nome_programa,
    terça_do_programa,
)
from .montagem import montar_programa

# ===========================================================================
# FUNÇÃO PRINCIPAL
# ===========================================================================


def processar_giro(
    pasta_boletins: Path,
    saida: Optional[Path] = None,
    mmss: Optional[str] = None,
    ano: int = 2026,
    evitar_natal: bool = True,
    log_dir: Optional[Path] = None,
    verbose: bool = False,
) -> dict:
    """Processa o GIRO: gera plano, filtra boletins, transcreve, monta.

    Args:
        pasta_boletins: pasta com subpastas mensais de boletins (ex: JORNAIS/)
        saida: pasta de saída dos programas montados (default: DIR_OUTPUT)
        mmss: código específico do programa a processar (ex: "0101")
        ano: ano dos boletins (default: 2026)
        evitar_natal: ativa filtro de evitar Natal (default: True)
        log_dir: diretório para log de auditoria (default: logs/)
        verbose: log detalhado

    Returns:
        dict com resumo do processamento
    """
    if saida is None:
        saida = DIR_PROCESSED
    if log_dir is None:
        log_dir = LOGS_DIR_GIRO

    pasta_saida = saida
    pasta_saida.mkdir(parents=True, exist_ok=True)

    # Configura logger
    if verbose:
        nivel = 10  # DEBUG
    else:
        nivel = 20  # INFO
    log_file = log_dir / "giro_processamento.log"
    log_dir.mkdir(parents=True, exist_ok=True)
    configurar_logger("giro", nivel=nivel, arquivo=log_file, stdout=True)
    logger = get_logger()

    log_info("cli", "Processando GIRO nas Comarcas")
    log_info("cli", f"Pasta de boletins: {pasta_boletins}")
    log_info("cli", f"Saída: {pasta_saida}")
    log_info("cli", f"mmss: {mmss or 'todos'}")
    log_info("cli", f"evitar_natal: {evitar_natal}")

    # ---- Gera plano ----
    planos = gerar_plano(ano)
    plano_selecionado = planos
    if mmss:
        plano_selecionado = [p for p in planos if p["mmss"] == mmss]
        if not plano_selecionado:
            log_erro("cli", f"Programa {mmss} não encontrado no plano")
            return {"error": f"Programa {mmss} não encontrado"}

    log_info("plano", f"Plano gerado: {len(plano_selecionado)} programas para processar")
    for p in plano_selecionado:
        log_info(
            "plano",
            f"  {p['mmss']} | terça={p['data_terça']} | "
            f"notícias={p['seg_notícias']}→{p['dom_notícias']}",
        )

    # ---- Para cada programa, identificar notas nos boletins ----
    resultados = []
    MIN_NOTAS = 4  # mínimo de notas por programa
    MAX_NOTAS = 6  # máximo de notas por programa (para ao atingir)

    for plano in plano_selecionado:
        mmss = plano["mmss"]
        mes_boletim = plano["mes_boletim"]
        seg = date.fromisoformat(plano["seg_notícias"])
        dom = date.fromisoformat(plano["dom_notícias"])

        log_info(
            "seleção",
            f"Programa {mmss}: boletins de mês {mes_boletim:02d}/{ano} "
            f"({seg} → {dom})",
        )

        # Procurar boletins no período (busca recursiva em subpastas)
        boletins_no_periodo = []
        for boletim_path in pasta_boletins.rglob("BOLETIM_RADIO_TJRN_*.mp3"):
            m_data = re.match(
                r"BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_",
                boletim_path.name,
            )
            if m_data:
                dia, mes, ano_b = map(int, m_data.groups())
                data_boletim = date(ano_b, mes, dia)
                if seg <= data_boletim <= dom:
                    boletins_no_periodo.append((boletim_path, data_boletim))
                    log_debug(
                        "seleção",
                        f"  Boletim {boletim_path.name}: {data_boletim}",
                    )

        log_info(
            "seleção",
            f"  {mmss}: {len(boletins_no_periodo)} boletins no período",
        )

        # ---- PASSO 1: Coletar notas evitando Natal ----
        idx_nota_global = 0
        notas_aceitas_total = []
        modelo_whisper = None

        for boletim_path, data_boletim in boletins_no_periodo:
            # Parada antecipada: já atingiu o máximo de notas
            if len(notas_aceitas_total) >= MAX_NOTAS:
                log_info(
                    "threshold",
                    f"  {mmss}: Máximo de {MAX_NOTAS} notas atingido. Interrompendo Passo 1.",
                )
                break

            log_info(
                "nota",
                f"  [Passo 1] Processando boletim {boletim_path.name} ({data_boletim})...",
            )

            try:
                from .transcricao import processar_boletim
                notas_aceitas, idx_nota_global, modelo_whisper = processar_boletim(
                    caminho_boletim=boletim_path,
                    mmss=mmss,
                    idx_nota_global=idx_nota_global,
                    pasta_saida=pasta_saida / mmss,
                    evitar_natal=True,
                    metodo_deteccao="assinatura",
                    modelo=modelo_whisper,
                )
                notas_aceitas_total.extend(notas_aceitas)

            except ImportError:
                log_aviso(
                    "nota",
                    "  Transcrição não disponível — "
                    "instale faster-whisper para processar",
                )
                break
            except Exception as e:
                log_erro("nota", f"  Erro ao processar boletim: {e}")
                continue

        # ---- PASSO 2: Se < MIN_NOTAS, complementar com notas de Natal ----
        if len(notas_aceitas_total) < MIN_NOTAS:
            notas_faltantes = MIN_NOTAS - len(notas_aceitas_total)
            log_info(
                "threshold",
                f"  {mmss}: apenas {len(notas_aceitas_total)} nota(s) de outras cidades. "
                f"Preciso de mais {notas_faltantes} nota(s) institucional(is) de Natal.",
            )

            for boletim_path, data_boletim in boletins_no_periodo:
                if len(notas_aceitas_total) >= MIN_NOTAS:
                    log_info("threshold", f"  {mmss}: Meta atingida! Interrompendo busca.")
                    break

                log_info(
                    "nota",
                    f"  [Passo 2 - fallback] Re-processando {boletim_path.name} ({data_boletim})...",
                )

                try:
                    from .transcricao import processar_boletim
                    notas_natal, idx_nota_global, modelo_whisper = processar_boletim(
                        caminho_boletim=boletim_path,
                        mmss=mmss,
                        idx_nota_global=idx_nota_global,
                        pasta_saida=pasta_saida / mmss,
                        evitar_natal=False,  # aceita notas de Natal
                        metodo_deteccao="assinatura",
                        modelo=modelo_whisper,
                    )
                    # Adiciona apenas notas que ainda não estão na lista
                    existentes = {p.name for p in notas_aceitas_total}
                    for n in notas_natal:
                        if n.name not in existentes and len(notas_aceitas_total) < MIN_NOTAS:
                            notas_aceitas_total.append(n)
                            existentes.add(n.name)
                    
                    # Log de progresso: quantas ainda faltam
                    if len(notas_aceitas_total) < MIN_NOTAS:
                        ainda_faltam = MIN_NOTAS - len(notas_aceitas_total)
                        log_info("threshold", f"  {mmss}: ainda faltam {ainda_faltam} nota(s).")
                    else:
                        log_info("threshold", f"  {mmss}: Meta atingida! Interrompendo busca.")

                except Exception as e:
                    log_erro("nota", f"  Erro no fallback: {e}")
                    continue

            log_info(
                "threshold",
                f"  {mmss}: após fallback, {len(notas_aceitas_total)} nota(s) total(is).",
            )
        else:
            log_info(
                "threshold",
                f"  {mmss}: {len(notas_aceitas_total)} nota(s) de outras cidades "
                f"(≥{MIN_NOTAS}). Sem necessidade de fallback.",
            )

        log_info(
            "seleção",
            f"  {mmss}: {len(notas_aceitas_total)} notas aceitas "
            f"(de {len(boletins_no_periodo)} boletins processados)",
        )

        resultados.append({
            "mmss": mmss,
            "data_terça": plano["data_terça"],
            "boletins": len(boletins_no_periodo),
            "notas_selecionadas": len(notas_aceitas_total),
            "status": "processado" if notas_aceitas_total else "sem_notas",
        })

    return {
        "status": "planificado",
        "programas": resultados,
        "saida": str(pasta_saida),
        "log": str(log_file),
    }


# ===========================================================================
# MONTAGEM (se --montar informado)
# ===========================================================================


def montar_giro(
    pasta_notas: Path,
    mmss_list: Optional[list[str]] = None,
    log_dir: Optional[Path] = None,
    verbose: bool = False,
) -> list[Path]:
    """Monta programas a partir de notas já processadas.

    Args:
        pasta_notas: pasta contendo as notas processadas (GNC_N*.mp3)
        mmss_list: lista opcional de mmss para montar (senão, todos)
        log_dir: diretório de log
        verbose: log detalhado

    Returns:
        Lista de Paths dos programas montados
    """
    if log_dir is None:
        log_dir = LOGS_DIR_GIRO
    log_dir.mkdir(parents=True, exist_ok=True)

    nivel = 10 if verbose else 20
    configurar_logger("giro_montagem", nivel=nivel,
                     arquivo=log_dir / "giro_montagem.log",
                     stdout=True)
    logger = get_logger()

    log_info("montagem", f"Iniciando montagem a partir de {pasta_notas}")

    if not pasta_notas.exists():
        log_erro("montagem", f"Pasta de notas não existe: {pasta_notas}")
        return []

    # Agrupa notas por mmss
    from collections import defaultdict
    notas_por_mmss = defaultdict(list)

    for nota_path in pasta_notas.glob("GNC_*.mp3"):
        m_mmss = re.match(r"GNC_(\d{4})_N\d+", nota_path.name)
        if m_mmss:
            mmss = m_mmss.group(1)
            notas_por_mmss[mmss].append(nota_path)
            log_debug("montagem", f"  {nota_path.name} → GNC_{mmss}")

    if not mmss_list:
        mmss_list = sorted(notas_por_mmss.keys())
        log_info("montagem", f"Montando todos os {len(mmss_list)} programas disponíveis")
    else:
        log_info("montagem", f"Montando {len(mmss_list)} programas: {mmss_list}")

    # Monta cada programa
    resultados = []
    for mmss in mmss_list:
        notas = sorted(notas_por_mmss.get(mmss, []))
        if not notas:
            log_aviso("montagem", f"Nenhuma nota para GNC_{mmss}")
            continue

        log_info("montagem", f"Montando GNC_{mmss} com {len(notas)} notas")
        caminho = montar_programa(mmss, notas, logger=logger)
        if caminho:
            resultados.append(caminho)
            log_info("montagem", f"  → {caminho.name}")

    log_info(
        "montagem",
        f"Montagem concluída: {len(resultados)} programas",
        total=len(resultados),
        restantes=len(mmss_list) - len(resultados),
    )
    return resultados


# ===========================================================================
# CLI
# ===========================================================================


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="python -m giro",
        description="Processamento do GIRO nas Comarcas (RJ RN)",
        epilog="Exemplos:\n"
               "  python -m giro E:/.../JORNAIS/ --lista-plano\n"
               "  python -m giro E:/.../JORNAIS/ --mmss 0101 --verbose\n"
               "  python -m giro --montar E:/.../data/processed/GIRO_COMARCAS/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "pasta_boletins",
        type=str,
        nargs="?",
        default=None,
        help="Pasta dos boletins (ex: E:/.../JORNAIS/). "
             "Obrigatório para processamento; opcional com --lista-plano ou --montar.",
    )

    parser.add_argument(
        "--saida",
        type=Path,
        default=None,
        help="Pasta de saída dos programas montados",
    )
    parser.add_argument(
        "--mmss",
        type=str,
        default=None,
        help="Código do programa a processar (ex: 0101). "
             "Se não informado, processa todos.",
    )
    parser.add_argument(
        "--ano",
        type=int,
        default=2026,
        help="Ano dos boletins (default: 2026)",
    )
    parser.add_argument(
        "--nao-evitar-natal",
        action="store_true",
        dest="nao_evitar_natal",
        help="Desativa o filtro de evitar Natal (inclui notícias de Natal)",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="Diretório de log de auditoria (default: logs/)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log detalhado (DEBUG)",
    )
    parser.add_argument(
        "--lista-plano",
        action="store_true",
        help="Lista o plano de programas e sai",
    )
    parser.add_argument(
        "--montar",
        type=Path,
        default=None,
        help="Montar programas a partir de pasta de notas já processadas",
    )
    parser.add_argument(
        "--mmss-list",
        type=str,
        default=None,
        help="Lista de mmss separados por vírgula para montagem "
             "(ex: 0101,0102)",
    )

    args = parser.parse_args(argv)

    pasta_boletins = args.pasta_boletins or None

    # ---- Lista de plano ----
    if args.lista_plano:
        planos = gerar_plano(args.ano)
        print(f"=== Plano GIRO {args.ano} ===")
        print(f"{'mmss':<6} {'Terça':<12} {'Notícias (seg→dom)':<28} {'Boletim-mes':<12}")
        print("-" * 60)
        for p in planos:
            print(
                f"{p['mmss']:<6} "
                f"{p['data_terça']:<12} "
                f"{p['seg_notícias']}→{p['dom_notícias']:<28} "
                f"{p['mes_boletim']:<12}"
            )
        print()
        print(f"Total: {len(planos)} programas (12 meses × 4 semanas)")
        return 0

    # ---- Montagem ----
    if args.montar:
        mmss_list = None
        if args.mmss_list:
            mmss_list = [m.strip() for m in args.mmss_list.split(",")]
        return montar_giro(args.montar, mmss_list,
                          log_dir=args.log_dir, verbose=args.verbose) or 0

    # ---- Processamento principal ----
    if not pasta_boletins:
        parser.print_help()
        print("\nERRO: pasta_boletins é obrigatório para processamento.")
        return 1

    pasta_boletins_path = Path(pasta_boletins)
    if not pasta_boletins_path.exists():
        print(f"ERRO: pasta de boletins não existe: {pasta_boletins_path}")
        return 1

    resultado = processar_giro(
        pasta_boletins=pasta_boletins_path,
        saida=args.saida,
        mmss=args.mmss,
        ano=args.ano,
        evitar_natal=not args.nao_evitar_natal,
        log_dir=args.log_dir,
        verbose=args.verbose,
    )

    if "error" in resultado:
        print(f"ERRO: {resultado['error']}")
        return 1

    print("\n=== Resumo do processamento ===")
    for r in resultado["programas"]:
        print(
            f"  {r['mmss']} | terça={r['data_terça']} | "
            f"boletins={r['boletins']} | notas_previstas={r.get('notas_previstas', '?')}"
        )
    print(f"\nSaída: {resultado['saida']}")
    print(f"Log:   {resultado['log']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
