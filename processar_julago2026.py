#!/usr/bin/env python3
"""
Processamento direto dos boletins de Julho e Agosto 2026.
Usa subprocess por arquivo para evitar OOM.
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
LOG_FILE = PASTA_BASE / "logs" / f"etapa2_dispatcher_{time.strftime('%Y%m%d_%H%M%S')}.log"


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def find_julho_agosto_2026():
    """Encontra arquivos de Julho 2026 e Agosto 2026."""
    tarefas = []
    for month_dir in ["07", "08"]:
        mp3s = sorted((PASTA_BOLETINS / month_dir).rglob("*.mp3"))
        for f in mp3s:
            stem = f.stem
            # Filtrar apenas julho 2026 e agosto 2026
            if "_26_07_2026_" in stem or "_26_08_2026_" in stem:
                njud = f.parent.name
                # Verificar se ja esta OK
                caminho_estado = ESTADO_DIR / f"{stem}.json"
                if caminho_estado.exists():
                    try:
                        d = json.loads(caminho_estado.read_text(encoding="utf-8"))
                        if d.get("status") in ("OK", "ESGOTADO_ACEITO"):
                            continue
                    except:
                        pass
                tarefas.append({"arquivo": str(f), "njud": njud, "stem": stem})
    return tarefas


def processar_uma_subprocesso(arquivo, njud, stem):
    """Processa um arquivo em subprocesso separado."""
    script = f'''
import json, os, sys, warnings
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
    modelo = WhisperModel(_settings.MODELO_WHISPER, device="cpu", compute_type=_settings.COMPUTE_TYPE, cpu_threads=1)
    logger = LogPipeline(Path(pasta_saida) / "_logs")
    pasta_destino = pasta_cortes / njud

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
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
    msg = f"ERRO: {{e}}"
    print(msg)
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
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    log("=== ETAPA 2: Dispatcher Julho/Agosto 2026 ===")

    tarefas = find_julho_agosto_2026()
    log(f"{len(tarefas)} arquivo(s) pendente(s) de Julho/Agosto 2026.")

    if not tarefas:
        log("Nada a fazer - todos os boletins de jul/ago 2026 ja estao processados.")
        return

    ok_count = 0
    erro_count = 0

    for idx, tarefa in enumerate(tarefas):
        arquivo = tarefa["arquivo"]
        njud = tarefa["njud"]
        stem = tarefa["stem"]

        log(f"[{idx+1}/{len(tarefas)}] {Path(arquivo).name}")

        try:
            stdout, stderr = processar_uma_subprocesso(arquivo, njud, stem)
            if "OK" in stdout:
                log(f"  -> OK")
                ok_count += 1
            else:
                log(f"  -> ERRO: {stdout[:100]}")
                erro_count += 1
        except subprocess.TimeoutExpired:
            log(f"  -> TIMEOUT")
            erro_count += 1
        except Exception as e:
            log(f"  -> EXCEPTION: {e}")
            erro_count += 1

    log(f"\n=== CONCLUIDO ===")
    log(f"Total: {len(tarefas)}")
    log(f"OK: {ok_count}")
    log(f"ERRO: {erro_count}")
    log(f"Log salvo em: {LOG_FILE}")


if __name__ == "__main__":
    main()
