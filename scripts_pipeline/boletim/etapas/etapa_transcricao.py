"""
Etapa 1: Transcrição com Whisper + integração com cache.
"""
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # scripts_pipeline/

from shared.transcricao_cache import TranscricaoCache, calcular_hash_audio, get_cache

try:
    from faster_whisper import WhisperModel
    USE_FASTER = True
except ImportError:
    import whisper
    USE_FASTER = False

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TMP_DIR = Path(os.environ.get("DIVISOR_TMP", tempfile.gettempdir()))


def transcrever(audio, tmp_path, modelo):
    """ETAPA 1: transcrição com Whisper. Compatível com faster-whisper e openai-whisper.
    Usa word_timestamps=True para permitir cortes finos (claquete vs cabeça no mesmo segmento)."""
    audio.export(tmp_path, format="wav")
    
    if USE_FASTER:
        segments_iter, info = modelo.transcribe(tmp_path, language="pt", word_timestamps=True)
        segmentos = []
        for seg in segments_iter:
            entry = {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text
            }
            # Preservar word timestamps para corte fino de claquetes
            if hasattr(seg, "words") and seg.words:
                entry["words"] = [
                    {"word": w.word, "start": w.start, "end": w.end}
                    for w in seg.words
                ]
            segmentos.append(entry)
        os.unlink(tmp_path)
        return segmentos
    else:
        result = modelo.transcribe(tmp_path, language="pt", fp16=False, word_timestamps=True)
        os.unlink(tmp_path)
        return result["segments"]


def transcrever_com_cache(audio, tmp_path, modelo, arquivo_path=None):
    """Transcrição com suporte a cache. Se arquivo_path fornecido, tenta carregar
    do cache antes de transcrever. Salva no cache após transcrever."""
    if arquivo_path:
        try:
            cache = get_cache()
            hash_audio = calcular_hash_audio(str(arquivo_path))
            segmentos_cache = cache.get(hash_audio)
            if segmentos_cache is not None:
                print("  [cache] Transcrição carregada do cache")
                return segmentos_cache
        except Exception:
            pass  # Falha no cache: transcrever normalmente
    
    # Transcrever normalmente
    segmentos = transcrever(audio, tmp_path, modelo)
    
    # Salvar no cache
    if arquivo_path:
        try:
            cache = get_cache()
            hash_audio = calcular_hash_audio(str(arquivo_path))
            cache.put(hash_audio, segmentos)
            print("  [cache] Transcrição salva no cache")
        except Exception:
            pass
    
    return segmentos
