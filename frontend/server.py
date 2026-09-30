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
import signal
import mimetypes
import tempfile
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
PROJECT_DIR = Path(os.environ.get('PROJECT_DIR', str(Path(__file__).resolve().parents[1])))
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
jobs_lock = threading.RLock()
cancellations: Dict[str, threading.Event] = {}

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
    # Serialize state snapshots and replace atomically while workers update jobs.
    with jobs_lock:
        temporary = None
        try:
            JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=JOBS_FILE.parent, delete=False) as f:
                temporary = Path(f.name)
                json.dump(jobs, f, ensure_ascii=False, indent=2)
            os.replace(temporary, JOBS_FILE)
        except Exception as e:
            log(f'Falha ao salvar jobs: {e}')
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def gen_id():
    return str(uuid.uuid4())[:8]

# ============================================================
# Helpers
# ============================================================
def update_job(job_id: str, **kwargs):
    with jobs_lock:
        if job_id not in jobs:
            return
        if jobs[job_id]['status'] == 'cancelled':
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
class JobCancelled(Exception):
    pass


def check_cancelled(job_id: str):
    with jobs_lock:
        event = cancellations.get(job_id)
        cancelled = jobs.get(job_id, {}).get('status') == 'cancelled'
    if cancelled or (event is not None and event.is_set()):
        raise JobCancelled()


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       capture_output=True)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if os.name != 'nt':
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait()


def run_worker(job_id: str, tipo: str, input_dir: Path, output_dir: Path) -> Path:
    check_cancelled(job_id)
    env = os.environ.copy()
    env['PYTHONPATH'] = str(PROJECT_DIR / 'scripts_pipeline') + os.pathsep + env.get('PYTHONPATH', '')
    cmd = [sys.executable, str(PROJECT_DIR / 'frontend' / 'pipeline_worker.py'),
           tipo, str(input_dir), str(output_dir)]
    options = {'start_new_session': True} if os.name != 'nt' else {
        'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
    process = subprocess.Popen(cmd, cwd=PROJECT_DIR, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, **options)
    deadline = time.monotonic() + 600
    try:
        while True:
            check_cancelled(job_id)
            if time.monotonic() >= deadline:
                raise TimeoutError('Pipeline excedeu 600 segundos')
            try:
                stdout, stderr = process.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                continue
        check_cancelled(job_id)
        if process.returncode != 0:
            raise RuntimeError(f'Pipeline falhou ({process.returncode}): {stderr[-2000:]}')
        manifest = output_dir / 'resultado.json'
        result = json.loads(manifest.read_text(encoding='utf-8'))
        output = Path(result['output_path']).resolve()
        if not output.is_relative_to(output_dir.resolve()) or not output.is_file() or not output.stat().st_size:
            raise RuntimeError('Arquivo de saída inválido ou ausente')
        return output
    finally:
        stop_process(process)
        process.communicate()


def _simulate(job_id: str, tipo: str, output_dir: Path) -> Path:
    for i, etapa in enumerate(['Recebendo áudio…', 'Processando…', 'Gerando arquivo…']):
        check_cancelled(job_id)
        set_progress(job_id, (i + 1) * 25, etapa)
        event = cancellations[job_id]
        if event.wait(0.4):
            raise JobCancelled()
    from pydub import AudioSegment
    output = output_dir / f'{tipo}_simulacao.wav'
    AudioSegment.silent(duration=1000).export(str(output), format='wav')
    return output


def run_job(job_id: str, tipo: str, input_paths: list[Path]):
    """Run each job in private directories and a cancellable child process."""
    start = time.monotonic()
    input_dir = DATA_DIR / f'_tmp_{tipo}_{job_id}'
    output_dir = OUTPUT_DIR / job_id
    try:
        check_cancelled(job_id)
        input_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)
        for p in input_paths:
            check_cancelled(job_id)
            shutil.copy2(p, input_dir / p.name)
        set_progress(job_id, 10, 'Iniciando processamento…')
        output = (_simulate(job_id, tipo, output_dir) if SIMULATE else
                  run_worker(job_id, tipo, input_dir, output_dir))
        check_cancelled(job_id)
        set_done(job_id, output, time.monotonic() - start)
    except JobCancelled:
        set_cancelled(job_id)
    except Exception as e:
        set_error(job_id, str(e))
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)
        with jobs_lock:
            cancelled = jobs.get(job_id, {}).get('status') == 'cancelled'
            cancellations.pop(job_id, None)
        if cancelled:
            shutil.rmtree(output_dir, ignore_errors=True)

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
    filename = Path(file.filename.replace('\\', '/')).name
    dest = UPLOAD_DIR / f'{file_id}_{filename}'
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

    if not isinstance(input_ids, list) or any(not isinstance(uid, str) or not uid for uid in input_ids):
        raise HTTPException(400, 'inputs deve conter IDs de upload')
    if len(input_ids) != len(set(input_ids)):
        raise HTTPException(400, 'Uploads duplicados')
    if tipo == 'boletins' and len(input_ids) != 1:
        raise HTTPException(400, 'Boletins exige 1 áudio')
    if tipo == 'njud' and len(input_ids) != 4:
        raise HTTPException(400, 'NJUD exige 4 boletins')

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
            if f.is_file() and f.name.startswith(uid + '_'):
                input_paths.append(f)
                job['files'].append({'name': f.name, 'path': str(f)})
                found = True
                break
        if not found:
            log(f'Job {job_id}: upload {uid} não encontrado')
            update_job(job_id, status='error', etapa='Erro', error=f'Upload {uid} não encontrado')
            return {'id': job_id, 'job_id': job_id, 'tipo': job['tipo'], 'status': 'error',
                    'error': f'Upload {uid} não encontrado'}

    update_job(job_id, status='running', etapa='Iniciando…', files=job['files'])
    log(f"Job {job_id} ({tipo}): iniciado com {len(input_paths)} arquivos")

    # Executa em thread
    with jobs_lock:
        cancellations[job_id] = threading.Event()
    t = threading.Thread(target=run_job, args=(job_id, tipo, input_paths), daemon=True)
    t.start()

    return {'id': job_id, 'job_id': job_id, 'tipo': job['tipo'], 'status': 'running'}

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
        if job['status'] in {'queued', 'running'}:
            event = cancellations.get(job_id)
            if event is not None:
                event.set()
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
    return FileResponse(path, filename=path.name, media_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')

# ============================================================
# Run
# ============================================================
if __name__ == '__main__':
    import uvicorn
    log(f'Iniciando server na porta {PORT}')
    uvicorn.run(app, host='0.0.0.0', port=PORT, log_level='info')

