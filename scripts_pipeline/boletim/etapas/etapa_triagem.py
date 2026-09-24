"""
Etapa 0: Triagem inicial do áudio e carregamento do modelo Whisper.
"""
import sys
# Limpar paths do Hermes para evitar conflito de imports do faster_whisper
sys.path = [p for p in sys.path if 'hermes' not in p.lower() and 'AppData/Local/hermes' not in p]

import os
import tempfile
from pathlib import Path

from pydub import AudioSegment

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # scripts_pipeline/

# Usar faster-whisper (CTranslate2) — 1.3-3x mais rápido em CPU
try:
    from faster_whisper import WhisperModel
    USE_FASTER = True
except ImportError:
    import whisper
    USE_FASTER = False

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WHISPER_MODEL = os.environ.get("DIVISOR_WHISPER_MODEL", "small")


def triagem_audio(audio):
    """ETAPA 0: triagem inicial. Retorna dict com análise e ações."""
    duracao = len(audio) / 1000
    canais = audio.channels
    frame_rate = audio.frame_rate
    sample_width = audio.sample_width

    resultado = {
        "duracao_segundos": duracao,
        "canais": canais,
        "frame_rate": frame_rate,
        "sample_width": sample_width,
        "acoes": []
    }

    # Canal morto: um canal com amplitude próxima de 0
    if canais == 2:
        monoEsq = audio.split_to_mono()[0]
        monoDir = audio.split_to_mono()[1]

        maxEsq = monoEsq.max
        maxDir = monoDir.max

        if maxEsq < 500 and maxDir > 5000:
            resultado["canal_morto"] = "esquerdo"

        if maxEsq < 100 and maxDir > 1000:
            resultado["canal_morto"] = "esquerdo"
            resultado["acoes"].append("CORRIGIR: substituir canal esquerdo pelo direito (multiplicar esquerdo por fator de escala do direito)")
        elif maxDir < 100 and maxEsq > 1000:
            resultado["canal_morto"] = "direito"
            resultado["acoes"].append("CORRIGIR: substituir canal direito pelo esquerdo (multiplicar direito por fator de escala do esquerdo)")

        # Estéreo duplicado
        samplesEsq = list(monoEsq.get_array_of_samples())
        samplesDir = list(monoDir.get_array_of_samples())
        if samplesEsq == samplesDir:
            resultado["estereo_duplicado"] = True
            resultado["acoes"].append("CONVERTER: áudio estereo duplicado (L==R) → converter para mono")

    # Clipping
    if audio.max >= 32767 * 0.99:
        resultado["clipping_detectado"] = True
        resultado["acoes"].append("AVISO: possível clipping (pico próximo de 0dBFS)")

    return resultado


def carregar_modelo():
    """Carrega modelo Whisper (faster-whisper se disponível, senão openai-whisper)."""
    if USE_FASTER:
        print("  Usando faster-whisper (int8, CPU)...")
        return WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    else:
        print("  Usando openai-whisper (fallback)...")
        return whisper.load_model(WHISPER_MODEL)
