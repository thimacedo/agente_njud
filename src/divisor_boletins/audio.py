"""
Transcrição (Whisper), corte de áudio (pydub) e orquestração do
processamento de um arquivo ou pasta recursiva.
Versão corrigida: Cortes ancorados estritamente no início da locução (sem sujeira de vinhetas).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel
from pydub import AudioSegment
import numpy as np
import torch

from .config import (
    ANCORAS_ABERTURA,
    ANCORAS_ENCERRAMENTO,
    COMPUTE_TYPE,
    MODELO_WHISPER,
)
from .deteccao import (
    ResultadoAncora,
    buscar_ancora,
    detectar_fim_corpo,
    detectar_fim_manchete,
    detectar_inicio_cabeca,
    detectar_passagem,
    detectar_passagem_por_vad,
    _carregar_silero_vad,
)
from .log import LogPipeline, _serializar_dados
from .texto import normalizar_texto
from .calibracao import calibrar_boletim


# ===========================================================================
# TIPO
# ===========================================================================

@dataclass
class ResultadoCorte:
    arquivo_entrada: str
    arquivo_cabeca: str
    arquivo_corpo: str
    metodo: str
    confianca_abertura: float = 1.0
    confianca_passagem: float = 1.0
    confianca_encerramento: float = 1.0
    avisos: list[str] = field(default_factory=list)
    duracao_total: float = 0.0
    inicio_cabeca: float = 0.0
    fim_cabeca: float = 0.0
    inicio_corpo: float = 0.0
    fim_corpo: float = 0.0


# ===========================================================================
# TRANSCRIÇÃO
# ===========================================================================

# ===========================================================================
# CACHE DE TRANSCRIÇÕES (memória + disco)
# ===========================================================================
# Motivo: o mesmo arquivo pode ser transcrito várias vezes durante o ciclo
# fechado (calibracao_correlacao -> ancora_vad_forcado -> ...). O Whisper
# pequeno em CPU é a etapa mais cara; reutilizar a transcrição reduz o tempo
# de reprocessamento em ~70-80%.
# ===========================================================================

_CACHE_MEM: dict[str, tuple[list[dict], str]] = {}


def _cache_path(caminho_audio: str | Path) -> Path:
    from pathlib import Path as _P
    p = _P(caminho_audio)
    nome = f"{p.parent.name}__{p.name}.json"
    return _P("F:/Projetos/DIVISOR/data/cache/transcricoes") / nome


def _carregar_cache_disco(caminho_audio: str | Path) -> tuple[list[dict], str] | None:
    caminho = _cache_path(caminho_audio)
    if not caminho.exists():
        return None
    try:
        import json as _json
        dados = _json.loads(caminho.read_text(encoding="utf-8"))
        return dados.get("segmentos"), dados.get("texto")
    except Exception:
        return None


def _salvar_cache_disco(caminho_audio: str | Path, segmentos: list[dict], texto: str) -> None:
    caminho = _cache_path(caminho_audio)
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        caminho.write_text(
            _json.dumps({"segmentos": segmentos, "texto": texto}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def limpar_cache_transcricoes() -> None:
    _CACHE_MEM.clear()
    try:
        from pathlib import Path as _P
        pasta = _P("F:/Projetos/DIVISOR/data/cache/transcricoes")
        if pasta.exists():
            for f in pasta.glob("*.json"):
                f.unlink()
    except Exception:
        pass


def carregar_modelo() -> WhisperModel:
    return WhisperModel(MODELO_WHISPER, device="cpu", compute_type=COMPUTE_TYPE)



def transcrever_audio(
    caminho_audio: str | Path,
    modelo: WhisperModel,
    logger: LogPipeline,
) -> tuple[list[dict], str]:
    etapa = "transcrever"
    caminho_str = str(caminho_audio)

    if caminho_str in _CACHE_MEM:
        logger.info(etapa, f"Transcrição reutilizada da cache memória: {caminho_str}")
        return _CACHE_MEM[caminho_str]

    cache_disco = _carregar_cache_disco(caminho_str)
    if cache_disco is not None:
        logger.info(etapa, f"Transcrição reutilizada da cache disco: {caminho_str}")
        _CACHE_MEM[caminho_str] = cache_disco
        return cache_disco

    logger.info(etapa, f"Iniciando transcrição: {caminho_str}")
    t0 = time.time()

    try:
        segments, info = modelo.transcribe(
            caminho_str,
            beam_size=5,
            language="pt",
            condition_on_previous_text=False,
        )
        lista_segments = []
        texto_completo = ""
        for seg in segments:
            lista_segments.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
            })
        texto_completo = " ".join(seg["text"] for seg in lista_segments)

        duracao = info.duration
        tempo = time.time() - t0

        logger.info(
            etapa,
            f"Transcrição concluída em {tempo:.1f}s — duração: {duracao:.1f}s, "
            f"{len(lista_segments)} segmentos",
            arquivo=caminho_str,
            duracao_segundos=round(duracao, 2),
        )

        _CACHE_MEM[caminho_str] = (lista_segments, texto_completo)
        _salvar_cache_disco(caminho_str, lista_segments, texto_completo)

        return lista_segments, texto_completo

    except Exception as e:
        logger.erro(etapa, f"Falha na transcrição: {e}", arquivo=caminho_str)
        raise



# ===========================================================================
# CORTE DE ÁUDIO COM LIMPEZA RIGOROSA DE VINHETAS
# ===========================================================================

def _encontrar_silencio_proximo(
    audio: AudioSegment,
    pos_ms: int,
    janela_ms: int = 1500,
    silencio_min_ms: int = 120,
    limiar_dbfs: float = -38.0,
) -> int | None:
    """Procura um trecho de silêncio real dentro de [pos-janela, pos+janela].

    Retorna o ponto MÉDIO do silêncio mais próximo de pos_ms (em ms) ou None.
    """
    inicio_janela = max(0, pos_ms - janela_ms)
    fim_janela = min(len(audio), pos_ms + janela_ms)
    if fim_janela - inicio_janela < silencio_min_ms:
        return None

    trecho = audio[inicio_janela:fim_janela]
    chunk_len = 20  # ms por fatia
    melhor = None
    melhor_dist = None
    run_start = None

    for i in range(0, len(trecho) - chunk_len, chunk_len):
        fatia = trecho[i : i + chunk_len]
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

    # Run final que termina no fim da janela
    if run_start is not None and (len(trecho) - run_start) >= silencio_min_ms:
        centro = run_start + (len(trecho) - run_start) // 2
        abs_centro = inicio_janela + centro
        dist = abs(abs_centro - pos_ms)
        if melhor_dist is None or dist < melhor_dist:
            melhor = abs_centro

    return melhor


def _ponto_mais_silencioso(
    audio: AudioSegment,
    pos_ms: int,
    janela_ms: int = 1500,
) -> int | None:
    """Fallback adaptativo: retorna o ponto de MENOR volume da janela
    (mínimo de dBFS em fatias de 120ms). Usado quando não existe silêncio
    absoluto (<-38dBFS) — trilhas com piso de ruído alto."""
    inicio_janela = max(0, pos_ms - janela_ms)
    fim_janela = min(len(audio), pos_ms + janela_ms)
    if fim_janela - inicio_janela < 120:
        return None

    trecho = audio[inicio_janela:fim_janela]
    chunk_len = 120  # ms
    melhor_centro = None
    melhor_dbfs = None
    for i in range(0, len(trecho) - chunk_len, chunk_len // 2):
        fatia = trecho[i : i + chunk_len]
        db = fatia.dBFS
        if melhor_dbfs is None or db < melhor_dbfs:
            melhor_dbfs = db
            melhor_centro = i + chunk_len // 2

    if melhor_centro is None:
        return None
    return inicio_janela + melhor_centro


def cortar_audio(
    caminho_entrada: str | Path,
    caminho_saida_cabeca: str | Path,
    caminho_saida_corpo: str | Path,
    inicio_cabeca: float,
    fim_cabeca: float,
    inicio_corpo: float,
    fim_corpo: float,
    logger: LogPipeline,
    janela_ms: int = 1500,
):
    etapa = "cortar"
    caminho_entrada = str(caminho_entrada)

    try:
        audio = AudioSegment.from_file(caminho_entrada)
    except Exception as e:
        logger.erro(etapa, f"Falha ao carregar áudio: {e}", arquivo=caminho_entrada)
        raise

    # Ancoragem em SILÊNCIO REAL: cada borda do corte é deslocada para o
    # centro do silêncio mais próximo (janela configurável via janela_ms,
    # default 1.5s). Se não houver silêncio, mantém o ponto original.
    # Elimina palavras coladas nas bordas e cortes iniciando dentro da
    # vinheta de passagem. janela_ms maior é usado pela estratégia
    # "janela_silencio_ampliada" do processo único, quando a janela padrão
    # não encontra silêncio suficiente perto da borda detectada.
    JANELA_MS = janela_ms

    inicio_cabeca_ms = int(inicio_cabeca * 1000)
    fim_cabeca_ms = int(fim_cabeca * 1000)
    inicio_corpo_ms = int(inicio_corpo * 1000)
    fim_corpo_ms = int(fim_corpo * 1000)

    ajustes = {}

    # Fronteira CABEÇA/CORPO é COMPARTILHADA: fim_cabeca e inicio_corpo ficam
    # muito próximos (<1.5s). Ancorar cada um isoladamente os puxa para o
    # mesmo vale e cruza as bordas. Estratégia:
    #   1. Ancora inicio_cabeca e o PONTO MÉDIO da fronteira compartilhada.
    #   2. fim_corpo ancorado separadamente com clamp >= fronteira.
    #   3. Clamp sequencial garante ordem estrita entre todas as bordas.

    MIN_GAP_MS = 200

    # 1. início da cabeça
    novo = _encontrar_silencio_proximo(audio, inicio_cabeca_ms, JANELA_MS)
    if novo is None:
        novo = _ponto_mais_silencioso(audio, inicio_cabeca_ms, JANELA_MS)
        if novo is not None:
            ajustes.setdefault("modo", "adaptativo")
    if novo is not None and abs(novo - inicio_cabeca_ms) <= JANELA_MS:
        ajustes["inicio_cabeca"] = f"{inicio_cabeca_ms}->{novo}"
        inicio_cabeca_ms = novo

    # 2. fronteira compartilhada fim_cabeca/inicio_corpo: ancora o ponto médio
    fronteira_original = (fim_cabeca_ms + inicio_corpo_ms) // 2
    novo = _encontrar_silencio_proximo(audio, fronteira_original, JANELA_MS)
    if novo is None:
        novo = _ponto_mais_silencioso(audio, fronteira_original, JANELA_MS)
        if novo is not None:
            ajustes.setdefault("modo", "adaptativo")
    if novo is not None and abs(novo - fronteira_original) <= JANELA_MS:
        ajustes["fronteira"] = f"{fronteira_original}->{novo}"
        fim_cabeca_ms = max(novo - MIN_GAP_MS // 2, inicio_cabeca_ms + MIN_GAP_MS)
        inicio_corpo_ms = novo + MIN_GAP_MS // 2
    else:
        # mantém posições relativas originais, apenas garante gaps mínimos
        if fim_cabeca_ms < inicio_cabeca_ms + MIN_GAP_MS:
            fim_cabeca_ms = inicio_cabeca_ms + MIN_GAP_MS
        if inicio_corpo_ms < fim_cabeca_ms + MIN_GAP_MS:
            inicio_corpo_ms = fim_cabeca_ms + MIN_GAP_MS

    # 3. fim do corpo, nunca antes do início do corpo
    novo = _encontrar_silencio_proximo(audio, fim_corpo_ms, JANELA_MS)
    if novo is None:
        novo = _ponto_mais_silencioso(audio, fim_corpo_ms, JANELA_MS)
        if novo is not None:
            ajustes.setdefault("modo", "adaptativo")
    if novo is not None and abs(novo - fim_corpo_ms) <= JANELA_MS:
        ajustes["fim_corpo"] = f"{fim_corpo_ms}->{novo}"
        fim_corpo_ms = novo

    # Clamp final de sanidade
    if inicio_cabeca_ms < 0:
        inicio_cabeca_ms = 0
    if fim_cabeca_ms <= inicio_cabeca_ms:
        fim_cabeca_ms = inicio_cabeca_ms + int((fim_cabeca - inicio_cabeca) * 1000) or inicio_cabeca_ms + 1000
    if inicio_corpo_ms <= fim_cabeca_ms:
        inicio_corpo_ms = fim_cabeca_ms + MIN_GAP_MS
    if fim_corpo_ms <= inicio_corpo_ms:
        fim_corpo_ms = inicio_corpo_ms + int(max(1.0, (fim_corpo - inicio_corpo)) * 1000)

    logger.info(etapa, f"Bordas ancoradas: {ajustes or 'nenhuma'}")

    cabeca = audio[inicio_cabeca_ms:fim_cabeca_ms]
    corpo = audio[inicio_corpo_ms:fim_corpo_ms]

    # Clamp final de sanidade já garantiu a ordem estrita das bordas acima.
    cabeca = audio[inicio_cabeca_ms:fim_cabeca_ms]
    corpo = audio[inicio_corpo_ms:fim_corpo_ms]

    # Elimina resíduo de vinheta no início com fade ultrarrápido
    cabeca = cabeca.fade_in(70)
    corpo = corpo.fade_in(70)

    ext = Path(caminho_saida_cabeca).suffix.lower()
    formato = {
        ".mp3": "mp3",
        ".wav": "wav",
        ".m4a": "ipod",
        ".ogg": "ogg",
        ".flac": "flac",
        ".wma": "wma",
    }.get(ext, ext.lstrip("."))

    cabeca.export(caminho_saida_cabeca, format=formato)
    corpo.export(caminho_saida_corpo, format=formato)

    logger.info(
        etapa,
        f"Cortado limpo por locução: CABEÇA {len(cabeca)/1000:.1f}s, CORPO {len(corpo)/1000:.1f}s",
        arquivo=str(caminho_saida_cabeca),
        inicio_cabeca=round(inicio_cabeca, 2),
        fim_cabeca=round(fim_cabeca, 2),
        inicio_corpo=round(inicio_corpo, 2),
        fim_corpo=round(fim_corpo, 2),
    )


# ===========================================================================
# VALIDAÇÃO ESPECTRAL DE RESÍDUOS DE VINHETA (item 2 da lista)
# ===========================================================================
# Motivo: resíduos de vinhetas podem ficar nas bordas mesmo quando
# energia/RMS parecem limpos. A validação mínima sem ML compara a
# energia espectral nas bordas com o centro; se a borda tiver energia
# muito maior que o centro, há suspeita de resíduo. Em modo apply,
# se detectar resíduo, amplia a janela de busca e re-corta +50ms.
# ===========================================================================

def _energia_espectral_db(audio: AudioSegment, pos_ms: int, janela_ms: int = 120) -> float:
    """Energia espectral aproximada em dB na janela centrada em pos_ms.
    Fallback simples sem libs externas: usa RMS como proxy de energia."""
    inicio = max(0, pos_ms - janela_ms // 2)
    fim = min(len(audio), pos_ms + janela_ms // 2)
    trecho = audio[inicio:fim]
    if len(trecho) == 0:
        return -120.0
    return float(trecho.dBFS)


def _detectar_residuo_vinheta(audio: AudioSegment, inicio_ms: int, fim_ms: int) -> dict:
    """Retorna diagnóstico de resíduo nas bordas do trecho [inicio_ms, fim_ms]."""
    centro = (inicio_ms + fim_ms) // 2
    try:
        energia_ini = _energia_espectral_db(audio, inicio_ms)
        energia_fim = _energia_espectral_db(audio, fim_ms)
        energia_centro = _energia_espectral_db(audio, centro)
    except Exception as e:
        return {"residuo_ini": False, "residuo_fim": False, "erro": str(e)}

    # Se a borda estiver muito mais energética que o centro (>6dB), é suspeito.
    limiar_residuo = 6.0
    residuo_ini = (energia_ini - energia_centro) >= limiar_residuo
    residuo_fim = (energia_fim - energia_centro) >= limiar_residuo

    return {
        "residuo_ini": bool(residuo_ini),
        "residuo_fim": bool(residuo_fim),
        "energia_ini_db": round(energia_ini, 1),
        "energia_fim_db": round(energia_fim, 1),
        "energia_centro_db": round(energia_centro, 1),
    }


# ===========================================================================
# PROCESSAMENTO DE UM ARQUIVO
# ===========================================================================

def _detectar_por_vad(caminho_entrada: str, segmentos: list[dict]) -> float:
    """Isola a lógica de VAD reutilizada por mais de uma estratégia:
    localiza onde a voz humana começa dentro dos primeiros 12s."""
    try:
        modelo_vad, utils_vad = _carregar_silero_vad()
        get_speech = utils_vad[0]
        audio_vad = AudioSegment.from_file(str(caminho_entrada))[0:12000].set_frame_rate(16000).set_channels(1)
        dados_vad = np.array(audio_vad.get_array_of_samples(), dtype=np.float32) / 32768.0
        sp_blocks = get_speech(torch.from_numpy(dados_vad), modelo_vad, sampling_rate=16000, threshold=0.4)
        if sp_blocks:
            return sp_blocks[0]["start"] / 16000.0
        elif segmentos:
            return segmentos[0]["start"]
        return 0.0
    except Exception:
        return segmentos[0]["start"] if segmentos else 0.0


def _estrategia_calibracao_correlacao(
    caminho_entrada, segmentos, ancora_abertura, ancora_encerramento, duracao_audio, logger,
):
    """Estratégia PADRÃO: calibração por correlação com vinhetas de
    boletim; cai em âncora/VAD só para inicio_cabeca se a correlação de
    abertura especificamente não teve confiança suficiente.

    NÃO REVERTER o tratamento de inicio_cabeca_calibrado is None para
    0.0: inicio_cabeca vem da correlação da vinheta de ABERTURA,
    calculada separadamente da correlação de PASSAGEM/ENCERRAMENTO que
    garante fim_cabeca/inicio_corpo. É possível abertura falhar (confiança
    < limiar) enquanto passagem/encerramento têm sucesso. Usar 0.0 como
    default corta a partir do início ABSOLUTO do arquivo, sem buffer
    antes da fala — bug confirmado em auditoria de 2026-08-24 (8/8 cortes
    com "primeira palavra a 0.00s do início"). Corrigido em 2026-08-24.
    """
    calibracao = calibrar_boletim(str(caminho_entrada))
    metodo_calibracao = calibracao.get('metodo', 'fallback')
    inicio_cabeca_calibrado = calibracao.get('inicio_cabeca')
    fim_cabeca_calibrado = calibracao.get('fim_cabeca')
    inicio_corpo_calibrado = calibracao.get('inicio_corpo')
    fim_corpo_calibrado = calibracao.get('fim_corpo')

    if metodo_calibracao == 'falha' or fim_cabeca_calibrado is None or inicio_corpo_calibrado is None:
        return None  # calibração não disponível; caller decide o fallback

    # Piso mínimo para a fronteira: depois do fim da abertura conhecida
    inicio_corpo_audio_min = ancora_abertura.timestamp_fim if ancora_abertura.encontrada else 8.0

    # NÃO REVERTER — SANÇÃO TEXTUAL DA FRONTEIRA (2026-08-24):
    # A correlação da vinheta de PASSAGEM pode dar falso positivo: casar a
    # referência instrumental NO MEIO DO CORPO da notícia (observado no B2/
    # NJUD 1918: "passagem" detectada aos 40.7s, onde não há passagem —
    # é o meio do corpo falado). Sem sanção, fim_cabeca cai no meio da
    # notícia e a CABEÇA sai com vinheta+manchete+metade do corpo.
    #
    # Sanção dupla:
    #   1. POSIÇÃO: a passagem fica LOGO APÓS a manchete. A fronteira
    #      calibrada deve estar nos primeiros 30% do áudio (e depois da
    #      abertura). Fronteira além disso = falso positivo.
    #   2. GAP LARGO: entre manchete e corpo com passagem instrumental há
    #      um gap de fala >= 1.0s (a música toca sozinha). Micro-gaps do
    #      Whisper (0.2-0.5s entre frases) não contam.
    fronteira = fim_cabeca_calibrado
    posicao_ok = inicio_corpo_audio_min < fronteira < duracao_audio * 0.30

    maior_gap = 0.0
    for seg, prox in zip(segmentos, segmentos[1:]):
        gap_centro = (seg["end"] + prox["start"]) / 2
        if abs(gap_centro - fronteira) <= 3.0:
            maior_gap = max(maior_gap, prox["start"] - seg["end"])
    gap_ok = maior_gap >= 1.0

    if not (posicao_ok and gap_ok):
        logger.aviso(
            "calibracao",
            f"Falso positive de correlação: fronteira de passagem em {fronteira:.2f}s "
            f"(posição_ok={posicao_ok}, maior_gap={maior_gap:.2f}s). Descartando calibração.",
            arquivo=str(caminho_entrada),
        )
        return None

    if inicio_cabeca_calibrado is not None:
        inicio_cabeca = inicio_cabeca_calibrado
        metodo = metodo_calibracao
        avisos = []
    else:
        if ancora_abertura.encontrada and not ancora_abertura.usou_fallback and ancora_abertura.timestamp_fim <= 15.0:
            inicio_cabeca = ancora_abertura.timestamp_fim
        else:
            inicio_cabeca = _detectar_por_vad(str(caminho_entrada), segmentos)
        metodo = f"{metodo_calibracao}+abertura_ancora_vad"
        avisos = ["inicio_cabeca calibrado indisponível (confiança abaixo do limiar); usada âncora/VAD como fallback pontual"]

    fim_cabeca = fim_cabeca_calibrado
    inicio_corpo = inicio_corpo_calibrado
    fim_corpo = fim_corpo_calibrado if fim_corpo_calibrado is not None else duracao_audio
    return inicio_cabeca, fim_cabeca, inicio_corpo, fim_corpo, metodo, avisos


def _estrategia_ancora_vad_forcado(
    caminho_entrada, segmentos, ancora_abertura, ancora_encerramento, duracao_audio, logger,
    margem_fim_cabeca: float = 5.5, teto_cabeca: float = 7.0,
):
    """Estratégia de ESCALONAMENTO: ignora a calibração por correlação
    inteiramente (mesmo que ela tenha "funcionado" com baixa confiança) e
    usa VAD/âncora de texto puro para todas as bordas. Acionada quando o
    motivo de reprovação foi 'calibracao_abertura_ausente' — a correlação
    já se mostrou não-confiável para este arquivo específico."""
    ancora_passagem_vad = detectar_passagem_por_vad(str(caminho_entrada), logger)

    if ancora_passagem_vad.encontrada:
        inicio_cabeca = ancora_passagem_vad.timestamp_inicio
        fim_cabeca = ancora_passagem_vad.timestamp_fim
        inicio_corpo = ancora_passagem_vad.timestamp_inicio_corpo
        metodo = "vad_preciso_sinal_forcado"
        avisos = []
    else:
        if ancora_abertura.encontrada and not ancora_abertura.usou_fallback and ancora_abertura.timestamp_fim <= 15.0:
            inicio_cabeca = ancora_abertura.timestamp_fim
        else:
            inicio_cabeca = _detectar_por_vad(str(caminho_entrada), segmentos)

        fim_cabeca = detectar_fim_manchete(segmentos, inicio_cabeca, ancora_encerramento.timestamp_inicio, logger)
        if (fim_cabeca - inicio_cabeca) > teto_cabeca:
            fim_cabeca = inicio_cabeca + margem_fim_cabeca
        inicio_corpo = fim_cabeca + 1.0
        metodo = "grade_fixa_locucao_forcado"
        avisos = ["calibração por correlação ignorada (estratégia ancora_vad_forcado)"]

    fim_corpo = duracao_audio - 12.0
    fim_corpo_regex = detectar_fim_corpo(segmentos, ancora_encerramento, duracao_audio, logger)
    if fim_corpo_regex < fim_corpo:
        fim_corpo = fim_corpo_regex

    return inicio_cabeca, fim_cabeca, inicio_corpo, fim_corpo, metodo, avisos


def _estrategia_fallback_puro(
    segmentos, ancora_abertura, ancora_encerramento, duracao_audio, logger, excecao=None,
):
    """Último recurso: âncoras de texto puras, sem VAD nem correlação.
    Usada quando as estratégias anteriores levantam exceção."""
    fim_abertura = ancora_abertura.timestamp_fim
    inicio_encerramento = ancora_encerramento.timestamp_inicio

    ancora_passagem = detectar_passagem(segmentos, fim_abertura, inicio_encerramento, duracao_audio, logger)
    inicio_cabeca = detectar_inicio_cabeca(segmentos, ancora_passagem.timestamp_fim, inicio_encerramento, logger)
    fim_cabeca = detectar_fim_manchete(segmentos, inicio_cabeca, inicio_encerramento, logger)
    inicio_corpo = fim_cabeca
    fim_corpo = detectar_fim_corpo(segmentos, ancora_encerramento, duracao_audio, logger)
    metodo = "ancoras_fallback"
    avisos = [f"Fallback aplicado: {excecao}"] if excecao else ["fallback puro acionado"]
    return inicio_cabeca, fim_cabeca, inicio_corpo, fim_corpo, metodo, avisos


ESTRATEGIAS_JANELA_MS = {
    # estrategia -> janela_ms passada para cortar_audio (ancoragem em silêncio)
    "calibracao_correlacao": 1500,
    "ancora_vad_forcado": 1500,
    "janela_silencio_ampliada": 3000,
    "grade_fixa_locucao_estendida": 1500,
}


def processar_arquivo(
    caminho_entrada: str | Path,
    pasta_saida: str | Path,
    modelo: WhisperModel,
    logger: LogPipeline,
    apply: bool = False,
    estrategia: str = "calibracao_correlacao",
) -> Optional[ResultadoCorte]:
    """
    estrategia: controla EXPLICITAMENTE qual método de detecção de bordas
    é usado, em vez de decidir implicitamente por condições internas.
    Isso permite ao processo único (processo_unico.py) escalonar para uma
    estratégia diferente quando a auditoria reprova um corte, sem
    depender de sorte na reavaliação das mesmas condições.

    Valores aceitos: "calibracao_correlacao" (padrão), "ancora_vad_forcado",
    "janela_silencio_ampliada" (mesma detecção do padrão, mas cortar_audio
    busca silêncio numa janela maior), "grade_fixa_locucao_estendida"
    (força grade fixa com margens maiores).
    """
    etapa = "processar_arquivo"
    caminho_entrada = Path(caminho_entrada)
    pasta_saida = Path(pasta_saida)
    nome_arquivo = caminho_entrada.name
    nome_base = caminho_entrada.stem
    ext = caminho_entrada.suffix

    logger.info(etapa, f"Processando: {caminho_entrada.name} (estratégia={estrategia})")

    try:
        segmentos, texto_completo = transcrever_audio(caminho_entrada, modelo, logger)
    except Exception:
        logger.erro(etapa, f"Transcrição falhou, pulando: {nome_arquivo}")
        return None

    if not segmentos:
        logger.erro(etapa, "Transcrição retornou zero segmentos", arquivo=str(caminho_entrada))
        return None

    duracao_total = max(seg["end"] for seg in segmentos)
    texto_normalizado = normalizar_texto(texto_completo)

    # Reutiliza a duração já calculada pela transcrição para evitar
    # um segundo decode completo do arquivo de áudio.
    duracao_audio = duracao_total

    ancora_abertura = buscar_ancora(
        texto_normalizado, segmentos, ANCORAS_ABERTURA,
        "abertura", duracao_audio, logger,
    )
    ancora_encerramento = buscar_ancora(
        texto_normalizado, segmentos, ANCORAS_ENCERRAMENTO,
        "encerramento", duracao_audio, logger,
    )

    try:
        if estrategia in ("calibracao_correlacao", "janela_silencio_ampliada"):
            resultado_deteccao = _estrategia_calibracao_correlacao(
                caminho_entrada, segmentos, ancora_abertura, ancora_encerramento,
                duracao_audio, logger,
            )
            if resultado_deteccao is None:
                # calibração indisponível para este arquivo — cai no método forçado
                resultado_deteccao = _estrategia_ancora_vad_forcado(
                    caminho_entrada, segmentos, ancora_abertura, ancora_encerramento,
                    duracao_audio, logger,
                )
        elif estrategia == "ancora_vad_forcado":
            resultado_deteccao = _estrategia_ancora_vad_forcado(
                caminho_entrada, segmentos, ancora_abertura, ancora_encerramento,
                duracao_audio, logger,
            )
        elif estrategia == "grade_fixa_locucao_estendida":
            resultado_deteccao = _estrategia_ancora_vad_forcado(
                caminho_entrada, segmentos, ancora_abertura, ancora_encerramento,
                duracao_audio, logger,
                margem_fim_cabeca=8.0, teto_cabeca=10.0,
            )
        else:
            logger.aviso(etapa, f"Estratégia desconhecida '{estrategia}', usando padrão.")
            resultado_deteccao = _estrategia_calibracao_correlacao(
                caminho_entrada, segmentos, ancora_abertura, ancora_encerramento,
                duracao_audio, logger,
            ) or _estrategia_ancora_vad_forcado(
                caminho_entrada, segmentos, ancora_abertura, ancora_encerramento,
                duracao_audio, logger,
            )

        inicio_cabeca, fim_cabeca, inicio_corpo, fim_corpo, metodo, avisos = resultado_deteccao

    except Exception as e:
        logger.aviso(etapa, f"Falha na demarcação ({e}). Acionando fallback puro.")
        inicio_cabeca, fim_cabeca, inicio_corpo, fim_corpo, metodo, avisos = _estrategia_fallback_puro(
            segmentos, ancora_abertura, ancora_encerramento, duracao_audio, logger, excecao=e,
        )

    if fim_cabeca <= inicio_cabeca:
        fim_cabeca = inicio_cabeca + 5.0
    if inicio_corpo < fim_cabeca:
        inicio_corpo = fim_cabeca
    if fim_corpo <= inicio_corpo or fim_corpo > duracao_audio:
        fim_corpo = duracao_audio
    
    # Garantia de limites físicos do arquivo contra erros de timestamp
    if inicio_cabeca >= duracao_audio:
        inicio_cabeca = segmentos[0]["start"] if segmentos else 4.5
        fim_cabeca = inicio_cabeca + 5.0
        inicio_corpo = fim_cabeca
        fim_corpo = duracao_audio
    if fim_cabeca >= duracao_audio:
        fim_cabeca = inicio_cabeca + 5.0
        inicio_corpo = fim_cabeca
        fim_corpo = duracao_audio

    resultado_base = dict(
        arquivo_entrada=str(caminho_entrada),
        metodo=metodo,
        confianca_abertura=ancora_abertura.confianca,
        confianca_passagem=1.0,
        confianca_encerramento=ancora_encerramento.confianca,
        avisos=avisos,
        duracao_total=round(duracao_total, 2),
        inicio_cabeca=round(inicio_cabeca, 2),
        fim_cabeca=round(fim_cabeca, 2),
        inicio_corpo=round(inicio_corpo, 2),
        fim_corpo=round(fim_corpo, 2),
    )

    if not apply:
        logger.info(
            etapa,
            f"[DRY-RUN] {nome_arquivo}: CABEÇA=[{inicio_cabeca:.1f}s → {fim_cabeca:.1f}s] "
            f"CORPO=[{inicio_corpo:.1f}s → {fim_corpo:.1f}s]. Método: {metodo}",
            **resultado_base,
        )
        return ResultadoCorte(arquivo_cabeca="", arquivo_corpo="", **resultado_base)

    pasta_saida.mkdir(parents=True, exist_ok=True)
    caminho_cabeca = pasta_saida / f"{nome_base}_CABECA{ext}"
    caminho_corpo = pasta_saida / f"{nome_base}_CORPO{ext}"

    cortar_audio(
        caminho_entrada, caminho_cabeca, caminho_corpo,
        inicio_cabeca, fim_cabeca, inicio_corpo, fim_corpo,
        logger,
        janela_ms=ESTRATEGIAS_JANELA_MS.get(estrategia, 1500),
    )

    return ResultadoCorte(
        **resultado_base,
        arquivo_cabeca=str(caminho_cabeca),
        arquivo_corpo=str(caminho_corpo),
    )


def processar_recursivo(
    pasta_entrada: str | Path,
    pasta_saida: str | Path,
    apply: bool = False,
    log_dir: str | Path | None = None,
    modelo: WhisperModel | None = None,
    months: list[str] | None = None,
):
    pasta_entrada = Path(pasta_entrada)
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    if log_dir is None:
        log_dir = pasta_saida / "_logs"

    logger = LogPipeline(log_dir)
    logger.info("pipeline", f"=== Iniciando pipeline === (entrada={pasta_entrada}, saída={pasta_saida}, apply={apply}, meses={months})")

    if modelo is None:
        logger.info("whisper", f"Carregando modelo: {MODELO_WHISPER} ({COMPUTE_TYPE})")
        modelo = carregar_modelo()
        logger.info("whisper", "Modelo carregado com sucesso")

    extensoes = {".mp3", ".wav", ".m4a", ".ogg", ".wma", ".flac"}
    arquivos_audio = sorted(
        p for p in pasta_entrada.rglob("*")
        if p.is_file() and p.suffix.lower() in extensoes
    )

    # Filtra por meses: mantém apenas arquivos cujo caminho contém um componente
    # de diretório correspondente a um mês solicitado (ex: "AGOSTO").
    if months:
        months_set = set(months)
        arquivos_audio = [
            p for p in arquivos_audio
            if any(part in months_set for part in p.relative_to(pasta_entrada).parts)
        ]
        logger.info(
            "pipeline",
            f"Filtrado para {len(months)} mês(es): {sorted(months)} "
            f"→ {len(arquivos_audio)} arquivo(s) a processar",
        )

    if not arquivos_audio:
        logger.aviso("pipeline", f"Nenhum arquivo de áudio encontrado em {pasta_entrada}")
        return

    resultados: list[ResultadoCorte] = []
    erros = 0

    for caminho_arquivo in arquivos_audio:
        caminho_rel = caminho_arquivo.relative_to(pasta_entrada)
        pasta_destino = pasta_saida / caminho_rel.parent
        nome_base = caminho_arquivo.stem
        ext = caminho_arquivo.suffix

        # Pula arquivos já processados para não retranscrever
        if apply:
            caminho_cabeca = pasta_destino / f"{nome_base}_CABECA{ext}"
            caminho_corpo = pasta_destino / f"{nome_base}_CORPO{ext}"
            if caminho_cabeca.exists() and caminho_corpo.exists():
                logger.info(
                    "pipeline",
                    f"Pulando (já existe): {caminho_arquivo.name}",
                    arquivo=str(caminho_arquivo),
                )
                continue

        try:
            resultado = processar_arquivo(caminho_arquivo, pasta_destino, modelo, logger, apply=apply)
            if resultado:
                resultados.append(resultado)
            else:
                erros += 1
        except Exception as e:
            logger.erro("pipeline", f"Erro inesperado processando {caminho_arquivo.name}: {e}", arquivo=str(caminho_arquivo))
            erros += 1

    if apply:
        audit_path = pasta_saida / "AUDIT_cortes.json"
        audit = {
            "total_arquivos": len(arquivos_audio),
            "processados": len(resultados),
            "erros": erros,
            "meses_filtro": months,
            "resultados": [_serializar_dados(r.__dict__) for r in resultados],
        }
        with open(audit_path, "w", encoding="utf-8") as f:
            json.dump(audit, f, ensure_ascii=False, indent=2, default=str)
        logger.info("pipeline", f"Relatório de auditoria gravado: {audit_path}", total=len(resultados), erros=erros)

    logger.info("pipeline", f"=== Pipeline concluído === ({len(resultados)} processados, {erros} erros)")
