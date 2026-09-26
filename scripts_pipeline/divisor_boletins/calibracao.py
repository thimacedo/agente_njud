from __future__ import annotations

"""Calibração de boletim — mínimo compatível com o que o legado espera.

O doc ARQUITETURA_REAL.md descreve:
    → calibrar_boletim() [divisor_boletins/calibracao.py]

Calibrar, neste contexto, significa ajustar/validar o ponto de corte inicial
do boletim com base em evidências do áudio/transcrição, retornando
metadados de calibração que o cortar_audio() usa.

Este mínimo implementa calibrar_boletim como função que, dado um AudioSegment
e uma transcrição preliminar, decide o tempo de início útil do boletim
(após eventuais remoções de vinheta) e retorna um dict de calibração."""

from typing import Any


def calibrar_boletim(
    audio_total: Any,
    texto_inicio: str,
    *,
    vinheta_removida: bool = False,
    duracao_vinheta_s: float = 0.0,
    **kwargs: Any,
) -> dict[str, Any]:
    """Calibra o ponto de início do boletim para corte.

    Args:
        audio_total: AudioSegment do boletim (ou algo compatível com len()).
        texto_inicio: texto transcrito do início do boletim.
        vinheta_removida: se a vinheta de abertura já foi removida.
        duracao_vinheta_s: duração da vinheta removida, em segundos.

    Returns:
        dict com chave 'tempo_inicio_s' (float) e metadados de calibração.
    """
    tempo_inicio = 0.0
    if vinheta_removida and duracao_vinheta_s > 0:
        tempo_inicio = duracao_vinheta_s

    return {
        "tempo_inicio_s": tempo_inicio,
        "vinheta_removida": vinheta_removida,
        "duracao_vinheta_s": duracao_vinheta_s,
        "texto_inicio": texto_inicio,
    }
