#!/usr/bin/env python3
"""Processador serial com heartbeat - v3 para JORNAIS/AGOSTO/"""
import sys, os, json, time, gc
from pathlib import Path
from datetime import datetime

E = Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")
sys.path.insert(0, str(E / "src"))

from divisor_boletins.audio import processar_arquivo, carregar_modelo
from divisor_boletins.log import LogPipeline

temp_pasta = E / "JORNAIS" / "AGOSTO"
saida = E / "data" / "processed" / "PRODUCAO_2026"
estado_dir = saida / "estado_por_arquivo"
heartbeat_file = E / "logs" / "heartbeat.json"

def heartbeat(status, progresso):
    with open(heartbeat_file, "w") as f:
        json.dump({"pid": os.getpid(), "status": status, "progresso": progresso, "timestamp": datetime.now().isoformat()}, f)

heartbeat("carregando", "0/0")
print("Carregando modelo Whisper tiny...")

modelo = carregar_modelo()
logger = LogPipeline(log_dir=str(E / "logs" / "proc_v3"))
print("Modelo carregado.")

# Listar apenas NJUDs alvo
alvos = [str(n) for n in list(range(1909, 1927)) + list(range(1936, 1945))]
mp3s = []
for njud_dir in sorted(temp_pasta.iterdir()):
    if njud_dir.is_dir() and any(njud_dir.name == f"NJUD {n}" for n in list(range(1909,1927)) + list(range(1936,1945))):
        mp3s.extend(sorted(njud_dir.glob("*.mp3")))

print(f"Arquivos para processar: {len(mp3s)}")

heartbeat("rodando", f"0/{len(mp3s)}")

ok_count = 0
erro_count = 0

for i, mp3_path in enumerate(mp3s):
    try:
        result = processar_arquivo(str(mp3_path), str(saida), modelo, logger)
        if result:
            ok_count += 1
        else:
            erro_count += 1
    except Exception as e:
        erro_count += 1
    
    if (i + 1) % 10 == 0:
        heartbeat("rodando", f"{ok_count}/{len(mp3s)}")
        print(f"[{i+1}/{len(mp3s)}] {ok_count} OK, {erro_count} ERRO")
        gc.collect()

heartbeat("concluido", f"{ok_count}/{len(mp3s)}")
print(f"FINAL: {ok_count} OK, {erro_count} ERRO")
