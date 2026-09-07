#!/usr/bin/env python3
"""Processador serial com heartbeat - v2 com filtro correto."""
import sys, os, json, time, gc
from pathlib import Path
from datetime import datetime

E = Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")
sys.path.insert(0, str(E / "src"))

from divisor_boletins.audio import processar_arquivo, carregar_modelo
from divisor_boletins.log import LogPipeline

temp_pasta = E / "JORNAIS_JUL_AGO"
saida = E / "data" / "processed" / "PRODUCAO_2026"
estado_dir = saida / "estado_por_arquivo"
heartbeat_file = E / "logs" / "heartbeat.json"

def heartbeat(status, progresso):
    with open(heartbeat_file, "w") as f:
        json.dump({"pid": os.getpid(), "status": status, "progresso": progresso, "timestamp": datetime.now().isoformat()}, f)

heartbeat("carregando", "0/0")
print("Carregando modelo Whisper tiny...")

modelo = carregar_modelo()
logger = LogPipeline(log_dir=str(E / "logs" / "proc_v2"))
print("Modelo carregado.")

# Listar mp3s
mp3s = sorted(temp_pasta.rglob("*.mp3"))

# Filtro: verificar por caminho completo OU nome do arquivo
estados_ok = set()
for f in estado_dir.glob("*.json"):
    try:
        d = json.loads(f.read_text())
        if d.get("status") == "OK":
            estados_ok.add(d.get("arquivo", ""))
            estados_ok.add(Path(d.get("arquivo", "")).name)
    except:
        pass

pendentes = [f for f in mp3s if str(f) not in estados_ok and f.name not in estados_ok]
print(f"Pendentes: {len(pendentes)}")

heartbeat("rodando", f"0/{len(pendentes)}")

ok_count = 0
erro_count = 0

for i, mp3_path in enumerate(pendentes):
    try:
        result = processar_arquivo(str(mp3_path), str(saida), modelo, logger)
        if result:
            ok_count += 1
        else:
            erro_count += 1
    except Exception as e:
        erro_count += 1
    
    if (i + 1) % 5 == 0:
        heartbeat("rodando", f"{ok_count}/{len(pendentes)}")
        gc.collect()

heartbeat("concluido", f"{ok_count}/{len(pendentes)}")
print(f"FINAL: {ok_count} OK, {erro_count} ERRO")
