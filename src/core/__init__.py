"""
Core — Motor do Pipeline DIVISOR
=================================

Módulos principais de processamento de áudio, transcrição e montagem.
"""

from .divisor_boletins import (
    LogPipeline,
    EventoLog,
    ResultadoAncora,
    ResultadoCorte,
    processar_recursivo,
    carregar_modelo,
    montar_jornal,
    montar_todos_jornais,
)

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
