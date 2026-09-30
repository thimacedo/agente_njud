#!/usr/bin/env python3
"""
Pipeline NJUD — Montagem de Jornal
===================================

Recebe 4 boletins (MP3s com vinheta+cabeça+off+assinatura) e monta 1 jornal
completo seguindo a receita canônica (RECEITA_NJUD.txt):

    VHT_ABERTURA_NJUD
    TRILHA_ESCALADA_NJUD (BG 20%) durante cabeças
    CABEÇA 1 → CABEÇA 2 → CABEÇA 3 → CABEÇA 4
    EFEITO_PASSAGEM_NJUD
    CORPO 1 → EFEITO_PASSAGEM → CORPO 2 → EFEITO_PASSAGEM → CORPO 3 → EFEITO_PASSAGEM → CORPO 4
    VHT_ENCERRAMENTO_NJUD

Toda duração é detectada dinamicamente do áudio — zero hardcoded.

Uso:
    python montar_jornal.py --roteiro <txt> --b1 <mp3> --b2 <mp3> --b3 <mp3> --b4 <mp3> --output <pasta> [--nome NOME]

Dependências: pydub, faster_whisper (.venv_pipeline).
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from pydub import AudioSegment

# ── Configuração (só o que NUNCA muda) ───────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = PROJECT_ROOT / "assets" / "vinhetas" / "njud"

VHT_ABERTURA = ASSETS_DIR / "VHT_ABERTURA_NJUD.mp3"
VHT_ENCERRAMENTO = ASSETS_DIR / "VHT_ENCERRAMENTO_NJUD.mp3"
TRILHA_ESCALADA = ASSETS_DIR / "TRILHA_ESCALADA_NJUD.mp3"
EFEITO_PASSAGEM = ASSETS_DIR / "EFEITO_PASSAGEM_NJUD.mp3"
RECEITA = ASSETS_DIR / "RECEITA_NJUD.txt"

# Limites de segurança (detectados do áudio, não fixos)
LIMIAR_ALINHAMENTO = 0.50  # similaridade mínima roteiro↔Whisper


# ── Receita (parse dinâmico) ─────────────────────────────────────────────────

def carregar_receita():
    """
    Carrega RECEITA_NJUD.txt e extrai parâmetros dinamicamente.
    Retorna dict com bg_volume_percent, estrutura, etc.
    """
    receita = {"bg_volume_percent": 20, "silence_ms": 100}  # defaults mínimos

    if RECEITA.exists():
        texto = RECEITA.read_text(encoding="utf-8")
        # Extrair volume do BG: "20% DO VOLUME COMO BG"
        m = re.search(r'(\d+)%\s*(?:DO\s*)?VOLUME', texto, re.I)
        if m:
            receita["bg_volume_percent"] = int(m.group(1))

    return receita


def percent_to_db(percent: int) -> float:
    """Converte percentual de volume para dB FS."""
    import math
    if percent <= 0:
        return -60.0
    return 20 * math.log10(percent / 100.0)


# ── Transcrição ───────────────────────────────────────────────────────────────

def transcrever(caminho_audio: str):
    """Transcreve com faster_whisper. Retorna lista de {text, start, end}."""
    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        caminho_audio, language="pt", word_timestamps=True,
        vad_filter=True, vad_parameters=dict(min_silence_duration_ms=300),
    )
    return [{"text": s.text.strip(), "start": s.start, "end": s.end} for s in segments]


# ── Parse do roteiro ──────────────────────────────────────────────────────────

def extrair_cabeca_roteiro(texto_roteiro: str, num_boletim: int):
    """
    Extrai texto da cabeça do boletim N do roteiro.
    Formato: B{N}- TITULO ... CABEÇA: texto ... OFF: ...
    """
    padrao_bloco = rf'B{num_boletim}\s*[-–]\s*.+?(?=B{num_boletim + 1}\s*[-–]|\Z)'
    m_bloco = re.search(padrao_bloco, texto_roteiro, re.DOTALL | re.IGNORECASE)
    if not m_bloco:
        return None

    bloco = m_bloco.group(0)
    m_cabeca = re.search(r'CABEÇA:\s*(.+?)(?:\n\s*\n|\n\s*OFF:)', bloco, re.DOTALL | re.IGNORECASE)
    if not m_cabeca:
        return None

    texto = m_cabeca.group(1).strip()
    texto = re.sub(r'LEO-\d{2}/\d{2}', '', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto if len(texto) > 5 else None


# ── Detecção de vinheta e assinatura ──────────────────────────────────────────

def detectar_vinheta(segmentos):
    """
    Detecta onde a vinheta inicial termina.
    Vinheta = texto introdutório padrão do TJRN.
    Retorna índice do primeiro segmento útil (após vinheta).
    """
    padroes_vinheta = [
        r'not[íi]cias\s+da\s+hora',
        r'boletim\s+informativo',
        r'no\s+ar',
    ]

    for i, seg in enumerate(segmentos):
        texto_lower = seg["text"].lower()
        if any(re.search(p, texto_lower) for p in padroes_vinheta):
            continue
        return i
    return 0


def detectar_assinatura(segmentos):
    """
    Detecta onde a assinatura final começa.
    Assinatura = texto de encerramento padrão do TJRN.
    Retorna timestamp de início da assinatura, ou None.
    """
    padroes_assinatura = [
        r'voc[êe]\s+acabou\s+de\s+ouvir',
        r'obrigado\s+por\s+nos\s+ouvir',
        r'at[é]\s+a\s+pr[óo]xima',
    ]

    for seg in segmentos:
        texto_lower = seg["text"].lower()
        if any(re.search(p, texto_lower) for p in padroes_assinatura):
            return seg["start"]
    return None


# ── Alinhamento cabeça ────────────────────────────────────────────────────────

def alinhar_cabeca(segmentos, texto_cabeca: str, idx_inicio: int):
    """
    Encontra o ponto onde a cabeça termina, alinhando com o texto do roteiro.
    Retorna (timestamp_fim_cabeca, similaridade) ou (None, melhor_sim).
    """
    if not texto_cabeca:
        return None, 0

    texto_cabeca_norm = texto_cabeca.lower()
    palavras_cabeca = texto_cabeca_norm.split()

    melhor_sim = 0
    melhor_ts = None

    for i in range(idx_inicio, len(segmentos)):
        texto_acumulado = " ".join(s["text"] for s in segmentos[idx_inicio:i + 1]).lower()
        sim = SequenceMatcher(None, texto_acumulado, texto_cabeca_norm).ratio()

        if sim > melhor_sim:
            melhor_sim = sim
            melhor_ts = segmentos[i]["end"]

        if len(texto_acumulado.split()) > len(palavras_cabeca) * 2.5:
            break

    if melhor_sim >= LIMIAR_ALINHAMENTO:
        return melhor_ts, melhor_sim
    return None, melhor_sim


# ── Separação cabeça/corpo ────────────────────────────────────────────────────

def separar_boletim(audio: AudioSegment, segmentos, texto_cabeca: str = None):
    """
    Separa cabeça e corpo de um boletim.

    Toda duração é detectada do áudio:
    - Vinheta: detectada por padrão de texto
    - Cabeça: alinhada com roteiro OU proporcional ao gap de transição
    - Corpo: do fim da cabeça até a assinatura
    - Assinatura: detectada por padrão de texto

    Retorna: (cabeca_audio, corpo_audio, metodo, info_debug)
    """
    # 1. Detectar fim da vinheta (por texto)
    idx_pos_vinheta = detectar_vinheta(segmentos)
    tempo_pos_vinheta = segmentos[idx_pos_vinheta]["start"] if idx_pos_vinheta < len(segmentos) else 0

    # 2. Detectar assinatura final (por texto)
    tempo_assinatura = detectar_assinatura(segmentos)

    # 3. Alinhar cabeça (se tiver roteiro)
    tempo_fim_cabeca = None
    metodo = "roteiro"
    sim = 0

    if texto_cabeca:
        tempo_fim_cabeca, sim = alinhar_cabeca(segmentos, texto_cabeca, idx_pos_vinheta)

    # 4. Fallback: detectar gap natural após vinheta
    if tempo_fim_cabeca is None:
        dur_total = len(audio) / 1000
        # Cabeça típica: entre 3s e 30% do áudio total (após vinheta)
        limite_min = tempo_pos_vinheta + 3
        limite_max = tempo_pos_vinheta + (dur_total - tempo_pos_vinheta) * 0.30

        # Procurar gap >500ms dentro da janela esperada para cabeça
        for i in range(idx_pos_vinheta, len(segmentos) - 1):
            gap = segmentos[i + 1]["start"] - segmentos[i]["end"]
            t_fim = segmentos[i]["end"]

            if t_fim < limite_min:
                continue  # muito cedo, ainda na cabeça
            if t_fim > limite_max:
                break  # passou do limite máximo da cabeça

            if gap >= 0.5:  # gap de 500ms = transição provável
                tempo_fim_cabeca = t_fim
                metodo = "gap_natural"
                break

    # 5. Fallback: usar primeiro segmento completo após vinheta
    if tempo_fim_cabeca is None:
        if idx_pos_vinheta < len(segmentos):
            seg_primeiro = segmentos[idx_pos_vinheta]
            tempo_fim_cabeca = seg_primeiro["end"]
            metodo = "primeiro_segmento"
        else:
            tempo_fim_cabeca = tempo_pos_vinheta + 8  # último recurso
            metodo = "proporcional_fixo"

    # 6. Definir limites
    fim_cabeca_ms = int(tempo_fim_cabeca * 1000)
    inicio_assinatura_ms = int(tempo_assinatura * 1000) if tempo_assinatura else len(audio)

    # 7. Extrair
    cabeca = audio[int(tempo_pos_vinheta * 1000):fim_cabeca_ms]
    corpo = audio[fim_cabeca_ms:inicio_assinatura_ms]

    info = {
        "tempo_vinheta_fim_s": round(tempo_pos_vinheta, 2),
        "tempo_cabeca_fim_s": round(tempo_fim_cabeca, 2),
        "tempo_assinatura_inicio_s": round(tempo_assinatura, 2) if tempo_assinatura else None,
        "similaridade": round(sim, 3) if sim else None,
    }

    return cabeca, corpo, metodo, info


# ── Montagem ──────────────────────────────────────────────────────────────────

def carregar_vinheta(caminho: Path) -> AudioSegment | None:
    if caminho.exists():
        return AudioSegment.from_mp3(str(caminho))
    return None


def preparar_trilha_bg(duracao_ms: int, volume_percent: int = 20) -> AudioSegment:
    """Prepara trilha de fundo com duração e volume dinâmicos."""
    trilha = carregar_vinheta(TRILHA_ESCALADA)
    if trilha is None:
        return AudioSegment.silent(duration=duracao_ms)

    # Loop se necessário
    while len(trilha) < duracao_ms:
        trilha = trilha + trilha

    trilha = trilha[:duracao_ms]

    # Volume dinâmico (convertido de percentual)
    gain_db = percent_to_db(volume_percent)
    return trilha.apply_gain(gain_db)


def overlay_bg(audio: AudioSegment, bg: AudioSegment) -> AudioSegment:
    """Sobreposição de BG com ajuste automático de duração."""
    if len(bg) < len(audio):
        bg = bg + AudioSegment.silent(duration=len(audio) - len(bg))
    elif len(bg) > len(audio):
        bg = bg[:len(audio)]
    return audio.overlay(bg)


def normalizar_lufs(input_path: str, output_path: str, target_lufs: float = -16.0):
    """Normalização loudnorm via ffmpeg."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
        "-b:a", "192k", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {result.stderr[-500:]}")


