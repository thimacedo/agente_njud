#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Programador — DIVISOR
Backend mínimo para o frontend web.

Serve o frontend + endpoints de upload/jobs/download.
Chama os agentes existentes do src/ para processar áudio.

VERSÃO LOCAL: python server.py  →  http://localhost:8001
VERSÃO ONLINE: backend em host com acesso ao PROJECT_DIR + frontend estático no Vercel
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# ============================================================
# FastAPI
# ============================================================
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# ============================================================
# Config
# ============================================================
PROJECT_DIR = Path(os.environ.get('PROJECT_DIR', r'E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR'))
FRONTEND_DIR = PROJECT_DIR / 'frontend'
INDEX_HTML = FRONTEND_DIR / 'index.html'
DATA_DIR = PROJECT_DIR / 'data'
UPLOAD_DIR = Path(os.environ.get('UPLOAD_DIR', str(DATA_DIR / 'uploads')))
OUTPUT_DIR = Path(os.environ.get('OUTPUT_DIR', str(DATA_DIR / 'output')))
JOBS_FILE = DATA_DIR / 'jobs_state.json'
PORT = int(os.environ.get('PORT', '8001'))
SIMULATE = os.environ.get('SIMULATE', '0') == '1'
VERBOSE = os.environ.get('VERBOSE', '0') == '1'
DRIVER_ENABLED = os.environ.get('DRIVER_ENABLED', '0') == '1'

# Ensure dirs
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# Logging
# ============================================================
def log(msg: str, *args, **kwargs):
    ts = datetime.now().strftime('%H:%M:%S')
    if VERBOSE:
        print(f"[{ts}] SERVER: {msg}", *args, **kwargs, flush=True)
    else:
        print(f"[{ts}] SERVER: {msg}", flush=True)

# ============================================================
# State
# ============================================================
jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = threading.Lock()

def load_jobs():
    global jobs
    if JOBS_FILE.exists():
        try:
            with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                jobs = json.load(f)
            log(f'Carregou {len(jobs)} jobs de {JOBS_FILE}')
        except Exception as e:
            log(f'Falha ao carregar jobs: {e}')
            jobs = {}
    else:
        jobs = {}

def save_jobs():
    try:
        with open(JOBS_FILE, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f'Falha ao salvar jobs: {e}')

def gen_id():
    return str(uuid.uuid4())[:8]

# ============================================================
# Helpers
# ============================================================
def update_job(job_id: str, **kwargs):
    with jobs_lock:
        if job_id not in jobs:
            return
        jobs[job_id].update(kwargs)
        jobs[job_id]['updated_at'] = datetime.now().isoformat()
    save_jobs()

def set_progress(job_id: str, progress: int, etapa: str):
    update_job(job_id, progress=progress, etapa=etapa)

def set_done(job_id: str, output_path: Path, duration_s: float):
    update_job(job_id, status='done', progress=100, etapa='Concluído',
               output_path=str(output_path), duration_s=round(duration_s, 1))
    log(f"Job {job_id}: concluído em {round(duration_s,1)}s → {output_path.name}")

def set_error(job_id: str, error: str):
    update_job(job_id, status='error', progress=100, etapa='Erro', error=error)
    log(f"Job {job_id}: erro → {error}")

def set_cancelled(job_id: str):
    update_job(job_id, status='cancelled', progress=100, etapa='Cancelado')
    log(f"Job {job_id}: cancelado")

# ============================================================
# Pipeline calls (agentes existentes)
# ============================================================
def run_pipeline_boletins(job_id: str, input_path: Path, output_dir: Path) -> Optional[Path]:
    """
    Processa um boletim (edição).
    Por enquanto: simula ou chama subprocess do divisor_boletins.
    """
    set_progress(job_id, 10, 'Recebendo áudio…')
    time.sleep(0.5)

    if SIMULATE:
        _simulate(job_id, 'boletins')
        out = output_dir / f'editado_{input_path.stem}.mp3'
        out.parent.mkdir(parents=True, exist_ok=True)
        # não cria arquivo real em simulação
        set_done(job_id, out, 3.0)
        return out

    # Tenta subprocess do divisor_boletins (se disponível)
    # python -m src.divisor_boletins.cli dividir <input> <output>
    try:
        cmd = [
            sys.executable, '-m', 'src.divisor_boletins.cli', 'dividir',
            str(input_path.parent), str(output_dir),
            '--apply',
        ]
        log(f"Executando: {' '.join(cmd)}")
        set_progress(job_id, 30, 'Iniciando divisor de boletins…')
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"Código de saída {r.returncode}: {r.stderr}")
        log(f"Divisor concluído: {r.stdout[-300:]}")
        out = output_dir / f'{input_path.stem}_editado.mp3'
        set_done(job_id, out, 10.0)
        return out
    except Exception as e:
        set_error(job_id, f"Erro no pipeline: {e}")
        return None

