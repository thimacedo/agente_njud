"""
Pacote regras/ — DEPRECADO / não usado pela cadeia real.

Ver aviso completo em __getattr__/warnings.warn abaixo e em
ARQUITETURA_REAL.md e ARQUITETURA_ALVO_2026-09-14.md (seção 1.3).
"""
from __future__ import annotations

import warnings

warnings.warn(
    "src/regras/* (livro.py, njud.py, giro.py, boletim.py) não é importado "
    "pela cadeia de produção real (executar_programa.py -> "
    "core.processamento.processar_boletim -> divisor_boletins/audio.py). "
    "Confirmado em ARQUITETURA_REAL.md. Não presumir que corrigir bugs aqui "
    "afeta produção sem antes confirmar migração explícita.",
    DeprecationWarning,
    stacklevel=2,
)
