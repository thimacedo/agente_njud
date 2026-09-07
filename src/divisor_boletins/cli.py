"""
CLI unificada com subcomandos: dividir e montar.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cmd_dividir(argv: list[str] | None = None):
    """Subcomando: divide boletins em CABEÇA e CORPO."""
    parser = argparse.ArgumentParser(
        prog="divisor_boletins dividir",
        description="Divide boletins de rádio do TJRN em cabeça (manchete) e corpo.",
    )
    parser.add_argument("pasta_entrada", help="Pasta raiz com os áudios")
    parser.add_argument("pasta_saida", help="Pasta raiz de saída (estrutura espelhada)")
    parser.add_argument("--log-dir", default=None,
                        help="Pasta para logs (padrão: <pasta_saida>/_logs)")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--dry-run", action="store_true", default=True,
                        help="Só mostra cortes propostos (padrão)")
    grupo.add_argument("--apply", action="store_true",
                        help="Grava os arquivos _CABECA/_CORPO + AUDIT_cortes.json")

    args = parser.parse_args(argv)

    from .audio import processar_recursivo
    processar_recursivo(
        args.pasta_entrada, args.pasta_saida,
        apply=args.apply, log_dir=args.log_dir,
    )

    if not args.apply:
        print(
            "\nModo dry-run: nada foi gravado. Rode novamente com --apply "
            "depois de revisar os cortes acima (especialmente os marcados com ⚠)."
        )


def cmd_montar(argv: list[str] | None = None):
    """Subcomando: monta o jornal completo a partir de cortes."""
    parser = argparse.ArgumentParser(
        prog="divisor_boletins montar",
        description="Monta um ou mais jornais completos a partir de cortes _CABECA/_CORPO.",
    )
    parser.add_argument("pasta_entrada", help="Pasta raiz com subpastas (uma por jornal)")
    parser.add_argument("pasta_saida", help="Pasta raiz de saída (estrutura espelhada)")
    parser.add_argument("--log-dir", default=None, help="Pasta para logs")
    parser.add_argument("--sem-intercalar", action="store_true",
                        help="Não intercalar vozes")

    args = parser.parse_args(argv)

    from .log import LogPipeline
    from .montagem import montar_todos_jornais

    pasta_entrada = Path(args.pasta_entrada)
    pasta_saida = Path(args.pasta_saida)
    log_dir = Path(args.log_dir) if args.log_dir else pasta_saida / "_logs"

    logger = LogPipeline(log_dir)
    resultados = montar_todos_jornais(
        pasta_entrada,
        pasta_saida,
        logger,
        intercalar=not args.sem_intercalar,
    )

    for r in resultados:
        print(r)


def main(argv: list[str] | None = None):
    """Ponto de entrada principal — despacha para o subcomando correto."""
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help"):
        # Sem subcomando: mostra ajuda geral
        print("Uso: python -m divisor_boletins <subcomando> [opções]\n")
        print("Subcomandos:")
        print("  dividir   Divide boletins em CABEÇA e CORPO")
        print("  montar    Monta jornais completos a partir dos cortes")
        print()
        print("Exemplos:")
        print("  python -m divisor_boletins dividir audios/ saida/ --dry-run")
        print("  python -m divisor_boletins dividir audios/ saida/ --apply")
        print("  python -m divisor_boletins montar saida/ jornais_final/")
        print()
        print("Compatibilidade reversa (sem subcomando):")
        print("  python -m divisor_boletins audios/ saida/ --dry-run")
        print("  → equivale a 'dividir audios/ saida/ --dry-run'")
        return

    subcomandos = {"dividir": cmd_dividir, "montar": cmd_montar}

    if argv[0] in subcomandos:
        subcomandos[argv[0]](argv[1:])
    else:
        # Compatibilidade reversa: se o primeiro arg NÃO é um subcomando
        # conhecido, assume que é o antigo estilo "dividir <entrada> <saida>"
        cmd_dividir(argv)
