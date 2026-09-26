from __future__ import annotations

"""divisor_boletins — reconstrução mínima funcional.

Este pacote foi reconstruído a partir do legado real (remocao_vinheta.py,
deteccao_vinheta_espectral.py, individual_cuts.py, giro/log.py) e da
documentação que descreve a interface esperada (ARQUITETURA_REAL.md,
DECISOES.md).

Funções esperadas pelo código legado que ainda referencia este pacote:
    - divisor_boletins.audio.processar_arquivo
    - divisor_boletins.audio.carregar_modelo
    - divisor_boletins.log.LogPipeline
    - divisor_boletins.deteccao.buscar_ancora
    - divisor_boletins.deteccao._carregar_silero_vad
    - divisor_boletins.calibracao.calibrar_boletim

Interface CLI pública:
    python -m divisor_boletins dividir <pasta_entrada> <pasta_saida> --apply
"""

from .audio import carregar_modelo, processar_arquivo, transcrever_audio
from .calibracao import calibrar_boletim
from .deteccao import LIMIAR_CORRELACAO, buscar_ancora, _carregar_silero_vad
from .log import LogPipeline

__all__ = [
    "carregar_modelo",
    "processar_arquivo",
    "transcrever_audio",
    "calibrar_boletim",
    "LIMIAR_CORRELACAO",
    "buscar_ancora",
    "_carregar_silero_vad",
    "LogPipeline",
]
