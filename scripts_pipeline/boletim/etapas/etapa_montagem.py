"""
Etapa 6: Montagem final com vinhetas, BG e normalização de loudness.
"""
import os
import re
import sys
import subprocess
import tempfile
from pathlib import Path

from pydub import AudioSegment

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # scripts_pipeline/

from shared.bgm_mixer import mix_bgm

try:
    from faster_whisper import WhisperModel
    USE_FASTER = True
except ImportError:
    import whisper
    USE_FASTER = False

PROJECT_ROOT = Path(__file__).resolve().parents[3]
VHT_DIR = Path(os.environ.get("DIVISOR_ASSETS", PROJECT_ROOT / "assets" / "vinhetas" / "boletim"))
TMP_DIR = Path(os.environ.get("DIVISOR_TMP", tempfile.gettempdir()))
BG_PATH = VHT_DIR / "BG - BOLETIM.mp3"


def carregar_vht(nome):
    """Carrega uma vinheta do diretório de assets."""
    caminho = VHT_DIR / nome
    if caminho.exists():
        return AudioSegment.from_mp3(str(caminho))
    return None


def calcular_duracao_cabeca(segmento_audio, texto_cabeca, modelo):
    """Calcula a duração da cabeça no áudio com base no texto do roteiro.
    
    Usa word-level timestamps do Whisper para encontrar onde cada palavra
    do roteiro aparece no áudio. A cabeça termina na última palavra encontrada.
    
    Retorna a duração em segundos.
    Se não encontrar correspondência, retorna 20s como fallback.
    """
    if not texto_cabeca:
        return 20  # fallback
    
    # Transcrever com word timestamps
    tmp = tempfile.mktemp(suffix='.wav', dir=str(TMP_DIR))
    segmento_audio.export(tmp, format="wav")
    
    if USE_FASTER:
        segments_iter, info = modelo.transcribe(tmp, language="pt", word_timestamps=True)
        segmentos_boletim = [{"start": s.start, "end": s.end, "text": s.text, "words": s.words} for s in segments_iter]
    else:
        result = modelo.transcribe(tmp, language="pt", word_timestamps=True)
        segmentos_boletim = result["segments"]
    
    os.unlink(tmp)
    
    # Normalizar texto da cabeça para comparação
    cabeca_norm = re.sub(r'[^\w\s]', '', texto_cabeca.lower()).strip()
    palavras_cabeca = cabeca_norm.split()
    
    if not palavras_cabeca:
        return 20
    
    # Coletar todas as palavras com timestamps
    todas_palavras = []
    for seg in segmentos_boletim:
        if "words" in seg:
            for w in seg["words"]:
                todas_palavras.append({"word": w.word, "start": w.start, "end": w.end})
        else:
            # Fallback: estimar timestamps
            todas_palavras.append({"word": seg["text"], "start": seg["start"], "end": seg["end"]})
    
    # Procurar palavras da cabeça em ordem no áudio
    # A cabeça termina quando encontramos uma palavra que NÃO pertence à cabeça
    palavras_encontradas = []
    idx_palavra = 0
    
    for palavra_audio in todas_palavras:
        if idx_palavra >= len(palavras_cabeca):
            break
        
        palavra_cabeca = palavras_cabeca[idx_palavra]
        palavra_norm = re.sub(r'[^\w]', '', palavra_cabeca.lower())
        palavra_audio_norm = re.sub(r'[^\w]', '', palavra_audio["word"].lower())
        
        if not palavra_norm or not palavra_audio_norm:
            continue
        
        # Verificar se a palavra do áudio corresponde à palavra da cabeça
        if palavra_norm in palavra_audio_norm or palavra_audio_norm in palavra_norm:
            score = len(set(palavra_norm) & set(palavra_audio_norm)) / max(len(palavra_norm), len(palavra_audio_norm))
            if score >= 0.5:
                palavras_encontradas.append({
                    "palavra": palavra_cabeca,
                    "timestamp": palavra_audio["end"],
                    "score": score
                })
                idx_palavra += 1
    
    if palavras_encontradas:
        # A cabeça termina na última palavra encontrada em ordem
        ultima_palavra = palavras_encontradas[-1]
        duracao = ultima_palavra["timestamp"]
        print(f"  [DEBUG] cabeça termina em {duracao:.1f}s ({len(palavras_encontradas)}/{len(palavras_cabeca)} palavras encontradas)")
        return duracao
    
    # Fallback: 20% do boletim
    duracao_total = len(segmento_audio) / 1000
    fallback = min(max(duracao_total * 0.20, 10), 30)
    print(f"  [DEBUG] FALLBACK: {fallback:.1f}s (duracao_total={duracao_total:.1f}s)")
    return fallback


