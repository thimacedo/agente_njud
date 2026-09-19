#!/usr/bin/env python3
"""Spike 003: detectar vinheta por correlação espectral."""
import numpy as np
from scipy.signal import correlate
from pydub import AudioSegment
from pathlib import Path
import random, os, json

ASSETS = r"E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\assets\vinhetas\boletim"
VHT_REF = f"{ASSETS}/VHT_ABERTURA_BOLETIM.mp3"
BOLETINS_DIR = r"E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\boletins"

def audio_to_mono_array(audio):
    """Converte AudioSegment para numpy array mono (float32, normalizado)."""
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
    if audio.channels == 2:
        samples = samples.reshape((-1, 2)).mean(axis=1)
    # Normalizar para [-1, 1]
    max_val = np.max(np.abs(samples))
    if max_val > 0:
        samples = samples / max_val
    return samples, audio.frame_rate

def resample(audio, target_rate):
    """Resample audio para target_rate."""
    if audio.frame_rate != target_rate:
        audio = audio.set_frame_rate(target_rate)
    return audio

def detectar_vinheta_espectral(audio_path, ref_path, threshold=0.7):
    """Detecta vinheta por correlação espectral.
    Retorna (tempo_inicio, tempo_fim, score) ou None se não encontrada.
    """
    # Carregar referência
    ref = AudioSegment.from_mp3(ref_path)
    ref = resample(ref, 16000)  # resample para 16kHz para velocidade
    ref_samples, ref_rate = audio_to_mono_array(ref)
    
    # Carregar áudio de teste (apenas primeiros 30s para detecção)
    audio = AudioSegment.from_mp3(audio_path)
    if len(audio) > 30000:  # >30s
        audio = audio[:30000]
    audio = resample(audio, 16000)
    audio_samples, audio_rate = audio_to_mono_array(audio)
    
    # Cross-correlation
    corr = correlate(audio_samples, ref_samples, mode='valid')
    
    # Encontrar pico
    pico_idx = np.argmax(np.abs(corr))
    pico_val = np.abs(corr[pico_idx])
    
    # Normalizar score (0-1)
    score = pico_val / (np.linalg.norm(ref_samples) * np.linalg.norm(ref_samples))
    
    # Converter índice para tempo
    tempo_inicio = pico_idx / audio_rate
    tempo_fim = tempo_inicio + (len(ref_samples) / audio_rate)
    
    if score < threshold:
        return None, score
    
    return (tempo_inicio, tempo_fim, score), score

def main():
    print("=" * 70)
    print("SPIKE 003: spectral-vinheta-detection")
    print("=" * 70)
    
    ref = AudioSegment.from_mp3(VHT_REF)
    print(f"Referência: {VHT_REF}")
    print(f"  Duração: {len(ref)/1000:.2f}s, {ref.channels}ch, {ref.frame_rate}Hz")
    print()
    
    # Selecionar 3 arquivos aleatórios (brutos)
    brutos = list(Path(BOLETINS_DIR).glob("*.mp3"))
    random.shuffle(brutos)
    amostra = brutos[:3]
    
    resultados = []
    
    for audio_path in amostra:
        print(f"--- {audio_path.name} ({os.path.getsize(audio_path)/1024/1024:.1f}MB) ---")
        
        resultado, score = detectar_vinheta_espectral(str(audio_path), VHT_REF, threshold=0.5)
        
        if resultado:
            t_ini, t_fim, s = resultado
            print(f"  ✅ Vinheta detectada!")
            print(f"     Início: {t_ini:.3f}s")
            print(f"     Fim: {t_fim:.3f}s")
            print(f"     Score: {s:.3f}")
            resultados.append({
                "arquivo": audio_path.name,
                "detectado": True,
                "inicio_s": round(t_ini, 3),
                "fim_s": round(t_fim, 3),
                "score": round(s, 3)
            })
        else:
            print(f"  ❌ Vinheta não detectada (score={score:.3f})")
            resultados.append({
                "arquivo": audio_path.name,
                "detectado": False,
                "score": round(score, 3)
            })
        print()
    
    # Resumo
    print("=" * 70)
    print("RESUMO")
    print("=" * 70)
    detectados = sum(1 for r in resultados if r["detectado"])
    print(f"  Total testado: {len(resultados)}")
    print(f"  Detectados: {detectados}/{len(resultados)}")
    
    if detectados > 0:
        scores = [r["score"] for r in resultados if r["detectado"]]
        print(f"  Score médio: {np.mean(scores):.3f}")
        print(f"  Score min: {np.min(scores):.3f}")
        print(f"  Score max: {np.max(scores):.3f}")
    
    # Salvar
    out_path = Path(__file__).parent / "resultados.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print(f"\n  Resultados salvos: {out_path}")

if __name__ == "__main__":
    main()
