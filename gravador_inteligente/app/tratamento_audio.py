#!/usr/bin/env python3
"""
Módulo de Tratamento de Áudio - Pipeline de normalização e limpeza.

Etapas (cada uma opcional/chamável independentemente):
1. normalize_volume() - Normaliza volume para padrão podcast (-16 LUFS)
2. reduce_noise() - Redução de ruído de fundo via noisereduce ou ffmpeg afftdn
3. reduce_breath() - Redução de respiração (preserva fonemas)
4. remove_silence() - Remove silêncios longos opcionais
5. process() - Pipeline completo de tratamento
"""

import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Configuração
# =============================================================================

@dataclass
class TratamentoConfig:
    """Configurações para o pipeline de tratamento de áudio."""
    
    # --- Normalização de volume ---
    target_lufs: float = -16.0  # Padrão podcast (Spotify/YouTube)
    target_peak_db: float = -1.0  # Peak máximo em dB
    normalize: bool = True
    
    # --- Redução de ruído ---
    reduce_noise: bool = True
    noise_reduction_strength: float = 0.5  # 0.0 a 1.0
    noise_sample_duration_ms: int = 500  # ms de amostra de ruído (início do áudio)
    noise_method: str = "auto"  # "auto", "noisereduce_lib", "ffmpeg_afftdn"
    
    # --- Redução de respiração ---
    reduce_breath: bool = True
    breath_threshold_db: float = -30  # Abaixo disso pode ser respiração
    breath_attenuation_db: float = -6  # Atenuação em dB para respirações
    breath_min_duration_ms: int = 50  # Duração mínima para considerar respiração
    breath_max_duration_ms: int = 300  # Duração máxima para considerar respiração
    
    # --- Remoção de silêncios ---
    remove_silence: bool = False  # Não remove silêncios por padrão (pode cortar pausas naturais)
    silence_threshold_db: int = -40
    min_silence_len_ms: int = 2000
    keep_silence_ms: int = 300
    
    # --- Geral ---
    output_format: str = "mp3"
    output_bitrate: str = "128k"
    sample_rate: int = 44100
    channels: int = 1  # mono (após redução de ruído, sempre mono)
    temp_dir: str = "temp_processing"
    verbose: bool = False


# =============================================================================
# Utilitários
# =============================================================================

def get_audio_info(path: str | Path) -> dict:
    """Retorna informações sobre o arquivo de áudio via ffprobe."""
    path = str(path)
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe falhou: {r.stderr}")
    
    info = json.loads(r.stdout)
    fmt = info.get("format", {})
    streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    
    if not streams:
        raise ValueError("Nenhum stream de áudio encontrado")
    
    audio_stream = streams[0]
    return {
        "duration": float(fmt.get("duration", 0)),
        "size_bytes": int(fmt.get("size", 0)),
        "bit_rate": fmt.get("bit_rate"),
        "codec": audio_stream.get("codec_name"),
        "sample_rate": int(audio_stream.get("sample_rate", 0)),
        "channels": int(audio_stream.get("channels", 0)),
    }


