#!/usr/bin/env python3
"""Compatibilidade: execute o pipeline com o interpretador do projeto."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / '.venv_pipeline' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
if not PYTHON.is_file():
    raise SystemExit('Crie .venv_pipeline com dev.ps1 setup antes de executar.')
env = os.environ.copy()
env.setdefault('DIVISOR_TMP', str(ROOT / 'data/tmp'))
Path(env['DIVISOR_TMP']).mkdir(parents=True, exist_ok=True)
env['PYTHONPATH'] = os.pathsep.join([str(ROOT / 'scripts_pipeline'), str(ROOT)])
raise SystemExit(subprocess.call(
    [str(PYTHON), str(ROOT / 'scripts_pipeline/boletim/processar_boletim_canonico.py'), *sys.argv[1:]],
    cwd=ROOT, env=env))
