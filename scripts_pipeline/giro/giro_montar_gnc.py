#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Montagem de GNCs — GIRO nas Comarcas (v2 — CORRIGIDO)
========================================================
Correções aplicadas:
1. Usa `src/registro_programas.py` para isolamento total
2. Lê notas de `data/output/GIRO/<codigo>/` (isolado)
3. Monta GNCs em `data/output/GIRO/<codigo>/GNC_<codigo>_<data>.mp3`
4. Sincroniza com H: apenas no final
5. Valida regras de isolamento antes de executar
"""

import argparse
import json
import re
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────
# IMPORTS CANÓNICOS
# ──────────────────────────────────────────────────────────────────────
PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT / "src"))

from registro_programas import (
    OUTPUT_DIR,
    obter_programa,
    TipoPrograma,
)

# Guard de isolamento
from isolamento import requer_programa, validar_path, IsolamentoError

# ──────────────────────────────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────────────────────────────

MIN_NOTAS = 4
MAX_NOTAS = 6

# Pasta de notas isolada
NOTAS_DIR = OUTPUT_DIR / "GIRO"

# Pasta de GNCs (saída final)
GNC_DIR = OUTPUT_DIR / "GIRO"

# Vinhetas
VHT_DIR = PROJECT / "assets" / "vinhetas" / "giro"
VHT_ABERTURA = "VHT_ABERTURA_GIRO.mp3"
VHT_PASSAGEM = "VHT_PASSAGEM_GIRO.mp3"
VHT_ENCERRAMENTO = "VHT_ENCERRAMENTO_GIRO.mp3"

# Destino H:
DESTINO_H = Path("H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/03_GIRO_NAS_COMARCAS")


# ──────────────────────────────────────────────────────────────────────
# FUNÇÕES
# ──────────────────────────────────────────────────────────────────────

def carregar_planejamento(codigo: str) -> dict | None:
    """Carrega o JSON de planejamento de um programa."""
    caminho = PROJECT / "config" / "planejamento_2026" / f"giro_{codigo}.json"
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return None


def carregar_vinheta(nome: str):
    """Carrega vinheta do diretório giro."""
    caminho = VHT_DIR / nome
    if caminho.exists():
        from pydub import AudioSegment
        return AudioSegment.from_mp3(str(caminho))
    raise FileNotFoundError(f"Vinheta não encontrada: {caminho}")


def montar_gnc(cod: str, notas: list[Path], data_str: str) -> Path | None:
    """Monta um GNC a partir das notas."""
    print(f"  Montando {cod}...")
    
    # Carregar vinhetas
    try:
        vht_abertura = carregar_vinheta(VHT_ABERTURA)
        vht_passagem = carregar_vinheta(VHT_PASSAGEM)
        vht_encerramento = carregar_vinheta(VHT_ENCERRAMENTO)
    except FileNotFoundError as e:
        print(f"    ✗ ERRO: {e}")
        return None
    
    # Montar programa
    from pydub import AudioSegment
    from pydub.effects import normalize
    
    programa_audio = AudioSegment.empty()
    programa_audio += vht_abertura
    
    for i, nota in enumerate(notas):
        if i > 0:
            programa_audio += vht_passagem
        nota_audio = AudioSegment.from_mp3(str(nota))
        nota_audio = normalize(nota_audio)
        programa_audio += nota_audio
    
    programa_audio += vht_encerramento
    
    # Salvar
    nome = f"GNC_{cod}_{data_str}.mp3"
    saida = GNC_DIR / nome
    programa_audio.export(str(saida), format="mp3")
    
    dur = len(programa_audio) / 1000
    print(f"    ✓ {nome} ({dur:.1f}s)")
    return saida


def sincronizar_h():
    """Sincroniza GNCs com H:."""
    if not DESTINO_H.exists():
        print(f"  ⚠ H: não acessível — sincronização ignorada")
        return 0
    
    copiados = 0
    for gnc in sorted(GNC_DIR.glob("GNC_*.mp3")):
        destino_f = DESTINO_H / gnc.name
        if not destino_f.exists() or gnc.stat().st_size != destino_f.stat().st_size:
            shutil.copy2(str(gnc), str(destino_f))
            copiados += 1
            print(f"  ✓ {gnc.name} → H:")
    
    return copiados


def main():
    parser = argparse.ArgumentParser(
        description="Montagem de GNCs — GIRO (v2 canónica)."
    )
    parser.add_argument("-p", "--programa", help="Processa apenas este programa")
    parser.add_argument("--pular-h", action="store_true", help="Não sincroniza com H:")
    args = parser.parse_args()

    # ──────────────────────────────────────────────────────────────────
    # GUARD DE ISOLAMENTO
    # ──────────────────────────────────────────────────────────────────
    requer_programa("giro")
    
    # Validar que estamos no diretório correto
    try:
        validar_path(GNC_DIR, "giro")
        validar_path(NOTAS_DIR, "giro")
    except IsolamentoError as e:
        print(f"✗ ERRO DE ISOLAMENTO: {e}")
        sys.exit(1)

    # ──────────────────────────────────────────────────────────────────
    # CARREGAR VINHETAS
    # ──────────────────────────────────────────────────────────────────
    print("=" * 70)
    print("MONTAGEM DE GNCs — GIRO (v2 CANÓNICA)")
    print("=" * 70)
    print(f"Notas dir: {NOTAS_DIR}")
    print(f"GNC dir:   {GNC_DIR}")
    print()

    # ──────────────────────────────────────────────────────────────────
    # PROCESSAR PROGRAMAS
    # ──────────────────────────────────────────────────────────────────
    if args.programa:
        cods = [args.programa]
    else:
        # Listar programas com notas
        cods = []
        for d in sorted(NOTAS_DIR.iterdir()):
            if d.is_dir() and list(d.glob("*.mp3")):
                cods.append(d.name)

    montados = 0
    falhados = []

    for cod in cods:
        # Carregar planejamento
        plano = carregar_planejamento(cod)
        if not plano:
            print(f"✗ {cod}: planejamento não encontrado")
            continue
        
        data_exib_str = plano.get("data_exibicao", "")
        if not data_exib_str:
            print(f"✗ {cod}: data_exibicao não definida")
            continue
        
        # Formatar data para nome do ficheiro (DD-MM-AAAA)
        try:
            data_exib = datetime.strptime(data_exib_str, "%Y-%m-%d")
            data_str = data_exib.strftime("%d-%m-%Y")
        except ValueError:
            data_str = data_exib_str
        
        # Carregar notas
        notas_dir = NOTAS_DIR / cod
        if not notas_dir.exists():
            print(f"✗ {cod}: sem notas em {notas_dir}")
            continue
        
        notas = sorted(notas_dir.glob("*.mp3"))
        
        if len(notas) < MIN_NOTAS:
            print(f"✗ {cod}: apenas {len(notas)} notas (mínimo {MIN_NOTAS})")
            continue
        
        if len(notas) > MAX_NOTAS:
            print(f"⊘ {cod}: {len(notas)} notas (máximo {MAX_NOTAS}) — usando primeiras {MAX_NOTAS}")
            notas = notas[:MAX_NOTAS]
        
        print(f"\n· {cod} ({data_str}): montando {len(notas)} notas...")
        
        try:
            caminho = montar_gnc(cod, notas, data_str)
            if caminho:
                montados += 1
        except Exception as e:
            print(f"    ✗ ERRO: {e}")
            falhados.append(cod)
            continue

    # ──────────────────────────────────────────────────────────────────
    # SINCRONIZAR H:
    # ──────────────────────────────────────────────────────────────────
    if not args.pular_h:
        print(f"\n=== Sincronização com H: ===")
        copiados = sincronizar_h()
        print(f"Copiados para H: {copiados}")

    print(f"\n=== RESUMO ===")
    print(f"Montados: {montados}")
    print(f"Falhados: {len(falhados)}")
    if falhados:
        print(f"Programas falhados: {falhados}")


if __name__ == "__main__":
    main()
