# coding: utf-8
"""
Transcrição e extração de notas do GIRO nas Comarcas.

Diferente do NJUD (que separa CABEÇA/CORPO), o GIRO trata cada nota
como unidade única (manchete+corpo em leitura contínua).

Fluxo:
    1. Transcrever boletim com faster-whisper
    2. Detectar notas individuais (vinheta de passagem ou silêncio)
    3. Para cada nota: aplicar filtro geográfico na transcrição
    4. Cortar áudio das notas aceitas
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import (
    LIMIAR_ANCORA_GIRO,
    LIMIAR_FIM_PASSAGEM_GIRO,
    LIMIAR_INICIO_FALA_GIRO,
    DIR_ASSETS_VINHETAS,
    VHT_PASSAGEM_GIRO_NOME,
)
from .filtro import ResultadoFiltro, filtrar_nota
from .log import get_logger, log_info, log_debug, log_aviso, log_erro

# Cache de transcrição (memória)
_CACHE_MEM: dict[str, tuple[list[dict], str]] = {}


# ===========================================================================
# ESTRUTURAS
# ===========================================================================


@dataclass
class NotaExtraida:
    """Uma nota individual extraída de um boletim."""
    idx: int  # índice sequencial no boletim
    texto: str  # texto completo da nota (manchete+corpo)
    inicio_seg: float  # timestamp de início (s)
    fim_seg: float  # timestamp de fim (s)
    segmentos: list[dict] = field(default_factory=list)  # segmentos whisper
    classificacao: Optional[ResultadoFiltro] = None
    aceita: bool = False


@dataclass
class BoletimProcessado:
    """Resultado do processamento de um boletim."""
    caminho: Path
    notas: list[NotaExtraida] = field(default_factory=list)
    transcricao_completa: str = ""
    duracao_s: float = 0.0
    erro: Optional[str] = None


# ===========================================================================
# TRANSCRIÇÃO
# ===========================================================================


def _carregar_cache_disco(caminho_str: str) -> Optional[tuple[list[dict], str]]:
    """Tenta carregar transcrição do cache em disco."""
    try:
        cache_dir = CACHE_TRANSCRICOES
        if not cache_dir.exists():
            return None
        h = hashlib.md5(caminho_str.encode()).hexdigest()
        cache_file = cache_dir / f"{h}.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return data["segmentos"], data["texto"]
    except Exception:
        pass
    return None


def _salvar_cache_disco(caminho_str: str, segmentos: list[dict], texto: str) -> None:
    """Salva transcrição no cache em disco."""
    try:
        cache_dir = CACHE_TRANSCRICOES
        cache_dir.mkdir(parents=True, exist_ok=True)
        h = hashlib.md5(caminho_str.encode()).hexdigest()
        cache_file = cache_dir / f"{h}.json"
        cache_file.write_text(
            json.dumps({"segmentos": segmentos, "texto": texto}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def transcrever_boletim(
    caminho_audio: Path,
    modelo=None,
    beam_size: int = 5,
) -> tuple[list[dict], str]:
    """Transcreve um boletim com faster-whisper.

    Args:
        caminho_audio: caminho do MP3 do boletim
        modelo: instância WhisperModel (se None, carrega automaticamente)
        beam_size: beam size do whisper

    Returns:
        (lista_segmentos, texto_completo)
    """
    caminho_str = str(caminho_audio)

    # Cache memória
    if caminho_str in _CACHE_MEM:
        return _CACHE_MEM[caminho_str]

    # Cache disco
    cache_disco = _carregar_cache_disco(caminho_str)
    if cache_disco is not None:
        _CACHE_MEM[caminho_str] = cache_disco
        return cache_disco

    # Carregar modelo se necessário
    if modelo is None:
        from faster_whisper import WhisperModel
        modelo = WhisperModel(MODELO_WHISPER, device="cpu", compute_type=COMPUTE_TYPE)

    t0 = time.time()
    log_info("transcricao", f"Iniciando transcrição: {caminho_str}")

    try:
        segments, info = modelo.transcribe(
            caminho_str,
            beam_size=beam_size,
            language="pt",
            condition_on_previous_text=False,
        )
    finally:
        # Liberar memória alocada pelo MKL/Intel Math Kernel Library
        import gc
        gc.collect()

    lista_segments = []
    for seg in segments:
        lista_segments.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
        })

    texto_completo = " ".join(seg["text"] for seg in lista_segments)
    duracao = info.duration
    tempo = time.time() - t0

    log_info(
        "transcricao",
        f"Transcrição concluída em {tempo:.1f}s — {duracao:.1f}s, "
        f"{len(lista_segments)} segmentos",
    )

    resultado = (lista_segments, texto_completo)
    _CACHE_MEM[caminho_str] = resultado
    _salvar_cache_disco(caminho_str, lista_segments, texto_completo)

    return resultado


# ===========================================================================
# DETECÇÃO DE NOTAS (separação por vinheta de passagem ou silêncio)
# ===========================================================================


def _detectar_notas_por_silencio(
    segmentos: list[dict],
    gap_min_s: float = 2.5,
) -> list[tuple[int, int]]:
    """Detecta notas por gaps de silêncio entre segmentos.

    No GIRO, cada nota é separada por uma vinheta de passagem (música).
    A vinheta gera um gap de silêncio na transcrição (sem texto).

    Args:
        segmentos: lista de segmentos whisper
        gap_min_s: gap mínimo (s) entre fim de um segmento e início do próximo
                   para considerar que é uma nova nota

    Returns:
        Lista de (idx_inicio, idx_fim) por nota
    """
    if not segmentos:
        return []

    notas = []
    inicio_nota = 0

    for i in range(1, len(segmentos)):
        gap = segmentos[i]["start"] - segmentos[i - 1]["end"]
        if gap >= gap_min_s:
            # Nova nota começa aqui
            notas.append((inicio_nota, i - 1))
            inicio_nota = i

    # Última nota
    notas.append((inicio_nota, len(segmentos) - 1))
    return notas


def _detectar_notas_por_assinatura(
    segmentos: list[dict],
) -> list[tuple[int, int]]:
    """Detecta notas por padrão de assinatura (LOC/OFF).

    Cada nota do boletim TJRN começa com uma assinatura padrão:
    "Tribunal de Justiça do Rio Grande do Norte [Nome do Locutor]"

    Args:
        segmentos: lista de segmentos whisper

    Returns:
        Lista de (idx_inicio, idx_fim) por nota
    """
    import re

    PADRAO_ASSINATURA = re.compile(
        r"tribunal de justi[çc]a do rio grande do norte",
        re.IGNORECASE,
    )

    notas = []
    inicio_nota = 0

    for i, seg in enumerate(segmentos):
        if i > 0 and PADRAO_ASSINATURA.search(seg["text"]):
            # Verificar se há conteúdo substancial após a assinatura
            # (pelo menos 10s de áudio até o fim — senão é só encerramento)
            durante_restante = segmentos[-1]["end"] - seg["start"]
            if durante_restante < 10.0:
                # Assinatura final do boletim — ignorar como nova nota
                continue
            notas.append((inicio_nota, i - 1))
            inicio_nota = i

    notas.append((inicio_nota, len(segmentos) - 1))
    return notas


def extrair_notas(
    segmentos: list[dict],
    texto_completo: str,
    metodo: str = "arquivo",
) -> list[NotaExtraida]:
    """Extrai notas individuais da transcrição de um boletim.

    Cada arquivo de boletim TJRN (B1, B2, B3...) já é uma nota individual.
    Não há necessidade de detectar limites internos — o arquivo inteiro é a nota.

    Args:
        segmentos: segmentos whisper
        texto_completo: texto completo da transcrição
        metodo: "arquivo" (padrão) — 1 nota por arquivo

    Returns:
        Lista com 1 NotaExtraida (o arquivo inteiro)
    """
    if not segmentos:
        return []

    return [NotaExtraida(
        idx=1,
        texto=texto_completo,
        inicio_seg=segmentos[0]["start"],
        fim_seg=segmentos[-1]["end"],
        segmentos=segmentos,
    )]


# ===========================================================================
# CORTE DE ÁUDIO
# ===========================================================================


def _encontrar_silencio(
    audio,
    pos_ms: int,
    janela_ms: int = 1500,
    silencio_min_ms: int = 120,
    limiar_dbfs: float = -38.0,
) -> Optional[int]:
    """Encontra o centro do silêncio mais próximo de pos_ms."""
    from pydub import AudioSegment

    inicio_janela = max(0, pos_ms - janela_ms)
    fim_janela = min(len(audio), pos_ms + janela_ms)
    if fim_janela - inicio_janela < silencio_min_ms:
        return None

    trecho = audio[inicio_janela:fim_janela]
    chunk_len = 20
    melhor = None
    melhor_dist = None
    run_start = None

    for i in range(0, len(trecho) - chunk_len, chunk_len):
        fatia = trecho[i:i + chunk_len]
        if fatia.dBFS < limiar_dbfs:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and (i - run_start) >= silencio_min_ms:
                centro = run_start + (i - run_start) // 2
                abs_centro = inicio_janela + centro
                dist = abs(abs_centro - pos_ms)
                if melhor_dist is None or dist < melhor_dist:
                    melhor = abs_centro
                    melhor_dist = dist
            run_start = None

    if run_start is not None and (len(trecho) - run_start) >= silencio_min_ms:
        centro = run_start + (len(trecho) - run_start) // 2
        abs_centro = inicio_janela + centro
        dist = abs(abs_centro - pos_ms)
        if melhor_dist is None or dist < melhor_dist:
            melhor = abs_centro

    return melhor


def cortar_nota(
    caminho_boletim: Path,
    caminho_saida: Path,
    inicio_s: float,
    fim_s: float,
    margem_inicio_s: float = 0.3,
    margem_fim_s: float = 0.5,
) -> bool:
    """Corta uma nota do boletim, ancorando bordas no silêncio.

    Args:
        caminho_boletim: MP3 do boletim original
        caminho_saida: MP3 de saída (nota isolada)
        inicio_s: timestamp de início da nota (s)
        fim_s: timestamp de fim da nota (s)
        margem_inicio_s: margem antes do início para cortar vinheta
        margem_fim_s: margem depois do fim para cortar vinheta

    Returns:
        True se cortou com sucesso
    """
    from pydub import AudioSegment

    try:
        audio = AudioSegment.from_file(str(caminho_boletim))
    except Exception as e:
        log_erro("corte", f"Falha ao carregar áudio: {e}")
        return False

    # Converter timestamps para ms
    inicio_ms = max(0, int((inicio_s - margem_inicio_s) * 1000))
    fim_ms = min(len(audio), int((fim_s + margem_fim_s) * 1000))

    # Ancorar em silêncio
    inicio_ancorado = _encontrar_silencio(audio, inicio_ms)
    fim_ancorado = _encontrar_silencio(audio, fim_ms)

    if inicio_ancorado is not None:
        inicio_ms = inicio_ancorado
    if fim_ancorado is not None:
        fim_ms = fim_ancorado

    if fim_ms <= inicio_ms:
        log_aviso("corte", f"Corte inválido: inicio={inicio_ms}ms, fim={fim_ms}ms")
        return False

    trecho = audio[inicio_ms:fim_ms]

    # Normalizar volume
    from pydub.effects import normalize
    trecho = normalize(trecho)

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    trecho.export(str(caminho_saida), format="mp3", bitrate="192k")

    duracao = len(trecho) / 1000
    log_debug("corte", f"Nota cortada: {caminho_saida.name} ({duracao:.1f}s)")
    return True


# ===========================================================================
# PIPELINE COMPLETO: transcreve → extrai → filtra → corta
# ===========================================================================


def processar_boletim(
    caminho_boletim: Path,
    mmss: str,
    idx_nota_global: int,
    pasta_saida: Path,
    evitar_natal: bool = True,
    metodo_deteccao: str = "assinatura",
    modelo=None,
) -> tuple[list[Path], int, object]:
    """Pipeline completo de processamento de um boletim.

    Args:
        caminho_boletim: MP3 do boletim
        mmss: código do programa (ex: "0804")
        idx_nota_global: contador global de notas (para numeração sequencial)
        pasta_saida: pasta onde salvar as notas cortadas
        evitar_natal: filtro de evitar Natal
        metodo_deteccao: "assinatura" ou "silencio"
        modelo: WhisperModel (opcional)

    Returns:
        (lista de Paths das notas aceitas, novo idx_nota_global, modelo_whisper)
    """
    logger = get_logger()
    log_info("pipeline", f"Processando boletim: {caminho_boletim.name}")

    # 1. Transcrever
    try:
        segmentos, texto_completo = transcrever_boletim(caminho_boletim, modelo)
    except Exception as e:
        log_erro("pipeline", f"Falha na transcrição: {e}")
        return [], idx_nota_global, modelo

    # 2. Extrair notas
    notas = extrair_notas(segmentos, texto_completo, metodo=metodo_deteccao)
    log_info("pipeline", f"  {len(notas)} notas detectadas no boletim")

    # 3. Filtrar e cortar
    notas_aceitas = []
    for nota in notas:
        rf = filtrar_nota(nota.texto, evitar_natal, logger=logger)
        nota.classificacao = rf

        if rf.aceita or rf.classificacao.value == "ACEITA":
            nota.aceita = True
            idx_nota_global += 1

            # Nome do arquivo de saída
            from .utils import nome_corte_nota
            from datetime import date

            # Extrair data do nome do boletim
            import re
            m_data = re.match(
                r"BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_",
                caminho_boletim.name,
            )
            if m_data:
                dia, mes, ano = m_data.groups()
                data_str = f"{dia}-{mes}-{ano[2:]}"
            else:
                data_str = date.today().strftime("%d-%m-%y")

            nome_arquivo = nome_corte_nota(mmss, idx_nota_global, data_str)
            caminho_saida = pasta_saida / nome_arquivo

            # Cortar áudio
            sucesso = cortar_nota(
                caminho_boletim,
                caminho_saida,
                nota.inicio_seg,
                nota.fim_seg,
            )
            if sucesso:
                notas_aceitas.append(caminho_saida)
                log_info(
                    "pipeline",
                    f"  Nota {idx_nota_global} ACEITA: {nome_arquivo} "
                    f"({rf.motivo})",
                )
            else:
                log_aviso("pipeline", f"  Falha no corte da nota {idx_nota_global}")
        else:
            log_debug(
                "pipeline",
                f"  Nota {nota.idx} FILTRADA: {rf.classificacao.value} "
                f"({rf.motivo})",
            )

    log_info(
        "pipeline",
        f"  Boletim processado: {len(notas_aceitas)}/{len(notas)} notas aceitas",
    )
    return notas_aceitas, idx_nota_global, modelo


# ===========================================================================
# LIMPEZA DE CACHE
# ===========================================================================


def limpar_cache_transcricoes() -> None:
    """Limpa o cache de transcrições em memória."""
    global _CACHE_MEM
    _CACHE_MEM.clear()
