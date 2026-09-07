#!/usr/bin/env python3
"""Processador serial com heartbeat.
Rode via: python scripts_pipeline/processor_com_heartbeat.py
Monitore: logs/heartbeat.json
"""
import sys, os, json, time, gc
from pathlib import Path
from datetime import datetime

E = Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")
sys.path.insert(0, str(E / "src"))

from divisor_boletins.audio import processar_arquivo, carregar_modelo
from divisor_boletins.log import LogPipeline

# Config
temp_pasta = E / "JORNAIS_JUL_AGO"
saida = E / "data" / "processed" / "PRODUCAO_2026"
estado_dir = saida / "estado_por_arquivo"
heartbeat_file = E / "logs" / "heartbeat.json"
log_file = E / "logs" / "processor_direto.log"

def heartbeat(status, progresso, pid):
    with open(heartbeat_file, "w") as f:
        json.dump({
            "pid": pid,
            "status": status,
            "progresso": progresso,
            "timestamp": datetime.now().isoformat()
        }, f)

# Carregar modelo
heartbeat("carregando", "0/0", os.getpid())
print("Carregando modelo Whisper tiny...")

modelo = carregar_modelo()
logger = LogPipeline(log_dir=str(E / "logs" / "processor_direto"))
print("Modelo carregado.")

# Listar arquivos
mp3s = sorted(temp_pasta.rglob("*.mp3"))

# Filtrar pendentes
feitos = set()
for f in estado_dir.glob("*.json"):
    try:
        d = json.loads(f.read_text())
        if d.get("status") == "OK":
            feitos.add(d.get("arquivo", ""))
            feitos.add(Path(d.get("arquivo", "")).name)
    except:
        pass

pendentes = [f for f in mp3s if str(f) not in feitos and f.name not in feitos]
print(f"Pendentes: {len(pendentes)}")

ok_count = 0
erro_count = 0

heartbeat("rodando", f"0/{len(pendentes)}", os.getpid())

for i, mp3_path in enumerate(pendentes):
    try:
        result = processar_arquivo(str(mp3_path), str(saida), modelo, logger)
        if result:
            ok_count += 1
        else:
            erro_count += 1
    except Exception as e:
        erro_count += 1
        with open(log_file, "a") as log:
            log.write(f"ERRO: {mp3_path.name}: {e}\n")
    
    heartbeat("rodando", f"{ok_count}/{len(pendentes)}", os.getpid())
    
    if (i + 1) % 5 == 0:
        gc.collect()

heartbeat("concluido", f"{ok_count}/{len(pendentes)}", os.getpid())
print(f"FINAL: {ok_count} OK, {erro_count} ERRO")
