#!/usr/bin/env python
"""
ETAPA 2: Montagem dos jornais.
Itera sobre JORNAIS_DIVIDIDOS/ e monta cada NJUD com 4 cortes (_CABECA/_CORPO).
Gera logs em logs/montagem_<timestamp>.log
"""
from __future__ import annotations
import os
import sys
from datetime import datetime
from pathlib import Path

# Garante que o src/ está no path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
os.chdir(str(Path(__file__).resolve().parent.parent))  # muda para raiz do projeto

from divisor_boletins.montagem import montar_jornal, montar_todos_jornais
from divisor_boletins.log import LogPipeline
from config.settings import settings

# Caminhos baseados nos settings
PASTA_ENTRADA = Path(settings.BASE_DIR) / 'data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS'
PASTA_SAIDA = Path(settings.JORNAIS_MONTADOS)     # data/output/JORNAIS_FINAL
LOGS_DIR = Path(settings.LOGS_DIR)           # logs/

# Criar logs dir se não existir
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Timestamp para o log
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = LOGS_DIR / f"montagem_{timestamp}.log"

logger = LogPipeline(log_dir=str(LOGS_DIR))

print(f"=" * 70)
print(f"ETAPA 2: MONTAGEM DOS JORNais")
print(f"Entrada : {PASTA_ENTRADA}")
print(f"Saida   : {PASTA_SAIDA}")
print(f"Log     : {log_path}")
print(f"=" * 70)

# Contar NJUDs com cortes completos
from collections import Counter
total_njuds = 0
njuds_completos = 0
njuds_parciais = 0
njuds_vazios = 0

for njud_dir in sorted(PASTA_ENTRADA.iterdir()):
    if not njud_dir.is_dir():
        continue
    total_njuds += 1
    cabecas = list(njud_dir.glob('*_CABECA.mp3'))
    corpos = list(njud_dir.glob('*_CORPO.mp3'))
    if len(cabecas) == 0 and len(corpos) == 0:
        njuds_vazios += 1
    elif len(cabecas) >= 2 and len(corpos) >= 2:
        njuds_completos += 1
    else:
        njuds_parciais += 1

print(f"\nEstado atual de JORNAIS_DIVIDIDOS/:")
print(f"  Total de pastas NJUD  : {total_njuds}")
print(f"  Completos (4+ cortes) : {njuds_completos}")
print(f"  Parciais (2-3 cortes) : {njuds_parciais}")
print(f"  Vazios (0 cortes)     : {njuds_vazios}")

logger.info("pipeline", "=" * 60)
logger.info("pipeline", "ETAPA 2: MONTAGEM DOS JORNais")
logger.info("pipeline", f"Entrada: {PASTA_ENTRADA}")
logger.info("pipeline", f"Saida: {PASTA_SAIDA}")
logger.info("pipeline", f"Total NJUDs: {total_njuds}")
logger.info("pipeline", f"Completos: {njuds_completos}, Parciais: {njuds_parciais}, Vazios: {njuds_vazios}")

# Executar montagem
print(f"\nIniciando montagem...")
logger.info("pipeline", "Iniciando montagem...")

resultados = montar_todos_jornais(
    pasta_entrada=PASTA_ENTRADA,
    pasta_saida=PASTA_SAIDA,
    logger=logger,
    intercalar=settings.INTERCALAR_VOCES,
)

print(f"\nMontagem concluída!")
print(f"  Jornais montados: {len(resultados)}")
logger.info("pipeline", f"Montagem concluída: {len(resultados)} jornais gerados")

for r in resultados:
    size_kb = r.stat().st_size / 1024
    duracao = round(r.stat().st_size / (128 * 1000 / 8), 1)  # estimativa para 128kbps
    print(f"  - {r.name} ({size_kb:.0f} KB) | {r}")
    logger.info("pipeline", f"  {r.name} ({size_kb:.0f} KB)")

# Resumo final
print(f"\n" + "=" * 70)
print(f"RESUMO:")
print(f"  NJUDs montados : {len(resultados)}")
print(f"  Log            : {log_path}")
print(f"  Output         : {PASTA_SAIDA}/")
print(f"=" * 70)
logger.info("pipeline", f"RESUMO: {len(resultados)} jornais montados. Log: {log_path}")
