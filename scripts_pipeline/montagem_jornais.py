# coding: utf-8
"""
Montador canônico NJUD — peças preparadas antes da montagem.

Entrada obrigatória: manifesto_producao.json gerado por
njud.controle_producao. Limpeza da passagem ocorre no boletim individual;
BG, abertura e passagens NJUD são adicionados somente depois.
Quatro pares cabeça/corpo em WAV ou MP3, ordem editorial do manifesto,
data de edição explícita, limite de 300s e saída CANDIDATO versionada.
Nunca sobrescreve versões nem aprova escuta/conteúdo automaticamente.

As funções legadas de separação permanecem importáveis para compatibilidade,
mas o ponto de entrada montar_jornal não aceita brutos ou cortes sem manifesto.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from pydub import AudioSegment
from pydub.effects import normalize
from pydub.silence import detect_nonsilent

# ---------------------------------------------------------------------
# Garantir que src/ está no path para importar divisor_boletins.log
# (este script vive em scripts_pipeline/, src/ é irmão de scripts_pipeline/
# dentro de BASE_DIR — ver DECISOES.md Item 10, estrutura canônica).
# ---------------------------------------------------------------------
_BASE_DIR_PADRAO = Path(
    os.getenv("DIVISOR_BASE_DIR", str(Path(__file__).resolve().parent.parent))
)
_SRC_DIR = _BASE_DIR_PADRAO / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

try:
    from divisor_boletins.log import LogPipeline
except ImportError:
    # Fallback mínimo se divisor_boletins não for importável a partir daqui
    # (ex.: execução isolada fora da árvore do projeto) — não interrompe
    # a montagem, só perde o logging estruturado do LogPipeline.
    import logging

    class LogPipeline:  # type: ignore[no-redef]
        def __init__(self, pasta_log: Optional[Path | str] = None) -> None:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
            self._logger = logging.getLogger("montagem_jornais")

        def info(self, msg: str, *args) -> None:
            self._logger.info(msg, *args)

        def warning(self, msg: str, *args) -> None:
            self._logger.warning(msg, *args)

        def error(self, msg: str, *args) -> None:
            self._logger.error(msg, *args)


# ===========================================================================
# CONFIGURAÇÃO — caminhos via env var (DECISOES.md Item 10: nenhum caminho
# hardcoded fora de config; aqui usamos env var com default relativo ao
# BASE_DIR, mesmo padrão já aplicado em sync_drive.py/montagem_boletins.py).
# ===========================================================================

BASE_DIR = _BASE_DIR_PADRAO

DIR_JORNAIS_DIVIDIDOS = Path(
    os.getenv(
        "NJUD_JORNAIS_DIVIDIDOS_DIR",
        str(BASE_DIR / "data" / "processed" / "PRODUCAO_2026" / "JORNAIS_DIVIDIDOS"),
    )
)
DIR_JORNAIS_FINAL = Path(
    os.getenv("NJUD_JORNAIS_FINAL_DIR", str(BASE_DIR / "data" / "output" / "JORNAIS_FINAL"))
)
DIR_ASSETS_VINHETAS_NJUD = Path(
    os.getenv("NJUD_ASSETS_VINHETAS_DIR", str(BASE_DIR / "assets" / "vinhetas" / "njud"))
)

VHT_ABERTURA_NJUD_NOME = os.getenv("NJUD_VHT_ABERTURA_NOME", "VHT_ABERTURA_NJUD.mp3")
VHT_PASSAGEM_NJUD_NOME = os.getenv("NJUD_VHT_PASSAGEM_NOME", "EFEITO_PASSAGEM_NJUD.mp3")
VHT_ENCERRAMENTO_NJUD_NOME = os.getenv("NJUD_VHT_ENCERRAMENTO_NOME", "VHT_ENCERRAMENTO_NJUD.mp3")
TRILHA_ESCALADA_NJUD_NOME = os.getenv("NJUD_TRILHA_ESCALADA_NOME", "TRILHA_ESCALADA_NJUD.mp3")
RECEITA_NJUD_NOME = os.getenv("NJUD_RECEITA_NOME", "RECEITA_NJUD.txt")

# Quantas peças (boletins) compõem um jornal — parte da estrutura imutável
# do Item 9. Não é hardcode de instância: é a definição do formato do
# programa, igual a "um boletim tem cabeça+corpo".
N_BOLETINS_POR_JORNAL = int(os.getenv("NJUD_BOLETINS_POR_JORNAL", "4"))

# Similaridade mínima roteiro↔Whisper para aceitar o alinhamento da cabeça.
LIMIAR_ALINHAMENTO = float(os.getenv("NJUD_LIMIAR_ALINHAMENTO", "0.50"))


# ===========================================================================
# DESCOBERTA DE PASTAS DE NJUD
# ===========================================================================

_RE_NJUD_PASTA = re.compile(r"njud[_\s]*0*(\d+)", re.IGNORECASE)
_RE_INDICE_B = re.compile(r"(?:^|[^A-Za-z0-9])B0*(\d+)(?![A-Za-z0-9])", re.IGNORECASE)
_RE_DATA_BOLETIM = re.compile(r"_(\d{2})_(\d{2})_(\d{4})_")


def _extrair_numero_njud(nome_pasta: str) -> Optional[str]:
    """Extrai o número do NJUD do nome da pasta (ex.: 'NJUD_1918' ou 'NJUD 1918' -> '1918')."""
    m = _RE_NJUD_PASTA.search(nome_pasta)
    if m:
        return m.group(1)
    return None


def _listar_pastas_njud(pasta_entrada: Path) -> list[Path]:
    """Encontra pastas de NJUD em <entrada>/<NJUD>/ ou <entrada>/<MÊS>/<NJUD>/.

    Formato aceito conforme Item 6b: detecção por regex "NJUD <num>" no
    nome da pasta, em qualquer nível de profundidade imediato (direto ou
    dentro de uma pasta de mês).
    """
    pastas: list[Path] = []
    if not pasta_entrada.exists():
        return pastas

    for item in sorted(pasta_entrada.iterdir()):
        if not item.is_dir():
            continue
        if _extrair_numero_njud(item.name):
            pastas.append(item)
        else:
            # pode ser uma pasta de mês contendo pastas de NJUD dentro
            for sub in sorted(item.iterdir()):
                if sub.is_dir() and _extrair_numero_njud(sub.name):
                    pastas.append(sub)

    return pastas


def _indice_boletim(caminho: Path) -> int:
    """Extrai o índice B<n> do nome do arquivo/pasta do boletim para ordenação.

    Não assume sequência sem lacunas (B1, B2, B6, B7 é válido) — só ordena
    numericamente.
    """
    m = _RE_INDICE_B.search(caminho.name)
    if m:
        return int(m.group(1))
    return 0


def _localizar_pares_cabeca_corpo(pasta_njud: Path) -> list[tuple[Path, Path]]:
    """Localiza os pares (CABECA, CORPO) dentro da pasta de um NJUD.

    Procura em <pasta_njud>/**/*_CABECA.mp3 e casa cada uma com o
    *_CORPO.mp3 correspondente (mesmo prefixo, trocando o sufixo).
    """
    if (pasta_njud / "manifesto_producao.json").exists():
        from njud.controle_producao import carregar_pares
        return carregar_pares(pasta_njud)[1]
    pares: list[tuple[Path, Path]] = []
    cabecas = sorted(pasta_njud.rglob("*_CABECA.mp3"), key=_indice_boletim)

    for cabeca in cabecas:
        corpo = cabeca.with_name(cabeca.name.replace("_CABECA.mp3", "_CORPO.mp3"))
        if not corpo.exists():
            raise FileNotFoundError(
                f"CORPO ausente para {cabeca.name} (esperado: {corpo.name})"
            )
        pares.append((cabeca, corpo))

    return pares


def _extrair_data_boletim(caminhos: list[Path]) -> Optional[str]:
    """Extrai DD-MM-AAAA do nome de qualquer um dos arquivos de boletim.

    Regra do Item 2: a data do jornal SEMPRE vem do nome dos boletins de
    origem (padrão BOLETIM_RADIO_TJRN_DD_MM_AAAA_Bx...), nunca de
    contagem de dias úteis a partir de uma âncora fixa.
    """
    for caminho in caminhos:
        m = _RE_DATA_BOLETIM.search(caminho.name)
        if m:
            dd, mm, aaaa = m.groups()
            return f"{dd}-{mm}-{aaaa}"
    return None


def _tem_cabecas_corpos_prontos(pasta: Path) -> bool:
    """True se a pasta já contém cortes CABEÇA/CORPO (modo backward compat)."""
    return (pasta / "manifesto_producao.json").exists() or any(pasta.rglob("*_CABECA.mp3"))


# ===========================================================================
# RECEITA — parâmetros dinâmicos (volume do BG)
# ===========================================================================


def carregar_receita() -> dict:
    """Carrega RECEITA_NJUD.txt e extrai parâmetros dinamicamente."""
    receita = {"bg_volume_percent": 20}
    receita_path = DIR_ASSETS_VINHETAS_NJUD / RECEITA_NJUD_NOME
    if receita_path.exists():
        texto = receita_path.read_text(encoding="utf-8")
        m = re.search(r"(\d+)%\s*(?:DO\s*)?VOLUME", texto, re.I)
        if m:
            receita["bg_volume_percent"] = int(m.group(1))
    return receita


def percent_to_db(percent: int) -> float:
    """Converte percentual de volume para dB FS."""
    if percent <= 0:
        return -60.0
    return 20 * math.log10(percent / 100.0)


# ===========================================================================
# SEPARAÇÃO CABEÇA/CORPO (modo bruto) — absorvido de njud/montar_jornal.py
# ===========================================================================


def transcrever(caminho_audio: str) -> list[dict]:
    """Transcreve com faster_whisper. Retorna lista de {text, start, end}."""
    from faster_whisper import WhisperModel

    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        caminho_audio,
        language="pt",
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300),
    )
    return [{"text": s.text.strip(), "start": s.start, "end": s.end} for s in segments]


def extrair_cabeca_roteiro(texto_roteiro: str, num_boletim: int) -> Optional[str]:
    """Extrai texto da cabeça do boletim N do roteiro.

    Formato: B{N}- TITULO ... CABEÇA: texto ... OFF: ...
    """
    padrao_bloco = rf"B{num_boletim}\s*[-–]\s*.+?(?=B{num_boletim + 1}\s*[-–]|\Z)"
    m_bloco = re.search(padrao_bloco, texto_roteiro, re.DOTALL | re.IGNORECASE)
    if not m_bloco:
        return None

    bloco = m_bloco.group(0)
    m_cabeca = re.search(r"CABEÇA:\s*(.+?)(?:\n\s*\n|\n\s*OFF:)", bloco, re.DOTALL | re.IGNORECASE)
    if not m_cabeca:
        return None

    texto = m_cabeca.group(1).strip()
    texto = re.sub(r"LEO-\d{2}/\d{2}", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto if len(texto) > 5 else None


def detectar_vinheta(segmentos: list[dict]) -> int:
    """Detecta onde a vinheta inicial termina (por padrão de texto)."""
    padroes_vinheta = [
        r"not[íi]cias\s+da\s+hora",
        r"boletim\s+informativo",
        r"no\s+ar",
    ]
    for i, seg in enumerate(segmentos):
        texto_lower = seg["text"].lower()
        if any(re.search(p, texto_lower) for p in padroes_vinheta):
            continue
        return i
    return 0


def detectar_assinatura(segmentos: list[dict]) -> Optional[float]:
    """Detecta onde a assinatura final começa. Retorna timestamp ou None."""
    padroes_assinatura = [
        r"voc[êe]\s+acabou\s+de\s+ouvir",
        r"obrigado\s+por\s+nos\s+ouvir",
        r"at[é]\s+a\s+pr[óo]xima",
    ]
    for seg in segmentos:
        texto_lower = seg["text"].lower()
        if any(re.search(p, texto_lower) for p in padroes_assinatura):
            return seg["start"]
    return None


def alinhar_cabeca(
    segmentos: list[dict], texto_cabeca: str, idx_inicio: int
) -> tuple[Optional[float], float]:
    """Encontra o ponto onde a cabeça termina, alinhando com o roteiro.

    Retorna (timestamp_fim_cabeca, similaridade) ou (None, melhor_sim).
    """
    if not texto_cabeca:
        return None, 0

    texto_cabeca_norm = texto_cabeca.lower()
    palavras_cabeca = texto_cabeca_norm.split()

    melhor_sim = 0
    melhor_ts = None

    for i in range(idx_inicio, len(segmentos)):
        texto_acumulado = " ".join(s["text"] for s in segmentos[idx_inicio : i + 1]).lower()
        sim = SequenceMatcher(None, texto_acumulado, texto_cabeca_norm).ratio()

        if sim > melhor_sim:
            melhor_sim = sim
            melhor_ts = segmentos[i]["end"]

        if len(texto_acumulado.split()) > len(palavras_cabeca) * 2.5:
            break

    if melhor_sim >= LIMIAR_ALINHAMENTO:
        return melhor_ts, melhor_sim
    return None, melhor_sim


def separar_boletim(
    audio: AudioSegment, segmentos: list[dict], texto_cabeca: Optional[str] = None
) -> tuple[AudioSegment, AudioSegment, str, dict]:
    """Separa cabeça e corpo de um boletim. Toda duração é detectada do áudio.

    Estratégias em ordem de preferência:
    1. Alinhamento roteiro↔Whisper
    2. Gap natural (>500ms) após a vinheta
    3. Primeiro segmento completo após a vinheta
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
        limite_min = tempo_pos_vinheta + 3
        limite_max = tempo_pos_vinheta + (dur_total - tempo_pos_vinheta) * 0.30

        for i in range(idx_pos_vinheta, len(segmentos) - 1):
            gap = segmentos[i + 1]["start"] - segmentos[i]["end"]
            t_fim = segmentos[i]["end"]

            if t_fim < limite_min:
                continue
            if t_fim > limite_max:
                break
            if gap >= 0.5:
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
            tempo_fim_cabeca = tempo_pos_vinheta + 8
            metodo = "proporcional_fixo"

    # 6. Definir limites e extrair
    fim_cabeca_ms = int(tempo_fim_cabeca * 1000)
    inicio_assinatura_ms = int(tempo_assinatura * 1000) if tempo_assinatura else len(audio)

    cabeca = audio[int(tempo_pos_vinheta * 1000) : fim_cabeca_ms]
    corpo = audio[fim_cabeca_ms:inicio_assinatura_ms]

    info = {
        "tempo_vinheta_fim_s": round(tempo_pos_vinheta, 2),
        "tempo_cabeca_fim_s": round(tempo_fim_cabeca, 2),
        "tempo_assinatura_inicio_s": round(tempo_assinatura, 2) if tempo_assinatura else None,
        "similaridade": round(sim, 3) if sim else None,
    }

    return cabeca, corpo, metodo, info


