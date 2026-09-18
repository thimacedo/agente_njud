#!/usr/bin/env python3
"""
Processador serial para NJUD (versão modularizada).
Herda de processor_v3.py — usa settings namespaced do NJUD.

Fluxo:
    1. Carrega modelo Whisper
    2. Processa cada MP3 de NJUD alvo
    3. Gera heartbeat em logs/njud/heartbeat.json
    4. Registra resultados em estado_por_arquivo/
"""
from __future__ import annotations

import gc
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from config.njud import settings

# Caminhos namespaced
TEMP_PASTA = settings.BASE_DIR / "JORNAIS" / "AGOSTO"
SAIDA = settings.BASE_DIR / "data" / "processed" / "PRODUCAO_2026"
ESTADO_DIR = SAIDA / "estado_por_arquivo"
HEARTBEAT_FILE = settings.LOGS_DIR_NJUD / "heartbeat.json"
LOG_DIR = settings.LOGS_DIR_NJUD / "proc_v3"

# Garante diretórios
LOG_DIR.mkdir(parents=True, exist_ok=True)
ESTADO_DIR.mkdir(parents=True, exist_ok=True)


def heartbeat(status: str, progresso: str) -> None:
    """Grava estado atual do processador em JSON (logs/njud/heartbeat.json)."""
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "pid": os.getpid(),
            "status": status,
            "progresso": progresso,
            "timestamp": datetime.now().isoformat(),
        }, f)


def main() -> int:
    """Entry point principal."""
    # Caminho base
    BASE_DIR = settings.BASE_DIR
    sys.path.insert(0, str(BASE_DIR / "src"))

    from divisor_boletins.audio import processar_arquivo, carregar_modelo
    from divisor_boletins.log import LogPipeline

    # Heartbeat inicial
    heartbeat("carregando", "0/0")
    print("Carregando modelo Whisper tiny...")

    modelo = carregar_modelo()
    logger = LogPipeline(log_dir=str(LOG_DIR))
    print("Modelo carregado.")

    # Listar apenas NJUDs alvo
    alvos = [str(n) for n in list(range(1909, 1927)) + list(range(1936, 1945))]
    mp3s: list[Path] = []

    if not TEMP_PASTA.exists():
        print(f"ERRO: pasta de entrada não existe: {TEMP_PASTA}")
        return 1

    for njud_dir in sorted(TEMP_PASTA.iterdir()):
        if njud_dir.is_dir() and any(
            njud_dir.name == f"NJUD {n}" for n in alvos
        ):
            mp3s.extend(sorted(njud_dir.glob("*.mp3")))

    print(f"Arquivos para processar: {len(mp3s)}")

    heartbeat("rodando", f"0/{len(mp3s)}")

    ok_count = 0
    erro_count = 0

    for i, mp3_path in enumerate(mp3s):
        try:
            result = processar_arquivo(str(mp3_path), str(SAIDA), modelo, logger)
            if result:
                ok_count += 1
            else:
                erro_count += 1
        except Exception as e:
            erro_count += 1
            print(f"  ERRO em {mp3_path.name}: {e}")

        if (i + 1) % 10 == 0:
            heartbeat("rodando", f"{ok_count}/{len(mp3s)}")
            print(f"[{i+1}/{len(mp3s)}] {ok_count} OK, {erro_count} ERRO")
            gc.collect()

    heartbeat("concluido", f"{ok_count}/{len(mp3s)}")
    print(f"FINAL: {ok_count} OK, {erro_count} ERRO")

    # Finaliza log de estado
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / "processamento_final.txt", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] OK={ok_count}, ERRO={erro_count}, TOTAL={len(mp3s)}\n")

    return 0 if erro_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
