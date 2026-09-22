"""
bgm_mixer.py — Mixagem de trilha de fundo (BGM) com Auto-Ducking dinâmico.

Portado de radioflow/backend/bgm_mixer.py em 2026-09-14.
Adaptado para o pipeline canônico de boletins TJRN.

Responsabilidade única: sobrepor uma trilha de fundo ao áudio de voz,
realizando loop e redução de volume adaptativa (ducking) baseada na
energia RMS da voz. A BGM desce automaticamente durante a fala e sobe
nos momentos de silêncio, emulando o comportamento de um mixer de rádio
profissional.
"""

import os
import numpy as np
from pydub import AudioSegment


# ── Constantes de Duck ─────────────────────────────────────────────────────────
# NOTA: estes valores são GANHO (dB) aplicados sobre o nível original do BG.
# BG - BOLETIM.mp3 tem RMS de -21.5 dBFS.
# Para que o BG fique a -14 dBFS em silêncio: ganho = -14 - (-21.5) = +7.5 dB
# Para que o BG fique a -20 dBFS durante voz: ganho = -20 - (-21.5) = +1.5 dB

# Volume da BGM em silêncio (fundo de abertura / fechamento)
# Ganho sobre BG original (-21.5 dBFS). +12 = BG a -9.5 dBFS (bem audível)
BGM_FULL_DB: float = 12.0

# Volume da BGM quando o locutor está falando
# +6 = BG a -15.5 dBFS (audível sob voz, não compete)
BGM_DUCK_DB: float = 6.0

# Limiar de energia RMS (float normalizado) para detectar presença de voz.
# Abaixo deste valor → silêncio; acima → voz ativa.
VOICE_RMS_THRESHOLD: float = 0.004

# Tamanho do bloco de análise em ms (quanto menor, mais responsivo)
ANALYSIS_CHUNK_MS: int = 50

# Constantes de suavização do envelope de ducking (em amostras de 50ms).
# Attack: quantos blocos para descer o volume (resposta rápida).
# Release: quantos blocos para subir o volume (resposta lenta e suave).
ATTACK_BLOCKS: int = 2
RELEASE_BLOCKS: int = 12


def mix_bgm(
    voice_segment: AudioSegment,
    bgm_path: str | None,
    bgm_full_db: float = BGM_FULL_DB,
    bgm_duck_db: float = BGM_DUCK_DB,
) -> AudioSegment:
    """
    Mixa uma trilha de fundo (BGM) sob o áudio de voz com Auto-Ducking dinâmico.

    O algoritmo:
    1. Analisa a energia RMS da voz em blocos de ANALYSIS_CHUNK_MS.
    2. Classifica cada bloco como "voz ativa" ou "silêncio".
    3. Aplica um envelope de ganho suavizado (attack/release) à BGM,
       descendo quando há voz e subindo quando há silêncio.
    4. Mixtura bloco a bloco.

    Se bgm_path for None ou não existir, retorna o segmento original.
    """
    if not bgm_path or not os.path.exists(bgm_path):
        return voice_segment

    # ── Preparar BGM em loop ───────────────────────────────────────────────────
    bgm_raw = AudioSegment.from_file(bgm_path)

    # Normalizar para mesma taxa de amostragem e canais que a voz
    bgm_raw = bgm_raw.set_frame_rate(voice_segment.frame_rate)
    bgm_raw = bgm_raw.set_channels(voice_segment.channels)

    # Loop da BGM para cobrir toda a duração da voz
    while len(bgm_raw) < len(voice_segment):
        bgm_raw = bgm_raw + bgm_raw
    bgm_raw = bgm_raw[: len(voice_segment)]

    # ── Análise de energia da voz ──────────────────────────────────────────────
    voice_samples = _to_float_array(voice_segment)
    bgm_samples = _to_float_array(bgm_raw)

    num_frames = voice_segment.frame_count()
    frames_per_chunk = int(voice_segment.frame_rate * ANALYSIS_CHUNK_MS / 1000)
    n_chunks = max(1, int(np.ceil(num_frames / frames_per_chunk)))

    # Calcular RMS por bloco
    rms_per_chunk = _compute_rms_blocks(voice_samples, frames_per_chunk, n_chunks)

    # Determinar se cada bloco tem voz ativa
    is_voice = rms_per_chunk > VOICE_RMS_THRESHOLD

    # Construir envelope de ganho suavizado (em dB) via attack/release
    gain_envelope_db = _build_gain_envelope(
        is_voice, n_chunks, bgm_full_db, bgm_duck_db
    )

    # ── Aplicar envelope bloco a bloco ────────────────────────────────────────
    ducked_bgm = _apply_gain_envelope(bgm_samples, gain_envelope_db, frames_per_chunk, n_chunks)

    # ── Remontar AudioSegment e mixar ─────────────────────────────────────────
    ducked_bgm_segment = _float_array_to_segment(ducked_bgm, voice_segment)
    return ducked_bgm_segment.overlay(voice_segment)


