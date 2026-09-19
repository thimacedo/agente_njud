#!/usr/bin/env python3
"""Spike 004: compara Whisper base vs small para cobertura do roteiro."""
import time, json, re, tempfile, os, random
import numpy as np
from pydub import AudioSegment
from pathlib import Path

BOLETINS_DIR = r"E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\boletins"

# Roteiros de referência (OFF) para alguns dias
ROT = {
    "17 SET": "Uma empresa de tecnologia e varejo online terá que restituir valores pagos por uma consumidora após ela comprar produtos na plataforma e não recebê-los. Consta na sentença que a mulher adquiriu um notebook, no valor de R$ 1.199,90 e um jipe infantil elétrico, por R$ 949,90, entretanto, mesmo constando como entregue no sistema da ré, o notebook nunca foi recebido pela autora da ação.",
    "04 SET": "A Câmara Criminal do TJRN negou recurso do Ministério Público e manteve a decisão que deixou de reconhecer falta grave de um apenado após o rompimento da tornozeleira eletrônica. O colegiado entendeu que o descumprimento das condições do monitoramento, por si só, não justifica a regressão automática do regime de cumprimento da pena.",
}

def normalizar(texto):
    import unicodedata
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto

def cobertura(texto, roteiro):
    t = set(normalizar(texto).split())
    r = set(normalizar(roteiro).split())
    return len(t & r) / len(r) if r else 0.0

def transcrever_faster(path, model_size="base"):
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    audio = AudioSegment.from_mp3(path)
    tmp = tempfile.mktemp(suffix=".wav", dir=r"C:\Users\THIAGO\AppData\Local\Temp")
    audio.export(tmp, format="wav")
    t0 = time.time()
    segments, info = model.transcribe(tmp, language="pt")
    texto = " ".join(s.text for s in segments)
    elapsed = time.time() - t0
    os.unlink(tmp)
    return texto.strip(), elapsed

def main():
    print("=" * 70)
    print("SPIKE 004: whisper-small-vs-base")
    print("=" * 70)
    
    # Selecionar 2 arquivos com roteiro conhecido
    alvos = []
    for dia, roteiro in ROT.items():
        for f in Path(BOLETINS_DIR).glob(f"*{dia}*.mp3"):
            # Preferir arquivos editados (menores, mais rápidos)
            if "_saida" in str(f):
                continue
            alvos.append((str(f), roteiro, dia))
            break
    
    if len(alvos) < 2:
        # Fallback: usar qualquer arquivo
        brutos = list(Path(BOLETINS_DIR).glob("*.mp3"))
        random.shuffle(brutos)
        for f in brutos[:2]:
            if "_saida" not in str(f):
                alvos.append((str(f), ROT.get("17 SET", ""), "unknown"))
    
    resultados = []
    
    for path, roteiro, dia in alvos[:2]:
        fname = Path(path).name
        print(f"\n--- {fname} ({dia}) ---")
        
        # Base
        print("  Whisper base...", end="", flush=True)
        texto_base, tempo_base = transcrever_faster(path, "base")
        cov_base = cobertura(texto_base, roteiro)
        print(f" {tempo_base:.1f}s, cobertura={cov_base:.2%}")
        
        # Small
        print("  Whisper small...", end="", flush=True)
        texto_small, tempo_small = transcrever_faster(path, "small")
        cov_small = cobertura(texto_small, roteiro)
        print(f" {tempo_small:.1f}s, cobertura={cov_small:.2%}")
        
        delta = cov_small - cov_base
        speedup = tempo_small / tempo_base if tempo_base > 0 else 0
        print(f"  Delta: {delta:+.2%}, Speedup: {speedup:.1f}x mais lento")
        
        resultados.append({
            "arquivo": fname,
            "dia": dia,
            "base_tempo": round(tempo_base, 1),
            "small_tempo": round(tempo_small, 1),
            "base_cobertura": round(float(cov_base), 3),
            "small_cobertura": round(float(cov_small), 3),
            "delta": round(float(delta), 3),
            "slowdown": round(float(speedup), 1)
        })
    
    # Resumo
    print(f"\n{'='*70}")
    print("RESUMO")
    print("=" * 70)
    for r in resultados:
        print(f"  {r['arquivo']}:")
        print(f"    Base:   {r['base_tempo']:6.1f}s, {r['base_cobertura']:.2%}")
        print(f"    Small:  {r['small_tempo']:6.1f}s, {r['small_cobertura']:.2%}")
        print(f"    Delta:  {r['delta']:+.2%}, {r['slowdown']:.1f}x mais lento")
    
    # Salvar
    out = Path(__file__).parent / "resultados.json"
    with open(out, "w") as f:
        json.dump(resultados, f, indent=2)
    print(f"\nSalvo: {out}")

if __name__ == "__main__":
    main()