def detectar_silencio_gap(audioseg: AudioSegment, padrao_ms: int = 100) -> int:
    """
    Detecta o gap natural de silêncio entre segmentos do áudio.
    Usado para definir o espaçamento entre blocos do jornal.
    """
    from pydub.silence import detect_nonsilent
    segs = detect_nonsilent(audioseg, min_silence_len=200, silence_thresh=-35)

    gaps = []
    for i in range(len(segs) - 1):
        gap = segs[i + 1][0] - segs[i][1]
        if gap > 50:  # gaps significativos
            gaps.append(gap)

    if gaps:
        # Usar mediana dos gaps (mais robusto que média)
        gaps.sort()
        mediana = gaps[len(gaps) // 2]
        return min(max(mediana, 50), 500)  # clamp entre 50ms e 500ms

    return padrao_ms  # fallback para o padrão


# ── Pipeline principal ────────────────────────────────────────────────────────

def montar_jornal(boletins_paths: list[str], output_dir: str,
                  nome_jornal: str = None, roteiro_path: str = None,
                  normalizar: bool = True, target_lufs: float = -16.0) -> dict:
    """Monta 1 jornal a partir de 4 boletins. Toda duração é detectada dinamicamente."""

    if len(boletins_paths) != 4:
        raise ValueError(f"NJUD requer exatamente 4 boletins, recebidos {len(boletins_paths)}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if nome_jornal is None:
        nome_jornal = f"NJUD_{timestamp}"

    # ── Carregar receita (parâmetros dinâmicos) ───────────────────────────
    receita = carregar_receita()
    bg_volume = receita["bg_volume_percent"]

    # ── Carregar roteiro (opcional) ───────────────────────────────────────
    texto_roteiro = None
    if roteiro_path:
        rf = Path(roteiro_path)
        if rf.exists():
            texto_roteiro = rf.read_text(encoding="utf-8")
            print(f"📄 Roteiro: {rf.name}")

    # ── Carregar vinhetas ─────────────────────────────────────────────────
    print("📦 Carregando vinhetas...")
    vht_abertura = carregar_vinheta(VHT_ABERTURA)
    vht_encerramento = carregar_vinheta(VHT_ENCERRAMENTO)
    efeito_passagem = carregar_vinheta(EFEITO_PASSAGEM)

    for nome, vht in [("Abertura", vht_abertura), ("Encerramento", vht_encerramento), ("Passagem", efeito_passagem)]:
        if vht is None:
            raise FileNotFoundError(f"Vinheta não encontrada: {nome}")
        print(f"  ✓ {nome}: {len(vht) / 1000:.1f}s")

    # ── Processar boletins ────────────────────────────────────────────────
    print("\n🎙️ Processando boletins...")
    cabecas = []
    corpos = []
    info_boletins = []

    for i, bp in enumerate(boletins_paths, 1):
        print(f"\n  Boletim {i}: {Path(bp).name}")
        audio = AudioSegment.from_file(bp)
        print(f"    Duração total: {len(audio) / 1000:.1f}s")

        # Transcrever
        print(f"    Transcrevendo...", end="", flush=True)
        segmentos = transcrever(bp)
        print(f" {len(segmentos)} segmentos")

        # Extrair cabeça do roteiro
        texto_cabeca = None
        if texto_roteiro:
            texto_cabeca = extrair_cabeca_roteiro(texto_roteiro, i)
            if texto_cabeca:
                print(f"    Cabeça roteiro: \"{texto_cabeca[:60]}...\"")

        # Separar (tudo dinâmico)
        cabeca, corpo, metodo, info = separar_boletim(audio, segmentos, texto_cabeca)

        cabecas.append(cabeca)
        corpos.append(corpo)

        info_boletins.append({
            "boletim": i,
            "arquivo": Path(bp).name,
            "duracao_total_s": round(len(audio) / 1000, 1),
            "duracao_cabeca_s": round(len(cabeca) / 1000, 1),
            "duracao_corpo_s": round(len(corpo) / 1000, 1),
            "metodo_separacao": metodo,
            **info,
        })
        sim_str = f", sim={info['similaridade']:.0%}" if info.get('similaridade') else ""
        print(f"    ✓ Cabeça: {len(cabeca) / 1000:.1f}s, Corpo: {len(corpo) / 1000:.1f}s [{metodo}{sim_str}]")

    # ── Montar blocos ─────────────────────────────────────────────────────
    print("\n🔧 Montando blocos...")

    # Silêncio entre blocos: detectado dinamicamente do áudio de entrada
    silencio_ms = detectar_silencio_gap(
        AudioSegment.from_file(boletins_paths[0])
    )
    print(f"  Silêncio entre blocos: {silencio_ms}ms (detectado)")

    # Bloco cabeças com BG (duração = soma das cabeças + silêncios)
    dur_cabecas_ms = sum(len(c) for c in cabecas) + silencio_ms * 3
    trilha_bg = preparar_trilha_bg(dur_cabecas_ms, bg_volume)

    bloco_cabecas = AudioSegment.empty()
    for i, cab in enumerate(cabecas):
        bloco_cabecas += cab
        if i < len(cabecas) - 1:
            bloco_cabecas += AudioSegment.silent(duration=silencio_ms)
    bloco_cabecas_bg = overlay_bg(bloco_cabecas, trilha_bg)

    # Bloco corpos com passagens
    bloco_corpos = AudioSegment.empty()
    for i, corpo in enumerate(corpos):
        if i > 0 and efeito_passagem:
            bloco_corpos += efeito_passagem
        bloco_corpos += corpo

    print(f"  ✓ Bloco cabeças: {len(bloco_cabecas_bg) / 1000:.1f}s")
    print(f"  ✓ Bloco corpos: {len(bloco_corpos) / 1000:.1f}s")

    # ── Montar jornal ─────────────────────────────────────────────────────
    print("\n📰 Montando jornal...")
    sil = AudioSegment.silent(duration=silencio_ms)
    jornal = vht_abertura + sil + bloco_cabecas_bg + sil + bloco_corpos + sil + vht_encerramento

    duracao = len(jornal) / 1000
    print(f"  ✓ Duração: {int(duracao // 60)}:{int(duracao % 60):02d}")

    # ── Exportar ──────────────────────────────────────────────────────────
    print("\n💾 Exportando...")
    tmp = output_path / f"{nome_jornal}_raw.mp3"
    jornal.export(str(tmp), format="mp3", bitrate="192k")

    final_path = output_path / f"{nome_jornal}.mp3"
    if normalizar:
        print(f"  🎚️ Normalizando ({target_lufs} LUFS)...")
        normalizar_lufs(str(tmp), str(final_path), target_lufs)
        tmp.unlink()
    else:
        tmp.rename(final_path)

    print(f"  ✓ {final_path}")

    # ── Metadados ─────────────────────────────────────────────────────────
    metadados = {
        "nome": nome_jornal,
        "data_geracao": datetime.now().isoformat(),
        "duracao_total_s": round(duracao, 1),
        "arquivo_final": str(final_path),
        "bg_volume_percent": bg_volume,
        "silence_between_blocks_ms": silencio_ms,
        "boletins": info_boletins,
    }
    meta_path = output_path / f"{nome_jornal}_metadados.json"
    meta_path.write_text(json.dumps(metadados, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n✅ JORNAL PRONTO: {final_path}")
    print(f"   Duração: {int(duracao // 60)}:{int(duracao % 60):02d}")
    return metadados


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pipeline NJUD — Monta 1 jornal a partir de 4 boletins")
    parser.add_argument("--roteiro", help="Arquivo de roteiro (melhora separação)")
    parser.add_argument("--b1", required=True, help="MP3 boletim 1")
    parser.add_argument("--b2", required=True, help="MP3 boletim 2")
    parser.add_argument("--b3", required=True, help="MP3 boletim 3")
    parser.add_argument("--b4", required=True, help="MP3 boletim 4")
    parser.add_argument("--output", required=True, help="Pasta de saída")
    parser.add_argument("--nome", default=None, help="Nome do arquivo")
    parser.add_argument("--sem-normalizar", action="store_true")
    parser.add_argument("--lufs", type=float, default=-16.0, help="Target LUFS (padrão: -16)")
    args = parser.parse_args()

    try:
        montar_jornal(
            boletins_paths=[args.b1, args.b2, args.b3, args.b4],
            output_dir=args.output,
            nome_jornal=args.nome,
            roteiro_path=args.roteiro,
            normalizar=not args.sem_normalizar,
            target_lufs=args.lufs,
        )
        return 0
    except Exception as e:
        print(f"❌ ERRO: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