# ── Funções Auxiliares Privadas ────────────────────────────────────────────────


def _to_float_array(segment: AudioSegment) -> np.ndarray:
    """Converte AudioSegment para array float32 normalizado [-1, 1]."""
    raw = np.array(segment.get_array_of_samples(), dtype=np.float32)
    if segment.channels == 2:
        # Interleaved stereo → média dos canais para análise de envelope
        raw = raw.reshape(-1, 2).mean(axis=1)
    return raw / 32768.0


def _compute_rms_blocks(
    samples: np.ndarray, frames_per_chunk: int, n_chunks: int
) -> np.ndarray:
    """Calcula o RMS de cada bloco de frames."""
    rms = np.zeros(n_chunks, dtype=np.float32)
    for i in range(n_chunks):
        start = i * frames_per_chunk
        end = min(start + frames_per_chunk, len(samples))
        block = samples[start:end]
        if len(block) > 0:
            rms[i] = float(np.sqrt(np.mean(block ** 2)))
    return rms


def _build_gain_envelope(
    is_voice: np.ndarray,
    n_chunks: int,
    full_db: float,
    duck_db: float,
) -> np.ndarray:
    """
    Constrói envelope de ganho (em dB) com ataque e liberação suavizados.

    - Quando `is_voice[i]` é True  → descer para duck_db (attack).
    - Quando `is_voice[i]` é False → subir para full_db  (release).
    """
    gain_db = np.full(n_chunks, full_db, dtype=np.float32)
    current_gain = full_db

    for i in range(n_chunks):
        target = duck_db if is_voice[i] else full_db

        if target < current_gain:
            # Descendo (attack) — mais rápido
            step = (current_gain - target) / ATTACK_BLOCKS
            current_gain = max(target, current_gain - step)
        else:
            # Subindo (release) — mais lento e suave
            step = (target - current_gain) / RELEASE_BLOCKS
            current_gain = min(target, current_gain + step)

        gain_db[i] = current_gain

    return gain_db


def _apply_gain_envelope(
    bgm_samples: np.ndarray,
    gain_envelope_db: np.ndarray,
    frames_per_chunk: int,
    n_chunks: int,
) -> np.ndarray:
    """Aplica o envelope de ganho (em dB) ao array de samples da BGM."""
    output = np.zeros_like(bgm_samples)

    for i in range(n_chunks):
        start = i * frames_per_chunk
        end = min(start + frames_per_chunk, len(bgm_samples))
        linear_gain = 10.0 ** (gain_envelope_db[i] / 20.0)
        output[start:end] = bgm_samples[start:end] * linear_gain

    return output


def _float_array_to_segment(samples: np.ndarray, reference: AudioSegment) -> AudioSegment:
    """Converte array float32 de volta para AudioSegment."""
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16).tobytes()

    return AudioSegment(
        data=pcm,
        sample_width=2,  # 16-bit
        frame_rate=reference.frame_rate,
        channels=1,  # envelope foi calculado em mono; stereo é tratado no overlay
    ).set_channels(reference.channels)
