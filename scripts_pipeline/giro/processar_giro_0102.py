#!/usr/bin/env python3
"""
Script de invocação para processar GIRO 02/2026 usando o novo entry point.

Este script demonstra como usar core/processamento/processar_boletim.py
para processar os boletins do período 08-14/01/2026.
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Adicionar workspace ao PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Import do entry point
from core.processamento.processar_boletim import processar_boletim


def descobrir_boletins(periodo_inicio: str, periodo_fim: str, base_dir: str = "data/boletins") -> list:
    """
    Descobre boletins disponíveis no período especificado.
    
    Args:
        periodo_inicio: Data inicial no formato YYYY-MM-DD
        periodo_fim: Data final no formato YYYY-MM-DD
        base_dir: Diretório base onde os boletins estão armazenados
    
    Returns:
        Lista de dicionários com caminho dos boletins encontrados
    """
    from datetime import datetime, timedelta
    
    inicio = datetime.strptime(periodo_inicio, "%Y-%m-%d")
    fim = datetime.strptime(periodo_fim, "%Y-%m-%d")
    
    boletins = []
    data_atual = inicio
    
    while data_atual <= fim:
        # Padrão de nomenclatura: BOLETIM_YYYY-MM-DD.mp3 ou similar
        data_str = data_atual.strftime("%Y-%m-%d")
        
        # Procurar em possíveis locais
        possiveis_caminhos = [
            Path(base_dir) / f"BOLETIM_{data_str}.mp3",
            Path(base_dir) / f"boletim_{data_str}.wav",
            Path("input") / data_atual.strftime("%Y") / data_atual.strftime("%m") / f"boletim_{data_str}.mp3",
        ]
        
        for caminho in possiveis_caminhos:
            if caminho.exists():
                boletins.append({
                    'data': data_str,
                    'caminho_audio': str(caminho),
                    'caminho_saida': str(caminho.parent / 'output')
                })
                logger.info(f"Boletim encontrado: {caminho}")
                break
        
        data_atual += timedelta(days=1)
    
    if not boletins:
        logger.warning(f"Nenhum boletim encontrado no período {periodo_inicio} a {periodo_fim}")
        logger.info("Criando lista simulada para teste...")
        
        # Para teste: criar entradas simuladas
        data_atual = inicio
        while data_atual <= fim:
            data_str = data_atual.strftime("%Y-%m-%d")
            boletins.append({
                'data': data_str,
                'caminho_audio': f"/tmp/boletim_simulado_{data_str}.mp3",
                'caminho_saida': '/tmp/output_giro'
            })
            data_atual += timedelta(days=1)
    
    return boletins


def main():
    """Executa o processamento do GIRO 02/2026."""
    
    # Carregar roteiro
    roteiro_path = Path("config/roteiro_giro_0102.json")
    
    if not roteiro_path.exists():
        logger.error(f"Roteiro não encontrado: {roteiro_path}")
        logger.info("Usando configurações padrão...")
        
        roteiro = {
            "programa": "GIRO",
            "codigo": "0102",
            "data_base": "2026-01-14",
            "periodo_coleta": {
                "inicio": "2026-01-08",
                "fim": "2026-01-14"
            },
            "parametros": {
                "BOLETINS_POR_PROGRAMA": 5,
                "FORMATO_CORTE": "SILENCIO",
                "DURACAO_SILENCIO_MINIMA": 1.0,
                "REGRA_SEM_FALLBACK": True,
                "PERMITIR_REMONTAGEM": False,
                "LIMIARES_AUDITORIA": {
                    "duracao_minima_cabeca": 5.0,
                    "duracao_minima_corpo": 10.0,
                    "duracao_maxima_total": 300.0,
                    "tolerancia_silencio": 0.2
                }
            },
            "config_demucs": {
                "habilitado": False,
                "modelo": "htdemucs",
                "stems": ["vocals", "other"]
            },
            "saida": {
                "diretorio": "output/giro/2026-01",
                "padrao_nome": "GIRO_{codigo}_{DD-MM-YYYY}.mp3"
            }
        }
    else:
        with open(roteiro_path, 'r', encoding='utf-8') as f:
            roteiro = json.load(f)
    
    logger.info("=" * 60)
    logger.info(f"GIRO {roteiro['codigo']} - {roteiro['data_base']}")
    logger.info("=" * 60)
    
    # Descobrir boletins disponíveis
    periodo = roteiro.get('periodo_coleta', {})
    boletins = descobrir_boletins(
        periodo.get('inicio', '2026-01-08'),
        periodo.get('fim', '2026-01-14')
    )
    
    logger.info(f"Boletins encontrados: {len(boletins)}")
    for b in boletins:
        logger.info(f"  - {b['data']}: {b['caminho_audio']}")
    
    # Executar processamento
    resultado = processar_boletim(
        programa='GIRO',
        roteiro_inicial=roteiro,
        boletins_disponiveis=boletins
    )
    
    # Reportar resultado
    logger.info("=" * 60)
    logger.info("RESULTADO FINAL")
    logger.info("=" * 60)
    
    if resultado['sucesso']:
        logger.info("✅ Processamento CONCLUÍDO com sucesso!")
        logger.info(f"Boletins processados: {len(resultado['boletins_processados'])}")
    else:
        logger.error("❌ Processamento FALHOU")
        logger.error(f"Erros: {resultado['erros']}")
    
    if resultado['avisos']:
        logger.warning(f"Avisos: {resultado['avisos']}")
    
    # Salvar relatório
    relatorio_path = Path(roteiro['saida']['diretorio']) / f"relatorio_giro_{roteiro['codigo']}.json"
    relatorio_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(relatorio_path, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Relatório salvo em: {relatorio_path}")
    
    return 0 if resultado['sucesso'] else 1


if __name__ == '__main__':
    exit(main())
