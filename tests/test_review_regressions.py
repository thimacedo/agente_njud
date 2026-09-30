"""Regressions for destructive cuts, package imports and web job lifecycle."""
import asyncio
import importlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from pydub import AudioSegment

from boletim.etapas.etapa_cortes import processar_cortes_boletim
from shared.core import Corte, sincronizar_transcricao_com_cortes

ROOT = Path(__file__).resolve().parents[1]


def cortar(repeticoes, claquetes, segmentos=(), geral=None):
    # Every millisecond has an identifiable sample, so tests check which
    # content survives rather than duration alone.
    return processar_cortes_boletim(
        list(segmentos), list(range(20000)), repeticoes, claquetes, geral,
        {'marcadores': {1: 0}, 'assinaturas': []}, 1, 1)[1]['audio']


def test_cortes_de_classes_diferentes_preservam_conteudo():
    result = cortar([{'inicio': 2, 'fim': 4}], {1: {'inicio': 10, 'fim': 12}})
    source = list(range(20000))
    assert result == source[:2000] + source[4000:10000] + source[12000:]


def test_claquete_detectada_duas_vezes_remove_uma_vez():
    result = cortar([], {1: {'inicio': 0, 'fim': 2}},
                    [{'start': 0, 'end': 2, 'text': 'B1.'},
                     {'start': 2, 'end': 3, 'text': 'Conteúdo'}])
    assert result == list(range(2000, 20000))


def test_cortes_sobrepostos_e_adjacentes():
    result = cortar([{'inicio': 2, 'fim': 5}],
                    {1: {'inicio': 4, 'fim': 7}, 2: {'inicio': 7, 'fim': 8}})
    assert result == list(range(2000)) + list(range(8000, 20000))


@pytest.mark.parametrize('later_cut,expected', [
    (Corte(14, 16), [(8, 12), (12, 16)]),
    (Corte(14, 25), [(8, 12)]),
    (Corte(9, 12), [(7, 15)]),
])
def test_sync_preserva_deslocamento_acumulado(later_cut, expected):
    segments = [{'start': 10, 'end': 20,
                 'text': 'um dois tres quatro cinco seis sete oito nove dez'}]
    result = sincronizar_transcricao_com_cortes(segments, [Corte(0, 2), later_cut])
    assert [(s['start'], s['end']) for s in result] == expected


