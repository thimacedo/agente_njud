#!/usr/bin/env python3
"""Wrapper para isolar o pipeline do Hermes agent."""
import os
import subprocess
import sys

# Limpar variáveis de ambiente que podem causar conflito
env = os.environ.copy()
# Remover PYTHONPATH que aponta para paths do Hermes
if 'PYTHONPATH' in env:
    paths = env['PYTHONPATH'].split(os.pathsep)
    paths = [p for p in paths if 'hermes' not in p.lower()]
    env['PYTHONPATH'] = os.pathsep.join(paths) if paths else ''

# Desabilitar sitecustomize/usercustomize do Hermes
env['PYTHONNOUSERSITE'] = '1'

# Limpar sys.path via sitecustomize injection
env['PYTHONSTARTUP'] = ''

# Comando real
script = r"E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\scripts_pipeline\boletim\processar_boletim_canonico.py"
python = r"E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\.venv_pipeline\Scripts\python.exe"

# Criar um sitecustomize temporário que limpa os paths do Hermes
sitecustomize_content = """
import sys
sys.path = [p for p in sys.path if 'hermes' not in p.lower() and 'AppData/Local/hermes' not in p]
"""

import tempfile
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir=os.path.dirname(python)) as f:
    f.write(sitecustomize_content)
    sitecustomize_path = f.name

# Adicionar o sitecustomize ao path do Python
env['PYTHONPATH'] = os.path.dirname(sitecustomize_path) + os.pathsep + env.get('PYTHONPATH', '')

# Executar
result = subprocess.run(
    [python, script] + sys.argv[1:],
    env=env,
    cwd=r"E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR",
)

# Limpar
os.unlink(sitecustomize_path)

sys.exit(result.returncode)
