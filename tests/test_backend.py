"""API e ligação com o pipeline, sem tocar dados de produção ou baixar modelos."""
import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def backend(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('UPLOAD_DIR', str(tmp_path / 'uploads'))
    monkeypatch.setenv('OUTPUT_DIR', str(tmp_path / 'output'))
    monkeypatch.setenv('SIMULATE', '0')
    path = Path(__file__).resolve().parents[1] / 'frontend/server.py'
    spec = importlib.util.spec_from_file_location('backend_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_health_and_multipart_upload(backend):
    with TestClient(backend.app) as client:
        assert client.get('/health').json()['status'] == 'ok'
        response = client.post('/api/upload', files={'file': ('smoke.wav', b'RIFF', 'audio/wav')})
        assert response.status_code == 200
        assert Path(response.json()['path']).read_bytes() == b'RIFF'
        assert client.post('/api/upload', files={'file': ('bad.txt', b'x')}).status_code == 400


def test_njud_uses_current_python_and_canonical_script(backend, monkeypatch):
    backend.jobs['test'] = {}
    monkeypatch.setattr(backend.time, 'sleep', lambda _: None)
    output = backend.OUTPUT_DIR / 'NJUD_smoke.mp3'
    def run(job_id, cmd, **kwargs):
        assert cmd[:2] == [sys.executable, '-c']
        assert 'from montagem_jornais import montar_jornal' in cmd[2]
        assert job_id == 'test'
        output.write_bytes(b'test')
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(backend, 'run_command', run)
    assert backend.run_pipeline_njud('test', backend.UPLOAD_DIR, backend.OUTPUT_DIR) == output
    assert backend.jobs['test']['status'] == 'done'


def test_division_does_not_report_missing_output_as_success(backend, monkeypatch):
    backend.jobs['test'] = {}
    monkeypatch.setattr(backend.time, 'sleep', lambda _: None)
    def run(job_id, cmd, **kwargs):
        assert cmd[:3] == [sys.executable, '-m', 'boletim.processar_boletim_canonico']
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(backend, 'run_command', run)
    assert backend.run_pipeline_boletins('test', backend.UPLOAD_DIR / 'smoke.mp3', backend.OUTPUT_DIR) is None
    assert backend.jobs['test']['status'] == 'error'


def test_subprocess_environment(backend, monkeypatch):
    backend.jobs['test'] = {}
    class Process:
        returncode = 0
        def __init__(self, cmd, **kwargs):
            assert cmd == [sys.executable, '-V']
            assert Path(kwargs['cwd']) == backend.PROJECT_DIR
            assert kwargs['env']['PYTHONPATH'].split(os.pathsep)[0] == str(backend.PIPELINE_DIR)
            assert kwargs['env']['PYTHONIOENCODING'] == 'utf-8'
            assert Path(kwargs['env']['DIVISOR_TMP']).is_dir()
        def communicate(self, timeout):
            return 'Python 3.11', ''
        def poll(self):
            return 0
    monkeypatch.setattr(backend.subprocess, 'Popen', Process)
    assert backend.run_command('test', [sys.executable, '-V']).returncode == 0
