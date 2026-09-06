#!/usr/bin/env python3
"""Processa 1 arquivo por vez da pasta JORNAIS_JUL_AGO, liberando memoria entre cada um."""
import subprocess, sys, os, json, time
from pathlib import Path

E = Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")
temp_pasta = E / "JORNAIS_JUL_AGO"
estado_dir = E / "data" / "processed" / "PRODUCAO_2026" / "estado_por_arquivo"
log_file = E / "logs" / "serial_jul_ago.log"

mp3s = sorted(temp_pasta.rglob("*.mp3"))

with open(log_file, "w") as log:
    log.write(f"Total mp3s: {len(mp3s)}\n")
    log.flush()

    ok_count = 0
    erro_count = 0

    for i, mp3_path in enumerate(mp3s):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(E / "src")
        env["MKL_NUM_THREADS"] = "1"
        env["OMP_NUM_THREADS"] = "1"
        env["OPENBLAS_NUM_THREADS"] = "1"

        cmd = [
            sys.executable, "-c",
            f"""
import sys, json, gc
sys.path.insert(0, 'src')
from pathlib import Path
from divisor_boletins.audio import processar_arquivo

caminho = r'{mp3_path}'
saida = r'{E / "data" / "processed" / "PRODUCAO_2026"}'

try:
    result = processar_arquivo(caminho, saida)
    print('OK' if result else 'FAIL')
    gc.collect()
except Exception as e:
    print(f'ERRO: {{e}}')
"""
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
            output = result.stdout.strip()

            if "OK" in output and "ERRO" not in output:
                ok_count += 1
                status = "OK"
            else:
                erro_count += 1
                status = f"ERRO: {output[:80]}"

            log.write(f"[{i+1}/{len(mp3s)}] {mp3_path.parent.name}/{mp3_path.name}: {status}\n")
            log.flush()

        except subprocess.TimeoutExpired:
            erro_count += 1
            log.write(f"[{i+1}/{len(mp3s)}] {mp3_path.name}: TIMEOUT\n")
            log.flush()
        except Exception as e:
            erro_count += 1
            log.write(f"[{i+1}/{len(mp3s)}] {mp3_path.name}: {e}\n")
            log.flush()

        if (i + 1) % 10 == 0:
            log.write(f"--- PROGRESSO: {ok_count} OK, {erro_count} ERRO de {i+1} ---\n")
            log.flush()

    log.write(f"\n=== FINAL: {ok_count} OK, {erro_count} ERRO ===\n")

print(f"Concluido: {ok_count} OK, {erro_count} ERRO")
