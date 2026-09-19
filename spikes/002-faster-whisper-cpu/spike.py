#!/usr/bin/env python3
"""Spike 002: compara openai-whisper vs faster-whisper em CPU."""
import time
import tempfile
import os
import json
import re
from pathlib import Path
from pydub import AudioSegment

AUDIO_PATH = r"E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\boletins\17 SET B1-B5-2_saida\BOLETIM_RADIO_TJRN_17_SET_2026_B1__TJRN_EMPRESA_DEVOLVER_VALORES_FALHA_COMPRA.mp3"

ROTEIRO_OFF = """Uma empresa de tecnologia e varejo online terá que restituir valores pagos por uma consumidora após ela comprar produtos na plataforma e não recebê-los. Consta na sentença que a mulher adquiriu um notebook, no valor de R$ 1.199,90 e um jipe infantil elétrico, por R$ 949,90, entretanto, mesmo constando como entregue no sistema da ré, o notebook nunca foi recebido pela autora da ação. De acordo com os autos, a consumidora tentou exercer o direito de arrependimento em relação ao jipe, porém, não conseguiu efetuar o procedimento por sua conta ter sido bloqueada pela ré, inviabilizando a devolução e o reembolso. Já a empresa alegou a regularidade da prestação do serviço e afirmou que o notebook foi entregue no endereço da autora. O caso foi julgado pelo 4º Juizado Especial Cível e Criminal da Comarca de Mossoró. O juiz responsável pelo caso, destacou que a relação jurídica entre as partes é de consumo, levando em consideração o Código de Defesa do Consumidor. Ainda de acordo com o magistrado, mesmo com a ré afirmando que o notebook foi entregue em dezembro do ano passado segundo registros sistêmicos internos, essas provas são insuficientes para comprovar o adimplemento da obrigação."""

def normalizar(texto):
    import unicodedata
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto

def calcular_cobertura(texto_transcrito, texto_roteiro):
    t_norm = set(normalizar(texto_transcrito).split())
    r_norm = set(normalizar(texto_roteiro).split())
    if not r_norm:
        return 0.0
    return len(r_norm & t_norm) / len(r_norm)

def transcricao_openai_whisper(audio_path):
    import whisper
    modelo = whisper.load_model("base")
    tmp = tempfile.mktemp(suffix=".wav", dir=r"C:\Users\THIAGO\AppData\Local\Temp")
    AudioSegment.from_mp3(audio_path).export(tmp, format="wav")
    t0 = time.time()
    result = modelo.transcribe(tmp, language="pt", fp16=False)
    elapsed = time.time() - t0
    os.unlink(tmp)
    return result["text"].strip(), elapsed

def transcricao_faster_whisper(audio_path):
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    tmp = tempfile.mktemp(suffix=".wav", dir=r"C:\Users\THIAGO\AppData\Local\Temp")
    AudioSegment.from_mp3(audio_path).export(tmp, format="wav")
    t0 = time.time()
    segments, info = model.transcribe(tmp, language="pt")
    texto = " ".join(s.text for s in segments)
    elapsed = time.time() - t0
    os.unlink(tmp)
    return texto.strip(), elapsed

def main():
    print("=" * 60)
    print("SPIKE 002: faster-whisper-cpu")
    print("=" * 60)
    print(f"ÁUDIO: {Path(AUDIO_PATH).name}")
    print()

    resultados = {}

    # Teste 1: openai-whisper
    print("--- openai-whisper (baseline) ---")
    try:
        texto, tempo = transcricao_openai_whisper(AUDIO_PATH)
        cobertura = calcular_cobertura(texto, ROTEIRO_OFF)
        resultados["openai_whisper"] = {"tempo_s": tempo, "cobertura": cobertura, "texto_inicio": texto[:150]}
        print(f"  Tempo: {tempo:.1f}s")
        print(f"  Cobertura: {cobertura:.2%}")
        print(f"  Início: {texto[:150]}...")
    except Exception as e:
        print(f"  ERRO: {e}")
        resultados["openai_whisper"] = {"erro": str(e)}
    print()

    # Teste 2: faster-whisper
    print("--- faster-whisper (int8) ---")
    try:
        texto, tempo = transcricao_faster_whisper(AUDIO_PATH)
        cobertura = calcular_cobertura(texto, ROTEIRO_OFF)
        resultados["faster_whisper_int8"] = {"tempo_s": tempo, "cobertura": cobertura, "texto_inicio": texto[:150]}
        print(f"  Tempo: {tempo:.1f}s")
        print(f"  Cobertura: {cobertura:.2%}")
        print(f"  Início: {texto[:150]}...")
    except ImportError as e:
        print(f"  faster-whisper não instalado: {e}")
        print("  Instalando...")
        import subprocess
        subprocess.run(["pip", "install", "faster-whisper"], check=True)
        print("  Reexecutando...")
        texto, tempo = transcricao_faster_whisper(AUDIO_PATH)
        cobertura = calcular_cobertura(texto, ROTEIRO_OFF)
        resultados["faster_whisper_int8"] = {"tempo_s": tempo, "cobertura": cobertura, "texto_inicio": texto[:150]}
        print(f"  Tempo: {tempo:.1f}s")
        print(f"  Cobertura: {cobertura:.2%}")
    except Exception as e:
        print(f"  ERRO: {e}")
        resultados["faster_whisper_int8"] = {"erro": str(e)}
    print()

    # Resumo
    print("=" * 60)
    print("RESUMO")
    print("=" * 60)
    for nome, r in resultados.items():
        if "erro" in r:
            print(f"  {nome}: ERRO - {r['erro']}")
        else:
            print(f"  {nome}: {r['tempo_s']:.1f}s, {r['cobertura']:.2%}")

    # Speedup
    if "openai_whisper" in resultados and "faster_whisper_int8" in resultados:
        t_base = resultados["openai_whisper"]["tempo_s"]
        t_fast = resultados["faster_whisper_int8"]["tempo_s"]
        speedup = t_base / t_fast if t_fast > 0 else 0
        print(f"\n  Speedup: {speedup:.1f}x")

    # Salvar
    out_path = Path(__file__).parent / "resultados.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print(f"\nResultados salvos em: {out_path}")

if __name__ == "__main__":
    main()
