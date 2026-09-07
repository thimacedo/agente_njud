#!/usr/bin/env python3
"""
Processamento serial via subprocess - 1 arquivo por processo.
Cada arquivo eh processado em um subprocesso separado para garantir
que a memoria seja totalmente liberada entre cada processamento.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PASTA_BASE = Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")
PASTA_BOLETINS = PASTA_BASE / "JORNAIS"
PASTA_SAIDA = PASTA_BASE / "data/processed/PRODUCAO_2026"
ESTADO_DIR = PASTA_SAIDA / "estado_por_arquivo"
PYTHON = sys.executable


def processar_uma(arquivo, njud, stem):
    """Processa um arquivo em um subprocesso separado."""
    script = f'''
import json, os, sys, traceback
sys.path.insert(0, r"{str(PASTA_BASE / 'src')}")

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["MKL_DISABLE_FAST_MM"] = "1"

import torch
torch.set_num_threads(1)
torch.set_num_interop_threads(1)

from pathlib import Path
from faster_whisper import WhisperModel
from divisor_boletins.audio import processar_arquivo
from divisor_boletins.log import LogPipeline
from audit.individual_cuts import analisar_par

arquivo = r"{arquivo}"
njud = "{njud}"
pasta_saida = r"{str(PASTA_SAIDA)}"
caminho_estado = Path(pasta_saida) / "estado_por_arquivo" / "{stem}.json"
pasta_cortes = Path(pasta_saida) / "JORNAIS_DIVIDIDOS"

# Verificar se ja esta OK
if caminho_estado.exists():
    try:
        d = json.loads(caminho_estado.read_text(encoding="utf-8"))
        if d.get("status") in ("OK", "ESGOTADO_ACEITO"):
            print("SKIP")
            sys.exit(0)
    except:
        pass

try:
    modelo = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=1)
    logger = LogPipeline(Path(pasta_saida) / "_logs")
    pasta_destino = pasta_cortes / njud

    resultado = processar_arquivo(arquivo, str(pasta_destino), modelo, logger, apply=True)
    if resultado is None:
        raise RuntimeError("processar_arquivo retornou None")
    
    cabeca = resultado.arquivo_cabeca
    corpo = resultado.arquivo_corpo
    
    audit_status, audit_motivos = analisar_par(cabeca, corpo, modelo)
    
    estado = {{
        "arquivo": arquivo,
        "njud": njud,
        "status": "OK" if audit_status == "OK" else "CORTADO",
        "cabeca": cabeca,
        "corpo": corpo,
        "audit_status": audit_status,
        "audit_motivos": audit_motivos,
    }}
    
    caminho_estado.parent.mkdir(parents=True, exist_ok=True)
    caminho_estado.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK")
except Exception as e:
    print(f"ERRO: {{e}}")
    try:
        caminho_estado.parent.mkdir(parents=True, exist_ok=True)
        caminho_estado.write_text(json.dumps({{
            "arquivo": arquivo, "njud": njud, "status": "ERRO", "erro": str(e)
        }}, ensure_ascii=False, indent=2), encoding="utf-8")
    except:
        pass
    sys.exit(1)
'''
    result = subprocess.run(
        [PYTHON, "-c", script],
        capture_output=True, text=True, timeout=300,
        env={**os.environ, "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "MKL_DISABLE_FAST_MM": "1"},
        cwd=str(PASTA_BASE),
    )
    return result.stdout.strip(), result.stderr.strip()


def main():
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    
    # Listar todos os MP3s
    tarefas = []
    for arq in sorted(PASTA_BOLETINS.rglob("*.mp3")):
        njud = arq.parent.name
        stem = arq.stem
        caminho_estado = ESTADO_DIR / f"{stem}.json"
        if caminho_estado.exists():
            try:
                d = json.loads(caminho_estado.read_text(encoding="utf-8"))
                if d.get("status") in ("OK", "ESGOTADO_ACEITO"):
                    continue
            except:
                pass
        tarefas.append({"arquivo": str(arq), "njud": njud, "stem": stem})

    print(f"[subprocess] {len(tarefas)} arquivo(s) para processar.")
    if not tarefas:
        print("[subprocess] Nada a fazer.")
        return

    ok_count = 0
    erro_count = 0

    for idx, tarefa in enumerate(tarefas):
        arquivo = tarefa["arquivo"]
        njud = tarefa["njud"]
        stem = tarefa["stem"]
        
        print(f"[{idx+1}/{len(tarefas)}] {Path(arquivo).name}...", end=" ", flush=True)
        
        try:
            stdout, stderr = processar_uma(arquivo, njud, stem)
            if "OK" in stdout:
                print("OK")
                ok_count += 1
            else:
                print(f"ERRO: {stdout[:80]}")
                erro_count += 1
        except subprocess.TimeoutExpired:
            print("TIMEOUT")
            erro_count += 1
        except Exception as e:
            print(f"EXCEPTION: {e}")
            erro_count += 1

        if (idx + 1) % 10 == 0:
            import psutil
            mem = psutil.virtual_memory()
            print(f"  >>> Progresso: {ok_count} OK, {erro_count} ERRO | Mem livre: {mem.available/1024**3:.1f}GB")

    print(f"\n=== CONCLUIDO ===")
    print(f"Total: {len(tarefas)}")
    print(f"OK: {ok_count}")
    print(f"ERRO: {erro_count}")


if __name__ == "__main__":
    main()
