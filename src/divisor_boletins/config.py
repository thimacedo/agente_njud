"""
Configurações globais do pipeline de divisão de boletins.

Todos os thresholds, âncoras de texto e padrões regex ficam aqui.
Para calibrar o pipeline, edite apenas este arquivo.
"""

from __future__ import annotations

import re

# ===========================================================================
# MODELO WHISPER
# ===========================================================================

MODELO_WHISPER = "small"
COMPUTE_TYPE = "int8"

# ===========================================================================
# THRESHOLDS DE DETECÇÃO
# ===========================================================================

LIMIAR_ANCORA = 0.55                # similaridade mínima para âncoras
LIMIAR_SILENCIO_PASSAGEM = 1.2      # gap mínimo (s) para detectar passagem
DURACAO_MINIMA_PASSAGEM = 0.5       # duração mínima de gap para considerar
LIMIAR_FIM_MANCHETE = 0.8           # gap mínimo para fim da manchete
LIMIAR_INICIO_CABECA = 0.8          # gap mínimo para início da cabeça
LIMIAR_FIM_CORPO = 1.5             # margem mínima para fim do CORPO

# Janela de tempo esperada para a passagem instrumental
JANELA_PASSAGEM_INICIO = 7.0
JANELA_PASSAGEM_FIM = 25.0   # ampliado de 13s (2026-08-24): a passagem real
                             # fica após a manchete (~16-18s); janela curta
                             # fazia o VAD confundir gap vinheta→manchete
                             # com passagem e cortar a CABEÇA dentro da vinheta

# ===========================================================================
# ÂNCORAS DE VINHETA (normalizadas: sem acento, minúsculo)
# ===========================================================================

# Texto REAL das vinhetas do TJRN (transcrito via Whisper):
#   VH ABERTURA: "no ar, noticias da hora, o boletim informativo do
#                 tribunal de justica do rio grande do norte"
#   VH ENCERRAMENTO: "voce acabou de ouvir noticias da hora o boletim
#                     informativo do tribunal de justica do rio grande
#                     do norte"

ANCORAS_ABERTURA = [
    "boletim informativo do tribunal de justica",
    "noticias da hora",
    "no ar",
    "boletim informativo do rio grande do norte",
]

ANCORAS_ENCERRAMENTO = [
    "voce acabou de ouvir",
    "obrigado por nos ouvir",
    "ate a proxima",
    "leonardo almeida",
    "samuel ferreira",
]

# ===========================================================================
# PADRÃO DE ASSINATURA DO LOCUTOR
# ===========================================================================

# Detecta: "tribunal de justica do rio grande do norte" + nome do locutor
_PADRAO_ASSINATURA_NORMALIZADA = re.compile(
    r"tribunal de justica do rio grande do norte"
    r"(?:\s+para a\s+radio justiça)?"
    r"[\s,]+[A-Za-z]+(?:\s+[A-Za-z]+)*\s*$",
    flags=re.IGNORECASE,
)
