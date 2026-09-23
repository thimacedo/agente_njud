"""Detecção automática de locutores no áudio.

Usa pydub + numpy para segmentar fala e classificar locutores
por características de voz (pitch via FFT, energia RMS).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

logger = logging.getLogger(__name__)

# Locutores conhecidos com perfis de voz estimados
# pitch_medio_esperado em Hz (valores típicos para vozes masculinas/femininas)
LOCUTORES_CONHECIDOS: dict[str, dict] = {
    "Thiago Macedo": {"pitch_range": (85, 160), "energia_tipo": "media"},
    "Samuel Ferreira": {"pitch_range": (90, 170), "energia_tipo": "media-alta"},
    "Lívia Rodrigues": {"pitch_range": (165, 260), "energia_tipo": "media"},
    "Leonardo Almeida": {"pitch_range": (80, 155), "energia_tipo": "media"},
}

# Parâmetros de segmentação de fala
SILENCE_THRESH_DB = -40  # dBFS
MIN_SILENCE_LEN_MS = 300  # milissegundos


@dataclass
class SegmentoFala:
    """Representa um segmento de fala detectado no áudio."""
    audio_segment: AudioSegment
    inicio_ms: int
    fim_ms: int
    duracao_ms: int = field(init=False)

    def __post_init__(self) -> None:
        self.duracao_ms = self.fim_ms - self.inicio_ms

    @property
    def duracao_segundos(self) -> float:
        return self.duracao_ms / 1000.0


def extrair_segmentos_fala(
    audio_path: str | Path,
    silence_thresh: int = SILENCE_THRESH_DB,
    min_silence_len: int = MIN_SILENCE_LEN_MS,
) -> list[SegmentoFala]:
    """Segmenta o áudio em trechos de fala usando detecção de silêncio.

    Args:
        audio_path: Caminho para o arquivo de áudio.
        silence_thresh: Limiar de silêncio em dBFS (padrão: -40).
        min_silence_len: Duração mínima de silêncio em ms (padrão: 300).

    Returns:
        Lista de SegmentoFala com os trechos de fala detectados.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")

    logger.info("Carregando áudio: %s", audio_path)
    audio = AudioSegment.from_file(str(audio_path))

    logger.info(
        "Detectando segmentos de fala (silence_thresh=%d dBFS, min_silence_len=%d ms)",
        silence_thresh,
        min_silence_len,
    )
    ranges = detect_nonsilent(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
    )

    segmentos: list[SegmentoFala] = []
    for inicio, fim in ranges:
        trecho = audio[inicio:fim]
        segmentos.append(
            SegmentoFala(
                audio_segment=trecho,
                inicio_ms=inicio,
                fim_ms=fim,
            )
        )

    logger.info("Detectados %d segmentos de fala", len(segmentos))
    return segmentos


def _audio_to_numpy(audio_segment: AudioSegment) -> np.ndarray:
    """Converte um AudioSegment para numpy array normalizado [-1, 1]."""
    samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float64)
    # Normalizar para [-1, 1]
    max_val = float(1 << (audio_segment.sample_width * 8 - 1))
    return samples / max_val


def _calcular_pitch(audio_segment: AudioSegment) -> float:
    """Calcula o pitch fundamental (F0) via autocorrelação/FFT.

    Retorna a frequência fundamental estimada em Hz.
    """
    samples = _audio_to_numpy(audio_segment)
    sample_rate = audio_segment.frame_rate

    if len(samples) < 2:
        return 0.0

    # Aplicar janela Hann
    janela = np.hanning(len(samples))
    samples_janelados = samples * janela

    # FFT
    fft_result = np.fft.rfft(samples_janelados)
    magnitudes = np.abs(fft_result)
    freqs = np.fft.rfftfreq(len(samples_janelados), d=1.0 / sample_rate)

    # Considerar apenas faixa de voz humana (75 Hz - 300 Hz)
    mask_voz = (freqs >= 75) & (freqs <= 300)
    if not np.any(mask_voz):
        return 0.0

    magnitudes_voz = magnitudes[mask_voz]
    freqs_voz = freqs[mask_voz]

    # Pico de magnitude na faixa de voz
    idx_pico = np.argmax(magnitudes_voz)
    pitch = float(freqs_voz[idx_pico])

    return pitch


def _calcular_energia_rms(audio_segment: AudioSegment) -> float:
    """Calcula a energia RMS do segmento de áudio."""
    samples = _audio_to_numpy(audio_segment)
    if len(samples) == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(samples ** 2)))
    return rms


