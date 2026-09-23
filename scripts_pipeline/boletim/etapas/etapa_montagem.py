"""
Etapa 6: Montagem final com vinhetas, BG e normalização de loudness.
"""
import sys
# Garantir que .venv_pipeline é encontrado antes do Hermes
import os
_VENV_SITE = os.path.join(os.path.dirname(__file__).rsplit(os.sep + "scripts_pipeline", 1)[0], ".venv_pipeline", "Lib", "site-packages")
if _VENV_SITE not in sys.path:
    sys.path.insert(0, _VENV_SITE)
# Limpar paths do Hermes para evitar conflito de imports do faster_whisper
sys.path = [p for p in sys.path if 'hermes' not in p.lower() and 'AppData/Local/hermes' not in p]

import os
import re
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
    
    Usa heurística: número de palavras × 0.4s/palavra (média para locução em PT-BR).
    Evita transcrever novamente (economiza RAM).
    
    Retorna a duração em segundos.
    """
    if not texto_cabeca:
        return 20  # fallback
    
    # Heurística: palavra leva ~0.4s em locução jornalística
    import re
    palavras = re.findall(r'\w+', texto_cabeca)
    duracao = len(palavras) * 0.4
    
    # Limites razoáveis
    duracao = max(5, min(duracao, 30))
    
    return duracao


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
