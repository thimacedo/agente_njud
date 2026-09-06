#!/usr/bin/env python
"""
ETAPA 2 (continuação): Montar os NJUDs faltantes.
Itera sobre JORNAIS_DIVIDIDOS/ e monta apenas os NJUDs que ainda não têm
MP3 em JORNAIS_FINAL/.
"""
from __future__ import annotations
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Garante que o src/ está no path e muda para raiz do projeto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
os.chdir(str(Path(__file__).resolve().parent.parent))

from divisor_boletins.montagem import montar_jornal
from divisor_boletins.log import LogPipeline
from config.settings import settings

# Caminhos
PASTA_ENTRADA = Path(settings.BASE_DIR) / 'data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS'
PASTA_SAIDA = Path(settings.JORNAIS_MONTADOS)
LOGS_DIR = Path(settings.LOGS_DIR)
PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = LOGS_DIR / f"montagem_continuacao_{timestamp}.log"
logger = LogPipeline(log_dir=str(LOGS_DIR))

print("=" * 70)
print("ETAPA 2 (continuação): Montagem dos NJUDs faltantes")
print(f"Entrada : {PASTA_ENTRADA}")
print(f"Saida   : {PASTA_SAIDA}")
print(f"Log     : {log_path}")
print("=" * 70)

# Já montados
mp3_existentes = set()
for m in PASTA_SAIDA.glob('*.mp3'):
    m_njud = re.search(r'NJUD_(\d+)', m.name)
    if m_njud:
        mp3_existentes.add(int(m_njud.group(1)))

# Identifica NJUDs faltantes
faltantes = []
for njud_dir in sorted(PASTA_ENTRADA.iterdir()):
    if not njud_dir.is_dir():
        continue
    cab = list(njud_dir.glob('*_CABECA.mp3'))
    cor = list(njud_dir.glob('*_CORPO.mp3'))
    if len(cab) >= 4 and len(cor) >= 4:
        m_njud = re.search(r'NJUD\s*(\d+)', njud_dir.name)
        if m_njud:
            njud_num = int(m_njud.group(1))
            if njud_num not in mp3_existentes:
                faltantes.append((njud_dir, njud_num))

print(f"\nNJUDs faltantes: {len(faltantes)}")
logger.info("pipeline", f"NJUDs faltantes para montar: {len(faltantes)}")

# Monta um a um
montados = 0
erros = 0
for njud_dir, njud_num in faltantes:
    print(f"\nMontando {njud_dir.name} (NJUD {njud_num})...")
    logger.info("pipeline", f"Montando {njud_dir.name} (NJUD {njud_num})")
    try:
        caminho = montar_jornal(
            njud_dir,
            PASTA_SAIDA,
            logger,
            nome_jornal=njud_dir.name,
            intercalar=settings.INTERCALAR_VOCES,
        )
        if caminho:
            size_mb = caminho.stat().st_size / (1024 * 1024)
            print(f"  OK: {caminho.name} ({size_mb:.1f} MB)")
            montados += 1
        else:
            print(f"  ERRADO: falha na montagem")
            logger.erro("pipeline", f"Falha ao montar: {njud_dir.name}")
            erros += 1
    except Exception as e:
        print(f"  ERRO: {e}")
        logger.erro("pipeline", f"Exceção ao montar {njud_dir.name}: {e}")
        erros += 1

print(f"\n{'=' * 70}")
print(f"RESUMO:")
print(f"  Montados: {montados}")
print(f"  Erros  : {erros}")
print(f"  Log    : {log_path}")
print(f"{'=' * 70}")
logger.info("pipeline", f"RESUMO: {montados} montados, {erros} erros. Log: {log_path}")