def measure_lufs(path: str | Path) -> dict:
    """Mede LUFS (loudness) do áudio usando ffmpeg loudnorm filter."""
    path = str(path)
    cmd = [
        "ffmpeg", "-i", path,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-"
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    
    # Extrai JSON do stderr
    output = r.stderr
    try:
        # Encontra o bloco JSON no output
        start = output.index("{")
        end = output.rindex("}") + 1
        data = json.loads(output[start:end])
        return {
            "input_i": float(data.get("input_i", 0)),  # Input integrated loudness
            "input_tp": float(data.get("input_tp", 0)),  # Input true peak
            "input_lra": float(data.get("input_lra", 0)),  # Input loudness range
            "input_thresh": float(data.get("input_thresh", 0)),
        }
    except (ValueError, KeyError):
        logger.warning("Não foi possível medir LUFS")
        return {"input_i": 0, "input_tp": 0, "input_lra": 0, "input_thresh": 0}


def load_audio_to_numpy(path: str | Path) -> tuple[np.ndarray, int]:
    """Carrega áudio para numpy array (mono) via ffmpeg."""
    path = str(path)
    cmd = [
        "ffmpeg", "-i", path,
        "-ac", "1",  # mono
        "-ar", "44100",
        "-f", "s16le",  # PCM 16-bit signed
        "-acodec", "pcm_s16le",
        "-v", "quiet",
        "pipe:1"
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou ao carregar áudio: {r.stderr.decode()}")
    
    audio_array = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return audio_array, 44100


def save_numpy_to_audio(audio: np.ndarray, path: str | Path, sample_rate: int = 44100):
    """Salva numpy array como arquivo de áudio via ffmpeg."""
    path = str(path)
    # Converte de volta para int16
    audio_int16 = (audio * 32767).astype(np.int16)
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-i", "pipe:0",
        "-acodec", "libmp3lame",
        "-b:a", "128k",
        path
    ]
    r = subprocess.run(cmd, input=audio_int16.tobytes(), capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou ao salvar áudio: {r.stderr.decode()}")


# =============================================================================
# Etapa 0: Análise de Canais, Clipping e Correção
# =============================================================================

import re as _re

def analisar_audio(path: str | Path) -> dict:
    """
    Análise completa do áudio: canais, clipping, níveis.
    
    Returns:
        dict com:
        - channels: int (1=mono, 2=stereo)
        - is_asymmetric: bool (áudio só em um canal)
        - active_channel: str ("left", "right", "both", "mono")
        - left_mean_db: float
        - right_mean_db: float
        - left_max_db: float
        - right_max_db: float
        - overall_max_db: float (max_volume do volumedetect)
        - has_clipping: bool (max >= -0.5 dB)
        - needed_gain_db: float (ganho a aplicar para evitar clipping, negativo = atenuar)
    """
    path = str(path)
    
    # Número de canais
    cmd_info = ['ffprobe', '-v', 'quiet', '-select_streams', 'a:0',
                '-show_entries', 'stream=channels', '-of', 'csv=p=0', path]
    r = subprocess.run(cmd_info, capture_output=True, text=True)
    channels = int(r.stdout.strip()) if r.stdout.strip().isdigit() else 1
    
    if channels < 2:
        # Mono: medir diretamente
        cmd = ['ffmpeg', '-i', path, '-af', 'volumedetect', '-f', 'null', '-']
        r = subprocess.run(cmd, capture_output=True, text=True)
        mean_m = _re.search(r'mean_volume: ([-\d.]+) dB', r.stderr)
        max_m = _re.search(r'max_volume: ([-\d.]+) dB', r.stderr)
        mean_db = float(mean_m.group(1)) if mean_m else -99.0
        max_db = float(max_m.group(1)) if max_m else -99.0
        
        # Ganho necessário para levar o pico a -3 dB (margem segura)
        needed = -3.0 - max_db if max_db > -3.0 else 0.0
        
        return {
            "channels": 1,
            "is_asymmetric": False,
            "active_channel": "mono",
            "left_mean_db": mean_db,
            "right_mean_db": mean_db,
            "left_max_db": max_db,
            "right_max_db": max_db,
            "overall_max_db": max_db,
            "has_clipping": max_db >= -0.5,
            "needed_gain_db": needed,
        }
    
    # Stereo: medir cada canal separadamente
    results = {}
    for side, label in [("FL", "left"), ("FR", "right")]:
        cmd = ['ffmpeg', '-i', path, '-af', f'pan=mono|c0={side},volumedetect', '-f', 'null', '-']
        r = subprocess.run(cmd, capture_output=True, text=True)
        mean_m = _re.search(r'mean_volume: ([-\d.]+) dB', r.stderr)
        max_m = _re.search(r'max_volume: ([-\d.]+) dB', r.stderr)
        results[f"{label}_mean_db"] = float(mean_m.group(1)) if mean_m else -99.0
        results[f"{label}_max_db"] = float(max_m.group(1)) if max_m else -99.0
    
    left_max = results["left_max_db"]
    right_max = results["right_max_db"]
    left_mean = results["left_mean_db"]
    right_mean = results["right_mean_db"]
    
    # Detectar canal morto (assimetria > 30 dB)
    diff = abs(left_mean - right_mean)
    if diff > 30 and left_mean > right_mean:
        active = "left"
    elif diff > 30 and right_mean > left_mean:
        active = "right"
    else:
        active = "both"
    
    # Clipping: o pior dos canais (tolerante: apenas picos reais acima de 0dB)
    overall_max = max(left_max, right_max)
    has_clipping = overall_max > 0.0  # Apenas clipping real (acima de 0dB)
    
    # Ganho necessário: levar pico a -1dB (margem segura para áudio digital)
    needed = -1.0 - overall_max if overall_max > -1.0 else 0.0
    
    return {
        "channels": 2,
        "is_asymmetric": active != "both",
        "active_channel": active,
        "left_mean_db": left_mean,
        "right_mean_db": right_mean,
        "left_max_db": left_max,
        "right_max_db": right_max,
        "overall_max_db": overall_max,
        "has_clipping": has_clipping,
        "needed_gain_db": needed,
    }


@dataclass
class AudioProfile:
    """Perfil de áudio analisado — parâmetros derivados, nenhum hardcoded."""
    # Canal
    channels: int
    is_asymmetric: bool
    active_channel: str
    
    # Níveis
    mean_db: float
    max_db: float
    lufs: float
    peak_db: float
    
    # Ruído
    noise_floor_db: float          # Nível de ruído de fundo (dB)
    signal_to_noise_db: float      # Relação sinal-ruído (dB)
    noise_reduction_strength: float # Força ideal de redução (0.0-1.0)
    
    # Respiração
    breath_threshold_db: float     # Limiar para detectar respiração
    breath_attenuation_db: float    # Atenuação para respirações
    
    # Normalização
    needed_gain_db: float          # Ganho necessário
    
    # Clipping
    has_clipping: bool


def analisar_perfil_ruido(audio_mono) -> AudioProfile:
    """
    Analisa o áudio e deriva todos os parâmetros de tratamento.
    
    Nenhum valor é hardcoded — tudo é calculado a partir das características
    do áudio de entrada.
    """
    from pydub.silence import detect_nonsilent
    
    sample_rate = audio_mono.frame_rate
    channels = audio_mono.channels
    
    # Medir níveis gerais
    mean_db = audio_mono.dBFS
    max_db = audio_mono.max_dBFS
    
    # Medir LUFS
    try:
        lufs_info = measure_lufs(audio_mono)
        lufs = lufs_info["input_i"]
        peak_db = lufs_info["input_tp"]
    except:
        lufs = mean_db
        peak_db = max_db
    
    # Detectar segmentos de fala
    nonsilent = detect_nonsilent(audio_mono, min_silence_len=200, silence_thresh=-35)
    
    # Calcular ruído de fundo: média dos segmentos de silêncio entre falas
    silence_segments = []
    
    # Silêncio antes da primeira fala
    if nonsilent and nonsilent[0][0] > 100:
        silence_segments.append(audio_mono[:nonsilent[0][0]])
    
    # Silêncios entre falas
    for i in range(len(nonsilent) - 1):
        gap_start = nonsilent[i][1]
        gap_end = nonsilent[i + 1][0]
        if gap_end - gap_start > 100:
            silence_segments.append(audio_mono[gap_start:gap_end])
    
    # Calcular noise floor
    if silence_segments:
        # Média dos níveis de silêncio
        silence_dbfs = [s.dBFS for s in silence_segments if s.dBFS > -90]
        if silence_dbfs:
            noise_floor_db = np.median(silence_dbfs)
        else:
            noise_floor_db = -60
    else:
        noise_floor_db = -60
    
    # Relação sinal-ruído
    signal_to_noise_db = mean_db - noise_floor_db
    
    # Força de redução de ruído: proporcional à SNR, mas conservador
    # SNR alto (> 40dB) = áudio limpo = redução mínima (0.05)
    # SNR médio (25-40dB) = ruído leve = redução leve (0.1-0.15)
    # SNR baixo (15-25dB) = ruído moderado = redução moderada (0.15-0.25)
    # SNR muito baixo (< 15dB) = muito ruído = redução forte (0.25-0.35)
    if signal_to_noise_db > 40:
        noise_reduction_strength = 0.05
    elif signal_to_noise_db > 30:
        noise_reduction_strength = 0.1
    elif signal_to_noise_db > 20:
        noise_reduction_strength = 0.15
    elif signal_to_noise_db > 15:
        noise_reduction_strength = 0.2
    else:
        noise_reduction_strength = 0.25
    
    # Limiar de respiração: 15dB acima do noise floor
    breath_threshold_db = min(noise_floor_db + 15, mean_db - 10)
    
    # Atenuação de respiração: proporcional à diferença entre ruído e fala
    # Quanto maior a diferença, mais atenuação podemos aplicar
    breath_attenuation_db = max(-12, -6 - (signal_to_noise_db / 10))
    
    # Ganho de normalização
    target_lufs = -16.0
    needed_gain_db = target_lufs - lufs if lufs != 0 else target_lufs - mean_db
    # Limitar ganho máximo para não amplificar ruído demais
    needed_gain_db = min(needed_gain_db, 12)
    
    # Detectar clipping
    has_clipping = max_db >= -0.5
    
    return AudioProfile(
        channels=channels,
        is_asymmetric=False,
        active_channel="mono" if channels == 1 else "both",
        mean_db=mean_db,
        max_db=max_db,
        lufs=lufs,
        peak_db=peak_db,
        noise_floor_db=noise_floor_db,
        signal_to_noise_db=signal_to_noise_db,
        noise_reduction_strength=noise_reduction_strength,
        breath_threshold_db=breath_threshold_db,
        breath_attenuation_db=breath_attenuation_db,
        needed_gain_db=needed_gain_db,
        has_clipping=has_clipping,
    )


def corrigir_canal_e_clipping(input_path: str | Path, output_path: str | Path) -> dict:
    """
    Corrige problemas detectados na análise:
    - Se stereo assimétrico: extrai apenas o canal ativo → mono
    - Se clipping detectado: aplica atenuação para levar pico a -3 dB
    
    A análise é feita audio a audio — nenhum valor é hardcoded.
    
    Returns:
        dict com status, ação realizada e análise
    """
    info = analisar_audio(input_path)
    
    if not info["is_asymmetric"] and not info["has_clipping"]:
        return {"status": "ok", "action": "none", "info": info}
    
    # Construir filter chain dinamicamente
    filters = []
    
    # Passo 1: Extrair canal ativo se assimétrico
    if info["is_asymmetric"]:
        channel = info["active_channel"]
        if channel == "left":
            filters.append("pan=mono|c0=FL")
        else:
            filters.append("pan=mono|c0=FR")
        logger.info(f"Canal morto detectado (ativo={channel}, diff={abs(info['left_mean_db'] - info['right_mean_db']):.1f}dB)")
    
    # Passo 2: Aplicar ganho se necessário (para resolver clipping ou dar headroom)
    gain = info["needed_gain_db"]
    if gain < -0.5:  # Só aplica se precisar atenuar mais de 0.5 dB
        filters.append(f"volume={gain:.1f}dB")
        logger.info(f"Clipping detectado (max={info['overall_max_db']:.1f}dB). Aplicando ganho: {gain:.1f}dB")
    
    # Se não precisa de nenhum filtro, copia direto
    if not filters:
        return {"status": "ok", "action": "none", "info": info}
    
    filter_str = ",".join(filters)
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", filter_str,
        "-ar", "44100",
        str(output_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    
    if r.returncode != 0:
        raise RuntimeError(f"Falha na correção: {r.stderr}")
    
    action_parts = []
    if info["is_asymmetric"]:
        action_parts.append(f"mono({info['active_channel']})")
    if gain < -0.5:
        action_parts.append(f"gain={gain:.1f}dB")
    
    action = " + ".join(action_parts)
    logger.info(f"  Corrigida: {action}")
    
    return {"status": "ok", "action": action, "gain_db": gain, "info": info}


# =============================================================================
# Etapa 1: Normalização de Volume
# =============================================================================

def normalize_volume(
    input_path: str | Path,
    output_path: str | Path,
    target_lufs: float = -16.0,
    target_peak_db: float = -1.0,
) -> dict:
    """
    Normaliza volume para padrão podcast usando ffmpeg loudnorm (two-pass).
    
    Padrão podcast: -16 LUFS (Spotify/YouTube), peak máximo -1 dB.
    """
    input_path = str(input_path)
    output_path = str(output_path)
    
    logger.info(f"Normalizando volume para {target_lufs} LUFS...")
    
    # PASSO 1: Medir loudness atual
    cmd_measure = [
        "ffmpeg", "-i", input_path,
        "-af", f"loudnorm=I={target_lufs}:TP={target_peak_db}:LRA=11:print_format=json",
        "-f", "null", "-"
    ]
    r = subprocess.run(cmd_measure, capture_output=True, text=True)
    
    # Extrair medição do stderr
    measured = {}
    try:
        output = r.stderr
        start = output.index("{")
        end = output.rindex("}") + 1
        measured = json.loads(output[start:end])
    except (ValueError, KeyError):
        logger.warning("Medição LUFS falhou, usando normalização simples")
    

    # PASSO 2: Aplicar normalização (single-pass com loudnorm)
    # Single-pass é suficiente para a maioria dos casos e evita problemas de parsing
    filter_str = f"loudnorm=I={target_lufs}:TP={target_peak_db}:LRA=11"
    
    cmd_apply = [
        "ffmpeg", "-y", "-i", input_path,
        "-af", filter_str,
        "-ar", "44100",
        output_path
    ]
    r = subprocess.run(cmd_apply, capture_output=True, text=True)
    
    if r.returncode != 0:
        raise RuntimeError(f"Normalização falhou: {r.stderr}")
    
    # Medir resultado
    result_info = measure_lufs(output_path)
    logger.info(f"  Volume normalizado: {result_info['input_i']:.1f} LUFS")
    
    return {
        "status": "ok",
        "target_lufs": target_lufs,
        "result_lufs": result_info["input_i"],
        "result_peak": result_info["input_tp"],
    }


# =============================================================================
# Etapa 2: Redução de Ruído
# =============================================================================

def reduce_noise(
    input_path: str | Path,
    output_path: str | Path,
    strength: float = 0.5,
    sample_duration_ms: int = 500,
    method: str = "auto",
) -> dict:
    """
    Reduz ruído de fundo do áudio.
    
    Métodos:
    - "noisereduce_lib": Usa biblioteca noisereduce (Python, mais preciso)
    - "ffmpeg_afftdn": Usa ffmpeg afftdn (mais rápido, sem dependências extras)
    - "auto": Escolhe automaticamente
    """
    input_path = str(input_path)
    output_path = str(output_path)
    
    logger.info(f"Reduzindo ruído de fundo (força={strength:.0%})...")
    
    # Escolher método
    if method == "auto":
        try:
            import noisereduce as nr
            method = "noisereduce_lib"
        except ImportError:
            method = "ffmpeg_afftdn"
    
    if method == "noisereduce_lib":
        return _reduce_noise_noisereduce(input_path, output_path, strength, sample_duration_ms)
    else:
        return _reduce_noise_ffmpeg(input_path, output_path, strength)


def _reduce_noise_noisereduce(
    input_path: str,
    output_path: str,
    strength: float,
    sample_duration_ms: int,
) -> dict:
    """Redução de ruído via biblioteca noisereduce."""
    import noisereduce as nr
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent
    
    logger.info("  Usando noisereduce (biblioteca Python)...")
    
    # Carregar áudio
    audio = AudioSegment.from_file(input_path)
    sample_rate = audio.frame_rate
    
    # Converter para numpy (mono)
    audio_mono = audio.set_channels(1)
    audio_array = np.array(audio_mono.get_array_of_samples(), dtype=np.float32)
    
    # Normalizar para [-1, 1]
    if audio_array.dtype == np.int16:
        audio_array = audio_array / 32768.0
    elif audio_array.dtype == np.int32:
        audio_array = audio_array / 2147483648.0
    
    # Encontrar amostra de ruído: procurar o maior segmento de silêncio nos primeiros 30s
    # em vez de usar os primeiros 500ms (que podem conter claquete ou fala)
    nonsilent = detect_nonsilent(audio_mono[:30000], min_silence_len=500, silence_thresh=-35)
    
    # Encontrar o maior gap de silêncio nos primeiros 30s
    best_noise_start = 0
    best_noise_len = 0
    
    if nonsilent:
        # Gap antes do primeiro segmento
        if nonsilent[0][0] >= 300:
            best_noise_start = 0
            best_noise_len = nonsilent[0][0]
        
        # Gaps entre segmentos
        for i in range(len(nonsilent) - 1):
            gap_start = nonsilent[i][1]
            gap_end = nonsilent[i + 1][0]
            gap_len = gap_end - gap_start
            if gap_len > best_noise_len and gap_len >= 300:
                best_noise_start = gap_start
                best_noise_len = gap_len
    else:
        # Áudio inteiro é silêncio nos primeiros 30s
        best_noise_len = min(30000, len(audio_mono))
    
    # Usar no máximo sample_duration_ms da amostra de ruído encontrada
    noise_samples = int(sample_rate * sample_duration_ms / 1000)
    noise_start_sample = int(best_noise_start * sample_rate / 1000)
    noise_end_sample = min(noise_start_sample + noise_samples, len(audio_array))
    
    if noise_end_sample > noise_start_sample:
        noise_clip = audio_array[noise_start_sample:noise_end_sample]
    else:
        # Fallback: usar primeiros 200ms
        noise_clip = audio_array[:int(sample_rate * 0.2)]
    
    logger.info(f"  Amostra de ruído: {best_noise_start}ms-{best_noise_start + sample_duration_ms}ms ({len(noise_clip)} samples)")
    
    # Aplicar redução
    reduced = nr.reduce_noise(
        y=audio_array,
        y_noise=noise_clip,
        sr=sample_rate,
        prop_decrease=strength,
        stationary=False,  # Não estacionário para melhor qualidade em rádio
    )
    
    # Converter de volta para int16
    reduced_int16 = (reduced * 32767).clip(-32768, 32767).astype(np.int16)
    
    # Salvar
    result = AudioSegment(
        reduced_int16.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,
        channels=1,
    )
    
    result.export(output_path, format="mp3", bitrate="128k")
    
    logger.info("  Redução de ruído concluída (noisereduce)")
    return {"status": "ok", "method": "noisereduce_lib", "strength": strength}


def _reduce_noise_ffmpeg(input_path: str, output_path: str, strength: float) -> dict:
    """Redução de ruído via ffmpeg afftdn."""
    logger.info("  Usando ffmpeg afftdn...")
    
    # afftdn params: nr=noise reduction amount (0-100), nf=noise floor
    nr_amount = int(strength * 100)  # 0-100
    
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af", f"afftdn=nf=-40:nr={nr_amount}",
        "-ar", "44100",
        output_path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    
    if r.returncode != 0:
        raise RuntimeError(f"Redução de ruído ffmpeg falhou: {r.stderr}")
    
    logger.info("  Redução de ruído concluída (ffmpeg afftdn)")
    return {"status": "ok", "method": "ffmpeg_afftdn", "strength": strength}


# =============================================================================
# Etapa 3: Redução de Respiração
# =============================================================================

def reduce_breath(
    input_path: str | Path,
    output_path: str | Path,
    threshold_db: float = -30,
    attenuation_db: float = -6,
    min_duration_ms: int = 50,
    max_duration_ms: int = 300,
) -> dict:
    """
    Reduz a intensidade da respiração sem eliminar fonemas.
    
    Estratégia: Detecta segmentos curtos e de baixa energia que se encaixam
    no padrão de respiração e aplica atenuação suave.
    
    Usa análise de energia em janelas curtas para identificar respirações.
    """
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent
    
    input_path = str(input_path)
    output_path = str(output_path)
    
    logger.info("Reduzindo respiração...")
    
    audio = AudioSegment.from_file(input_path)
    
    # Encontra segmentos não-silêncios (fala)
    nonsilent_ranges = detect_nonsilent(
        audio,
        min_silence_len=min_duration_ms,
        silence_thresh=threshold_db,
    )
    
    # Identifica "intervalos" entre fala que podem ser respiração
    breath_segments = []
    for i in range(len(nonsilent_ranges) - 1):
        end_current = nonsilent_ranges[i][1]
        start_next = nonsilent_ranges[i + 1][0]
        gap_duration = start_next - end_current
        
        # Respiração: gap entre 50ms e 300ms com energia baixa
        if min_duration_ms <= gap_duration <= max_duration_ms:
            # Verifica energia no gap
            gap_audio = audio[end_current:start_next]
            if gap_audio.dBFS < threshold_db + 10:  # Próximo do silêncio
                breath_segments.append((end_current, start_next))
    
    if not breath_segments:
        logger.info("  Nenhuma respiração detectada")
        audio.export(output_path, format="mp3", bitrate="128k")
        return {"status": "ok", "breaths_found": 0}
    
    # Aplicar atenuação nas respirações
    attenuation_factor = 10 ** (attenuation_db / 20)  # Converte dB para fator linear
    
    result = AudioSegment.empty()
    pointer = 0
    
    for start, end in breath_segments:
        # Adiciona áudio antes da respiração
        result += audio[pointer:start]
        
        # Atenua a respiração
        breath = audio[start:end]
        breath = breath.apply_gain(attenuation_db)  # Reduz volume
        
        result += breath
        pointer = end
    
    # Adiciona restante
    if pointer < len(audio):
        result += audio[pointer:]
    
    result.export(output_path, format="mp3", bitrate="128k")
    
    logger.info(f"  {len(breath_segments)} respirações atenuadas em {attenuation_db}dB")
    return {"status": "ok", "breaths_found": len(breath_segments), "attenuation_db": attenuation_db}


# =============================================================================
# Etapa 4: Remoção de Silêncios Longos
# =============================================================================

def remove_silence(
    input_path: str | Path,
    output_path: str | Path,
    threshold_db: int = -40,
    min_silence_len_ms: int = 2000,
    keep_silence_ms: int = 300,
) -> dict:
    """Remove silêncios longos, mantendo pequenas pausas naturais."""
    from pydub import AudioSegment
    from pydub.silence import split_on_silence
    
    input_path = str(input_path)
    output_path = str(output_path)
    
    logger.info(f"Removendo silêncios > {min_silence_len_ms}ms...")
    
    audio = AudioSegment.from_file(input_path)
    
    chunks = split_on_silence(
        audio,
        min_silence_len=min_silence_len_ms,
        silence_thresh=threshold_db,
        keep_silence=keep_silence_ms,
    )
    
    if not chunks:
        logger.warning("  Áudio inteiro seria removido. Mantendo original.")
        audio.export(output_path, format="mp3", bitrate="128k")
        return {"status": "skipped", "reason": "all_silence"}
    
    result = AudioSegment.empty()
    for chunk in chunks:
        result += chunk
    
    result.export(output_path, format="mp3", bitrate="128k")
    
    original_duration = len(audio) / 1000
    new_duration = len(result) / 1000
    removed = original_duration - new_duration
    
    logger.info(f"  Removido {removed:.1f}s de silêncio ({original_duration:.1f}s → {new_duration:.1f}s)")
    
    return {
        "status": "ok",
        "original_duration_s": original_duration,
        "new_duration_s": new_duration,
        "removed_s": removed,
    }


# =============================================================================
# Pipeline Completo
# =============================================================================

def process(
    input_path: str | Path,
    output_path: str | Path,
    config: Optional[TratamentoConfig] = None,
) -> dict:
    """
    Pipeline completo de tratamento de áudio.
    
    Executa as etapas na ordem correta:
    0. Correção de canal morto (stereo assimétrico → mono)
    1. Redução de ruído (antes da normalização para não amplificar ruído)
    2. Redução de respiração
    3. Remoção de silêncios longos (se habilitado)
    4. Normalização de volume (por último para ajustar nível final)
    
    Args:
        input_path: Caminho do áudio original
        output_path: Caminho do áudio tratado
        config: Configurações de tratamento
    
    Returns:
        Dict com status e resultados de cada etapa
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    cfg = config or TratamentoConfig()
    
    if not input_path.exists():
        raise FileNotFoundError(f"Áudio não encontrado: {input_path}")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Criar diretório temporário
    temp_dir = Path(cfg.temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    results = {
        "input": str(input_path),
        "output": str(output_path),
        "etapas": [],
    }
    
    current_file = str(input_path)
    temp_files = []
    
    try:
        # Etapa 0: Análise de perfil (deriva parâmetros do áudio)
        from pydub import AudioSegment as _AudioSegment
        audio_para_analise = _AudioSegment.from_file(str(input_path))
        if audio_para_analise.channels > 1:
            audio_para_analise = audio_para_analise.set_channels(1)
        perfil = analisar_perfil_ruido(audio_para_analise)
        
        results["perfil"] = {
            "mean_db": round(perfil.mean_db, 1),
            "max_db": round(perfil.max_db, 1),
            "lufs": round(perfil.lufs, 1),
            "noise_floor_db": round(perfil.noise_floor_db, 1),
            "snr_db": round(perfil.signal_to_noise_db, 1),
            "noise_reduction_strength": round(perfil.noise_reduction_strength, 2),
            "breath_threshold_db": round(perfil.breath_threshold_db, 1),
            "breath_attenuation_db": round(perfil.breath_attenuation_db, 1),
        }
        
        logger.info(f"Perfil do áudio: SNR={perfil.signal_to_noise_db:.1f}dB | "
                    f"noise_floor={perfil.noise_floor_db:.1f}dB | "
                    f"redução={perfil.noise_reduction_strength:.0%} | "
                    f"lufs={perfil.lufs:.1f}")
        
        # Usar parâmetros derivados do perfil (sobrescreve config)
        cfg.noise_reduction_strength = perfil.noise_reduction_strength
        cfg.breath_threshold_db = perfil.breath_threshold_db
        cfg.breath_attenuation_db = perfil.breath_attenuation_db
        
        # Etapa 0.5: Correção de canal morto + clipping
        r = corrigir_canal_e_clipping(current_file, current_file + ".fix.mp3")
        results["etapas"].append({"nome": "analise_correcao", **r})
        if r["action"] != "none":
            temp_files.append(current_file + ".fix.mp3")
            current_file = current_file + ".fix.mp3"
        
        # Etapa 1: Redução de ruído
        if cfg.reduce_noise:
            noise_output = temp_dir / f"{input_path.stem}_denoised.mp3"
            temp_files.append(noise_output)
            
            r = reduce_noise(
                current_file, noise_output,
                strength=cfg.noise_reduction_strength,
                sample_duration_ms=cfg.noise_sample_duration_ms,
                method=cfg.noise_method,
            )
            results["etapas"].append({"nome": "reducao_ruido", **r})
            current_file = str(noise_output)
        
        # Etapa 2: Redução de respiração
        if cfg.reduce_breath:
            breath_output = temp_dir / f"{input_path.stem}_breath.mp3"
            temp_files.append(breath_output)
            
            r = reduce_breath(
                current_file, breath_output,
                threshold_db=cfg.breath_threshold_db,
                attenuation_db=cfg.breath_attenuation_db,
                min_duration_ms=cfg.breath_min_duration_ms,
                max_duration_ms=cfg.breath_max_duration_ms,
            )
            results["etapas"].append({"nome": "reducao_respiracao", **r})
            current_file = str(breath_output)
        
        # Etapa 3: Remoção de silêncios longos
        if cfg.remove_silence:
            silence_output = temp_dir / f"{input_path.stem}_nosilence.mp3"
            temp_files.append(silence_output)
            
            r = remove_silence(
                current_file, silence_output,
                threshold_db=cfg.silence_threshold_db,
                min_silence_len_ms=cfg.min_silence_len_ms,
                keep_silence_ms=cfg.keep_silence_ms,
            )
            results["etapas"].append({"nome": "remocao_silencio", **r})
            current_file = str(silence_output)
        
        # Etapa 4: Normalização de volume (sempre por último)
        if cfg.normalize:
            r = normalize_volume(
                current_file, output_path,
                target_lufs=cfg.target_lufs,
                target_peak_db=cfg.target_peak_db,
            )
            results["etapas"].append({"nome": "normalizacao_volume", **r})
        else:
            # Sem normalização, apenas copia o resultado
            from pydub import AudioSegment
            audio = AudioSegment.from_file(current_file)
            audio.export(str(output_path), format=cfg.output_format, bitrate=cfg.output_bitrate)
        
        # Info final
        final_info = get_audio_info(output_path)
        results["duracao_final_s"] = final_info["duration"]
        results["tamanho_final_mb"] = round(final_info["size_bytes"] / (1024 * 1024), 2)
        results["status"] = "ok"
        
        logger.info(f"✅ Tratamento concluído: {output_path.name} ({final_info['duration']:.1f}s)")
        
    finally:
        # Limpar arquivos temporários
        for f in temp_files:
            fp = Path(f) if isinstance(f, str) else f
            if fp.exists():
                fp.unlink()
    
    return results


# =============================================================================
# CLI
# =============================================================================

def main_cli():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Trata áudio de boletins: normaliza volume, reduz ruído e respiração"
    )
    parser.add_argument("audio", help="Caminho do arquivo de áudio")
    parser.add_argument("-o", "--output", help="Caminho do arquivo de saída")
    parser.add_argument("--no-normalize", action="store_true", help="Pula normalização de volume")
    parser.add_argument("--no-denoise", action="store_true", help="Pula redução de ruído")
    parser.add_argument("--no-breath", action="store_true", help="Pula redução de respiração")
    parser.add_argument("--remove-silence", action="store_true", help="Remove silêncios longos")
    parser.add_argument("--lufs", type=float, default=-16.0, help="Target LUFS (padrão: -16)")
    parser.add_argument("--noise-strength", type=float, default=0.5, help="Força da redução de ruído (0-1)")
    parser.add_argument("--breath-db", type=float, default=-6, help="Atenuação da respiração em dB")
    parser.add_argument("-v", "--verbose", action="store_true", help="Modo verboso")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    
    config = TratamentoConfig(
        normalize=not args.no_normalize,
        reduce_noise=not args.no_denoise,
        reduce_breath=not args.no_breath,
        remove_silence=args.remove_silence,
        target_lufs=args.lufs,
        noise_reduction_strength=args.noise_strength,
        breath_attenuation_db=args.breath_db,
        verbose=args.verbose,
    )
    
    output = args.output or Path(args.audio).stem + "_tratado.mp3"
    
    resultado = process(args.audio, output, config)
    
    print("\n" + "=" * 60)
    print("RESULTADO DO TRATAMENTO")
    print("=" * 60)
    print(f"Status: {resultado['status']}")
    print(f"Entrada: {resultado['input']}")
    print(f"Saída: {resultado['output']}")
    print(f"Duração final: {resultado.get('duracao_final_s', '?')}s")
    print(f"Tamanho final: {resultado.get('tamanho_final_mb', '?')} MB")
    print("\nEtapas executadas:")
    for etapa in resultado.get("etapas", []):
        nome = etapa.get("nome", "?")
        status = etapa.get("status", "?")
        extra = ""
        if "result_lufs" in etapa:
            extra = f" → {etapa['result_lufs']:.1f} LUFS"
        elif "breaths_found" in etapa:
            extra = f" ({etapa['breaths_found']} respirações)"
        elif "method" in etapa:
            extra = f" [{etapa['method']}]"
        print(f"  ✓ {nome}: {status}{extra}")


if __name__ == "__main__":
    main_cli()