def detectar_silencio_gap(audioseg: AudioSegment, padrao_ms: int = 100) -> int:
    """Detecta o gap natural de silêncio entre segmentos do áudio.

    Usado para definir o espaçamento entre blocos do jornal.
    """
    segs = detect_nonsilent(audioseg, min_silence_len=200, silence_thresh=-35)

    gaps = []
    for i in range(len(segs) - 1):
        gap = segs[i + 1][0] - segs[i][1]
        if gap > 50:
            gaps.append(gap)

    if gaps:
        gaps.sort()
        mediana = gaps[len(gaps) // 2]
        return min(max(mediana, 50), 500)

    return padrao_ms


# ===========================================================================
# MONTAGEM — helpers
# ===========================================================================


def _carregar_vinheta(nome_arquivo: str, etapa: str, logger) -> Optional[AudioSegment]:
    caminho = DIR_ASSETS_VINHETAS_NJUD / nome_arquivo
    if not caminho.exists():
        logger.error(f"[{etapa}] Vinheta NJUD não encontrada: {caminho}")
        return None
    try:
        return AudioSegment.from_file(str(caminho))
    except Exception as e:
        logger.error(f"[{etapa}] Erro ao carregar vinheta {caminho}: {e}")
        return None


def preparar_trilha_bg(duracao_ms: int, volume_percent: int = 20) -> AudioSegment:
    """Prepara trilha de fundo com duração e volume dinâmicos."""
    caminho = DIR_ASSETS_VINHETAS_NJUD / TRILHA_ESCALADA_NJUD_NOME
    if not caminho.exists():
        return AudioSegment.silent(duration=duracao_ms)

    trilha = AudioSegment.from_file(str(caminho))

    # Loop se necessário
    while len(trilha) < duracao_ms:
        trilha = trilha + trilha

    trilha = trilha[:duracao_ms]
    return trilha.apply_gain(percent_to_db(volume_percent))


def overlay_bg(audio: AudioSegment, bg: AudioSegment) -> AudioSegment:
    """Sobreposição de BG com ajuste automático de duração."""
    if len(bg) < len(audio):
        bg = bg + AudioSegment.silent(duration=len(audio) - len(bg))
    elif len(bg) > len(audio):
        bg = bg[: len(audio)]
    return audio.overlay(bg)


def normalizar_lufs(input_path: str, output_path: str, target_lufs: float = -16.0) -> None:
    """Normalização loudnorm via ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-af",
        f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
        "-b:a",
        "192k",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {result.stderr[-500:]}")


# ===========================================================================
# MONTAGEM — jornal
# ===========================================================================


def _montar_de_cortes(
    pasta_njud: Path, numero_njud: str, bg_volume: int, logger
) -> Optional[AudioSegment]:
    """Monta o jornal a partir de cortes CABEÇA/CORPO já prontos."""
    etapa = "montagem_jornal"

    try:
        pares = _localizar_pares_cabeca_corpo(pasta_njud)
    except FileNotFoundError as e:
        logger.error(f"[{etapa}] NJUD {numero_njud}: {e} — jornal NÃO será montado (peça pendente)")
        return None

    if len(pares) != N_BOLETINS_POR_JORNAL:
        logger.error(
            f"[{etapa}] NJUD {numero_njud}: esperado {N_BOLETINS_POR_JORNAL} boletins, "
            f"encontrado {len(pares)} — jornal NÃO será montado (peça pendente, Item 6/6b)"
        )
        return None

    vht_abertura = _carregar_vinheta(VHT_ABERTURA_NJUD_NOME, etapa, logger)
    vht_passagem = _carregar_vinheta(VHT_PASSAGEM_NJUD_NOME, etapa, logger)
    vht_encerramento = _carregar_vinheta(VHT_ENCERRAMENTO_NJUD_NOME, etapa, logger)
    if vht_abertura is None or vht_passagem is None or vht_encerramento is None:
        logger.error(f"[{etapa}] NJUD {numero_njud}: vinheta(s) de NJUD ausente(s) — abortando")
        return None

    # Bloco cabeças com BG (volume da RECEITA)
    bloco_cabecas = AudioSegment.empty()
    for indice, (cabeca_path, _corpo_path) in enumerate(pares):
        try:
            if indice:
                bloco_cabecas += AudioSegment.silent(duration=80, frame_rate=bloco_cabecas.frame_rate)
            bloco_cabecas += normalize(AudioSegment.from_file(str(cabeca_path)))
        except Exception as e:
            logger.error(f"[{etapa}] Erro ao carregar {cabeca_path}: {e}")
            return None

    trilha_bg = preparar_trilha_bg(len(bloco_cabecas), bg_volume).fade_out(min(80, len(bloco_cabecas)))
    bloco_cabecas_bg = overlay_bg(bloco_cabecas, trilha_bg)

    # Ordem imutável do Item 9
    jornal = AudioSegment.empty()
    jornal += vht_abertura
    jornal += bloco_cabecas_bg
    jornal += vht_passagem

    for indice, (_cabeca_path, corpo_path) in enumerate(pares):
        if indice:
            jornal += vht_passagem
        try:
            jornal += normalize(AudioSegment.from_file(str(corpo_path)))
            # Respiro antes da passagem/encerramento, sem cortar a fala.
            jornal += AudioSegment.silent(duration=120, frame_rate=jornal.frame_rate)
        except Exception as e:
            logger.error(f"[{etapa}] Erro ao carregar {corpo_path}: {e}")
            return None

    jornal += vht_encerramento
    return jornal


def _montar_de_brutos(
    pasta_njud: Path,
    numero_njud: str,
    bg_volume: int,
    texto_roteiro: Optional[str],
    logger,
) -> Optional[AudioSegment]:
    """Monta o jornal a partir de MP3s brutos (separa cabeça/corpo no caminho)."""
    etapa = "montagem_jornal"

    boletins_mp3s = sorted(pasta_njud.glob("*.mp3"), key=_indice_boletim)
    if len(boletins_mp3s) != N_BOLETINS_POR_JORNAL:
        logger.error(
            f"[{etapa}] NJUD {numero_njud}: esperado {N_BOLETINS_POR_JORNAL} MP3s brutos, "
            f"encontrado {len(boletins_mp3s)}"
        )
        return None

    vht_abertura = _carregar_vinheta(VHT_ABERTURA_NJUD_NOME, etapa, logger)
    vht_passagem = _carregar_vinheta(VHT_PASSAGEM_NJUD_NOME, etapa, logger)
    vht_encerramento = _carregar_vinheta(VHT_ENCERRAMENTO_NJUD_NOME, etapa, logger)
    if vht_abertura is None or vht_passagem is None or vht_encerramento is None:
        logger.error(f"[{etapa}] NJUD {numero_njud}: vinheta(s) de NJUD ausente(s) — abortando")
        return None

    cabecas: list[AudioSegment] = []
    corpos: list[AudioSegment] = []

    for i, bp in enumerate(boletins_mp3s, 1):
        logger.info(f"  Boletim {i}: {bp.name}")
        audio = AudioSegment.from_file(str(bp))
        logger.info(f"    Duração total: {len(audio) / 1000:.1f}s")

        logger.info("    Transcrevendo...")
        segmentos = transcrever(str(bp))
        logger.info(f"    {len(segmentos)} segmentos")

        texto_cabeca = None
        if texto_roteiro:
            texto_cabeca = extrair_cabeca_roteiro(texto_roteiro, _indice_boletim(bp))
            if texto_cabeca:
                logger.info(f'    Cabeça roteiro: "{texto_cabeca[:60]}..."')

        cabeca, corpo, metodo, info = separar_boletim(audio, segmentos, texto_cabeca)
        cabecas.append(cabeca)
        corpos.append(corpo)

        sim_str = f", sim={info['similaridade']:.0%}" if info.get("similaridade") else ""
        logger.info(
            f"    ✓ Cabeça: {len(cabeca) / 1000:.1f}s, "
            f"Corpo: {len(corpo) / 1000:.1f}s [{metodo}{sim_str}]"
        )

    # Silêncio entre blocos: detectado dinamicamente do áudio de entrada
    silencio_ms = detectar_silencio_gap(AudioSegment.from_file(str(boletins_mp3s[0])))
    logger.info(f"  Silêncio entre blocos: {silencio_ms}ms (detectado)")

    # Bloco cabeças com BG
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
        if i > 0 and vht_passagem:
            bloco_corpos += vht_passagem
        bloco_corpos += corpo

    logger.info(f"  ✓ Bloco cabeças: {len(bloco_cabecas_bg) / 1000:.1f}s")
    logger.info(f"  ✓ Bloco corpos: {len(bloco_corpos) / 1000:.1f}s")

    sil = AudioSegment.silent(duration=silencio_ms)
    jornal = AudioSegment.empty()
    jornal += vht_abertura + sil + bloco_cabecas_bg + sil + bloco_corpos + sil + vht_encerramento
    return jornal


def montar_jornal(
    pasta_njud: Path,
    pasta_saida: Path,
    roteiro_path: Optional[str] = None,
    normalizar: bool = True,
    target_lufs: float = -16.0,
    logger=None,
) -> Optional[Path]:
    """Monta UM jornal NJUD. Detecta automaticamente o modo de entrada.

    Args:
        pasta_njud: pasta com cortes CABEÇA/CORPO OU com MP3s brutos.
        pasta_saida: pasta onde salvar o jornal montado (NJUD_*.mp3).
        roteiro_path: roteiro opcional (melhora separação no modo bruto).
        normalizar: aplica loudnorm no arquivo final.
        target_lufs: alvo de loudness.
        logger: logger opcional (LogPipeline).

    Returns:
        Path do jornal montado, ou None em caso de falha (NUNCA monta
        jornal incompleto, Item 6/6b).
    """
    if logger is None:
        logger = LogPipeline()

    etapa = "montagem_jornal"
    # Marcação/limpeza ocorre antes de montar. Falta de manifesto não autoriza
    # os antigos fallbacks de cortar pelo gap/primeiro segmento/proporção.
    from njud.controle_producao import carregar_pares, sha256
    try:
        manifesto, _ = carregar_pares(pasta_njud)
    except (OSError, ValueError, KeyError) as exc:
        logger.error(f"[{etapa}] Preparação auditável obrigatória: {exc}")
        return None
    numero_njud = _extrair_numero_njud(pasta_njud.name) or pasta_njud.name
    if str(manifesto["njud"]) != numero_njud:
        logger.error(f"[{etapa}] Número da pasta diverge do manifesto")
        return None
    logger.info(f"[{etapa}] Iniciando montagem do NJUD {numero_njud} ({pasta_njud})")

    receita = carregar_receita()
    bg_volume = receita["bg_volume_percent"]

    texto_roteiro = None
    if roteiro_path:
        rf = Path(roteiro_path)
        if rf.exists():
            texto_roteiro = rf.read_text(encoding="utf-8")
            logger.info(f"[{etapa}] Roteiro: {rf.name}")

    modo_cortes = _tem_cabecas_corpos_prontos(pasta_njud)

    if modo_cortes:
        logger.info(f"[{etapa}] Modo: cortes CABEÇA/CORPO prontos")
        jornal = _montar_de_cortes(pasta_njud, numero_njud, bg_volume, logger)
        arquivos_data = [p for par in _localizar_pares_cabeca_corpo(pasta_njud) for p in par]
    else:
        logger.info(f"[{etapa}] Modo: MP3s brutos (separação dinâmica)")
        jornal = _montar_de_brutos(pasta_njud, numero_njud, bg_volume, texto_roteiro, logger)
        arquivos_data = sorted(pasta_njud.glob("*.mp3"), key=_indice_boletim)

    if jornal is None:
        return None

    duracao = len(jornal) / 1000
    if duracao > 300:
        logger.error(f"[{etapa}] {duracao:.1f}s excede cinco minutos; requer edição conforme roteiro")
        return None
    logger.info(f"[{etapa}] Duração: {int(duracao // 60)}:{int(duracao % 60):02d}")

    # Nome final: NJUD_<numero>_<DD-MM-AAAA>.mp3 (Item 2 + Item 12)
    # A data dos boletins é a origem, não a data de exibição do jornal.
    data_str = datetime.fromisoformat(manifesto["data_edicao"]).strftime("%d-%m-%Y")
    if data_str is None:
        logger.warning(
            f"[{etapa}] NJUD {numero_njud}: data não encontrada no nome dos boletins "
            f"(esperado padrão _DD_MM_AAAA_) — gerando nome sem data"
        )
        nome_arquivo = f"NJUD_{numero_njud}.mp3"
    else:
        nome_arquivo = f"NJUD_{numero_njud}_{data_str}.mp3"

    versao = manifesto["versao"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", versao):
        logger.error(f"[{etapa}] Versão inválida")
        return None
    nome_arquivo = f"NJUD_{numero_njud}_{data_str}_{versao}_CANDIDATO.mp3"
    pasta_saida.mkdir(parents=True, exist_ok=True)
    tmp = pasta_saida / f"{nome_arquivo[:-4]}_raw.mp3"
    caminho_saida = pasta_saida / nome_arquivo
    if any(p.exists() for p in (tmp, caminho_saida, pasta_saida / f"{nome_arquivo[:-4]}_metadados.json")):
        logger.error(f"[{etapa}] Versão já existe; criar nova versão, sem sobrescrever")
        return None

    try:
        jornal.export(str(tmp), format="mp3", bitrate="192k")
    except Exception as e:
        logger.error(f"[{etapa}] Erro ao salvar jornal {tmp}: {e}")
        return None

    if normalizar:
        logger.info(f"[{etapa}] Normalizando ({target_lufs} LUFS)...")
        try:
            normalizar_lufs(str(tmp), str(caminho_saida), target_lufs)
        except RuntimeError as e:
            logger.error(f"[{etapa}] Normalização falhou: {e}")
            return None
        # Preservar também o intermediário para comparação/retrabalho.
    else:
        import shutil
        shutil.copy2(tmp, caminho_saida)

    check = subprocess.run(["ffmpeg", "-v", "error", "-i", str(caminho_saida), "-f", "null", "-"], capture_output=True)
    if check.returncode:
        logger.error(f"[{etapa}] Arquivo exportado não decodifica; versão não aprovada")
        return None
    logger.info(
        f"[{etapa}] Candidato NJUD {numero_njud} exportado, pendente de auditoria: {caminho_saida} "
        f"({duracao:.1f}s)"
    )

    metadados = {
        "nome": nome_arquivo,
        "numero_njud": numero_njud,
        "data_geracao": datetime.now().isoformat(),
        "duracao_total_s": round(duracao, 1),
        "arquivo_final": str(caminho_saida),
        "bg_volume_percent": bg_volume,
        "modo": "cortes_prontos" if modo_cortes else "brutos",
        "status": "candidato_pendente_auditoria",
        "master_aprovado": False,
        "sha256": sha256(caminho_saida),
        "manifesto_sha256": sha256(pasta_njud / "manifesto_producao.json"),
        "data_edicao": manifesto["data_edicao"],
        "data_boletins": manifesto["data_boletins"],
        "versao": manifesto["versao"],
        "bg_aplicado_apenas_cabecas": True,
        "respiro_apos_corpo_ms": 120,
        "assets_sha256": {p.name: sha256(p) for p in DIR_ASSETS_VINHETAS_NJUD.iterdir() if p.is_file()},
    }
    meta_path = pasta_saida / f"{nome_arquivo[:-4]}_metadados.json"
    meta_path.write_text(json.dumps(metadados, indent=2, ensure_ascii=False), encoding="utf-8")

    return caminho_saida


def montar_todos(
    pasta_entrada: Path,
    pasta_saida: Path,
    roteiro_path: Optional[str] = None,
    njud_lista: Optional[list[str]] = None,
    logger=None,
) -> tuple[list[Path], list[str]]:
    """Monta todos os jornais NJUD encontrados em pasta_entrada.

    Args:
        pasta_entrada: JORNAIS_DIVIDIDOS (ou pasta de mês contendo NJUDs).
        pasta_saida: JORNAIS_FINAL.
        roteiro_path: roteiro opcional (modo bruto).
        njud_lista: lista opcional de números de NJUD para filtrar (senão, todos).
        logger: logger opcional.

    Returns:
        (montados, falhas) — Paths dos jornais montados e números de NJUD
        que falharam (peça pendente, vinheta ausente etc.).
    """
    if logger is None:
        logger = LogPipeline()

    etapa = "montagem_jornais_todos"
    pastas_njud = _listar_pastas_njud(pasta_entrada)

    if not pastas_njud:
        logger.warning(f"[{etapa}] Nenhuma pasta de NJUD encontrada em {pasta_entrada}")
        return [], []

    if njud_lista:
        filtro = set(njud_lista)
        pastas_njud = [p for p in pastas_njud if _extrair_numero_njud(p.name) in filtro]

    from njud.controle_producao import carregar_pares, validar_grade
    try:
        validar_grade([carregar_pares(p)[0] for p in pastas_njud])
    except (OSError, ValueError, KeyError) as exc:
        logger.error(f"[{etapa}] Grade/preparação inválida: {exc}")
        return [], [_extrair_numero_njud(p.name) or p.name for p in pastas_njud]

    logger.info(f"[{etapa}] {len(pastas_njud)} NJUD(s) candidato(s) em {pasta_entrada}")

    montados: list[Path] = []
    falhas: list[str] = []

    for pasta_njud in pastas_njud:
        numero = _extrair_numero_njud(pasta_njud.name) or pasta_njud.name
        resultado = montar_jornal(
            pasta_njud,
            pasta_saida,
            roteiro_path=roteiro_path,
            logger=logger,
        )
        if resultado is not None:
            montados.append(resultado)
        else:
            falhas.append(numero)

    logger.info(
        f"[{etapa}] Montagem concluída: {len(montados)} jornal(is) montado(s), "
        f"{len(falhas)} falha(s)/pendência(s)"
    )
    if falhas:
        logger.warning(f"[{etapa}] NJUDs não montados (peça pendente ou erro): {', '.join(falhas)}")

    return montados, falhas


# ===========================================================================
# CLI
# ===========================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monta jornais NJUD a partir de cortes CABEÇA/CORPO ou de MP3s brutos."
    )
    parser.add_argument(
        "pasta_entrada",
        nargs="?",
        type=Path,
        default=DIR_JORNAIS_DIVIDIDOS,
        help=f"Pasta com os NJUDs (cortes ou brutos) (default: {DIR_JORNAIS_DIVIDIDOS})",
    )
    parser.add_argument(
        "pasta_saida",
        nargs="?",
        type=Path,
        default=DIR_JORNAIS_FINAL,
        help=f"Pasta de saída dos jornais montados (default: {DIR_JORNAIS_FINAL})",
    )
    parser.add_argument(
        "--roteiro",
        default=None,
        help="Arquivo de roteiro (melhora a separação no modo bruto).",
    )
    parser.add_argument(
        "--njud",
        action="append",
        default=None,
        help="Número de NJUD a montar (pode repetir); default: todos os encontrados.",
    )
    parser.add_argument(
        "--sem-normalizar",
        action="store_true",
        help="Não aplica loudnorm no arquivo final.",
    )
    parser.add_argument(
        "--lufs",
        type=float,
        default=-16.0,
        help="Alvo de loudness (default: -16 LUFS).",
    )
    args = parser.parse_args()

    logger = LogPipeline(args.pasta_saida / "logs" if hasattr(args.pasta_saida, "__truediv__") else None)

    montados, falhas = montar_todos(
        args.pasta_entrada,
        args.pasta_saida,
        roteiro_path=args.roteiro,
        njud_lista=args.njud,
        logger=logger,
    )

    print(f"\nMontados: {len(montados)}")
    for m in montados:
        print(f"  {m}")
    if falhas:
        print(f"\nPendentes/falharam: {len(falhas)}")
        for f in falhas:
            print(f"  NJUD {f}")

    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