def run_pipeline_njud(job_id: str, input_dir: Path, output_dir: Path) -> Optional[Path]:
    """
    Monta um NJUD a partir de 4 boletins (já cortes).
    """
    set_progress(job_id, 10, 'Recebendo boletins…')
    time.sleep(0.5)

    if SIMULATE:
        _simulate(job_id, 'njud')
        out = output_dir / f'NJUD_{time.strftime("%y%m")}_{time.strftime("%d-%m-%y")}.mp3'
        set_done(job_id, out, 5.0)
        return out

    # Tenta subprocess do divisor_boletins montar
    try:
        cmd = [
            sys.executable, '-m', 'src.divisor_boletins.cli', 'montar',
            str(input_dir), str(output_dir),
        ]
        log(f"Executando: {' '.join(cmd)}")
        set_progress(job_id, 30, 'Montando jornal NJUD…')
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"Código de saída {r.returncode}: {r.stderr}")
        log(f"Montagem concluída: {r.stdout[-300:]}")
        # Encontra o jornal gerado
        montados = list(output_dir.glob('NJUD_*.mp3'))
        if not montados:
            raise RuntimeError('Nenhum jornal gerado')
        out = montados[-1]
        set_done(job_id, out, 15.0)
        return out
    except Exception as e:
        set_error(job_id, f"Erro no pipeline NJUD: {e}")
        return None

def run_pipeline_giro(job_id: str, input_dir: Path, output_dir: Path) -> Optional[Path]:
    """
    Monta programa GIRO a partir de boletins.
    Usa src/giro/montagem.montar_programa
    """
    set_progress(job_id, 10, 'Recebendo boletins…')
    time.sleep(0.5)

    if SIMULATE:
        _simulate(job_id, 'giro')
        out = output_dir / f'GIRO_{time.strftime("%y%m")}_{time.strftime("%d-%m-%y")}.mp3'
        set_done(job_id, out, 6.0)
        return out

    try:
        # Tenta importar função de montagem
        from src.giro.montagem import montar_programa
        mmss = time.strftime('%y%m')
        notas = list(input_dir.glob('*.mp3'))
        if not notas:
            raise RuntimeError('Nenhum boletim para montar')
        notas_sorted = sorted(notas, key=lambda p: p.name)
        out = montar_programa(mmss, notas_sorted, output_dir)
        set_done(job_id, out, 20.0)
        return out
    except Exception as e:
        set_error(job_id, f"Erro no pipeline GIRO: {e}")
        return None

def _simulate(job_id: str, tipo: str):
    etapas = {
        'boletins': ['Enviando áudio…','Transcrevendo…','Detectando erros…','Aplicando cortes…','Gerando áudio editado…'],
        'njud':    ['Recebendo boletins…','Alinhando matrizes…','Ordenando…','Montando jornal…','Gerando arquivo final…'],
        'giro':    ['Recebendo boletins…','Verificando…','Definindo ordem…','Montando programa…','Gerando arquivo final…'],
    }[tipo]
    for i, etapa in enumerate(etapas):
        set_progress(job_id, int((i+1)/len(etapas)*80), etapa)
        time.sleep(0.4 + (i*0.2))

# ============================================================
# Background job runner
# ============================================================
def run_job(job_id: str, tipo: str, input_paths: list[Path]):
    """Executa pipeline em thread separada."""
    start = time.time()
    tipo_label = {'boletins':'Boletim', 'njud':'NJUD', 'giro':'Giro'}.get(tipo, tipo)
    log(f"Job {job_id} ({tipo_label}): iniciando com {len(input_paths)} arquivos")

    try:
        if tipo == 'boletins':
            if len(input_paths) != 1:
                set_error(job_id, 'Boletins espera exatamente 1 áudio')
                return
            out = run_pipeline_boletins(job_id, input_paths[0], OUTPUT_DIR)
        elif tipo == 'njud':
            # usa pasta temporária com os 4 boletins
            tmp = DATA_DIR / f'_tmp_njud_{job_id}'
            if tmp.exists():
                shutil.rmtree(tmp)
            tmp.mkdir(parents=True)
            for p in input_paths:
                shutil.copy2(p, tmp / p.name)
            out = run_pipeline_njud(job_id, tmp, OUTPUT_DIR)
            shutil.rmtree(tmp, ignore_errors=True)
        elif tipo == 'giro':
            tmp = DATA_DIR / f'_tmp_giro_{job_id}'
            if tmp.exists():
                shutil.rmtree(tmp)
            tmp.mkdir(parents=True)
            for p in input_paths:
                shutil.copy2(p, tmp / p.name)
            out = run_pipeline_giro(job_id, tmp, OUTPUT_DIR)
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            set_error(job_id, f'Tipo desconhecido: {tipo}')
    except Exception as e:
        set_error(job_id, str(e))

# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(title='Programador — DIVISOR', version='0.1.0')

# CORS (frontend pode estar em outra origem no Vercel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

# ============================================================
# Startup
# ============================================================
@app.on_event('startup')
async def startup():
    load_jobs()
    log(f'Server iniciado na porta {PORT}')
    log(f'UPLOAD_DIR: {UPLOAD_DIR}')
    log(f'OUTPUT_DIR: {OUTPUT_DIR}')
    log(f'SIMULATE: {SIMULATE}')

