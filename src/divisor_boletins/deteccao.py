"""
Funções de detecção de marcas no áudio transcrito.

Detecta vinhetas de abertura/encerramento (por âncoras de texto),
música de passagem (por gaps de silêncio), fim da manchete e
assinatura do locutor.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import (
    ANCORAS_ABERTURA,
    ANCORAS_ENCERRAMENTO,
    DURACAO_MINIMA_PASSAGEM,
    JANELA_PASSAGEM_FIM,
    JANELA_PASSAGEM_INICIO,
    LIMIAR_ANCORA,
    LIMIAR_FIM_MANCHETE,
    LIMIAR_INICIO_CABECA,
    LIMIAR_SILENCIO_PASSAGEM,
    _PADRAO_ASSINATURA_NORMALIZADA,
)
from .log import LogPipeline
from .texto import normalizar_ancoras, normalizar_texto, similaridade

# ---------------------------------------------------------------------------
# Cache do Silero VAD para não recarregar o modelo a cada arquivo
# ---------------------------------------------------------------------------
_MODELO_VAD = None
_UTILS_VAD = None


def _carregar_silero_vad():
    global _MODELO_VAD, _UTILS_VAD
    if _MODELO_VAD is None:
        from torch.hub import load as torch_hub_load
        _MODELO_VAD, _UTILS_VAD = torch_hub_load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=True,
        )
    return _MODELO_VAD, _UTILS_VAD


# ===========================================================================
# TIPO
# ===========================================================================

@dataclass
class ResultadoAncora:
    encontrada: bool
    timestamp_inicio: float = 0.0
    timestamp_fim: float = 0.0
    confianca: float = 0.0
    texto_match: str = ""
    usou_fallback: bool = False
    timestamp_inicio_corpo: float = 0.0


# ===========================================================================
# BUSCA DE ÂNCORAS (ABERTURA / ENCERRAMENTO)
# ===========================================================================

def buscar_ancora(
    texto_normalizado: str,
    segmentos: list[dict],
    ancoras: list[str],
    tipo: str,
    duracao_total: float,
    logger: LogPipeline,
) -> ResultadoAncora:
    etapa = f"buscar_{tipo}"
    ancoras_norm = normalizar_ancoras(ancoras)

    textos_segmentos = []
    for seg in segmentos:
        tn = normalizar_texto(seg["text"])
        textos_segmentos.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": tn,
            "full": seg["text"],
        })

    if tipo == "encerramento":
        iter_segments = reversed(textos_segmentos)
    else:
        iter_segments = textos_segmentos

    # 1. Casamento direto por substring
    for ts in textos_segmentos:
        for ancora in ancoras_norm:
            if ancora in ts["text"]:
                logger.info(
                    etapa,
                    f"Âncora '{ancora}' encontrada (substring) "
                    f"no segmento t={ts['start']:.1f}s",
                )
                return ResultadoAncora(
                    encontrada=True,
                    timestamp_inicio=ts["start"],
                    timestamp_fim=ts["end"],
                    confianca=1.0,
                    texto_match=ts["full"],
                )

    # 2. Similaridade por segmento
    melhor_sim = 0.0
    melhor_seg = None
    melhor_ancora = ""

    for ts in iter_segments:
        for ancora in ancoras_norm:
            sim = similaridade(ts["text"], ancora)
            if sim > melhor_sim:
                melhor_sim = sim
                melhor_seg = ts
                melhor_ancora = ancora

    if melhor_seg is not None and melhor_sim >= LIMIAR_ANCORA:
        logger.info(
            etapa,
            f"Âncora '{melhor_ancora}' encontrada (similaridade={melhor_sim:.2f}) "
            f"no segmento t={melhor_seg['start']:.1f}s",
        )
        return ResultadoAncora(
            encontrada=True,
            timestamp_inicio=melhor_seg["start"],
            timestamp_fim=melhor_seg["end"],
            confianca=round(melhor_sim, 3),
            texto_match=melhor_seg["full"],
        )

    # 3. Fallback
    confianca_melhor = melhor_sim if melhor_seg else 0.0
    if tipo == "abertura":
        resultado = _fallback_abertura(
            duracao_total, segmentos, confianca_melhor, logger
        )
    else:
        resultado = _fallback_encerramento(
            duracao_total, segmentos, confianca_melhor, logger
        )

    logger.aviso(
        etapa,
        f"Âncora não encontrada — usando fallback proporcional "
        f"(confiança melhor={confianca_melhor:.2f} < limiar={LIMIAR_ANCORA}).",
    )
    return resultado


def _fallback_abertura(
    duracao_total: float,
    segmentos: list[dict],
    confianca_melhor: float,
    logger: LogPipeline,
) -> ResultadoAncora:
    if segmentos:
        fim = segmentos[0]["end"]
    else:
        fim = duracao_total * 0.12
    logger.aviso(
        "fallback_abertura",
        f"Fallback abertura usando fim do primeiro segmento: {fim:.1f}s",
    )
    return ResultadoAncora(
        encontrada=True,
        timestamp_fim=fim,
        confianca=confianca_melhor,
        usou_fallback=True,
    )


def _fallback_encerramento(
    duracao_total: float,
    segmentos: list[dict],
    confianca_melhor: float,
    logger: LogPipeline,
) -> ResultadoAncora:
    if segmentos:
        inicio = segmentos[-1]["start"]
    else:
        inicio = duracao_total * 0.88
    logger.aviso(
        "fallback_encerramento",
        f"Fallback encerramento usando início do último segmento: {inicio:.1f}s",
    )
    return ResultadoAncora(
        encontrada=True,
        timestamp_inicio=inicio,
        confianca=confianca_melhor,
        usou_fallback=True,
    )


# ===========================================================================
# DETECÇÃO DE PASSAGEM (MÚSICA INSTRUMENTAL — POR SILÊNCIO)
# ===========================================================================

def detectar_passagem(
    segmentos: list[dict],
    fim_abertura: float,
    inicio_encerramento: float,
    duracao_total: float,
    logger: LogPipeline,
) -> ResultadoAncora:
    """
    Detecta a música de passagem entre a abertura e a CABEÇA via gaps
    de silêncio entre segmentos de fala.
    """
    etapa = "buscar_passagem"

    gaps = []
    for i in range(len(segmentos) - 1):
        fim_seg = segmentos[i]["end"]
        inicio_prox = segmentos[i + 1]["start"]
        gap = inicio_prox - fim_seg
        if gap >= DURACAO_MINIMA_PASSAGEM:
            gaps.append({
                "fim_fala_anterior": fim_seg,
                "inicio_proxima_fala": inicio_prox,
                "duracao_gap": gap,
            })

    gaps_validos = [
        g for g in gaps
        if JANELA_PASSAGEM_INICIO <= g["fim_fala_anterior"] <= JANELA_PASSAGEM_FIM
    ]

    if gaps_validos:
        gap_maior = max(gaps_validos, key=lambda g: g["duracao_gap"])
        if gap_maior["duracao_gap"] >= LIMIAR_SILENCIO_PASSAGEM:
            logger.info(
                etapa,
                f"Passagem detectada por silêncio: gap={gap_maior['duracao_gap']:.1f}s "
                f"entre t={gap_maior['fim_fala_anterior']:.1f}s e "
                f"t={gap_maior['inicio_proxima_fala']:.1f}s",
            )
            return ResultadoAncora(
                encontrada=True,
                timestamp_inicio=gap_maior["fim_fala_anterior"],
                timestamp_fim=gap_maior["inicio_proxima_fala"],
                confianca=min(gap_maior["duracao_gap"] / 3.0, 1.0),
                usou_fallback=False,
            )

    if gaps:
        gap_maior = max(gaps, key=lambda g: g["duracao_gap"])
        logger.aviso(
            etapa,
            f"Passagem com gap menor que limiar; usando maior gap="
            f"{gap_maior['duracao_gap']:.1f}s "
            f"entre t={gap_maior['fim_fala_anterior']:.1f}s e "
            f"t={gap_maior['inicio_proxima_fala']:.1f}s",
        )
        return ResultadoAncora(
            encontrada=True,
            timestamp_inicio=gap_maior["fim_fala_anterior"],
            timestamp_fim=gap_maior["inicio_proxima_fala"],
            confianca=0.0,
            usou_fallback=True,
        )

    logger.aviso(etapa, "Nenhum gap encontrado; usando fallback fixo.")
    return ResultadoAncora(
        encontrada=True,
        timestamp_inicio=fim_abertura,
        timestamp_fim=fim_abertura + 2.0,
        confianca=0.0,
        usou_fallback=True,
    )


# ===========================================================================
# DETECÇÃO DE FIM DE MANCHETE / INÍCIO DE CABEÇA
# ===========================================================================

def detectar_fim_manchete(
    segmentos: list[dict],
    inicio_cabeca: float,
    fim_busca: float,
    logger: LogPipeline,
) -> float:
    """
    Fim da CABEÇA = primeiro ponto dentro da janela
    [inicio_cabeca, fim_busca] que tiver pontuação de fim de frase
    e/ou um gap grande de silêncio. Isso evita cortar manchete
    multipartida no meio de uma pausa pequena.
    """
    candidatos = [
        seg for seg in segmentos
        if seg["start"] >= inicio_cabeca - 0.2 and seg["end"] <= fim_busca + 0.5
    ]

    # 1. Pontuação forte como sinal primário de fim de manchete
    for seg in candidatos:
        texto = seg["text"].strip()
        if texto.endswith((".", "!", "?")):
            logger.info(
                "fim_manchete",
                f"Fim da manchete validado por pontuação em t={seg['end']:.1f}s",
            )
            return seg["end"]

    # 2. Gap grande como segundo sinal
    for i in range(len(candidatos) - 1):
        fim_seg = candidatos[i]["end"]
        inicio_prox = candidatos[i + 1]["start"]
        gap = inicio_prox - fim_seg
        if gap >= LIMIAR_FIM_MANCHETE:
            logger.info(
                "fim_manchete",
                f"Fim da manchete detectado no gap {gap:.1f}s em t={fim_seg:.1f}s",
            )
            return fim_seg

    # 3. Se os dois primeiros forem curtos e contínuos, trata como manchete
    #    multipartida e usa o fim do segundo segmento para evitar corte no meio
    if len(candidatos) >= 2:
        primeiro, segundo = candidatos[0], candidatos[1]
        gap = segundo["start"] - primeiro["end"]
        if (
            (primeiro["end"] - primeiro["start"]) < 10.0
            and (segundo["end"] - segundo["start"]) < 10.0
            and gap < 1.5
        ):
            logger.info(
                "fim_manchete",
                f"Manchete multipartida sem gap claro; "
                f"usando fim do segundo segmento t={segundo['end']:.1f}s",
            )
            return segundo["end"]

    # 4. Fallback final: primeiro candidato disponível
    for seg in candidatos:
        logger.aviso(
            "fim_manchete",
            f"Nenhum critério claro; usando fim do segmento t={seg['start']:.1f}s -> {seg['end']:.1f}s",
        )
        return seg["end"]

    logger.aviso(
        "fim_manchete",
        f"Nenhum segmento de fala encontrado para fim da manchete; "
        f"usando fallback {inicio_cabeca + 8.0:.1f}s",
    )
    return inicio_cabeca + 8.0


def detectar_inicio_cabeca(
    segmentos: list[dict],
    fim_passagem: float,
    fim_busca: float,
    logger: LogPipeline,
) -> float:
    """
    Início da CABEÇA = primeiro segmento de fala após a passagem,
    dentro da janela [fim_passagem, fim_busca].
    """
    for seg in segmentos:
        if seg["start"] >= fim_passagem - 0.2 and seg["start"] <= fim_busca + 0.5:
            logger.info(
                "inicio_cabeca",
                f"Início da cabeça detectado no segmento t={seg['start']:.1f}s",
            )
            return seg["start"]

    logger.aviso(
        "inicio_cabeca",
        f"Nenhum segmento de fala encontrado após passagem; "
        f"usando fallback {fim_passagem:.1f}s",
    )
    return fim_passagem


# ===========================================================================
# DETECÇÃO DE ASSINATURA NO FINAL DO CORPO
# ===========================================================================

def detectar_fim_corpo(
    segmentos: list[dict],
    ancora_encerramento: ResultadoAncora,
    duracao_total: float,
    logger: LogPipeline,
) -> float:
    """
    Remove a assinatura do locutor do final do CORPO.

    Estratégia:
    1. Regex da assinatura nos últimos segmentos, somente se houver
       vinheta de encerramento confirmada logo após.
    2. Se a âncora de encerramento foi detectada com confiança alta,
       usa o INÍCIO dela como fim do CORPO.
    3. Último recurso: início da âncora com margem de segurança.
    """
    inicio_enc = ancora_encerramento.timestamp_inicio

    # 1. Regex da assinatura, com confirmação por timing
    vinheta_enc_inicio = (
        inicio_enc if ancora_encerramento.encontrada else duracao_total
    )
    assinatura_confirmada = False
    for seg in reversed(segmentos):
        texto_norm = normalizar_texto(seg["text"])
        if _PADRAO_ASSINATURA_NORMALIZADA.search(texto_norm):
            distancia_ate_enc = vinheta_enc_inicio - seg["end"]
            if (
                distancia_ate_enc <= 3.0
                and seg["end"] <= vinheta_enc_inicio + 0.5
            ):
                logger.info(
                    "fim_corpo",
                    f"Assinatura confirmada por regex+timing no segmento "
                    f"t={seg['start']:.1f}s: '{seg['text'].strip()}' "
                    f"(distância até VH enc.: {distancia_ate_enc:.1f}s)",
                )
                assinatura_confirmada = True
                return seg["start"]
            logger.aviso(
                "fim_corpo",
                f"Match de assinatura em t={seg['start']:.1f}s descartado: "
                f"sem VH de encerramento confirmada logo após "
                f"(distância={distancia_ate_enc:.1f}s).",
            )
            break

    # 2. Âncora de encerramento confirmada — só usamos o início da âncora
    #    se a regex de assinatura não tiver confirmado corte exato antes.
    if not assinatura_confirmada:
        if ancora_encerramento.encontrada and not ancora_encerramento.usou_fallback:
            logger.info(
                "fim_corpo",
                f"Removendo encerramento do CORPO a partir de t={inicio_enc:.1f}s",
            )
            return inicio_enc

    # 3. Último recurso: margem reduzida sobre a âncora para não comer conteúdo
    margem = 0.5
    fim_corpo = max(inicio_enc - margem, 0.0)
    logger.aviso(
        "fim_corpo",
        f"Assinatura não confirmada por regex; cortando CORPO em "
        f"t={fim_corpo:.1f}s com margem {margem}s",
    )
    return fim_corpo


# ===========================================================================
# DETECÇÃO DE PASSAGEM POR SILERO VAD (camada de áudio)
# ===========================================================================

def detectar_passagem_por_vad(
    caminho_audio: str,
    logger: LogPipeline,
) -> ResultadoAncora:
    """
    Detecta a vinheta de passagem usando Silero VAD.

    Em vez de confiar apenas em gaps de texto/silêncio, analisa a onda de
    áudio e identifica com precisão onde a voz humana começa/termina.
    Em uma janela esperada, procura o trecho sem voz entre dois blocos
    de fala — esse buraco é a passagem instrumental.
    """
    etapa = "buscar_passagem_vad"

    try:
        modelo, utils = _carregar_silero_vad()
        get_speech_timestamps = utils[0]

        from pydub import AudioSegment
        import numpy as np
        import torch

        audio = AudioSegment.from_file(caminho_audio).set_frame_rate(16000).set_channels(1)
        inicio_ms = int(JANELA_PASSAGEM_INICIO * 1000)
        fim_ms = int(JANELA_PASSAGEM_FIM * 1000)
        trecho = audio[inicio_ms:fim_ms]

        dados = np.array(trecho.get_array_of_samples(), dtype=np.float32) / 32768.0
        tensor_audio = torch.from_numpy(dados)

        fala_blocos = get_speech_timestamps(
            tensor_audio,
            modelo,
            sampling_rate=16000,
            threshold=0.4,
            min_speech_duration_ms=200,
        )

        logger.info(
            etapa,
            f"VAD blocos encontrados na janela {JANELA_PASSAGEM_INICIO}s-"
            f"{JANELA_PASSAGEM_FIM}s: {len(fala_blocos)}",
        )

        if len(fala_blocos) >= 2:
            # CORREÇÃO 2026-08-24: o primeiro gap grande da janela pode ser
            # apenas o intervalo VINHETA → MANCHETE (não uma passagem).
            # Nesse caso o desenho correto é:
            #   [vinheta][gap][MANCHETE=bloco1][passagem?][CORPO=bloco2]
            # e a CABEÇA é o PRIMEIRO bloco de fala APÓS a vinheta.
            #
            # Heurística: se o primeiro bloco da janela termina antes de
            # JANELA_PASSAGEM_INICIO + ~2s (ou seja, colado no começo da
            # janela), ele provavelmente é o RABO DA VINHETA, não a
            # manchete — então a manchete é o bloco seguinte, e o gap
            # relevante é o DEPOIS dela.
            offset_s = JANELA_PASSAGEM_INICIO
            b0_fim_abs = offset_s + fala_blocos[0]["end"] / 16000.0
            b0_inicio_abs = offset_s + fala_blocos[0]["start"] / 16000.0

            if b0_fim_abs <= JANELA_PASSAGEM_INICIO + 2.5 and len(fala_blocos) >= 3:
                # bloco 0 = rabo da vinheta; manchete = bloco 1; corpo = bloco 2
                manchete = fala_blocos[1]
                corpo = fala_blocos[2]
                timestamp_inicio_cabeca = offset_s + manchete["start"] / 16000.0
                timestamp_fim_cabeca = offset_s + manchete["end"] / 16000.0
                timestamp_inicio_corpo = offset_s + corpo["start"] / 16000.0
                duracao_efeito = timestamp_inicio_corpo - timestamp_fim_cabeca

                logger.info(
                    etapa,
                    f"Bloco inicial identificado como rabo da vinheta "
                    f"(termina em {b0_fim_abs:.2f}s). Manchete="
                    f"[{timestamp_inicio_cabeca:.2f}→{timestamp_fim_cabeca:.2f}]s; "
                    f"passagem={duracao_efeito:.2f}s até {timestamp_inicio_corpo:.2f}s",
                )

                return ResultadoAncora(
                    encontrada=True,
                    timestamp_inicio=timestamp_inicio_cabeca,
                    timestamp_fim=timestamp_fim_cabeca,
                    timestamp_inicio_corpo=timestamp_inicio_corpo,
                    confianca=0.95,
                    usou_fallback=False,
                )

            # Comportamento original: bloco 0 já é a manchete
            fim_fala_1_rel = fala_blocos[0]["end"] / 16000.0
            inicio_fala_2_rel = fala_blocos[1]["start"] / 16000.0

            timestamp_inicio_cabeca = JANELA_PASSAGEM_INICIO + fala_blocos[0]["start"] / 16000.0
            timestamp_fim_cabeca = JANELA_PASSAGEM_INICIO + fim_fala_1_rel
            timestamp_inicio_corpo = JANELA_PASSAGEM_INICIO + inicio_fala_2_rel
            duracao_efeito = timestamp_inicio_corpo - timestamp_fim_cabeca

            logger.info(
                etapa,
                f"Passagem isolada via VAD: {duracao_efeito:.2f}s de não-fala "
                f"entre t={timestamp_fim_cabeca:.2f}s e t={timestamp_inicio_corpo:.2f}s",
            )

            return ResultadoAncora(
                encontrada=True,
                timestamp_inicio=timestamp_inicio_cabeca,
                timestamp_fim=timestamp_fim_cabeca,
                timestamp_inicio_corpo=timestamp_inicio_corpo,
                confianca=1.0,
                usou_fallback=False,
            )

        if fala_blocos:
            logger.aviso(
                etapa,
                f"VAD encontrou apenas 1 bloco na janela; "
                f"rejeitando VAD e caindo para fallback de texto."
            )
            return ResultadoAncora(encontrada=False)

        logger.aviso(
            etapa,
            f"VAD não encontrou blocos de fala na janela "
            f"{JANELA_PASSAGEM_INICIO}s-{JANELA_PASSAGEM_FIM}s; "
            f"blocos encontrados={len(fala_blocos)}",
        )
        return ResultadoAncora(encontrada=False)

    except Exception as e:
        logger.aviso(etapa, f"Falha ao rodar Silero VAD ({e}).")
        return ResultadoAncora(encontrada=False)
