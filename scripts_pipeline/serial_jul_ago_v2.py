#!/usr/bin/env python3
"""Processa 1 arquivo por vez, carregando modelo 1x e reutilizando."""
import sys, os, json, gc, time
from pathlib import Path

E = Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")
sys.path.insert(0, str(E / "src"))

from divisor_boletins.audio import processar_arquivo, carregar_modelo
from divisor_boletins.log import LogPipeline

temp_pasta = E / "JORNAIS" / "ALVO"
saida = E / "data" / "processed" / "PRODUCAO_2026"
log_file = E / "logs" / "serial_jul_ago_v2.log"

mp3s = sorted(temp_pasta.rglob("*.mp3"))

# Carregar modelo 1x
print("Carregando modelo Whisper tiny...")
modelo = carregar_modelo()
logger = LogPipeline(log_dir=str(E / "logs" / "serial_jul_ago_v2"))
print("Modelo carregado.")

with open(log_file, "w") as log:
    log.write(f"Total mp3s: {len(mp3s)}\n")
    log.flush()

    ok_count = 0
    erro_count = 0

    for i, mp3_path in enumerate(mp3s):
        try:
            result = processar_arquivo(str(mp3_path), str(saida), modelo, logger, apply=True)
            if result:
                ok_count += 1
                status = "OK"
            else:
                erro_count += 1
                status = "FAIL"
        except Exception as e:
            erro_count += 1
            status = f"ERRO: {str(e)[:80]}"

        log.write(f"[{i+1}/{len(mp3s)}] {mp3_path.parent.name}/{mp3_path.name}: {status}\n")
        log.flush()

        if (i + 1) % 10 == 0:
            log.write(f"--- PROGRESSO: {ok_count} OK, {erro_count} ERRO de {i+1} ---\n")
            log.flush()
            gc.collect()

    log.write(f"\n=== FINAL: {ok_count} OK, {erro_count} ERRO ===\n")

print(f"Concluido: {ok_count} OK, {erro_count} ERRO")
