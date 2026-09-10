#!/usr/bin/env python3
"""Executor serial dos GIROS de janeiro — modelo carregado 1x, processa em sequência."""
import sys, os, json, logging, gc
from pathlib import Path
from datetime import date

# Forçar vars de memória OBRIGATÓRIAS
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_THREADING_LAYER'] = 'GNU'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['TORCH_NUM_THREADS'] = '1'

ROOT = Path('E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR')
sys.path.insert(0, str(ROOT / 'src'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('giro_jan')

from core.processamento.processar_boletim import ConfigPrograma, processar_lote

PLAN_DIR = ROOT / 'config' / 'planejamento_2026'
BOLETINS_DIR = ROOT / 'JORNAIS'
SAIDA_DIR = ROOT / 'data' / 'processed' / 'PRODUCAO_2026'

programas = ['0101', '0102', '0104']  # 0103 invalidado (2 boletins < 4 mínimo)

for codigo in programas:
    json_path = PLAN_DIR / f'giro_{codigo}.json'
    if not json_path.exists():
        log.error('JSON não encontrado: %s', json_path)
        continue

    log.info('='*60)
    cfg = json.loads(json_path.read_text(encoding='utf-8'))
    log.info('Programa: GIRO %s | Exibição: %s', codigo, cfg['data_exibicao'])
    log.info('Janela: %s → %s', cfg['janela_coleta']['inicio'], cfg['janela_coleta']['fim'])

    config = ConfigPrograma(
        nome='giro',
        pasta_boletins=BOLETINS_DIR,
        pasta_saida=SAIDA_DIR,
        pasta_estado=SAIDA_DIR / 'estado_por_arquivo',
        pasta_log=SAIDA_DIR / '_logs',
        modelo_whisper='tiny',
        compute_type='int8',
        roteiro_corte='GIRO_CABEÇA_CORPO',
        minimo_boletins_para_montar=cfg.get('parametros', {}).get('boletins_minimos', 4),
        usar_separacao_stems=cfg.get('parametros', {}).get('usar_separacao_stems', False),
        data_inicio_coleta=cfg['janela_coleta']['inicio'],
        data_fim_coleta=cfg['janela_coleta']['fim'],
    )

    log.info('Iniciando processamento...')
    try:
        resultado = processar_lote(config)
        log.info('Concluído %s: status=%s, notas=%s', codigo, resultado.get('status'), resultado.get('notas_geradas'))
        gc.collect()
    except Exception as e:
        log.error('Erro em %s: %s', codigo, e)
        import traceback
        traceback.print_exc()
    gc.collect()

log.info('='*60)
log.info('GIRO janeiro concluído.')
