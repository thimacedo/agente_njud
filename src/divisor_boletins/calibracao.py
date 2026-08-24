"""
Calibragem de vinhetas de boletim por correlação cruzada (cross-correlation).
Utiliza os arquivos de referência em assets/vinhetas/ para encontrar posições
exatas nos boletins, eliminando sobras de áudio.

Se as vinhetas de boletim não existirem, retorna um resultado parcial sem
bloquear o pipeline.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from pydub import AudioSegment
from scipy.signal import correlate, correlation_lags

# Caminho local dos assets deste projeto
VINHETAS_DIR = Path("F:/Projetos/DIVISOR/assets/vinhetas")

# Nomes específicos de boletim (separados dos assets de jornal)
VINHETA_ABERTURA = "VHT_ABERTURA_BOLETIM.mp3"
VINHETA_PASSAGEM = "VHT_PASSAGEM_BOLETIM.mp3"
VINHETA_ENCERRAMENTO = "VHT_ENCERRAMENTO_BOLETIM.mp3"

_CACHE_VINHETAS: dict = {}
_CACHE_PATH = Path("F:/Projetos/DIVISOR/data/cache/_vinhetas_cache.pkl")


def _carregar_vinheta_raw(nome_arquivo: str) -> Optional[tuple[np.ndarray, int]]:
    caminho = VINHETAS_DIR / nome_arquivo
    if not caminho.exists():
        return None
    try:
        audio = AudioSegment.from_file(str(caminho)).set_frame_rate(16000).set_channels(1)
        dados = np.array(audio.get_array_of_samples(), dtype=np.float32) / 32768.0
        return dados, len(dados)
    except Exception as e:
        print(f"[calibracao] Falha ao carregar {caminho.name}: {e}")
        return None


def carregar_todas_vinhetas() -> dict:
    global _CACHE_VINHETAS
    if _CACHE_VINHETAS:
        return _CACHE_VINHETAS

    if _CACHE_PATH.exists():
        try:
            with open(_CACHE_PATH, 'rb') as f:
                _CACHE_VINHETAS = pickle.load(f)
            return _CACHE_VINHETAS
        except Exception:
            pass

    _CACHE_VINHETAS = {
        'abertura': _carregar_vinheta_raw(VINHETA_ABERTURA),
        'passagem': _carregar_vinheta_raw(VINHETA_PASSAGEM),
        'encerramento': _carregar_vinheta_raw(VINHETA_ENCERRAMENTO),
    }

    try:
        with open(_CACHE_PATH, 'wb') as f:
            pickle.dump(_CACHE_VINHETAS, f)
    except Exception:
        pass

    return _CACHE_VINHETAS


def encontrar_vinheta_por_correlacao(
    audio_boletim: AudioSegment,
    vinheta_ref: Optional[np.ndarray],
    janela_inicio: float = 0.0,
    janela_fim: Optional[float] = None,
    limiar_confianca: float = 0.35,
) -> Tuple[float, float, float]:
    if vinheta_ref is None:
        return 0.0, 0.0, 0.0

    boletim = audio_boletim.set_frame_rate(16000).set_channels(1)
    start_ms = int(janela_inicio * 1000)
    if janela_fim is not None:
        end_ms = int(janela_fim * 1000)
        boletim_recortado = boletim[start_ms:end_ms]
    else:
        boletim_recortado = boletim[start_ms:]

    sig = np.array(boletim_recortado.get_array_of_samples(), dtype=np.float32) / 32768.0
    ref_sig = vinheta_ref

    corr = correlate(sig, ref_sig, mode='valid')
    lags = correlation_lags(len(sig), len(ref_sig), mode='valid')

    if len(corr) == 0:
        return 0.0, 0.0, 0.0

    idx_peak = int(np.argmax(np.abs(corr)))
    pico = float(np.abs(corr[idx_peak]))
    abs_corr = np.abs(corr)
    mediana = float(np.median(abs_corr))
    confianca = pico / (mediana + 1e-8)

    if confianca < limiar_confianca:
        return 0.0, 0.0, 0.0

    offset_seg = float(lags[idx_peak]) / 16000.0
    start_global = janela_inicio + offset_seg
    end_global = start_global + (len(ref_sig) / 16000.0)
    return start_global, end_global, confianca


def calibrar_boletim(
    audio_path: str,
    limiar_abertura: float = 0.35,
    limiar_passagem: float = 0.35,
    limiar_encerramento: float = 0.35,
) -> dict:
    vinhetas = carregar_todas_vinhetas()
    try:
        audio = AudioSegment.from_file(audio_path)
    except Exception as e:
        return {
            'erro': str(e),
            'metodo': 'falha',
            'inicio_cabeca': None,
            'fim_cabeca': None,
            'inicio_corpo': None,
            'fim_corpo': None,
        }

    duracao_total = len(audio) / 1000.0
    resultado = {
        'abertura': None,
        'passagem': None,
        'encerramento': None,
        'inicio_cabeca': None,
        'fim_cabeca': None,
        'inicio_corpo': None,
        'fim_corpo': None,
        'metodo': 'calibracao_correlacao',
    }

    modo_sem_assets = vinhetas.get('abertura') is None and vinhetas.get('passagem') is None and vinhetas.get('encerramento') is None

    if modo_sem_assets:
        resultado['metodo'] = 'fallback'
        return resultado

    if vinhetas.get('abertura') is not None:
        try:
            ini, fim, conf = encontrar_vinheta_por_correlacao(
                audio, vinhetas['abertura'][0],
                janela_inicio=0.0,
                janela_fim=min(20.0, duracao_total),
                limiar_confianca=limiar_abertura,
            )
            if conf > 0:
                resultado['abertura'] = (ini, fim, conf)
                resultado['inicio_cabeca'] = fim
        except Exception:
            pass

    if vinhetas.get('encerramento') is not None:
        try:
            janela_ini = max(0, duracao_total - 25.0)
            ini, fim, conf = encontrar_vinheta_por_correlacao(
                audio, vinhetas['encerramento'][0],
                janela_inicio=janela_ini,
                janela_fim=duracao_total,
                limiar_confianca=limiar_encerramento,
            )
            if conf > 0:
                resultado['encerramento'] = (ini, fim, conf)
                resultado['fim_corpo'] = ini
        except Exception:
            pass

    if vinhetas.get('passagem') is not None:
        try:
            ini_busca = (resultado['inicio_cabeca'] or 0.0) + 1.0
            fim_busca = (resultado['fim_corpo'] or duracao_total) - 1.0
            if fim_busca > ini_busca:
                ini, fim, conf = encontrar_vinheta_por_correlacao(
                    audio, vinhetas['passagem'][0],
                    janela_inicio=ini_busca,
                    janela_fim=fim_busca,
                    limiar_confianca=limiar_passagem,
                )
                if conf > 0:
                    resultado['passagem'] = (ini, fim, conf)
                    resultado['fim_cabeca'] = ini
                    resultado['inicio_corpo'] = fim
        except Exception:
            pass

    if any(v is None for v in [resultado['inicio_cabeca'], resultado['fim_cabeca'], resultado['inicio_corpo'], resultado['fim_corpo']]):
        resultado['metodo'] = 'calibracao_correlacao+fallback'

    return resultado


def strip_silence(audio: AudioSegment, silence_thresh: int = -40) -> AudioSegment:
    from pydub.silence import detect_leading_silence
    start_trim = detect_leading_silence(audio, silence_thresh)
    end_trim = detect_leading_silence(audio.reverse(), silence_thresh)
    duration = len(audio)
    return audio[start_trim:duration - end_trim]
