#!/usr/bin/env python3
"""Wrapper do dispatcher: reinicia automaticamente quando morre.
O estado persiste, entao cada execucao continua de onde parou.
"""
import subprocess, sys, os, time, json
from pathlib import Path
from datetime import datetime

E = Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")
log_file = E / "logs" / "dispatcher_wrapper.log"
heartbeat_file = E / "logs" / "heartbeat_wrapper.json"

def contar_completos():
    estado_dir = E / "data" / "processed" / "PRODUCAO_2026" / "estado_por_arquivo"
    alvos = [str(n) for n in list(range(1909, 1927)) + list(range(1936, 1945))]
    njuds = {}
    for f in estado_dir.glob("*.json"):
        try:
            d = json.loads(f.read_text())
            n = d.get("njud", "").replace("NJUD ", "")
            s = d.get("status", "?")
            njuds.setdefault(n, []).append(s)
        except:
            pass
    return sum(1 for n in alvos if njuds.get(n, []).count("OK") >= 4)

def main():
    with open(log_file, "w") as log:
        ciclo = 0
        while True:
            ciclo += 1
            agora = datetime.now().strftime("%H:%M:%S")
            completos_antes = contar_completos()
            
            log.write(f"\n[{agora}] CICLO {ciclo}: iniciando dispatcher (completos: {completos_antes}/27)\n")
            log.flush()
            
            with open(heartbeat_file, "w") as f:
                json.dump({"status": "rodando", "ciclo": ciclo, "completos": completos_antes, "timestamp": agora}, f)
            
            # Rodar dispatcher
            env = os.environ.copy()
            env["PYTHONPATH"] = str(E / "src")
            env["MKL_NUM_THREADS"] = "1"
            env["OMP_NUM_THREADS"] = "1"
            
            proc = subprocess.Popen(
                ["python", str(E / "src" / "pipeline" / "dispatcher.py"),
                 str(E / "JORNAIS" / "ALVO"),
                 str(E / "data" / "processed" / "PRODUCAO_2026"),
                 "--max-workers", "1"],
                cwd=str(E), env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            
            # Aguardar o processo terminar
            proc.wait()
            
            completos_depois = contar_completos()
            log.write(f"[{agora}] CICLO {ciclo}: dispatcher morreu (exit={proc.returncode}). Completos: {completos_depois}/27\n")
            log.flush()
            
            # Verificar se terminou
            if completos_depois >= 25:  # 25 porque 1945 e 1946 nao tem fonte
                log.write("CONCLUIDO!\n")
                with open(heartbeat_file, "w") as f:
                    json.dump({"status": "concluido", "completos": completos_depois}, f)
                break
            
            # Aguardar antes de reiniciar
            time.sleep(10)

if __name__ == "__main__":
    main()
