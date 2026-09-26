from __future__ import annotations

"""Detecção de pontos de ancoragem para corte de boletim.

O doc ARQUITETURA_REAL.md descreve:
    → buscar_ancora() [divisor_boletins/deteccao.py]

E o DECISOES.md afirma que `_carregar_silero_vad` está definida e exportada
por este módulo.

Este mínimo agrupa:
    - buscar_ancora(): calcula um ponto de ancoragem a partir do áudio.
    - _carregar_silero_vad(): carregador opcional do Silero VAD (se disponível).
    - LIMIAR_CORRELACAO: exporte a constante do módulo legado de detecção
      espectral, para compatibilidade com quem importa de deteccao.py.
"""

import re
import unicodedata
from typing import Any, Optional

LIMIAR_CORRELACAO = 0.6  # compatível com deteccao_vinheta_espectral.LIMIAR_CORRELACAO

# Padrão da assinatura institucional de encerramento (comum a NJUD/GIRO):
# "Tribunal de Justiça do Rio Grande do Norte[, para a Rádio Justiça] <Nome>"
# no fim do texto acumulado. Institucional/estrutural — não é dado de
# instância (não hardcoda nomes de locutor).
_PADRAO_ASSINATURA = re.compile(
    r"tribunal de justi[çc]a do rio grande do norte"
    r"(?:\s+para a\s+radio justi[çc]a)?"
    r"[\s,]+[a-z]+(?:\s+[a-z]+)*\s*$",
    flags=re.IGNORECASE,
)


def _normalizar(texto: str) -> str:
    """Minúsculas, sem acento, sem pontuação — para casar o padrão de assinatura."""
    t = texto.lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _carregar_silero_vad(modelo_nome: str = "silero_vad") -> Any:
    """Carrega o Silero VAD se disponível; caso contrário retorna None.

    Este mínimo não depende de silero_vad instalado — quem usar deve garantir
    a dependência. Retorna um objeto compatível com a API esperada ou None.
    """
    try:
        import silero_vad  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        return silero_vad.load(model_name=modelo_nome)
    except Exception:
        return None


def buscar_ancora(
    audio: Any,
    *,
    segmentos: Optional[list[dict[str, Any]]] = None,
    temperatura: float = 0.0,
    duracao_vinheta_s: float = 0.0,
    texto_inicio: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Busca o instante em que começa a assinatura de encerramento do boletim.

    Este é o limite superior do CORPO em cortar_audio() (tempo_assinatura_inicio_s):
    o corpo vai do fim da cabeça até aqui; se não detectado, cai para o fim
    do áudio (retorna 'tempo_ancora_s': None, e cortar_audio() interpreta
    None como "vai até o fim").

    Detecção: varre os segmentos transcritos (com timestamp) de trás para
    frente, acumulando texto, até o acumulado bater com o padrão da
    assinatura institucional de encerramento. O tempo de início desse
    segmento é o instante retornado.

    Args:
        audio: objeto com len() em ms (ex.: AudioSegment).
        segmentos: lista de dicts {'start': float, 'end': float, 'text': str}
            vindos da transcrição (ex.: transcrever_audio(..., retornar_segmentos=True)).
            Sem segmentos, não há como localizar a assinatura no tempo.
        temperatura: não utilizado.
        duracao_vinheta_s: não usado para ancoragem de fim (mantido apenas
            por compatibilidade de assinatura de função).
        texto_inicio: não usado aqui (assinatura fica no FIM, não no início).

    Returns:
        dict com 'tempo_ancora_s' (float ou None), 'total_s' e 'metodo'.
    """
    try:
        total_ms = len(audio)
    except TypeError:
        total_ms = 0
    total_s = total_ms / 1000.0

    tempo_ancora_s: Optional[float] = None
    metodo = "nao_detectado"

    if segmentos:
        texto_acumulado = ""
        for seg in reversed(segmentos):
            texto_seg = _normalizar(str(seg.get("text", "")))
            texto_acumulado = f"{texto_seg} {texto_acumulado}".strip()
            if _PADRAO_ASSINATURA.search(texto_acumulado):
                tempo_ancora_s = float(seg.get("start", 0.0))
                metodo = "assinatura_regex"
                break

    return {
        "tempo_ancora_s": tempo_ancora_s,
        "total_s": total_s,
        "metodo": metodo,
    }
