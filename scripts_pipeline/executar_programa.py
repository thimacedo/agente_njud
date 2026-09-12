#!/usr/bin/env python3
"""
Executor único do pipeline unificado.
Lê um ou mais JSONs de planejamento e orquestra o processamento.

Uso:
    # Programa único
    python scripts_pipeline/executar_programa.py config/planejamento_2026/giro_0102.json

    # Todos os programas de um mês
    python scripts_pipeline/executar_programa.py config/planejamento_2026/ --mes 01

    # Todos os programas gerados
    python scripts_pipeline/executar_programa.py config/planejamento_2026/
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — ajustados para a estrutura real do projeto DIVISOR
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent  # /e/.../DIVISOR
sys.path.insert(0, str(ROOT / "src"))

from core.processamento.processar_boletim import ConfigPrograma, processar_lote

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("executar_programa")


def carregar_json(caminho: Path) -> dict:
    if not caminho.exists():
        log.error("Arquivo não encontrado: %s", caminho)
        sys.exit(1)
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def configurar_pipeline(json_config: dict, pasta_boletins: Path, pasta_saida: Path) -> ConfigPrograma:
    """
    Monta ConfigPrograma a partir do JSON de planejamento + pastas base.
    """
    codigo = json_config["codigo"]
    nome_programa = json_config["programa"].lower()

    return ConfigPrograma(
        nome=nome_programa,
        pasta_boletins=pasta_boletins,
        pasta_saida=pasta_saida,
        pasta_estado=pasta_saida / "estado_por_arquivo",
        pasta_log=pasta_saida / "_logs",
        modelo_whisper="tiny",
        compute_type="int8",
        roteiro_corte="GIRO_CABEÇA_CORPO" if nome_programa == "giro" else None,
        minimo_boletins_para_montar=json_config.get("parametros", {}).get("boletins_minimos", 4),
        usar_separacao_stems=json_config.get("parametros", {}).get("usar_separacao_stems", json_config.get("parametros", {}).get("usar_demucs", False)),
        # Janela de datas do plano (para filtragem no Giro)
        data_inicio_coleta=json_config.get("janela_coleta", {}).get("inicio"),
        data_fim_coleta=json_config.get("janela_coleta", {}).get("fim"),
    )


def executar_single(json_path: Path, pasta_boletins: Path, pasta_saida: Path) -> dict:
    """Processa um único programa a partir do seu JSON."""
    log.info("=" * 60)
    cfg_dict = carregar_json(json_path)

    codigo = cfg_dict["codigo"]
    nome_programa = cfg_dict["programa"].lower()
    data_exibicao = cfg_dict.get("data_exibicao", "?")
    janela = cfg_dict.get("janela_coleta", {})
    params = cfg_dict.get("parametros", {})

    log.info("Programa: %s %s  |  Exibição: %s", cfg_dict["programa"], codigo, data_exibicao)
    log.info("Janela coleta: %s → %s  (%d dias)",
             janela.get("inicio", "?"), janela.get("fim", "?"),
             janela.get("dias_totais", "?"))

    # Gate de montagem: verifica se há dias suficientes
    dias_disponiveis = janela.get("dias_totais", 0)
    minimo = params.get("boletins_minimos", 4)
    if dias_disponiveis < minimo:
        log.warning("Gate de montagem: %d dias < %d mínimos — ajuste manual pode ser necessário",
                     dias_disponiveis, minimo)

    # Detecta pasta base do programa na raiz (GIRO/, NJUD/, BOLETIM/)
    pasta_programa = ROOT / nome_programa.upper()
    pasta_programa.mkdir(parents=True, exist_ok=True)

    # Subpastas operacionais dentro da pasta do programa
    pasta_saida_prog = pasta_programa / "output" / codigo
    pasta_estado_prog = pasta_programa / "state" / codigo
    pasta_logs_prog = pasta_programa / "logs" / codigo
    pasta_cache_prog = pasta_programa / "cache" / codigo
    pasta_tmp_prog = pasta_programa / "tmp" / codigo

    for p in [pasta_saida_prog, pasta_estado_prog, pasta_logs_prog, pasta_cache_prog, pasta_tmp_prog]:
        p.mkdir(parents=True, exist_ok=True)

    log.info("Pasta base: %s", pasta_programa)
    log.info("Saída: %s", pasta_saida_prog)

    # Monta configuração usando a pasta do programa como base
    config = ConfigPrograma(
        nome=nome_programa,
        pasta_boletins=pasta_boletins,
        pasta_saida=pasta_saida_prog,
        pasta_estado=pasta_estado_prog,
        pasta_log=pasta_logs_prog,
        modelo_whisper="tiny",
        compute_type="int8",
        roteiro_corte="GIRO_CABEÇA_CORPO" if nome_programa == "giro" else None,
        minimo_boletins_para_montar=params.get("boletins_minimos", 4),
        usar_separacao_stems=params.get("usar_separacao_stems", params.get("usar_demucs", False)),
        data_inicio_coleta=janela.get("inicio"),
        data_fim_coleta=janela.get("fim"),
    )

    # Executa
    log.info("Iniciando processamento (%d boletins esperados)...", dias_disponiveis)
    resultado = processar_lote(config)

    log.info("Concluído para %s %s: %s", cfg_dict["programa"], codigo, resultado.get("status", "OK"))
    return resultado





if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Executor único do pipeline unificado (NJUD, BOLETIM, GIRO)."
    )
    parser.add_argument(
        "planejamento",
        type=str,
        help="Caminho para JSON de planejamento ou pasta GIRO/planejamento_2026/",
    )
    parser.add_argument(
        "--boletins",
        type=str,
        help="Pasta base dos boletins (padrão: H:/Meu Drive/RADIO TJRN CONTEUDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO/)",
    )
    parser.add_argument(
        "--mes",
        type=str,
        help="Filtra por mês (ex: 01 para janeiro). Só usado com pasta.",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=None,
        help="Pasta base de saída (se omitido, usa data/processed/PRODUCAO_2026/)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Log em nível DEBUG",
    )

    args = parser.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Pasta base dos boletins (cortes já processados localmente)
    BOLETINS_BASE = ROOT / "data" / "processed" / "PRODUCAO_2026" / "JORNAIS_DIVIDIDOS"
    pasta_boletins = Path(args.boletins) if args.boletins else BOLETINS_BASE

    plan_path = Path(args.planejamento)

    # É pasta ou arquivo?
    if plan_path.is_dir():
        if args.mes:
            padrao = f"*_{args.mes}*.json"
            jsons = sorted(plan_path.glob(padrao))
            if not jsons:
                log.error("Nenhum JSON encontrado para o mês %s em %s", args.mes, plan_path)
                sys.exit(1)
        else:
            jsons = sorted(plan_path.glob("*.json"))

        if not jsons:
            log.error("Nenhum arquivo JSON encontrado em %s", plan_path)
            sys.exit(1)

        log.info("Encontrados %d programa(s) em %s", len(jsons), plan_path)
        for j in jsons:
            executar_single(j, pasta_boletins, ROOT)

    else:
        executar_single(plan_path, pasta_boletins, ROOT)