@app.on_event('shutdown')
async def shutdown():
    log('Server encerrado')

# ============================================================
# Endpoints
# ============================================================
@app.get('/', response_class=HTMLResponse)
async def index():
    if not INDEX_HTML.exists():
        return HTMLResponse('<h1>Frontend não encontrado</h1><p>Crie frontend/index.html</p>', status_code=404)
    return HTMLResponse(INDEX_HTML.read_text(encoding='utf-8'))

@app.get('/health')
async def health():
    return {
        'status': 'ok',
        'version': '0.1.0',
        'simulate': SIMULATE,
        'upload_dir': str(UPLOAD_DIR),
        'output_dir': str(OUTPUT_DIR),
        'projects_dir': str(PROJECT_DIR),
    }

@app.post('/api/upload')
async def upload(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower().lstrip('.')
    if ext not in {'mp3','wav','m4a','ogg','flac'}:
        raise HTTPException(400, f'Formato não suportado: {ext}')
    file_id = gen_id()
    dest = UPLOAD_DIR / f'{file_id}_{file.filename}'
    try:
        content = await file.read()
        dest.write_bytes(content)
        log(f'Upload: {file.filename} → {dest.name} ({len(content)} bytes)')
        return {'id': file_id, 'filename': file.filename, 'size_bytes': len(content), 'path': str(dest)}
    except Exception as e:
        log(f'Erro no upload: {e}')
        raise HTTPException(500, f'Falha no upload: {e}')

@app.post('/api/jobs')
async def create_job(payload: dict):
    tipo = payload.get('tipo')
    input_ids = payload.get('inputs', [])
    if not tipo or not input_ids:
        raise HTTPException(400, 'tipo e inputs são obrigatórios')
    if tipo not in {'boletins','njud','giro'}:
        raise HTTPException(400, f'tipo inválido: {tipo}')

    with jobs_lock:
        job_id = gen_id()
        job = {
            'id': job_id,
            'tipo': {'boletins':'Boletim','njud':'NJUD','giro':'Giro'}[tipo],
            'name': f"{tipo.capitalize()} — {len(input_ids)} arquivo(s)",
            'status': 'queued',
            'progress': 0,
            'etapa': 'Enfileirado',
            'error': None,
            'output_path': None,
            'download_url': None,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'input_ids': input_ids,
            'files': [],
            'duration_s': None,
        }
        jobs[job_id] = job
    save_jobs()

    # Resolver paths de upload
    input_paths = []
    for uid in input_ids:
        found = False
        for f in UPLOAD_DIR.iterdir():
            if f.name.startswith(uid):
                input_paths.append(f)
                job['files'].append({'name': f.name, 'path': str(f)})
                found = True
                break
        if not found:
            log(f'Job {job_id}: upload {uid} não encontrado')
            update_job(job_id, status='error', etapa='Erro', error=f'Upload {uid} não encontrado')
            return {'job_id': job_id, 'error': f'Upload {uid} não encontrado'}

    update_job(job_id, status='running', etapa='Iniciando…', files=job['files'])
    log(f"Job {job_id} ({tipo}): iniciado com {len(input_paths)} arquivos")

    # Executa em thread
    t = threading.Thread(target=run_job, args=(job_id, tipo, input_paths), daemon=True)
    t.start()

    return {'job_id': job_id, 'status': 'running'}

@app.get('/api/jobs')
async def list_jobs():
    with jobs_lock:
        items = list(jobs.values())
    # ordena: running primeiro, depois mais recente
    items.sort(key=lambda j: (0 if j['status']=='running' else 1, j['created_at']), reverse=True)
    return {'jobs': items}

@app.get('/api/jobs/{job_id}')
async def get_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, 'Job não encontrado')
    resp = dict(job)
    # Se tiver output_path, adiciona download_url relativo
    if resp.get('output_path'):
        resp['download_url'] = f'/api/download/{job_id}'
    return resp

@app.delete('/api/jobs/{job_id}')
async def cancel_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, 'Job não encontrado')
    if job['status'] == 'running':
        # Tentativa de cancelamento (melhorável)
        log(f"Job {job_id}: cancelamento request (best-effort)")
        set_cancelled(job_id)
        return {'status': 'cancelled'}
    return {'status': job['status'], 'message': 'Não estava running'}

@app.get('/api/download/{job_id}')
async def download(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, 'Job não encontrado')
    if job['status'] != 'done':
        raise HTTPException(400, f'Job não está pronto (status={job["status"]})')
    path = Path(job['output_path'])
    if not path.exists():
        raise HTTPException(404, 'Arquivo de saída não encontrado')
    return FileResponse(path, filename=path.name, media_type='audio/mpeg')

# ============================================================
# Run
# ============================================================
if __name__ == '__main__':
    import uvicorn
    log(f'Iniciando server na porta {PORT}')
    uvicorn.run(app, host='0.0.0.0', port=PORT, log_level='info')