def test_pipeline_importavel_sem_path_do_boletim():
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'scripts_pipeline'))
    result = subprocess.run(
        [sys.executable, '-c', 'import boletim.processar_boletim_canonico; import giro.giro_montar_gnc'],
        cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv('PROJECT_DIR', str(tmp_path))
    module = importlib.import_module('frontend.server')
    monkeypatch.setattr(module, 'PROJECT_DIR', tmp_path)
    monkeypatch.setattr(module, 'DATA_DIR', tmp_path / 'data')
    monkeypatch.setattr(module, 'UPLOAD_DIR', tmp_path / 'data' / 'uploads')
    monkeypatch.setattr(module, 'OUTPUT_DIR', tmp_path / 'data' / 'output')
    monkeypatch.setattr(module, 'JOBS_FILE', tmp_path / 'data' / 'jobs.json')
    module.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    module.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    module.jobs.clear()
    module.cancellations.clear()
    return module


def add_job(server, job_id='job'):
    server.jobs[job_id] = {'id': job_id, 'status': 'running'}
    server.cancellations[job_id] = threading.Event()


def test_cancelled_job_never_becomes_done(server):
    add_job(server)
    assert asyncio.run(server.cancel_job('job'))['status'] == 'cancelled'
    server.set_done('job', Path('output.mp3'), 1)
    server.set_error('job', 'late error')
    assert server.jobs['job']['status'] == 'cancelled'


def test_simulation_produces_downloadable_file(server, monkeypatch):
    add_job(server)
    source = server.UPLOAD_DIR / 'audio.wav'
    source.write_bytes(b'input')
    monkeypatch.setattr(server, 'SIMULATE', True)
    server.run_job('job', 'boletins', [source])
    assert server.jobs['job']['status'] == 'done'
    output = Path(server.jobs['job']['output_path'])
    assert output.is_relative_to(server.OUTPUT_DIR / 'job')
    assert len(AudioSegment.from_wav(output)) == 1000
    assert asyncio.run(server.download('job')).media_type == 'audio/x-wav'


def test_cancel_running_subprocess(server):
    add_job(server)
    worker = server.PROJECT_DIR / 'frontend' / 'pipeline_worker.py'
    worker.parent.mkdir()
    marker = server.PROJECT_DIR / 'started'
    # A long-running real subprocess must stop when the API cancels it.
    worker.write_text('from pathlib import Path\nimport time\n'
                      f'Path({str(marker)!r}).write_text("started")\n'
                      'time.sleep(30)\n')
    caught = []

    def run():
        try:
            server.run_worker('job', 'giro', server.UPLOAD_DIR, server.OUTPUT_DIR / 'job')
        except Exception as exc:
            caught.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    deadline = time.monotonic() + 5
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert marker.exists()
    asyncio.run(server.cancel_job('job'))
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert len(caught) == 1 and isinstance(caught[0], server.JobCancelled)


def test_worker_requires_manifest_and_real_output(server):
    add_job(server)
    worker = server.PROJECT_DIR / 'frontend' / 'pipeline_worker.py'
    worker.parent.mkdir()
    worker.write_text('print("no output")\n')
    with pytest.raises(FileNotFoundError):
        server.run_worker('job', 'giro', server.UPLOAD_DIR, server.OUTPUT_DIR / 'job')


def test_job_api_returns_string_id(server, monkeypatch):
    source = server.UPLOAD_DIR / 'upload_audio.mp3'
    source.write_bytes(b'input')
    monkeypatch.setattr(server, 'run_job', lambda *args: None)
    result = asyncio.run(server.create_job({'tipo': 'boletins', 'inputs': ['upload']}))
    assert result['id'] == result['job_id']
    assert isinstance(result['id'], str)
    assert server.jobs[result['id']]['files'][0]['path'] == str(source)


def test_njud_rejects_incomplete_inputs(server):
    with pytest.raises(server.HTTPException) as exc:
        asyncio.run(server.create_job({'tipo': 'njud', 'inputs': ['one']}))
    assert exc.value.status_code == 400


def test_giro_assembly_uses_supplied_output_directory(tmp_path, monkeypatch):
    from giro import giro_montar_gnc
    monkeypatch.setattr(giro_montar_gnc, 'carregar_vinheta',
                        lambda _: AudioSegment.silent(duration=100))
    note = tmp_path / 'note.mp3'
    AudioSegment.silent(duration=1000).export(note, format='mp3')
    output = giro_montar_gnc.montar_gnc('0101', [note], '30-09-2026', tmp_path / 'private')
    assert output.parent == tmp_path / 'private'
    assert output.is_file()


@pytest.mark.parametrize('tipo,count', [('boletins', 1), ('njud', 4), ('giro', 4)])
def test_worker_routes_current_pipelines(tmp_path, monkeypatch, tipo, count):
    from frontend.pipeline_worker import processar
    entrada = tmp_path / 'entrada'
    entrada.mkdir()
    for n in range(1, count + 1):
        AudioSegment.silent(duration=1000).export(
            entrada / f'BOLETIM_RADIO_TJRN_30_09_2026_B{n}.wav', format='wav')
    if tipo == 'boletins':
        from boletim import processar_boletim_canonico

        def editar(audio):
            pasta = audio.parent / f'{audio.stem}_saida'
            pasta.mkdir()
            AudioSegment.silent(duration=1000).export(pasta / 'editado.mp3', format='mp3')
            return {'boletims_gerados': [{'arquivo': 'editado.mp3'}]}

        monkeypatch.setattr(processar_boletim_canonico, 'processar_canonico', editar)
    elif tipo == 'njud':
        from divisor_boletins import __main__ as divisor
        import montagem_jornais

        def dividir(entrada_mp3, cortes, aplicar):
            assert aplicar
            cortes.mkdir()
            for mp3 in entrada_mp3.glob('*.mp3'):
                for parte in ['CABECA', 'CORPO']:
                    AudioSegment.silent(duration=1000).export(
                        cortes / f'{mp3.stem}_{parte}.mp3', format='mp3')
            return 0

        monkeypatch.setattr(divisor, 'dividir', dividir)
        monkeypatch.setattr(montagem_jornais, '_carregar_vinheta',
                            lambda *args: AudioSegment.silent(duration=100))
    else:
        from giro import giro_montar_gnc
        monkeypatch.setattr(giro_montar_gnc, 'carregar_vinheta',
                            lambda _: AudioSegment.silent(duration=100))
    output = processar(tipo, entrada, tmp_path / 'output')
    assert output.is_relative_to(tmp_path / 'output')
    assert len(AudioSegment.from_mp3(output)) >= 1000