def montar_boletim_com_vinhetas(segmento_audio, vht_abertura, vht_passagem, vht_encerramento, cabeça_duracao=20):
    """ETAPA 6: monta estrutura completa: ABERTURA + CABEÇA + PASSAGEM + OFF(com BG ducking) + ENCERRAMENTO.

    - BG (background music) toca durante o OFF com ducking (volume reduzido).
    - BG nunca ultrapassa o fim do off.
    - Se o off é mais curto que o BG, o BG é cortado.
    - Se o off é mais longo, o BG termina antes do encerramento.
    - A vinheta de passagem é inserida entre a cabeça e o OFF.
    """
    vht_a = vht_abertura or carregar_vht("VHT_ABERTURA_BOLETIM.mp3")
    vht_p = vht_passagem or carregar_vht("VHT_PASSAGEM_BOLETIM.mp3")
    vht_e = vht_encerramento or carregar_vht("VHT_ENCERRAMENTO_BOLETIM.mp3")
    bg = carregar_vht("BG - BOLETIM.mp3")

    # Dividir em cabeça e off
    duracao_total = len(segmento_audio) / 1000
    if duracao_total > cabeça_duracao:
        cabeça = segmento_audio[:int(cabeça_duracao * 1000)]
        off = segmento_audio[int(cabeça_duracao * 1000):]
    else:
        cabeça = segmento_audio
        off = AudioSegment.silent(duration=0)

    # Montar partes sem BG primeiro
    partes = []
    if vht_a:
        partes.append(vht_a)

    partes.append(cabeça)

    # Inserir vinheta de passagem entre cabeça e OFF
    if vht_p:
        partes.append(vht_p)

    # OFF com BG em ducking dinâmico (BG desce durante a fala, sobe no silêncio)
    if len(off) > 0 and bg is not None:
        # Usa mix_bgm para ducking profissional baseado em RMS da voz
        off_com_bg = mix_bgm(off, BG_PATH)
        partes.append(off_com_bg)
    elif len(off) > 0:
        partes.append(off)

    if vht_e:
        partes.append(vht_e)

    if len(partes) > 1:
        montado = sum(partes[1:], partes[0])
    elif partes:
        montado = partes[0]
    else:
        montado = AudioSegment.silent(duration=1000)
    
    # Normalizar loudness para -16 LUFS (padrão rádio), TP=-1.5, LRA=11
    # Vinhetas estão em ~-19.6 dBFS; voz em ~-10 dBFS (estourando)
    # loudnorm equaliza para que voz e vinhetas fiquem no mesmo nível percebido
    tmp_in = tempfile.mktemp(suffix='.wav', dir=str(TMP_DIR))
    tmp_out = tempfile.mktemp(suffix='.wav', dir=str(TMP_DIR))
    montado.export(tmp_in, format="wav")
    subprocess.run([
        "ffmpeg", "-y", "-i", tmp_in,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        tmp_out
    ], check=True, capture_output=True)
    os.unlink(tmp_in)
    resultado = AudioSegment.from_wav(tmp_out)
    os.unlink(tmp_out)
    return resultado
