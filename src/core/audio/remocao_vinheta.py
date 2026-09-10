"""
core/audio/remocao_vinheta.py

Remoção proativa da vinheta de abertura do boletim (Camada A / Fase 2 do
projeto de correção GIRO/NJUD) antes do corte em CABEÇA/CORPO.

CONTEXTO DO BUG:
Com `usar_separacao_stems=False` (padrão atual em todos os JSONs de
planejamento), o corte (`divisor_boletins.audio.processar_arquivo`) opera
sobre o áudio bruto do boletim. Se `VHT_ABERTURA_BOLETIM.mp3` estiver no
início desse áudio, ela é preservada no arquivo CABEÇA gerado. A montagem
(GIRO ou NJUD) então soma sua própria vinheta de abertura por cima,
produzindo o defeito "vinheta de boletim + vinheta de programa".

Esta função é a camada de defesa que roda ANTES do corte, independente de
Demucs estar habilitado ou não (Camada B). Se Demucs falhar/estiver
desabilitado, esta é a rede de segurança leve.

Uso:
    from core.audio.remocao_vinheta import remover_vinheta_boletim

    audio_limpo = remover_vinheta_boletim(caminho_boletim, caminho_vinheta_ref)
    if audio_limpo is not None:
        arquivo_para_corte = salvar_temp(audio_limpo)   # ver integração abaixo
    else:
        arquivo_para_corte = caminho_boletim  # vinheta não detectada ou erro — segue original
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from pydub import AudioSegment
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# O modelo é caro para carregar (~1-2s) — reutiliza uma única instância
# por processo em vez de recarregar a cada chamada (bug do pseudocódigo original).
_MODELO_DETECCAO: Optional[WhisperModel] = None

# Quanto além do tamanho da vinheta ainda vale a pena transcrever, para
# cobrir pequenas variações de silêncio/fade-in na gravação original.
MARGEM_SEGURANCA_MS = 1500

# Mínimo de palavras-chave da vinheta que precisam reaparecer no início
# do boletim para considerarmos "vinheta detectada". 1 palavra é frágil
# demais (pode ser "de" ou "justiça" por coincidência); exigimos 2+.
MIN_PALAVRAS_COINCIDENTES = 2
TAMANHO_MIN_PALAVRA = 3
MAX_PALAVRAS_CHAVE = 6


def _get_modelo(modelo_whisper: str = "tiny") -> WhisperModel:
    global _MODELO_DETECCAO
    if _MODELO_DETECCAO is None:
        logger.info("Carregando modelo Whisper '%s' para detecção de vinheta", modelo_whisper)
        _MODELO_DETECCAO = WhisperModel(modelo_whisper, device="cpu", compute_type="int8")
    return _MODELO_DETECCAO


def _audio_para_array(segmento: AudioSegment, sample_rate_alvo: int = 16000) -> np.ndarray:
    """
    Converte um AudioSegment para float32 mono no sample rate que o
    faster-whisper espera. Evita escrever em arquivo temporário.

    NOTA: o pseudocódigo original passava o AudioSegment direto para
    `modelo.transcribe(...)`, o que não funciona — faster-whisper espera
    um caminho de arquivo ou um array numpy float32.
    """
    seg = segmento.set_channels(1).set_frame_rate(sample_rate_alvo)
    amostras = np.array(seg.get_array_of_samples()).astype(np.float32)
    amostras /= float(1 << (8 * seg.sample_width - 1))  # normaliza int16 -> [-1.0, 1.0]
    return amostras


def _transcrever(segmento: AudioSegment, modelo: WhisperModel) -> str:
    array = _audio_para_array(segmento)
    segmentos, _info = modelo.transcribe(array, language="pt", vad_filter=False)
    return " ".join(s.text.strip() for s in segmentos if s.text.strip())


def remover_vinheta_boletim(
    caminho_audio: Path,
    caminho_vinheta: Path,
    modelo_whisper: str = "tiny",
    min_palavras_coincidentes: int = MIN_PALAVRAS_COINCIDENTES,
) -> Optional[AudioSegment]:
    """
    Detecta e remove a vinheta de abertura do boletim, se presente no
    início do áudio.

    Estratégia: transcreve os primeiros N segundos do boletim (N = duração
    da vinheta de referência + margem de segurança) e transcreve a própria
    vinheta de referência. Se um número mínimo de palavras-chave da
    vinheta reaparecer no trecho inicial do boletim, considera a vinheta
    presente e corta a região correspondente.

    Args:
        caminho_audio: Caminho do áudio bruto do boletim.
        caminho_vinheta: Caminho da vinheta de referência
            (ex.: assets/vinhetas/boletim/VHT_ABERTURA_BOLETIM.mp3).
        modelo_whisper: Tamanho do modelo Whisper usado na detecção.
            Recomenda-se manter "tiny" aqui — é só detecção binária,
            não transcrição de produção. Considere usar
            settings.MODELO_WHISPER se quiser unificar com o resto do
            pipeline (ver nota de integração abaixo).
        min_palavras_coincidentes: Quantas palavras-chave da vinheta
            precisam reaparecer no início do boletim para confirmar.

    Returns:
        AudioSegment do boletim sem a vinheta de abertura, ou None se:
        - a vinheta não foi detectada (o áudio já está limpo), ou
        - ocorreu qualquer erro no processo.
        Em ambos os casos de None, o chamador deve usar o áudio original
        — esta função nunca deve bloquear o pipeline por conta própria
        (essa responsabilidade é da Camada C / RegraVinhetaBoletimAusente).
    """
    try:
        if not caminho_audio.exists():
            logger.warning("Áudio não encontrado: %s", caminho_audio)
            return None
        if not caminho_vinheta.exists():
            logger.warning("Vinheta de referência não encontrada: %s", caminho_vinheta)
            return None

        audio = AudioSegment.from_file(str(caminho_audio))
        vinheta = AudioSegment.from_file(str(caminho_vinheta))

        if len(vinheta) >= len(audio):
            logger.warning(
                "Vinheta (%dms) maior ou igual ao áudio (%dms) — pulando detecção: %s",
                len(vinheta), len(audio), caminho_audio.name,
            )
            return None

        janela_ms = len(vinheta) + MARGEM_SEGURANCA_MS
        trecho_inicial = audio[:janela_ms]

        modelo = _get_modelo(modelo_whisper)
        texto_trecho = _transcrever(trecho_inicial, modelo).lower()
        texto_vinheta = _transcrever(vinheta, modelo).lower()

        if not texto_vinheta:
            logger.info(
                "Vinheta de referência não produziu transcrição utilizável: %s",
                caminho_vinheta.name,
            )
            return None

        palavras_vinheta = [p for p in texto_vinheta.split() if len(p) > TAMANHO_MIN_PALAVRA]
        palavras_chave = palavras_vinheta[:MAX_PALAVRAS_CHAVE]
        coincidencias = [p for p in palavras_chave if p in texto_trecho]

        if len(coincidencias) < min_palavras_coincidentes:
            logger.debug(
                "Vinheta não detectada em %s (coincidências: %d/%d necessárias)",
                caminho_audio.name, len(coincidencias), min_palavras_coincidentes,
            )
            return None

        # Vinheta detectada — corta pela duração real da vinheta (não pela
        # janela com margem), para não descartar áudio de programa além
        # do necessário.
        logger.info(
            "Vinheta de boletim detectada em %s (coincidências: %s) — removendo %dms",
            caminho_audio.name, coincidencias, len(vinheta),
        )
        return audio[len(vinheta):]

    except Exception:
        logger.exception("Falha ao tentar remover vinheta de boletim em %s", caminho_audio)
        return None
