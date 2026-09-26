from __future__ import annotations

"""Audio processing — núcleo do divisor_boletins.

Esta é a reconstrução mínima do divisor_boletins/audio.py, baseada no que o
legado realmente implementa e no que o ARQUITETURA_REAL.md e o
processar_boletim.py esperam.

Funções esperadas pelo legado (documentadas em ARQUITETURA_REAL.md):
    - processar_arquivo(): ponto de entrada de processamento de um boletim.
    - carregar_modelo(): carrega o modelo Whisper de transcrição.
    - transcrever_audio(): transcreve um áudio com Whisper.
    - calibrar_boletim(): calibra o ponto de início (importado de calibracao.py).
    - cortar_audio(): executa o corte do áudio em CABEÇA/CORPO.

A interface CLI pública usada pelo njud_dividir.sh é:
    python -m divisor_boletins dividir <pasta_entrada> <pasta_saida> --apply
que é implementada em __main__.py. Este módulo fornece as primitivas."""

import logging
from pathlib import Path
from typing import Any, Optional

from faster_whisper import WhisperModel

from .calibracao import calibrar_boletim
from .deteccao import buscar_ancora

logger = logging.getLogger(__name__)

# Modelo único em memória, compatível com o padrão do legado
_MODELO: Optional[WhisperModel] = None


def carregar_modelo(modelo_nome: str = "tiny", **kwargs: Any) -> WhisperModel:
    """Carrega (ou reutiliza) o modelo Whisper para transcrição.

    Args:
        modelo_nome: nome do modelo Whisper (ex.: "tiny", "base", "small").

    Returns:
        WhisperModel carregado.
    """
    global _MODELO
    if _MODELO is None:
        logger.info("Carregando modelo Whisper '%s' para divisor_boletins.audio", modelo_nome)
        _MODELO = WhisperModel(modelo_nome, device="cpu", compute_type="int8")
    return _MODELO


def transcrever_audio(
    caminho_audio: Path | str,
    modelo: Optional[WhisperModel] = None,
    *,
    retornar_segmentos: bool = False,
    **kwargs: Any,
) -> str | tuple[str, list[dict[str, Any]]]:
    """Transcreve um arquivo de áudio com Whisper.

    Args:
        caminho_audio: caminho do arquivo de áudio.
        modelo: modelo Whisper pré-carregado. Se None, usa o carregado
            automaticamente pelo carregar_modelo().
        retornar_segmentos: se True, também devolve os segmentos com
            timestamp (start/end/text) que o faster-whisper já produz —
            necessário para localizar no TEMPO onde a assinatura de
            encerramento começa (ver deteccao.buscar_ancora()).

    Returns:
        Texto transcrito (str), ou (texto, segmentos) se retornar_segmentos=True.
    """
    modelo = modelo or carregar_modelo()
    try:
        from pydub import AudioSegment
        from pydub.silence import detect_nonsilent
    except ImportError as e:
        raise RuntimeError("pydub não disponível") from e

    audio = AudioSegment.from_file(str(caminho_audio))
    # Exporta para wav temporário, pois o faster-whisper aceita arquivo.
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        audio.export(tmp_path, format="wav")
        segments, _info = modelo.transcribe(tmp_path, language="pt", vad_filter=True)
        segmentos_lista: list[dict[str, Any]] = []
        partes_texto: list[str] = []
        for s in segments:
            texto_seg = s.text.strip()
            if texto_seg:
                partes_texto.append(texto_seg)
            segmentos_lista.append({"start": s.start, "end": s.end, "text": texto_seg})
        texto = " ".join(partes_texto)
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass

    if retornar_segmentos:
        return texto, segmentos_lista
    return texto


