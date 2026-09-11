#!/usr/bin/env python3
"""
scripts_pipeline/produzir_programa.py — Orquestração completa de produção.

Fluxo:
  1. Busca boletins do Drive H: (fonte read-only)
  2. Seleciona via regras centralizadas (src/regras/)
  3. Copia para staging local (data/staging/PROGRAMA/AAAA-MM-DD/)
  4. Processa via processar_boletim.py (Demucs + cortes)

Uso:
  python scripts_pipeline/produzir_programa.py giro 2026-01-21 --codigo 0103
  python scripts_pipeline/produzir_programa.py njud 2026-01-07 --codigo 2001
"""

import argparse
import sys
from datetime import date
from pathlib import Path

# Configuração
DRIVE_BOLETINS = Path("H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO")
BOLETINS_DIVIDIDOS = Path("data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS")
STAGING_ROOT = Path("data/staging")

# Adicionar src/ ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from regras.livro import TipoPrograma, SelecaoBoletins
from regras.njud import selecionar_boletins_njud
from regras.giro import selecionar_boletins_giro
from regras.boletim import listar_boletins_para_processar as processar_boletim_stems
from sync.coletor import coletar_boletins, ResultadoColeta


def buscar_boletins_drive() -> list[Path]:
    """
    Busca boletins já divididos (CABEÇA/CORPO) do cache local.
    
    O Drive H: contém os boletins completos (fonte read-only).
    O divisor_boletins gera os cortes em JORNAIS_DIVIDIDOS/.
    Trabalhamos com os cortes, não com o Drive diretamente.
    """
    if BOLETINS_DIVIDIDOS.exists():
        mp3s = sorted(BOLETINS_DIVIDIDOS.rglob("*.mp3"))
        print(f"[local] {len(mp3s)} boletins divididos em {BOLETINS_DIVIDIDOS}")
        return mp3s
    
    # Fallback: buscar do Drive (boletinos completos, sem CABECA/CORPO)
    if DRIVE_BOLETINS.exists():
        mp3s = sorted(DRIVE_BOLETINS.rglob("*.mp3"))
        print(f"[drive] {len(mp3s)} boletins completos em {DRIVE_BOLETINS}")
        return mp3s
    
    print(f"[erro] Nenhuma fonte de boletins encontrada")
    return []


def produzir(programa: str, data_exibicao: date, codigo: str | None = None) -> dict:
    """
    Produz um programa completo.

    Args:
        programa: 'njud', 'giro' ou 'boletim'
        data_exibicao: data de exibição do programa
        código: código do programa (ex: '0103', '2001')

    Returns:
        dict com resultado da produção
    """
    resultado = {
        "programa": programa,
        "data": data_exibicao.isoformat(),
        "codigo": codigo,
        "sucesso": False,
        "boletins_selecionados": 0,
        "boletins_coletados": 0,
        "erro": None,
    }

    try:
        # 1. Buscar boletins do Drive
        print(f"\n{'='*60}")
        print(f"PRODUZIR: {programa.upper()} {codigo or ''} ({data_exibicao})")
        print(f"{'='*60}")

        boletins_drive = buscar_boletins_drive()
        if not boletins_drive:
            resultado["erro"] = "Nenhum boletim encontrado no Drive"
            return resultado

        # 2. Selecionar via regras
        print(f"\n[regras] Selecionando boletins...")
        if programa == "njud":
            selecao = selecionar_boletins_njud(data_exibicao, boletins_drive, codigo)
        elif programa == "giro":
            try:
                selecao = selecionar_boletins_giro(data_exibicao, boletins_drive, codigo)
            except ValueError as e:
                # Fallback: se não há boletins na janela (início do ano),
                # usa boletins do próprio dia
                if "apenas 0 boletins na janela" in str(e):
                    from regras.livro import JanelaColeta
                    print(f"[regras] Janela vazia — usando boletins do dia {data_exibicao}")
                    janela_fallback = JanelaColeta(data_inicio=data_exibicao, data_fim=data_exibicao)
                    selecao = selecionar_boletins_giro(data_exibicao, boletins_drive, codigo, janela=janela_fallback)
                else:
                    raise
        elif programa == "boletim":
            selecao = processar_boletim_stems(data_exibicao, boletins_drive)
        else:
            resultado["erro"] = f"Programa inválido: {programa}"
            return resultado

        resultado["boletins_selecionados"] = selecao.quantidade
        print(f"[regras] {selecao.quantidade} arquivos selecionados ({selecao.quantidade // 2} boletins)")

        if selecao.quantidade == 0:
            resultado["erro"] = "Nenhum boletim selecionado"
            return resultado

        # 3. Copiar para staging
        print(f"\n[coletor] Copiando para staging...")
        tipo = TipoPrograma(programa.upper())
        resultado_coleta = coletar_boletins(selecao, data_exibicao)

        if not resultado_coleta.sucesso:
            print(f"[coletor] AVISO: coleta incompleta ({len(resultado_coleta.erros)} falhas)")

        resultado["boletins_coletados"] = len(resultado_coleta.arquivos_coletados)
        print(f"[coletor] {len(resultado_coleta.arquivos_coletados)} arquivos coletados")

        # 4. Processar (chamar processar_boletim.py)
        print(f"\n[processar] Iniciando processamento...")
        import subprocess
        env = {"PYTHONPATH": str(Path(__file__).resolve().parent.parent / "src")}
        cmd = [
            sys.executable, "-m", "core.processamento.processar_boletim",
            programa,
            "--data", data_exibicao.isoformat(),
        ]
        print(f"[processar] Comando: {' '.join(cmd)}")

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env={**__import__("os").environ, **env})
        if proc.returncode == 0:
            print(f"[processar] ✅ Concluído")
            resultado["sucesso"] = True
        else:
            print(f"[processar] ❌ Erro (código {proc.returncode})")
            if proc.stderr:
                print(f"  stderr: {proc.stderr[:500]}")
            resultado["erro"] = f"processar_boletim falhou (código {proc.returncode})"

    except Exception as e:
        resultado["erro"] = str(e)
        print(f"\n[erro] {type(e).__name__}: {e}")

    return resultado


def main():
    parser = argparse.ArgumentParser(description="Produz um programa completo")
    parser.add_argument("programa", choices=["njud", "giro", "boletim"])
    parser.add_argument("data", help="Data de exibição (YYYY-MM-DD)")
    parser.add_argument("--codigo", help="Código do programa (ex: 0103, 2001)")

    args = parser.parse_args()
    data = date.fromisoformat(args.data)

    resultado = produzir(args.programa, data, args.codigo)

    print(f"\n{'='*60}")
    print(f"RESULTADO: {'✅ SUCESSO' if resultado['sucesso'] else '❌ FALHA'}")
    print(f"  Programa: {resultado['programa']} {resultado['codigo'] or ''}")
    print(f"  Data: {resultado['data']}")
    print(f"  Selecionados: {resultado['boletins_selecionados']}")
    print(f"  Coletados: {resultado['boletins_coletados']}")
    if resultado["erro"]:
        print(f"  Erro: {resultado['erro']}")
    print(f"{'='*60}")

    return 0 if resultado["sucesso"] else 1


if __name__ == "__main__":
    sys.exit(main())
