"""
core/audio/deteccao_vinheta_espectral.py

Detecção de vinheta residual por correlação cruzada de forma de onda —
camada adicional, independente de transcrição Whisper.

MOTIVAÇÃO: tanto `remover_vinheta_boletim` (core/audio/remocao_vinheta.py)
quanto `RegraVinhetaBoletimAusente` (core/auditoria/regras.py) decidem se
a vinheta está presente comparando palavras-chave via `p in texto`, uma
comparação de substring sobre a transcrição do Whisper. Isso torna a
detecção sensível à qualidade da transcrição da vinheta (áudio curto,
musicalizado, difícil de transcrever bem).

Esta função fornece UM SINAL a mais para quem decide (processar_boletim.py):
o pico de correlação cruzada normalizada entre o início do CABEÇA e a
vinheta de referência, buscando o melhor alinhamento dentro de uma janela
de deslocamento. A busca por lag é ESSENCIAL: `cortar_audio()` ancora
bordas em silêncio e aplica fade_in, então o CABEÇA raramente começa na
amostra exata da vinheta — correlação fixa amostra-a-amostra zera com
apenas 40ms de deslocamento (verificado em teste, 2026-09-12).

Não depende de rede, modelo de ML ou transcrição — só pydub/numpy.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from pydub import AudioSegment

logger = logging.getLogger(__name__)

# Limiar do pico de correlação normalizada (0.0–1.0). Conservador (mais
# falsos positivos que negativos) porque o uso previsto é disparar RETRY
# de estratégia, não reprovação direta.
LIMIAR_CORRELACAO = 0.6

SAMPLE_RATE_COMPARACAO = 8000  # suficiente para forma de onda grosseira

# Janela de deslocamento tolerada (para cada lado). Cobre ancoragem em
# silêncio de cortar_audio (janela padrão 1500ms) com folga.
JANELA_LAG_MS = 2000


def _carregar_amostras(caminho: Path, duracao_ms: Optional[int] = None) -> np.ndarray:
    audio = AudioSegment.from_file(str(caminho))
    if duracao_ms is not None:
        audio = audio[:duracao_ms]
    audio = audio.set_channels(1).set_frame_rate(SAMPLE_RATE_COMPARACAO)
    amostras = np.array(audio.get_array_of_samples()).astype(np.float32)
    if amostras.size == 0:
        return amostras
    amostras /= float(1 << (8 * audio.sample_width - 1))
    return amostras


def _pico_correlacao_cruzada(sinal: np.ndarray, ref: np.ndarray, max_lag: int) -> float:
    """
    Pico da correlação de Pearson entre `ref` e janelas de `sinal`
    deslocadas em [0, max_lag]. Retorna 0.0 para sinais degenerados.
    """
    n_ref = len(ref)
    if n_ref == 0 or len(sinal) < n_ref // 2:
        return 0.0
    std_ref = np.std(ref)
    if std_ref == 0.0:
        return 0.0
    ref_c = (ref - ref.mean()) / std_ref

    melhor = 0.0
    # Passo de 1ms para não varrer amostra a amostra (custo O(lag*n)).
    passo = max(1, SAMPLE_RATE_COMPARACAO // 1000)
    for lag in range(0, max_lag + 1, passo):
        jan = sinal[lag : lag + n_ref]
        if len(jan) < n_ref // 2:
            break
        n = len(jan)
        r = ref_c[:n]
        std_j = np.std(jan)
        if std_j == 0.0:
            continue
        jan_c = (jan - jan.mean()) / std_j
        corr = float(np.dot(jan_c, r) / n)
        if corr > melhor:
            melhor = corr
    return melhor


def vinheta_presente_por_correlacao(
    caminho_cabeca: Path,
    caminho_vinheta_ref: Path,
    duracao_vinheta_s: float,
) -> tuple[bool, float]:
    """
    Verifica se o início de `caminho_cabeca` contém a vinheta de referência,
    tolerando deslocamento de até JANELA_LAG_MS.

    Returns:
        (detectado, correlacao_pico). Retorna (False, 0.0) em qualquer
        condição degenerada — nunca levanta exceção.
    """
    try:
        if not caminho_cabeca.exists() or not caminho_vinheta_ref.exists():
            return False, 0.0

        duracao_ms = int(duracao_vinheta_s * 1000)
        ref = _carregar_amostras(caminho_vinheta_ref, duracao_ms=duracao_ms)
        sinal = _carregar_amostras(caminho_cabeca, duracao_ms=duracao_ms + JANELA_LAG_MS)

        if ref.size == 0 or sinal.size == 0:
            return False, 0.0

        max_lag = int(JANELA_LAG_MS * SAMPLE_RATE_COMPARACAO / 1000)
        pico = max(0.0, _pico_correlacao_cruzada(sinal, ref, max_lag))
        return pico >= LIMIAR_CORRELACAO, pico

    except Exception:
        logger.exception("Falha ao calcular correlação de vinheta para %s", caminho_cabeca)
        return False, 0.0
