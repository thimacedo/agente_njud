"""
core/decisao/analisador.py

Decide COMO processar um áudio a partir do próprio áudio, não de um
valor fixo em config/planejamento_2026/*.json. Substitui gradualmente
os campos `usar_separacao_stems` / estratégia fixa de ConfigPrograma.

Compatibilidade: enquanto a migração está em curso, o Analisador pode
ser chamado com `snapshot_kb=None` (ainda funciona, cai na heurística
padrão) — nenhuma dependência circular ou trava por falta de dado.

Uso alvo dentro de core/processamento/processar_boletim.py:

    plano = decidir_estrategia(
        caminho_audio=Path(arquivo),
        programa=config.nome,
        kb=knowledge_base,          # opcional
        tentativas_anteriores=estado.tentativas,  # já existe em EstadoArquivo
    )
    # plano.usar_stems, plano.estrategia_sugerida, plano.justificativa
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

from core.aprendizado.knowledge_base import KnowledgeBase, EstatisticaEstrategia

ESTRATEGIAS_DISPONIVEIS = [
    "calibracao_correlacao",
    "ancora_vad_forcado",
    "janela_silencio_ampliada",
    "grade_fixa_locucao_estendida",
]


@dataclass
class FeaturesAudio:
    duracao_s: float
    energia_media_inicio_db: float  # primeiros 3s
    energia_media_fim_db: float     # últimos 3s
    proporcao_silencio_inicio: float  # 0-1, quanto do início é silêncio/baixa energia


@dataclass
class PlanoDeProcessamento:
    usar_stems: bool
    estrategia_sugerida: str
    justificativa: str
    features: FeaturesAudio


def extrair_features(caminho_audio: Path) -> FeaturesAudio:
    """
    Extrai características objetivas do áudio. Não decide nada — só mede.
    Mantido separado da decisão para poder ser testado isoladamente e
    para poder evoluir (ex: trocar por análise espectral mais sofisticada)
    sem tocar na lógica de decisão.
    """
    audio = AudioSegment.from_file(str(caminho_audio))
    duracao_s = len(audio) / 1000.0

    janela_ms = min(3000, len(audio))
    inicio = audio[:janela_ms]
    fim = audio[-janela_ms:]

    energia_inicio = inicio.dBFS if inicio.dBFS != float("-inf") else -90.0
    energia_fim = fim.dBFS if fim.dBFS != float("-inf") else -90.0

    # proporção do início considerada "silêncio" (limiar relativo, não fixo
    # em segundos — adapta-se ao próprio nível de ruído do arquivo)
    limiar_silencio_db = audio.dBFS - 12  # 12dB abaixo da média do arquivo inteiro
    passo_ms = 250
    passos_silenciosos = 0
    total_passos = max(1, janela_ms // passo_ms)
    for offset in range(0, janela_ms, passo_ms):
        trecho = audio[offset:offset + passo_ms]
        nivel = trecho.dBFS if trecho.dBFS != float("-inf") else -90.0
        if nivel < limiar_silencio_db:
            passos_silenciosos += 1
    proporcao_silencio_inicio = passos_silenciosos / total_passos

    return FeaturesAudio(
        duracao_s=duracao_s,
        energia_media_inicio_db=energia_inicio,
        energia_media_fim_db=energia_fim,
        proporcao_silencio_inicio=proporcao_silencio_inicio,
    )


def _melhor_estrategia_por_historico(
    stats: list[EstatisticaEstrategia],
    ja_tentadas: set[str],
) -> Optional[tuple[str, float]]:
    """Escolhe a estratégia (ainda não tentada) com maior taxa de sucesso histórica."""
    candidatas = [s for s in stats if s.estrategia not in ja_tentadas and s.total >= 5]
    if not candidatas:
        return None
    melhor = max(candidatas, key=lambda s: s.taxa_sucesso)
    return melhor.estrategia, melhor.taxa_sucesso


def decidir_estrategia(
    caminho_audio: Path,
    programa: str,
    kb: Optional[KnowledgeBase] = None,
    tentativas_anteriores: Optional[list[dict]] = None,
) -> PlanoDeProcessamento:
    """
    Decisão adaptativa por arquivo. Nunca falha por falta de KB — sempre
    tem uma heurística de fallback determinística.
    """
    features = extrair_features(caminho_audio)
    ja_tentadas = {t.get("estrategia") for t in (tentativas_anteriores or [])}

    # --- Decisão de stems: heurística baseada no próprio áudio, não em flag fixa.
    # Áudio com pouco silêncio detectável no início (energia alta e estável)
    # tem mais chance de ter vinheta/trilha colada — Demucs ajuda mais aqui.
    usar_stems = features.proporcao_silencio_inicio < 0.15 and features.energia_media_inicio_db > -30
    justificativa_stems = (
        f"proporcao_silencio_inicio={features.proporcao_silencio_inicio:.2f}, "
        f"energia_inicio={features.energia_media_inicio_db:.1f}dB -> "
        f"{'stems recomendado' if usar_stems else 'stems dispensável'}"
    )

    # --- Decisão de estratégia de corte: histórico da KB primeiro, heurística depois.
    snapshot = kb.snapshot_estrategias(programa) if kb is not None else []
    escolha_kb = _melhor_estrategia_por_historico(snapshot, ja_tentadas)

    if escolha_kb is not None:
        estrategia, taxa = escolha_kb
        justificativa = (
            f"{justificativa_stems}; estratégia '{estrategia}' escolhida pela KB "
            f"(taxa de sucesso histórica {taxa:.0%} para o programa '{programa}')"
        )
    else:
        # Heurística padrão determinística (idêntica à ordem já usada hoje),
        # usada quando não há dado suficiente na KB — nunca trava o sistema.
        restantes = [e for e in ESTRATEGIAS_DISPONIVEIS if e not in ja_tentadas]
        estrategia = restantes[0] if restantes else ESTRATEGIAS_DISPONIVEIS[-1]
        justificativa = f"{justificativa_stems}; sem histórico suficiente na KB, usando ordem padrão ({estrategia})"

    return PlanoDeProcessamento(
        usar_stems=usar_stems,
        estrategia_sugerida=estrategia,
        justificativa=justificativa,
        features=features,
    )