def classificar_locutor(segmento: SegmentoFala) -> dict:
    """Classifica o locutor de um segmento de fala.

    Analisa pitch (via FFT) e energia RMS para estimar qual locutor
    mais provavelmente está falando.

    Args:
        segmento: SegmentoFala a ser classificado.

    Returns:
        Dict com pitch_medio, energia, locutor_estimado e scores.
    """
    pitch = _calcular_pitch(segmento.audio_segment)
    energia = _calcular_energia_rms(segmento.audio_segment)

    # Calcular score para cada locutor conhecido
    scores: dict[str, float] = {}
    for nome, perfil in LOCUTORES_CONHECIDOS.items():
        pitch_min, pitch_max = perfil["pitch_range"]
        if pitch_min <= pitch <= pitch_max:
            # Score baseado na proximidade do centro do range
            centro = (pitch_min + pitch_max) / 2
            range_total = pitch_max - pitch_min
            distancia = abs(pitch - centro) / (range_total / 2)
            scores[nome] = max(0.0, 1.0 - distancia)
        else:
            # Fora do range: score penalizado
            dist_min = min(abs(pitch - pitch_min), abs(pitch - pitch_max))
            scores[nome] = max(0.0, 0.3 - dist_min / 200.0)

    # Selecionar locutor com maior score
    if scores:
        locutor_estimado = max(scores, key=scores.get)
        confianca = scores[locutor_estimado]
    else:
        locutor_estimado = "Desconhecido"
        confianca = 0.0

    return {
        "pitch_medio": round(pitch, 1),
        "energia": round(energia, 6),
        "locutor_estimado": locutor_estimado,
        "confianca": round(confianca, 3),
        "scores": {k: round(v, 3) for k, v in scores.items()},
        "inicio_ms": segmento.inicio_ms,
        "fim_ms": segmento.fim_ms,
        "duracao_segundos": round(segmento.duracao_segundos, 2),
    }


def estatisticas_locutores(audio_path: str | Path) -> dict:
    """Gera estatísticas agregadas por locutor.

    Args:
        audio_path: Caminho para o arquivo de áudio.

    Returns:
        Dict com estatísticas por locutor: tempo_fala, pitch_medio,
        energia_media, quantidade_segmentos.
    """
    segmentos = extrair_segmentos_fala(audio_path)
    if not segmentos:
        logger.warning("Nenhum segmento de fala detectado.")
        return {"locutores": {}, "total_segmentos": 0}

    # Classificar cada segmento
    classificacoes = [classificar_locutor(seg) for seg in segmentos]

    # Agregar por locutor
    stats: dict[str, dict] = {}
    for cls in classificacoes:
        locutor = cls["locutor_estimado"]
        if locutor not in stats:
            stats[locutor] = {
                "tempo_fala_segundos": 0.0,
                "pitch_valores": [],
                "energia_valores": [],
                "quantidade_segmentos": 0,
            }
        stats[locutor]["tempo_fala_segundos"] += cls["duracao_segundos"]
        stats[locutor]["pitch_valores"].append(cls["pitch_medio"])
        stats[locutor]["energia_valores"].append(cls["energia"])
        stats[locutor]["quantidade_segmentos"] += 1

    # Calcular médias
    resultado: dict = {"locutores": {}, "total_segmentos": len(segmentos)}
    for locutor, dados in stats.items():
        pitches = [p for p in dados["pitch_valores"] if p > 0]
        energias = [e for e in dados["energia_valores"] if e > 0]

        resultado["locutores"][locutor] = {
            "tempo_fala_segundos": round(dados["tempo_fala_segundos"], 2),
            "pitch_medio": round(float(np.mean(pitches)), 1) if pitches else 0.0,
            "energia_media": round(float(np.mean(energias)), 6) if energias else 0.0,
            "quantidade_segmentos": dados["quantidade_segmentos"],
        }

    return resultado


def detectar_locutores(audio_path: str | Path) -> dict:
    """Pipeline completo de detecção de locutores.

    Segmenta o áudio, classifica cada segmento e gera estatísticas.

    Args:
        audio_path: Caminho para o arquivo de áudio.

    Returns:
        Dict com segmentos classificados e estatísticas agregadas.
    """
    logger.info("Iniciando detecção de locutores: %s", audio_path)

    segmentos = extrair_segmentos_fala(audio_path)
    if not segmentos:
        logger.warning("Nenhum segmento de fala detectado.")
        return {
            "segmentos": [],
            "estatisticas": {"locutores": {}, "total_segmentos": 0},
        }

    # Classificar cada segmento
    classificacoes = [classificar_locutor(seg) for seg in segmentos]

    # Gerar estatísticas
    stats = estatisticas_locutores(audio_path)

    resultado = {
        "segmentos": classificacoes,
        "estatisticas": stats,
    }

    logger.info(
        "Detecção concluída: %d segmentos, %d locutores identificados",
        len(classificacoes),
        len(stats["locutores"]),
    )

    return resultado