def _carregar_vinheta_ref(
    assets_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Retorna o caminho da vinheta de abertura de referência, se existir."""
    if assets_dir is None:
        assets_dir = Path(__file__).resolve().parent.parent.parent / "assets" / "vinhetas" / "njud"
    vinheta = assets_dir / "VHT_ABERTURA_NJUD.mp3"
    if not vinheta.exists():
        return None
    return vinheta


def _remover_vinheta(
    audio: Any,
    vinheta_ref: Optional[Path] = None,
    modelo: Optional[WhisperModel] = None,
) -> tuple[Any, bool, float]:
    """Tenta remover a vinheta de abertura do áudio.

    Retorna (audio_limpo, foi_removida, duracao_vinheta_s).
    """
    if vinheta_ref is None:
        vinheta_ref = _carregar_vinheta_ref()
    if vinheta_ref is None or not vinheta_ref.exists():
        return audio, False, 0.0

    try:
        from core.audio.remocao_vinheta import remover_vinheta_boletim
    except ImportError:
        logger.warning("remocao_vinheta não disponível — pulando remoção de vinheta")
        return audio, False, 0.0

    try:
        from pydub import AudioSegment
    except ImportError:
        return audio, False, 0.0

    from pathlib import Path

    resultado = remover_vinheta_boletim(
        Path("entrada_temporaria.mp3"),
        vinheta_ref,
        modelo_whisper="tiny",
        min_palavras_coincidentes=2,
    )
    if resultado is None:
        return audio, False, 0.0
    return resultado, True, len(resultado) / 1000.0


def cortar_audio(
    audio: Any,
    *,
    tempo_cabeca_fim_s: float,
    tempo_pos_vinheta_s: float = 0.0,
    tempo_assinatura_inicio_s: Optional[float] = None,
    **kwargs: Any,
) -> tuple[Any, Any]:
    """Corta um áudio em cabeça e corpo.

    Args:
        audio: AudioSegment.
        tempo_cabeca_fim_s: instante (em s) onde a cabeça termina.
        tempo_pos_vinheta_s: instante (em s) onde o conteúdo útil começa
            (após remoção de vinheta, se aplicável).
        tempo_assinatura_inicio_s: instante (em s) onde a assinatura começa,
            se detectada; caso contrário usa o final do áudio.

    Returns:
        (cabeca, corpo) como AudioSegments.
    """
    from pydub import AudioSegment

    inicio_ms = int(tempo_pos_vinheta_s * 1000)
    fim_cabeca_ms = int(tempo_cabeca_fim_s * 1000)
    if tempo_assinatura_inicio_s is None:
        inicio_assinatura_ms = len(audio)
    else:
        inicio_assinatura_ms = int(tempo_assinatura_inicio_s * 1000)

    cabeca = audio[inicio_ms:fim_cabeca_ms]
    corpo = audio[fim_cabeca_ms:inicio_assinatura_ms]
    return cabeca, corpo


def processar_arquivo(
    caminho_audio: Path | str,
    pasta_saida: Path | str,
    *,
    modelo: Optional[WhisperModel] = None,
    logger: Optional[Any] = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Processa UM arquivo de áudio: transcreve, calibra e corta.

    Esta é a função central que o processar_boletim.py espera que o
    divisor_boletins/audio.py forneça. No mínimo:
        1. transcreve o áudio
        2. calibra o ponto de início
        3. retorna um dict com os resultados (sem salvar cortado, pois
           a etapa de salvar cortada pertence ao processar_boletim.py ou
           ao script de divisão).

    Args:
        caminho_audio: caminho do áudio de entrada.
        pasta_saida: diretório de saída (pode ser usado para salvar resultados).
        modelo: modelo Whisper opcional.
        logger: logger opcional.

    Returns:
        dict com chaves: 'transcricao', 'calibracao', 'ancora', 'audio_seg',
        'caminho_saida', 'status'.
    """
    caminho_audio = Path(caminho_audio)
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    log = logger or logging.getLogger(__name__)
    log.info("processar_arquivo: %s", caminho_audio.name)

    if not caminho_audio.exists():
        log.error("arquivo não encontrado: %s", caminho_audio)
        return {"status": "erro", "erro": "arquivo não encontrado"}

    # 1. Transcrição (com segmentos com timestamp, necessários para
    # localizar a assinatura de encerramento no tempo em buscar_ancora())
    log.info("transcrevendo %s", caminho_audio.name)
    texto, segmentos = transcrever_audio(caminho_audio, modelo=modelo, retornar_segmentos=True)
    log.info("transcricao concluida (%d chars, %d segmentos)", len(texto), len(segmentos))

    # 2. Calibração
    from pydub import AudioSegment

    audio = AudioSegment.from_file(str(caminho_audio))
    calibracao = calibrar_boletim(
        audio,
        texto,
        vinheta_removida=False,
        duracao_vinheta_s=0.0,
    )
    log.info("calibracao: %s", calibracao)

    # 3. Ancora (assinatura de encerramento — limite superior do CORPO)
    ancora = buscar_ancora(
        audio,
        segmentos=segmentos,
        duracao_vinheta_s=calibracao.get("duracao_vinheta_s", 0.0),
        texto_inicio=texto,
    )
    log.info("ancora: %s", ancora)

    # 4. Monta resultado
    return {
        "status": "ok",
        "transcricao": texto,
        "calibracao": calibracao,
        "ancora": ancora,
        "audio_seg": audio,
        "caminho_saida": str(pasta_saida),
        "caminho_entrada": str(caminho_audio),
    }
