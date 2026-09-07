#!/usr/bin/env python3
"""Processa 1 NJUD por vez via subprocess. Cada NJUD eh um processo separado que morre apos terminar."""
import subprocess, sys, os, json, time
from pathlib import Path
from datetime import datetime

E = Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")
sys.path.insert(0, str(E / "src"))

pasta_alvo = E / "JORNAIS" / "ALVO"
saida = E / "data" / "processed" / "PRODUCAO_2026"
estado_dir = saida / "estado_por_arquivo"
log_file = E / "logs" / "njud_por_njud.log"
heartbeat_file = E / "logs" / "heartbeat_njud.json"

alvos = [str(n) for n in list(range(1909, 1927)) + list(range(1936, 1945))]

def heartbeat(njud, status, progresso):
    with open(heartbeat_file, "w") as f:
        json.dump({"njud": njud, "status": status, "progresso": progresso, "timestamp": datetime.now().isoformat()}, f)

with open(log_file, "w") as log:
    log.write("=== PROCESSAMENTO NJUD POR NJUD ===\n")
    log.flush()
    
    for i, njud in enumerate(alvos):
        njud_pasta = pasta_alvo / f"NJUD {njud}"
        if not njud_pasta.exists():
            log.write(f"NJUD {njud}: pasta nao existe, pulando\n")
            log.flush()
            continue
        
        mp3s = list(njud_pasta.glob("*.mp3"))
        if not mp3s:
            log.write(f"NJUD {njud}: sem mp3s, pulando\n")
            log.flush()
            continue
        
        # Verificar se ja esta completo
        ok_count = 0
        for f in estado_dir.glob("*.json"):
            try:
                d = json.loads(f.read_text())
                if d.get("njud") == f"NJUD {njud}" and d.get("status") == "OK":
                    ok_count += 1
            except:
                pass
        
        if ok_count >= 4:
            log.write(f"NJUD {njud}: ja completo ({ok_count} OK), pulando\n")
            log.flush()
            continue
        
        log.write(f"\n[{i+1}/{len(alvos)}] NJUD {njud}: processando {len(mp3s)} mp3s...\n")
        log.flush()
        heartbeat(njud, "processando", f"0/{len(mp3s)}")
        
        # Script que processa todos os mp3s de 1 NJUD
        script = f'''
import sys, os, json, gc
sys.path.insert(0, r"{E / 'src'}")
from pathlib import Path
from divisor_boletins.audio import processar_arquivo, carregar_modelo
from divisor_boletins.log import LogPipeline

modelo = carregar_modelo()
logger = LogPipeline(log_dir=r"{E / 'logs' / f'njud_{njud}'}")
mp3s = {[[str(f)] for f in mp3s]}
saida = r"{saida}"

ok = 0
erro = 0
for mp3 in mp3s:
    try:
        result = processar_arquivo(mp3, saida, modelo, logger)
        if result:
            ok += 1
        else:
            erro += 1
    except Exception as e:
        erro += 1
    gc.collect()

print(f"NJUD {njud}: {{ok}} OK, {{erro}} ERRO")
'''
        
        env = os.environ.copy()
        env["PYTHONPATH"] = str(E / "src")
        env["MKL_NUM_THREADS"] = "1"
        env["OMP_NUM_THREADS"] = "1"
        env["OPENBLAS_NUM_THREADS"] = "1"
        
        # Deletar estados antigos deste NJUD para reprocessar
        for f in estado_dir.glob("*.json"):
            try:
                d = json.loads(f.read_text())
                if d.get("njud") == f"NJUD {njud}":
                    f.unlink()
            except:
                pass
        
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(E), env=env,
            capture_output=True, text=True, timeout=600
        )
        
        output = result.stdout.strip()
        log.write(f"  {output}\n")
        log.flush()
        
        # Verificar resultado
        ok_count = 0
        for f in estado_dir.glob("*.json"):
            try:
                d = json.loads(f.read_text())
                if d.get("njud") == f"NJUD {njud}" and d.get("status") == "OK":
                    ok_count += 1
            except:
                pass
        
        if ok_count >= 4:
            heartbeat(njud, "concluido", f"{ok_count}/{len(mp3s)}")
            log.write(f"  -> NJUD {njud}: SELLO OK ({ok_count} arquivos OK)\n")
        else:
            heartbeat(njud, "parcial", f"{ok_count}/{len(mp3s)}")
            log.write(f"  -> NJUD {njud}: PARCIAL ({ok_count} arquivos OK)\n")
        log.flush()

log.write("\n=== FINAL ===\n")
print("Concluido!")
