#!/usr/bin/env python3
"""
auditar_boletins.py — Audita boletins comparando transcrição com roteiro.

Uso:
    python auditar_boletins.py <pasta_saida> [--roteiros <pasta_roteiros>] [--modelo base]

Exemplo:
    python auditar_boletins.py "boletins/18 SET B6-B10_saida" --roteiros "boletins/"
    python auditar_boletins.py "boletins/17 SET B1-B5_saida"
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

from pydub import AudioSegment

# Usar faster-whisper se disponível
try:
    from faster_whisper import WhisperModel
    USE_FASTER = True
except ImportError:
    import whisper
    USE_FASTER = False

# Reutilizar módulos shared do pipeline
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.text_utils import normalizar_texto, extrair_palavras_significativas
from shared.core import calcular_cobertura_roteiro
from processar_boletim_canonico import carregar_roteiros


def transcrever(audio_path: Path, modelo) -> str:
    """Transcreve um arquivo de áudio."""
    audio = AudioSegment.from_mp3(str(audio_path))
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    audio.export(tmp_path, format="wav")
    
    try:
        if USE_FASTER:
            segments_iter, info = modelo.transcribe(tmp_path, language="pt")
            texto = " ".join(s.text for s in segments_iter)
        else:
            result = modelo.transcribe(tmp_path, language="pt", fp16=False)
            texto = " ".join(s["text"] for s in result["segments"])
    finally:
        os.unlink(tmp_path)
    
    return texto


def verificar_repeticoes(texto: str) -> list:
    """Detecta frases repetidas no texto."""
    frases = texto.split(". ")
    frases_repetidas = []
    for i, frase in enumerate(frases):
        frase_norm = normalizar_texto(frase)
        if len(frase_norm.split()) <= 3:
            continue
        for f in frases[i+1:]:
            if frase_norm == normalizar_texto(f):
                frases_repetidas.append(frase[:80])
                break
    return frases_repetidas


def auditar_boletim(
    audio_path: Path,
    roteiro_cabeca: str,
    roteiro_off: str,
    modelo
) -> dict:
    """Audita um boletim individual."""
    texto = transcrever(audio_path, modelo)
    
    # Cobertura
    cov_cab, cab_cab, cab_tot = calcular_cobertura_roteiro(texto, roteiro_cabeca)
    cov_off, off_cab, off_tot = calcular_cobertura_roteiro(texto, roteiro_off)
    
    # Repetições
    repeticoes = verificar_repeticoes(texto)
    
    # Palavras faltando
    palavras_roteiro = extrair_palavras_significativas(roteiro_off)
    palavras_texto = extrair_palavras_significativas(texto)
    faltando = palavras_roteiro - palavras_texto
    
    return {
        "arquivo": audio_path.name,
        "duracao_segundos": len(AudioSegment.from_mp3(str(audio_path))) / 1000,
        "cobertura_cabeca": round(cov_cab, 3),
        "cobertura_off": round(cov_off, 3),
        "repeticoes": len(repeticoes),
        "palavras_faltando": len(faltando),
    }


def main():
    parser = argparse.ArgumentParser(description="Audita boletins comparando transcrição com roteiro")
    parser.add_argument("pasta_saida", help="Pasta com boletins MP3")
    parser.add_argument("--roteiros", help="Pasta com roteiros .txt", default=None)
    parser.add_argument("--modelo", default="base", help="Modelo Whisper (tiny/base/small/medium)")
    args = parser.parse_args()
    
    pasta = Path(args.pasta_saida)
    if not pasta.exists():
        print(f"❌ Pasta não encontrada: {pasta}")
        sys.exit(1)
    
    # Carregar modelo
    print(f"Carregando modelo Whisper ({args.modelo})...")
    if USE_FASTER:
        modelo = WhisperModel(args.modelo, device="cpu", compute_type="int8")
    else:
        modelo = whisper.load_model(args.modelo)
    
    # Carregar roteiros
    roteiros = {}
    if args.roteiros:
        primeiro_mp3 = next(pasta.glob("*.mp3"), None)
        if primeiro_mp3:
            m_data = re.search(r'(\d{1,2})\s*[Ss][Ee][Tt]', primeiro_mp3.stem)
            data_str = f"{m_data.group(1)} SET" if m_data else ""
            m_faixa = re.search(r'B(\d+)\s*[-–eE]\s*B(\d+)', primeiro_mp3.stem)
            if m_faixa:
                b_ini, b_fim = int(m_faixa.group(1)), int(m_faixa.group(2))
            else:
                b_ini, b_fim = 1, 10
            roteiros = carregar_roteiros(Path(args.roteiros), data_str, b_ini, b_fim)
    
    # Encontrar boletins
    arquivos = sorted(pasta.glob("*.mp3"))
    if not arquivos:
        print("❌ Nenhum arquivo MP3 encontrado")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"AUDITORIA: {pasta.name}")
    print(f"Boletins: {len(arquivos)} | Roteiros: {len(roteiros)}")
    print(f"{'='*60}\n")
    
    resultados = []
    for arq in arquivos:
        m = re.search(r'B(\d+)', arq.stem)
        if not m:
            continue
        n = int(m.group(1))
        
        rot = roteiros.get(n, {})
        cabeca = rot.get("cabeca", "")
        off = rot.get("off", "")
        
        print(f"B{n}: {arq.name[:50]}")
        
        resultado = auditar_boletim(arq, cabeca, off, modelo)
        resultados.append(resultado)
        
        print(f"  Cabeça: {resultado['cobertura_cabeca']:.1%}")
        print(f"  OFF:    {resultado['cobertura_off']:.1%}")
        print(f"  Repetições: {resultado['repeticoes']}")
        print(f"  Palavras faltando: {resultado['palavras_faltando']}")
        print()
    
    # Resumo
    if resultados:
        media_cab = sum(r["cobertura_cabeca"] for r in resultados) / len(resultados)
        media_off = sum(r["cobertura_off"] for r in resultados) / len(resultados)
        print(f"{'='*60}")
        print(f"RESUMO: Cabeça média={media_cab:.1%} | OFF média={media_off:.1%}")
        print(f"{'='*60}")


if __name__ == "__main__":
    import re
    main()
