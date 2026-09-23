"""Geração de texto a partir do áudio editado (boletim já processado).

Transcreve usando faster_whisper, formata como roteiro jornalístico
e exporta em múltiplos formatos (txt, srt, json, vtt).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SegmentoTranscricao:
    """Segmento de transcrição com timestamps."""
    inicio: float  # segundos
    fim: float  # segundos
    texto: str
    palavras: list[dict] | None = None  # word-level timestamps


def transcrever_editado(
    audio_path: str | Path,
    model_size: str = "large-v3",
    language: str = "pt",
    device: str = "cpu",
    compute_type: str = "int8",
) -> list[SegmentoTranscricao]:
    """Transcreve o áudio editado usando faster_whisper.

    Args:
        audio_path: Caminho para o arquivo de áudio.
        model_size: Tamanho do modelo Whisper.
        language: Idioma do áudio (padrão: 'pt').
        device: Dispositivo de inferência ('cpu' ou 'cuda').
        compute_type: Tipo de cálculo para o modelo.

    Returns:
        Lista de SegmentoTranscricao com texto e timestamps.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")

    logger.info("Transcrevendo áudio: %s", audio_path)

    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )

    logger.info(
        "Detectado idioma: %s (probabilidade: %.2f)",
        info.language,
        info.language_probability,
    )

    segmentos: list[SegmentoTranscricao] = []
    for segment in segments_iter:
        palavras = None
        if segment.words:
            palavras = [
                {
                    "palavra": w.word,
                    "inicio": round(w.start, 3),
                    "fim": round(w.end, 3),
                    "probabilidade": round(w.probability, 3),
                }
                for w in segment.words
            ]

        segmentos.append(
            SegmentoTranscricao(
                inicio=round(segment.start, 3),
                fim=round(segment.end, 3),
                texto=segment.text.strip(),
                palavras=palavras,
            )
        )

    logger.info("Transcrição concluída: %d segmentos", len(segmentos))
    return segmentos


def formatar_roteiro(texto: str) -> str:
    """Formata texto transcrito como roteiro jornalístico.

    Remove timestamps, organiza em parágrafos e limpa artefatos.

    Args:
        texto: Texto bruto da transcrição.

    Returns:
        Texto formatado como roteiro.
    """
    # Remover timestamps tipo [00:00:00] ou [00:00.000]
    texto_limpo = re.sub(r"\[\d{2}:\d{2}[:\.]\d{2,3}\]", "", texto)

    # Remover quebras de linha excessivas
    texto_limpo = re.sub(r"\n{3,}", "\n\n", texto_limpo)

    # Dividir em parágrafos por ponto final seguido de espaço e maiúscula
    frases = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú])", texto_limpo)

    # Agrupar frases em parágrafos (a cada ~3 frases)
    paragrafos: list[str] = []
    grupo_atual: list[str] = []
    for i, frase in enumerate(frases):
        grupo_atual.append(frase.strip())
        if len(grupo_atual) >= 3 or i == len(frases) - 1:
            paragrafos.append(" ".join(grupo_atual))
            grupo_atual = []

    # Limpar cada parágrafo
    paragrafos_limpos = []
    for paragrafo in paragrafos:
        paragrafo = paragrafo.strip()
        # Remover espaços múltiplos
        paragrafo = re.sub(r"\s+", " ", paragrafo)
        if paragrafo:
            paragrafos_limpos.append(paragrafo)

    return "\n\n".join(paragrafos_limpos)


def _formatar_tempo_srt(segundos: float) -> str:
    """Formata tempo no formato SRT: HH:MM:SS,mmm."""
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = int(segundos % 60)
    milissegundos = int((segundos % 1) * 1000)
    return f"{horas:02d}:{minutos:02d}:{segs:02d},{milissegundos:03d}"


def _formatar_tempo_vtt(segundos: float) -> str:
    """Formata tempo no formato VTT: HH:MM:SS.mmm."""
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = int(segundos % 60)
    milissegundos = int((segundos % 1) * 1000)
    return f"{horas:02d}:{minutos:02d}:{segs:02d}.{milissegundos:03d}"


def gerar_legendas(
    segmentos: list[SegmentoTranscricao],
    formato: str = "srt",
) -> str:
    """Gera conteúdo de legendas a partir de segmentos com timestamps.

    Args:
        segmentos: Lista de SegmentoTranscricao.
        formato: Formato de saída ('srt' ou 'vtt').

    Returns:
        String com o conteúdo das legendas formatado.
    """
    formato = formato.lower().strip(".")
    if formato not in ("srt", "vtt"):
        raise ValueError(f"Formato não suportado: {formato}. Use 'srt' ou 'vtt'.")

    if formato == "vtt":
        linhas = ["WEBVTT", ""]
        for i, seg in enumerate(segmentos, 1):
            inicio = _formatar_tempo_vtt(seg.inicio)
            fim = _formatar_tempo_vtt(seg.fim)
            linhas.append(f"{inicio} --> {fim}")
            linhas.append(seg.texto)
            linhas.append("")
    else:  # srt
        linhas = []
        for i, seg in enumerate(segmentos, 1):
            inicio = _formatar_tempo_srt(seg.inicio)
            fim = _formatar_tempo_srt(seg.fim)
            linhas.append(str(i))
            linhas.append(f"{inicio} --> {fim}")
            linhas.append(seg.texto)
            linhas.append("")

    return "\n".join(linhas)


def exportar_roteiro(
    audio_path: str | Path,
    output_path: str | Path,
    formato: str = "txt",
    model_size: str = "large-v3",
    language: str = "pt",
    device: str = "cpu",
    compute_type: str = "int8",
) -> Path:
    """Pipeline completo: transcreve, formata e exporta o roteiro.

    Args:
        audio_path: Caminho para o arquivo de áudio.
        output_path: Caminho do arquivo de saída.
        formato: Formato de saída ('txt', 'srt', 'json', 'vtt').
        model_size: Tamanho do modelo Whisper.
        language: Idioma do áudio.
        device: Dispositivo de inferência.
        compute_type: Tipo de cálculo.

    Returns:
        Path do arquivo gerado.
    """
    formato = formato.lower().strip(".")
    formatos_validos = ("txt", "srt", "json", "vtt")
    if formato not in formatos_validos:
        raise ValueError(
            f"Formato '{formato}' não suportado. Use: {formatos_validos}"
        )

    audio_path = Path(audio_path)
    output_path = Path(output_path)

    # Transcrever
    segmentos = transcrever_editado(
        audio_path,
        model_size=model_size,
        language=language,
        device=device,
        compute_type=compute_type,
    )

    # Gerar conteúdo conforme formato
    if formato == "txt":
        texto_bruto = " ".join(seg.texto for seg in segmentos)
        conteudo = formatar_roteiro(texto_bruto)
    elif formato == "json":
        conteudo = json.dumps(
            [asdict(seg) for seg in segmentos],
            ensure_ascii=False,
            indent=2,
        )
    elif formato in ("srt", "vtt"):
        conteudo = gerar_legendas(segmentos, formato=formato)
    else:
        # Nunca chega aqui por causa da validação acima
        conteudo = ""

    # Escrever arquivo
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(conteudo, encoding="utf-8")

    logger.info("Roteiro exportado: %s (formato: %s)", output_path, formato)
    return output_path
