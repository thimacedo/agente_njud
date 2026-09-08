#!/usr/bin/env python3
"""
Executor Genérico do GIRO.
Lê um arquivo JSON de planejamento e executa o pipeline unificado.

Uso:
    PYTHONPATH=src python scripts_pipeline/giro/executor_giro.py config/planejamento_2026/giro_0101.json
"""
import sys
import os
import json
import logging

# Setup path correto para o projeto
# O workspace tem 'core/' e 'src/' na raiz
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT_DIR)  # Adiciona /workspace ao path

from core.processamento.processar_boletim import processar_boletim, validar_gate_boletins
from src.divisor_boletins.audio import processar_arquivo

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def carregar_planejamento(caminho_json):
    if not os.path.exists(caminho_json):
        raise FileNotFoundError(f"Arquivo de planejamento não encontrado: {caminho_json}")
    
    with open(caminho_json, 'r', encoding='utf-8') as f:
        return json.load(f)

def obter_funcao_corte(parametros):
    """
    Retorna a função de corte adequada baseada nos parâmetros do JSON.
    Para o GIRO, usamos o processo padrão com estratégia de silêncio.
    """
    if parametros.get('corte_por_silencio'):
        logger.info("Usando estratégia de corte por silêncio.")
        # Retorna uma função que chama processar_arquivo com estrategia='silencio'
        return lambda caminho_audio, saida: processar_arquivo(caminho_audio, saida, estrategia='silencio')
    else:
        logger.info("Usando estratégia de corte padrão (vinheta/VAD).")
        return lambda caminho_audio, saida: processar_arquivo(caminho_audio, saida, estrategia='padrao')

def main():
    if len(sys.argv) != 2:
        print("Uso: python scripts_pipeline/giro/executor_giro.py <caminho_para_json>")
        print("Ex: python scripts_pipeline/giro/executor_giro.py config/planejamento_2026/giro_0101.json")
        sys.exit(1)
    
    caminho_json = sys.argv[1]
    
    try:
        # 1. Carregar Configuração
        logger.info(f"Carregando planejamento: {caminho_json}")
        config = carregar_planejamento(caminho_json)
        
        codigo = config['codigo']
        programa = config['programa']
        janela = config['janela_coleta']
        params = config['parametros']
        
        logger.info(f"Programa: {programa} {codigo}")
        logger.info(f"Período: {janela['inicio']} até {janela['fim']} ({janela['dias_totais']} dias)")
        
        # 2. Validar Gate Mínimo
        gate_valido, msg = validar_gate_boletins(janela['dias_totais'], params['boletins_minimos'])
        if not gate_valido:
            logger.error(f"ERRO CRÍTICO: {msg}. Abortando.")
            sys.exit(1)
            
        # 3. Preparar Pipeline
        cortar_fn = obter_funcao_corte(params)
        
        # Configurar contexto de auditoria baseado no JSON
        config_pipeline = {
            'programa': programa,
            'codigo': codigo,
            'data_exibicao': config['data_exibicao'],
            'fallback_permitido': params.get('fallback_audio_completo', False),
            'usar_demucs': params.get('usar_demucs', False),
            'duracao_silencio': params.get('duracao_silencio_segundos', 1.0)
        }
        
        # 4. Executar
        # Nota: processar_boletim precisa saber ONDE estão os arquivos de áudio brutos.
        # Assumindo estrutura: data_brutos/{data}/ ou similar
        
        logger.info("INICIANDO PROCESSAMENTO...")
        logger.info(f"[Simulação] Buscando boletins no período: {janela['inicio']} a {janela['fim']}")
        
        # Chamada real (descomentar quando os dados existirem e a assinatura estiver correta):
        # resultados = processar_boletim(
        #     programa=programa,
        #     periodo=(janela['inicio'], janela['fim']),
        #     cortar_fn=cortar_fn,
        #     config=config_pipeline
        # )
        
        logger.info("Pipeline finalizado com sucesso (simulação).")
        logger.info(f"Próximo passo: Verificar output/{programa}_{codigo}/")
        
    except Exception as e:
        logger.error(f"Falha na execução: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
