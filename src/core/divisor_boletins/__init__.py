"""
Divisor de Boletins de Rádio — TJRN
====================================

Pipeline de transcrição, detecção de vinhetas, corte e montagem.
"""

from .log import LogPipeline, EventoLog
from .deteccao import ResultadoAncora
from .audio import ResultadoCorte, processar_recursivo, carregar_modelo
from .montagem import montar_jornal, montar_todos_jornais

__all__ = [
    "LogPipeline",
    "EventoLog",
    "ResultadoAncora",
    "ResultadoCorte",
    "processar_recursivo",
    "carregar_modelo",
    "montar_jornal",
    "montar_todos_jornais",
]
