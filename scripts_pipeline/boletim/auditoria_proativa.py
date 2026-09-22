#!/usr/bin/env python3
"""
auditoria_proativa.py — Auditoria proativa de boletins processados.

Verifica automaticamente após o processamento:
1. Claquetes residuais (geral e individual)
2. Vazamento de assinatura entre boletins
3. Vinhetas (abertura, passagem, encerramento)
4. Background music (BG) no OFF
5. Cobertura do roteiro (cabeça e OFF)
6. Duração mínima e máxima

Uso:
    python auditoria_proativa.py <pasta_saida> [--roteiros <pasta_roteiros>] [--threshold <float>]

Exemplo:
    python auditoria_proativa.py "boletins/18 SET B6-B10_saida" --roteiros boletins/ --threshold 0.70
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import numpy as np
from pydub import AudioSegment

# Adicionar scripts_pipeline ao path
sys.path.insert(0, str(Path(__file__).parent.parent))
from boletim.processar_boletim_canonico import carregar_roteiros


def verificar_claquetes(segments, limite=20):
    """Verifica se há claquetes residuais nos primeiros `limite` segundos.
    
    Ignora a vinheta de abertura e transição (primeiros ~15s) que pode conter 
    alucinações do Whisper como "B-10" ao transcrever a vinheta.
    """
    problemas = []
    for seg in segments:
        if seg.start >= limite:
            break
        # Ignorar vinheta de abertura + transição (primeiros ~15s)
        if seg.start < 15:
            continue
        texto = seg.text.strip()
        # Padrão: letra + número (ex: "B6.", "B-10.", "M-10.")
        if re.match(r'^[A-Z][\-\s]?\d+[\.\s,]', texto, re.I) and len(texto) < 30:
            if 'tribunal' not in texto.lower() and 'justiça' not in texto.lower():
                problemas.append({
                    "timestamp": seg.start,
                    "texto": texto,
                    "tipo": "claquete_individual"
                })
        # Padrão: "Bolitinhos 18..." (claquete geral)
        if re.search(r'bolitinhos|boletins\s+\d', texto, re.I) and seg.start < 18:
            problemas.append({
                "timestamp": seg.start,
                "texto": texto[:50],
                "tipo": "claquete_geral"
            })
    return problemas


def verificar_vazamento_assinatura(segments, limite=30):
    """Verifica se há vazamento de assinatura do boletim anterior.
    
    Ignora a vinheta de abertura (primeiros ~12s) que contém 'Tribunal de Justiça'.
    """
    for seg in segments:
        if seg.start >= limite:
            break
        # Ignorar vinheta de abertura (contém "Tribunal de Justiça" legitimamente)
        if seg.start < 12:
            continue
        texto = seg.text.lower()
        # Assinatura: "Nardo Almeida", "Leonardo Amida", etc.
        if re.search(r'(nardo|leonardo)\s+(almeida|amida|umeda)', texto):
            return True, seg.start, seg.text.strip()
        # "Tribunal de Justiça do Rio Grande do Norte" após a vinheta = vazamento
        if 'tribunal de justiça' in texto and seg.start >= 12:
            return True, seg.start, seg.text.strip()
    return False, None, None


def _correlacao_vinheta(audio, ref_path, max_lag_s=2.0, limiar=0.6):
    """Detecta vinheta por correlação espectral (NCC) com busca de lag.
    
    Converte áudio e referência para mono, downsampling 4x para velocidade.
    Retorna (encontrado, timestamp_segundos).
    """
    from scipy.signal import correlate
    
    ref = AudioSegment.from_mp3(ref_path)
    ref = ref.set_channels(1).set_frame_rate(audio.frame_rate)
    
    # Downsample 4x
    ds = 4
    ref_samples = np.array(ref.get_array_of_samples()[::ds], dtype=np.float64) / 32768.0
    audio_samples = np.array(audio.get_array_of_samples(), dtype=np.float64) / 32768.0
    if audio.channels == 2:
        audio_samples = audio_samples.reshape(-1, 2).mean(axis=1)
    audio_samples = audio_samples[::ds]
    
    if len(ref_samples) < 100 or len(audio_samples) < len(ref_samples):
        return False, None
    
    # Correlação cruzada
    corr = correlate(audio_samples, ref_samples, mode='valid')
    if len(corr) == 0:
        return False, None
    
    # Normalizar
    ref_norm = np.linalg.norm(ref_samples)
    if ref_norm == 0:
        return False, None
    corr_norm = corr / ref_norm
    
    # Buscar pico com lag
    max_lag = int(max_lag_s * audio.frame_rate / ds)
    if max_lag > len(corr_norm):
        max_lag = len(corr_norm)
    
    pico_idx = np.argmax(corr_norm[:max_lag])
    pico_val = corr_norm[pico_idx]
    
    if pico_val >= limiar:
        timestamp = pico_idx * ds / audio.frame_rate
        return True, timestamp
    
    return False, None


def verificar_vinheta_abertura(audio, ref_path, limite=15):
    """Verifica se a vinheta de abertura está presente por correlação espectral."""
    if not ref_path or not os.path.exists(ref_path):
        return False, None
    encontrado, ts = _correlacao_vinheta(audio, ref_path, max_lag_s=3.0, limiar=0.6)
    if encontrado and ts < limite:
        return True, ts
    return False, None


def verificar_vinheta_encerramento(audio, ref_path, limite=20):
    """Verifica se a vinheta de encerramento está presente por correlação espectral.
    
    A vinheta de encerramento está no FIM do áudio, então correlacionamos
    o asset de encerramento contra os últimos N segundos do áudio.
    """
    if not ref_path or not os.path.exists(ref_path):
        return False, None
    
    dur = len(audio) / 1000
    if dur < 20:
        return False, None
    
    # Pegar últimos 25s do áudio (janela de busca)
    janela = audio[max(0, int((dur - 25) * 1000)):]
    encontrado, ts_rel = _correlacao_vinheta(janela, ref_path, max_lag_s=5.0, limiar=0.6)
    if encontrado:
        ts_abs = max(0, dur - 25) + ts_rel
        return True, ts_abs
    return False, None


def verificar_vinheta_passagem(audio, ref_path, inicio_pct=0.25, fim_pct=0.45):
    """Verifica se a vinheta de passagem está presente por correlação espectral.
    
    A passagem está na transição cabeça/off, tipicamente entre 25-45% do áudio.
    """
    if not ref_path or not os.path.exists(ref_path):
        return False, None
    
    dur = len(audio) / 1000
    inicio = int(inicio_pct * dur)
    fim = int(fim_pct * dur)
    
    if fim <= inicio:
        return False, None
    
    janela = audio[inicio*1000:fim*1000]
    encontrado, ts_rel = _correlacao_vinheta(janela, ref_path, max_lag_s=3.0, limiar=0.5)
    if encontrado:
        ts_abs = inicio + ts_rel
        return True, ts_abs
    return False, None


def verificar_bg_off(audio, inicio_pct=0.30, fim_pct=0.85):
    """Verifica se há background music no OFF (RMS > threshold em gaps).
    
    O OFF começa depois da cabeça + vinheta de abertura + passagem.
    Usar janela 30-85% do áudio para evitar vinhetas.
    Threshold 100: BG está presente se RMS mínimo > 100.
    """
    dur = len(audio) / 1000
    inicio = int(inicio_pct * dur)
    fim = int(fim_pct * dur)
    
    rms_min = float('inf')
    for t in range(inicio, min(fim, int(dur) - 2), 1):
        janela = audio[t*1000:(t+1)*1000]
        samples = np.array(janela.get_array_of_samples(), dtype=np.float32)
        rms = float(np.sqrt(np.mean(samples**2)))
        rms_min = min(rms_min, rms)
    
    return rms_min > 100, rms_min


def verificar_cobertura_roteiro(texto_transcrito, texto_roteiro):
    """Calcula cobertura de palavras do roteiro na transcrição."""
    if not texto_roteiro:
        return 0.0, 0, 0
    
    texto_norm = re.sub(r'[^\w\s]', '', texto_transcrito.lower())
    roteiro_norm = re.sub(r'[^\w\s]', '', texto_roteiro.lower())
    
    palavras_roteiro = set(roteiro_norm.split())
    palavras_texto = set(texto_norm.split())
    
    if not palavras_roteiro:
        return 0.0, 0, 0
    
    cobertas = len(palavras_roteiro & palavras_texto)
    total = len(palavras_roteiro)
    cobertura = cobertas / total
    
    return cobertura, cobertas, total


def auditar_boletim(arquivo_path, roteiro_cabeca="", roteiro_off="", threshold=0.70,
                    ref_abertura=None, ref_passagem=None, ref_encerramento=None,
                    audio_original_path=None):
    """Audita um boletim individual. Retorna dict com resultados.
    
    Se audio_original_path for fornecido, transcreve o áudio original (sem vinhetas)
    para verificar a cobertura do roteiro. Caso contrário, transcreve o áudio montado.
    """
    audio = AudioSegment.from_mp3(str(arquivo_path))
    dur = len(audio) / 1000
    
    # Transcrever o áudio original (sem vinhetas) se disponível
    # Isso evita que a vinheta de abertura cubra a cabeça e cause alucinações
    from faster_whisper import WhisperModel
    modelo = WhisperModel("base", device="cpu", compute_type="int8")
    
    if audio_original_path and Path(audio_original_path).exists():
        # Transcrever o áudio original (sem vinhetas)
        audio_para_transcrever = AudioSegment.from_mp3(str(audio_original_path))
        tmp = tempfile.mktemp(suffix='.wav', dir=None)
        audio_para_transcrever.export(tmp, format="wav")
        segments_iter, info = modelo.transcribe(tmp, language="pt")
        segments = list(segments_iter)
        os.unlink(tmp)
    else:
        # Fallback: transcrever o áudio montado (com vinhetas)
        tmp = tempfile.mktemp(suffix='.wav', dir=None)
        audio.export(tmp, format="wav")
        segments_iter, info = modelo.transcribe(tmp, language="pt")
        segments = list(segments_iter)
        os.unlink(tmp)
    
    texto_completo = " ".join(s.text.strip() for s in segments)
    
    # Verificações
    claquetes = verificar_claquetes(segments)
    vazamento, vazamento_ts, vazamento_txt = verificar_vazamento_assinatura(segments)
    abertura_ok, abertura_ts = verificar_vinheta_abertura(audio, ref_abertura)
    encerramento_ok, encerramento_ts = verificar_vinheta_encerramento(audio, ref_encerramento)
    passagem_ok, passagem_ts = verificar_vinheta_passagem(audio, ref_passagem)
    bg_ok, bg_rms = verificar_bg_off(audio)
    
    # Cobertura
    cov_cab, cab_cab, cab_tot = verificar_cobertura_roteiro(texto_completo, roteiro_cabeca)
    cov_off, off_cab, off_tot = verificar_cobertura_roteiro(texto_completo, roteiro_off)
    
    # Status
    problemas = []
    if claquetes:
        problemas.append(f"claquetes: {len(claquetes)}")
    if vazamento:
        problemas.append(f"vazamento assinatura em {vazamento_ts:.1f}s")
    if not abertura_ok:
        problemas.append("vinheta abertura ausente")
    if not encerramento_ok:
        problemas.append("vinheta encerramento ausente")
    if not bg_ok:
        problemas.append(f"BG ausente (RMS={bg_rms:.0f})")
    if cov_cab < threshold:
        problemas.append(f"cobertura cabeça {cov_cab:.0%} < {threshold:.0%}")
    if cov_off < threshold:
        problemas.append(f"cobertura OFF {cov_off:.0%} < {threshold:.0%}")
    
    status = "OK" if not problemas else "REPROVADO"
    
    return {
        "arquivo": str(arquivo_path),
        "duracao": dur,
        "status": status,
        "problemas": problemas,
        "claquetes": claquetes,
        "vazamento": {"detectado": vazamento, "timestamp": vazamento_ts, "texto": vazamento_txt},
        "vinheta_abertura": {"presente": abertura_ok, "timestamp": abertura_ts},
        "vinheta_encerramento": {"presente": encerramento_ok, "timestamp": encerramento_ts},
        "bg_off": {"presente": bg_ok, "rms_min": bg_rms},
        "cobertura_cabeca": {"cobertura": cov_cab, "cobertas": cab_cab, "total": cab_tot},
        "cobertura_off": {"cobertura": cov_off, "cobertas": off_cab, "total": off_tot},
    }


def auditoria_proativa(pasta_saida, pasta_roteiros=None, threshold=0.70,
                       ref_abertura=None, ref_passagem=None, ref_encerramento=None,
                       audio_original_path=None):
    """Executa auditoria proativa em todos os boletins da pasta."""
    pasta = Path(pasta_saida)
    arquivos = sorted([f for f in pasta.glob("*.mp3")])
    
    if not arquivos:
        print("Nenhum arquivo MP3 encontrado.")
        return []
    
    # Carregar roteiros
    roteiros = {}
    if pasta_roteiros:
        # Extrair data do primeiro arquivo
        primeiro = arquivos[0].stem
        m_data = re.search(r'(\d{1,2})\s*[Ss][Ee][Tt]', primeiro)
        data_str = f"{m_data.group(1)} SET" if m_data else ""
        
        # Extrair faixa
        m_faixa = re.search(r'B(\d+)\s*[-–eE]\s*B(\d+)', primeiro)
        if m_faixa:
            b_ini, b_fim = int(m_faixa.group(1)), int(m_faixa.group(2))
        else:
            b_ini, b_fim = 1, 10
        
        roteiros = carregar_roteiros(Path(pasta_roteiros), data_str, b_ini, b_fim)
    
    print("=" * 70)
    print("AUDITORIA PROATIVA DE BOLETINS")
    print("=" * 70)
    print(f"Pasta: {pasta_saida}")
    print(f"Arquivos: {len(arquivos)}")
    print(f"Threshold: {threshold:.0%}")
    if ref_abertura:
        print(f"Ref abertura: {ref_abertura}")
    if ref_passagem:
        print(f"Ref passagem: {ref_passagem}")
    if ref_encerramento:
        print(f"Ref encerramento: {ref_encerramento}")
    print()
    
    resultados = []
    for arq in arquivos:
        b_num = int(re.search(r'B(\d+)', arq.stem).group(1))
        rot = roteiros.get(b_num, {})
        
        resultado = auditar_boletim(
            arq,
            roteiro_cabeca=rot.get("cabeca", ""),
            roteiro_off=rot.get("off", ""),
            threshold=threshold,
            ref_abertura=ref_abertura,
            ref_passagem=ref_passagem,
            ref_encerramento=ref_encerramento,
            audio_original_path=audio_original_path
        )
        resultados.append(resultado)
        
        # Imprimir resumo
        status_icon = "✓" if resultado["status"] == "OK" else "✗"
        print(f"{status_icon} B{b_num} ({resultado['duracao']:.1f}s) — {resultado['status']}")
        if resultado["problemas"]:
            for p in resultado["problemas"]:
                print(f"    ⚠️ {p}")
        else:
            print(f"    Cabeça: {resultado['cobertura_cabeca']['cobertura']:.0%} | "
                  f"OFF: {resultado['cobertura_off']['cobertura']:.0%} | "
                  f"BG: {'✓' if resultado['bg_off']['presente'] else '✗'}")
    
    # Resumo final
    print()
    print("=" * 70)
    aprovados = sum(1 for r in resultados if r["status"] == "OK")
    reprovados = len(resultados) - aprovados
    print(f"RESUMO: {aprovados} aprovados, {reprovados} reprovados")
    print("=" * 70)
    
    if reprovados > 0:
        print("\nBoletins reprovados:")
        for r in resultados:
            if r["status"] != "OK":
                print(f"  - {Path(r['arquivo']).name}: {', '.join(r['problemas'])}")
    
    return resultados


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auditoria proativa de boletins")
    parser.add_argument("pasta_saida", help="Pasta com boletins MP3")
    parser.add_argument("--roteiros", help="Pasta com roteiros .txt", default=None)
    parser.add_argument("--threshold", type=float, default=0.60, help="Threshold de cobertura (default: 0.60, Item 18)")
    parser.add_argument("--ref-abertura", help="Path da vinheta de abertura", default=None)
    parser.add_argument("--ref-passagem", help="Path da vinheta de passagem", default=None)
    parser.add_argument("--ref-encerramento", help="Path da vinheta de encerramento", default=None)
    parser.add_argument("--audio-original", help="Path do áudio original (sem vinhetas) para transcrição", default=None)
    args = parser.parse_args()
    
    resultados = auditoria_proativa(
        args.pasta_saida, 
        args.roteiros, 
        args.threshold,
        ref_abertura=args.ref_abertura,
        ref_passagem=args.ref_passagem,
        ref_encerramento=args.ref_encerramento,
        audio_original_path=args.audio_original
    )
    
    # Salvar JSON
    saida_json = Path(args.pasta_saida) / "auditoria_proativa.json"
    with open(saida_json, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print(f"\nAuditoria salva em: {saida_json}")
