#!/usr/bin/env python3
"""Inicia o dispatcher com monitor, garantindo processo único.

REGRA DE OPERAÇÃO (2026-08-24): nunca deixar dois dispatchers ou dois
monitores rodando. Este script mata qualquer instância anterior
(pipeline/dispatcher.py / pipeline/monitor.py / orchestration/safe_runner.py)
antes de iniciar a nova. Uso:

    python iniciar_ciclo.py <pasta_boletins> <pasta_saida> [--max-workers N]
    python iniciar_ciclo.py --so-monitor <pasta_saida>
"""
import argparse
import os
import subprocess
import sys
import time

import psutil

ALVOS = ("pipeline/dispatcher.py", "pipeline/monitor.py",
         "orchestration/safe_runner.py")


def matar_instancias_anteriores(matar_monitor: bool):
    """Mata processos Python cuja linha de comando contenha um dos alvos."""
    eu = os.getpid()
    mortos = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.info["pid"] == eu:
                continue
            cmd = " ".join(proc.info["cmdline"] or [])
            if not any(alvo in cmd for alvo in ALVOS):
                continue
            eh_monitor = "pipeline/monitor.py" in cmd or "monitor_tempo_real.py" in cmd
            if eh_monitor and not matar_monitor:
                continue
            proc.terminate()
            mortos.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if mortos:
        _, vivos = psutil.wait_procs(
            [psutil.Process(p) for p in mortos if psutil.pid_exists(p)], timeout=5)
        for p in vivos:
            p.kill()
    return mortos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pasta_boletins", nargs="?")
    parser.add_argument("pasta_saida")
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--so-monitor", action="store_true",
                        help="Só inicia o monitor (mata monitores antigos).")
    args = parser.parse_args()

    src = os.path.dirname(os.path.abspath(__file__))
    py = sys.executable

    # Regra: matar instâncias antigas ANTES de iniciar a nova
    antigos = matar_instancias_anteriores(matar_monitor=True)
    if antigos:
        print(f"[iniciar] {len(antigos)} processo(s) antigo(s) finalizado(s): {antigos}")
        time.sleep(2)

    if args.so_monitor:
        subprocess.run([py, os.path.join(src, "pipeline", "monitor.py"),
                        args.pasta_saida])
        return

    subprocess.run([
        py, os.path.join(src, "pipeline", "dispatcher.py"),
        args.pasta_boletins, args.pasta_saida,
    ] + (["--max-workers", str(args.max_workers)] if args.max_workers else []))


if __name__ == "__main__":
    main()
