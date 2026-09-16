#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix Notes Pipeline — GIRO nas Comarcas (v2 — CORRIGIDO)
========================================================
Correções aplicadas:
1. Respeita regras universais de `regras/livro.py`:
   - Janela de coleta: [X-6, X-1] dias ANTERIORES à exibição
   - Mínimo 4, máximo 6 boletins por programa
2. Usa `src/registro_programas.py` para isolamento total
3. Lê datas dos JSONs de `config/planejamento_2026/` (não de dict interno)
4. Escreve saída em `data/output/GIRO/<codigo>/` (isolado)
"""

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────
# IMPORTS CANÓNICOS
# ──────────────────────────────────────────────────────────────────────
PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT / "src"))
sys.path.insert(0, str(PROJECT / "regras"))

from livro import (
    calcular_janela_semana_anterior,
)

# Preflight H: → workspace
sys.path.insert(0, str(PROJECT / "src"))
from preflight import preflight_giro

# ──────────────────────────────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────────────────────────────

ROOT_DIR = PROJECT
OUTPUT_DIR = ROOT_DIR / "data" / "output"
STAGING_DIR = ROOT_DIR / "data" / "staging"

# ──────────────────────────────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────────────────────────────

MIN_NOTAS = 4
MAX_NOTAS = 6
JANELA_DIAS = 6  # dias anteriores à exibição

# Pasta de cortes (output do pipeline GIRO)
CORTES_DIR = PROJECT / "GIRO" / "output"

# Pasta de destino isolada
NOTAS_DIR = OUTPUT_DIR / "GIRO"

# Padrão de nomenclatura
PADRAO_BOLETIM = re.compile(
    r"^BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_(B\d+)_(.+)$"
)


# ──────────────────────────────────────────────────────────────────────
# FUNÇÕES
# ──────────────────────────────────────────────────────────────────────

def carregar_planejamento(codigo: str) -> dict | None:
    """Carrega o JSON de planejamento de um programa."""
    caminho = PROJECT / "config" / "planejamento_2026" / f"giro_{codigo}.json"
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return None


def extrair_data_do_nome(nome: str) -> date | None:
    """Extrai data DD_MM_YYYY do nome de um diretório de corte."""
    m = re.search(r"(\d{2})_(\d{2})_(\d{4})", nome)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def get_base_name(nome: str) -> str:
    """Remove sufixos _CABECA, _CORPO, _v2, _<timestamp>."""
    base = nome
    for suf in ["_CABECA", "_CORPO"]:
        if base.endswith(suf):
            base = base[: -len(suf)]
            break
    base = re.sub(r"_v\d+$", "", base)
    base = re.sub(r"_\d{10,}$", "", base)
    return base


def merge_vocals(caminho_subdir: Path, saida: Path) -> bool:
    """Faz merge de vocals_CABECA.wav + vocals_CORPO.wav."""
    cabeca = caminho_subdir / "vocals_CABECA.wav"
    corpo = caminho_subdir / "vocals_CORPO.wav"

    # Estratégia 1: áudios no próprio diretório
    if cabeca.exists() and corpo.exists():
        try:
            from pydub import AudioSegment
            merged = AudioSegment.from_file(str(cabeca)) + AudioSegment.from_file(str(corpo))
            merged.export(str(saida), format="mp3")
            return True
        except Exception as e:
            print(f"    ✖  Erro merge (estratégia 1): {e}")

    # Estratégia 2: diretórios irmãos _CABECA/_CORPO
    base = caminho_subdir.name
    for suf in ["_CABECA", "_CORPO"]:
        if base.endswith(suf):
            base = base[: -len(suf)]
            break

    irmao_cabeca = caminho_subdir.parent / (base + "_CABECA")
    irmao_corpo = caminho_subdir.parent / (base + "_CORPO")

    if irmao_cabeca.exists() and (irmao_cabeca / "vocals_CABECA.wav").exists():
        cabeca = irmao_cabeca / "vocals_CABECA.wav"
    if irmao_corpo.exists() and (irmao_corpo / "vocals_CORPO.wav").exists():
        corpo = irmao_corpo / "vocals_CORPO.wav"

    if cabeca.exists() and corpo.exists():
        try:
            from pydub import AudioSegment
            merged = AudioSegment.from_file(str(cabeca)) + AudioSegment.from_file(str(corpo))
            merged.export(str(saida), format="mp3")
            return True
        except Exception as e:
            print(f"    ✖  Erro merge (estratégia 2): {e}")

    print(f"    ⚠  Áudios não encontrados: {caminho_subdir.name}")
    return False


def limpar_programa(cod: str) -> int:
    """Remove todas as notas MP3 do programa."""
    pasta = NOTAS_DIR / cod
    if not pasta.exists():
        return 0
    removidos = 0
    for f in pasta.glob("*.mp3"):
        f.unlink()
        removidos += 1
    print(f"  {cod}: removidos {removidos} arquivos")
    return removidos


def processar_programa(cod: str, only_missing: bool = False) -> int:
    """
    Processa um programa conforme regras canónicas.
    
    Regras:
    - Janela: [X-6, X-1] dias ANTERIORES à exibição
    - Min 4, Max 6 notas
    - Cada boletim (base) = 1 nota
    """
    # 1. Carregar planejamento
    planejamento = carregar_planejamento(cod)
    if not planejamento:
        print(f"  ✖  {cod}: planejamento não encontrado")
        return 0

    # 2. Extrair data de exibição
    data_exib_str = planejamento.get("data_exibicao")
    if not data_exib_str:
        print(f"  ✖  {cod}: data_exibicao não definida")
        return 0

    try:
        data_exib = datetime.strptime(data_exib_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"  ✖  {cod}: data inválida ({data_exib_str})")
        return 0

    # 3. Calcular janela de coleta (regra universal: [X-6, X-1])
    janela = calcular_janela_semana_anterior(data_exib, dias=JANELA_DIAS)

    # 4. Listar cortes disponíveis
    pasta_cortes = CORTES_DIR / cod / "cortes"
    if not pasta_cortes.exists():
        print(f"  ✖  {cod}: pasta de cortes não existe")
        return 0

    # 5. Coletar e agrupar boletins por data+base
    cortes_info = {}  # {(data, base): [dirs]}
    for d in pasta_cortes.iterdir():
        if not d.is_dir():
            continue
        data_real = extrair_data_do_nome(d.name)
        if not data_real:
            continue
        
        # Filtro: apenas boletins NA JANELA (anteriores à exibição)
        if data_real not in janela:
            continue
        
        base = get_base_name(d.name)
        chave = (data_real, base)
        if chave not in cortes_info:
            cortes_info[chave] = []
        cortes_info[chave].append(d)

    if not cortes_info:
        print(f"  ✖  {cod}: nenhum corte na janela {janela.data_inicio} a {janela.data_fim}")
        return 0

    # 6. Selecionar boletins (máximo 6)
    # Ordenar por data (mais próximos da exibição primeiro)
    chaves_ordenadas = sorted(cortes_info.keys(), key=lambda x: abs((x[0] - data_exib).days))
    
    selecionados = []
    for chave in chaves_ordenadas:
        if len(selecionados) >= MAX_NOTAS:
            break
        selecionados.append(chave)

    if len(selecionados) < MIN_NOTAS:
        print(f"  ✖  {cod}: apenas {len(selecionados)} notas na janela (mínimo {MIN_NOTAS})")
        return 0

    # 7. Gerar notas
    pasta_destino = NOTAS_DIR / cod
    pasta_destino.mkdir(parents=True, exist_ok=True)

    print(f"  {cod} (exib={data_exib}, janela={janela.data_inicio} a {janela.data_fim}): {len(selecionados)} notas")

    gerados = 0
    for data_real, base in selecionados:
        nome_nota = f"{base}.mp3"
        destino_nota = pasta_destino / nome_nota

        if only_missing and destino_nota.exists():
            continue
        if destino_nota.exists():
            continue

        dirs = cortes_info[(data_real, base)]
        if merge_vocals(dirs[0], destino_nota):
            gerados += 1
            print(f"    ✓ {nome_nota} [{data_real.strftime('%d-%m-%Y')}]")
        else:
            print(f"    ✖ falhou: {nome_nota}")

    if gerados > 0:
        print(f"  {cod}: {gerados} notas geradas")
    else:
        print(f"  {cod}: nenhuma nota gerada")

    return gerados


def main():
    parser = argparse.ArgumentParser(
        description="Converte cortes do pipeline GIRO em notas MP3 para montagem (v2 canónica)."
    )
    parser.add_argument("-p", "--programa", help="Processa apenas este programa")
    parser.add_argument("-l", "--limpar", action="store_true", help="Remove notas antes de reprocessar")
    parser.add_argument("-f", "--apenas-faltantes", action="store_true", help="Pula notas existentes")
    args = parser.parse_args()

    # Registrar programa ativo
    from isolamento import requer_programa
    requer_programa("giro")

    # Criar pastas isoladas
    NOTAS_DIR.mkdir(parents=True, exist_ok=True)

    if args.programa:
        cods = [args.programa]
    else:
        # Listar todos os programas com planejamento
        plano_dir = PROJECT / "config" / "planejamento_2026"
        cods = []
        for f in sorted(plano_dir.glob("giro_*.json")):
            cod = f.stem.replace("giro_", "")
            cods.append(cod)

    print("=" * 70)
    print("FIX NOTES PIPELINE — GIRO (v2 CANÓNICA)")
    print(f"Janela de coleta: {JANELA_DIAS} dias ANTERIORES à exibição")
    print(f"Min/Max notas: {MIN_NOTAS}-{MAX_NOTAS}")
    print(f"Saída isolada: {NOTAS_DIR}")
    print("=" * 70)
    print()

    total_gerados = 0
    total_programas = 0

    for cod in cods:
        print(f"--- {cod} ---")
        if args.limpar:
            limpar_programa(cod)
        
        # PRE-FLIGHT CHECK: copiar boletins de H: para workspace
        try:
            planejamento = carregar_planejamento(cod)
            if planejamento:
                data_exib_str = planejamento.get("data_exibicao")
                if data_exib_str:
                    data_exib = datetime.strptime(data_exib_str, "%Y-%m-%d").date()
                    janela = calcular_janela_semana_anterior(data_exib, dias=JANELA_DIAS)
                    preflight_giro(janela.data_inicio, janela.data_fim)
        except Exception as e:
            print(f"  ⚠ Preflight check falhou: {e}")
        
        gerados = processar_programa(cod, only_missing=args.apenas_faltantes)
        total_gerados += gerados
        if gerados > 0:
            total_programas += 1
        print()

    print("=" * 70)
    print(f"TOTAL: {total_gerados} notas geradas em {total_programas} programas")
    print("=" * 70)


if __name__ == "__main__":
    main()
