#!/usr/bin/env python3
"""Wrapper para isolar o pipeline do Hermes venv"""
import sys
import os

# Definir __file__ para o script principal
__file__ = os.path.abspath('scripts_pipeline/boletim/processar_boletim_canonico.py')

# Limpar paths do Hermes
sys.path = [p for p in sys.path if 'hermes' not in p.lower() and 'AppData/Local/hermes' not in p]

# Garantir que .venv_pipeline é encontrado primeiro
venv_site = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.venv_pipeline', 'Lib', 'site-packages')
if venv_site not in sys.path:
    sys.path.insert(0, venv_site)

sys.path.insert(0, 'scripts_pipeline')

# Executar o pipeline
exec(compile(open('scripts_pipeline/boletim/processar_boletim_canonico.py').read(), 'scripts_pipeline/boletim/processar_boletim_canonico.py', 'exec'))
