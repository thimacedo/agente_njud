#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix Notes Pipeline — GIRO nas Comarcas

 Lê o output do pipeline GIRO (GIRO/output/<code>/cortes/) e converte
 os cortes (vocals_CABECA.wav + vocals_CORPO.wav) em notas MP3 individuais
 em data/processed/PRODUCAO_2026/GIRO_COMARCAS/<code>/.

 Corrigido em relação à versão anterior:
 - Lê de GIRO/output/<code>/cortes/ (padrão do pipeline GIRO) em vez de
   JORNALS_DIVIDIDOS/ (padrão do pipeline NJUD, fonte errada)
 - Faz merge de vocals_CABECA.wav + vocals_CORPO.wav em cada nota
 - Nomeia a nota como <nome_boletim>.mp3

Uso:
    python fix_notes.py
    python fix_notes.py --programa 0102
    python fix_notes.py --limpar
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pydub import AudioSegment
from scripts_pipeline.giro.montar_direto import PROGRAMAS

BASE = Path(__file__).resolve().parent  # raiz do projeto (DIVISOR/)
GIRO_OUTPUT = BASE / "GIRO" / "output"          # GIRO/output/<code>/cortes/
GIRORC = BASE / "data" / "processed" / "PRODUCAO_2026" / "GIRO_COMARCAS"  # data/processed/.../GIRO_COMARCAS/<code>/

AUDIO_EXT = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}


def extrair_nome_boletim(caminho_subdir: Path) -> str:
    """Extrai o nome-base do boletim a partir do nome do subdiretório de corte.
    
    Ex: BOLETIM_RADIO_TJRN_14_01_2026_B1_TCERN_..._CABECA
        → BOLETIM_RADIO_TJRN_14_01_2026_B1_TCERN_..._CABECA.mp3
    """
    return caminho_subdir.name + ".mp3"


def merge_vocals(caminho_subdir: Path, saida: Path) -> bool:
    """Faz merge de vocals_CABECA.wav + vocals_CORPO.wav em uma única nota MP3.
    
    Returns True se sucesso, False se falhou ou arquivos incompletos.
    """
    cabeca = caminho_subdir / "vocals_CABECA.wav"
    corpo = caminho_subdir / "vocals_CORPO.wav"

    if not cabeca.exists():
        print(f"    ⚠  vocals_CABECA.wav não encontrado em {caminho_subdir.name}")
        return False
    if not corpo.exists():
        print(f"    ⚠  vocals_CORPO.wav não encontrado em {caminho_subdir.name}")
        return False

    try:
        audio_cabeca = AudioSegment.from_file(str(cabeca))
        audio_corpo = AudioSegment.from_file(str(corpo))
        merged = audio_cabeca + audio_corpo
        merged.export(str(saida), format="mp3")
        return True
    except Exception as e:
        print(f"    ✖  Erro no merge de {caminho_subdir.name}: {e}")
        return False


def limpar_programa(cod: str) -> int:
    """Remove todas as notas MP3 do programa em GIRORC (para reprocessamento)."""
    pasta = GIRORC / cod
    if not pasta.exists():
        print(f"  {cod}: pasta não existe, nada para limpar")
        return 0

    removidos = 0
    for f in pasta.glob("*.mp3"):
        f.unlink()
        removidos += 1
    print(f"  {cod}: removidos {removidos} arquivos")
    return removidos


def processar_programa(cod: str, only_missing: bool = False) -> int:
    """Processa um programa: converte cortes em notas MP3.
    
    Args:
        cod: código do programa (ex: "0102")
        only_missing: se True, ignora notas que já existem em GIRORC/cod/
    
    Returns:
        Número de notas geradas.
    """
    # Verificar se o programa tem data mapeada
    if cod not in PROGRAMAS:
        print(f"  ✖  {cod}: código não mapeado em PROGRAMAS")
        return 0

    # Diretório de cortes (output do pipeline GIRO)
    pasta_cortes = GIRO_OUTPUT / cod / "cortes"
    if not pasta_cortes.exists():
        print(f"  ✖  {cod}: pasta de cortes não existe em {pasta_cortes}")
        return 0

    # Diretório de destino (GIRO_COMARCAS/<code>/)
    pasta_destino = GIRORC / cod
    pasta_destino.mkdir(parents=True, exist_ok=True)

    # Encontrar todos os subdiretórios de corte
    cortes = sorted([d for d in pasta_cortes.iterdir() if d.is_dir()])
    print(f"  {cod}: {len(cortes)} cortes encontrados em {pasta_cortes}")

    gerados = 0
    falhados = 0

    for corte in cortes:
        nome_nota = extrair_nome_boletim(corte)
        destino_nota = pasta_destino / nome_nota

        if only_missing and destino_nota.exists():
            continue

        if destino_nota.exists():
            continue  # já existe (mesmo se only_missing=False, não sobrescreve por segurança)

        if merge_vocals(corte, destino_nota):
            gerados += 1
            print(f"    ✓ {nome_nota} ({corte.name})")
        else:
            falhados += 1

    if gerados > 0:
        print(f"  {cod}: {gerados} notas geradas, {falhados} falhadas")
    else:
        print(f"  {cod}: nenhuma nota gerada")

    return gerados


def main():
    parser = argparse.ArgumentParser(
        description="Converte cortes do pipeline GIRO em notas MP3 para montagem."
    )
    parser.add_argument(
        "--programa", "-p",
        help="Processa apenas o programa especificado (ex: 0102). Se omitido, processa todos."
    )
    parser.add_argument(
        "--limpar", "-l",
        action="store_true",
        help="Remove todas as notas MP3 existentes antes de reprocessar (uso com --programa)."
    )
    parser.add_argument(
        "--apenas-faltantes", "-f",
        action="store_true",
        help="Pula notas que já existem em GIRORC (para reprocessamento parcial)."
    )
    args = parser.parse_args()

    if args.limpar and not args.programa:
        print("Erro: --limpar requer --programa")
        sys.exit(1)

    if args.programa:
        cods = [args.programa]
    else:
        cods = sorted(PROGRAMAS.keys())

    print(f"=== FIX NOTES PIPELINE (GIRO) ===")
    print(f"Fonte:  GIRO/output/<code>/cortes/")
    print(f"Destino: data/processed/PRODUCAO_2026/GIRO_COMARCAS/<code>/")
    print(f"Programas: {len(cods)}")
    print()

    total_gerados = 0
    total_falhados = 0
    total_pulados = 0

    for cod in cods:
        print(f"--- {cod} ({PROGRAMAS[cod]}) ---")
        if args.limpar:
            limpar_programa(cod)

        gerados = processar_programa(cod, only_missing=args.apenas_faltantes)
        if gerados > 0:
            total_gerados += gerados
        total_pulados += len(list((GIRO_OUTPUT / cod / "cortes").glob("*"))) - gerados

    print()
    print(f"=== RESUMO ===")
    print(f"Programas processados: {len(cods)}")
    print(f"Notas geradas: {total_gerados}")
    print(f"Notas puladas (já existentes): {total_pulados}")
    print(f"Falhas: {total_falhados}")
    print()


if __name__ == "__main__":
    main()
