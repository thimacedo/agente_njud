#!/usr/bin/env python3
"""
comparacao_versoes.py — Compara duas versões de um boletim e destaca diferenças.

Funcionalidades:
    1. transcrever_versao(audio_path) — Transcreve usando Whisper
    2. comparar_textos(texto_a, texto_b) — Compara semanticamente usando shared/avaliacao.py
    3. gerar_diff(v1, v2) — Gera diferença legível
    4. comparar_versoes(path_v1, path_v2) — Pipeline completo de comparação

Formato de retorno: dict com score_similaridade, diferencas (lista), versoes (dict).
"""
import difflib
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from shared.avaliacao import (
    ResultadoAvaliacao,
    avaliar_transcricao,
    calcular_similaridade_semantica,
    extrair_entidades,
)
from shared.text_utils import normalizar_texto
from shared.transcricao_cache import TranscricaoCache, calcular_hash_audio


# ═══════════════════════════════════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Diferenca:
    """Representa uma diferença entre duas versões."""
    tipo: str  # "adicao", "remocao", "alteracao"
    trecho_v1: str
    trecho_v2: str
    contexto: str = ""


@dataclass
class ResultadoComparacao:
    """Resultado completo da comparação entre duas versões."""
    score_similaridade: float
    score_sentido: float
    score_entidades: float
    score_literal: float
    score_final: float
    aprovado: bool
    diferencas: list = field(default_factory=list)
    versoes: dict = field(default_factory=dict)
    resumo: str = ""
    motivo: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Transcrição de versão
# ═══════════════════════════════════════════════════════════════════════════════

def transcrever_versao(
    audio_path: str | Path,
    modelo: str = "base",
    usar_cache: bool = True,
    cache: Optional[TranscricaoCache] = None,
) -> str:
    """
    Transcreve um arquivo de áudio usando Whisper.

    Utiliza cache de transcrição para evitar retranscrição de áudios idênticos.

    Args:
        audio_path: Caminho para o arquivo de áudio.
        modelo: Modelo Whisper a usar (tiny, base, small, medium, large).
        usar_cache: Se True, verifica cache antes de transcrever.
        cache: Instância de TranscricaoCache (cria uma se None).

    Returns:
        Texto transcrito do áudio.

    Raises:
        FileNotFoundError: Se o arquivo de áudio não existe.
        RuntimeError: Se whisper não está instalado.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")

    # Verificar cache
    if usar_cache:
        if cache is None:
            cache = TranscricaoCache()
        hash_audio = calcular_hash_audio(audio_path)
        segmentos = cache.obter(hash_audio)
        if segmentos is not None:
            return " ".join(seg.get("text", "").strip() for seg in segmentos)

    # Transcrever com Whisper
    try:
        import whisper
    except ImportError:
        raise RuntimeError(
            "whisper não instalado. Execute: pip install openai-whisper"
        )

    model = whisper.load_model(modelo)
    result = model.transcribe(str(audio_path), language="pt", fp16=False)

    texto = result["text"].strip()

    # Salvar no cache
    if usar_cache:
        if cache is None:
            cache = TranscricaoCache()
        hash_audio = calcular_hash_audio(audio_path)
        segmentos_cache = [
            {"start": 0, "end": 0, "text": texto}
        ]
        cache.salvar(hash_audio, segmentos_cache)

    return texto


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Comparação semântica de textos
# ═══════════════════════════════════════════════════════════════════════════════

def comparar_textos(texto_a: str, texto_b: str) -> ResultadoAvaliacao:
    """
    Compara semanticamente dois textos usando shared/avaliacao.py.

    Utiliza a função avaliar_transcricao() que avalia:
    - Sentido (semântica) com peso 50%
    - Entidades (nomes, valores, termos) com peso 30%
    - Cobertura literal com peso 20%

    Args:
        texto_a: Texto da versão 1 (referência/base).
        texto_b: Texto da versão 2 (a comparar).

    Returns:
        ResultadoAvaliacao com scores e decisão.
    """
    return avaliar_transcricao(texto_a, texto_b)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Geração de diff legível
# ═══════════════════════════════════════════════════════════════════════════════

def gerar_diff(v1: str, v2: str, contexto: int = 3) -> list[Diferenca]:
    """
    Gera diferença legível entre dois textos.

    Usa difflib.SequenceMatcher para identificar adições, remoções e alterações.

    Args:
        v1: Texto da versão 1.
        v2: Texto da versão 2.
        contexto: Número de palavras de contexto ao redor de cada diferença.

    Returns:
        Lista de objetos Diferenca com tipo, trechos e contexto.
    """
    palavras_v1 = normalizar_texto(v1).split()
    palavras_v2 = normalizar_texto(v2).split()

    matcher = difflib.SequenceMatcher(None, palavras_v1, palavras_v2)
    diferencas = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        trecho_v1 = " ".join(palavras_v1[i1:i2])
        trecho_v2 = " ".join(palavras_v2[j1:j2])

        # Contexto: palavras antes e depois
        ctx_start = max(0, i1 - contexto)
        ctx_end = min(len(palavras_v1), i2 + contexto)
        contexto_str = " ".join(palavras_v1[ctx_start:ctx_end])

        if tag == "replace":
            tipo = "alteracao"
        elif tag == "delete":
            tipo = "remocao"
        elif tag == "insert":
            tipo = "adicao"
        else:
            continue

        diferencas.append(Diferenca(
            tipo=tipo,
            trecho_v1=trecho_v1,
            trecho_v2=trecho_v2,
            contexto=contexto_str,
        ))

    return diferencas


def formatar_diff_texto(v1: str, v2: str) -> str:
    """
    Gera representação textual do diff (estilo unified diff).

    Args:
        v1: Texto da versão 1.
        v2: Texto da versão 2.

    Returns:
        String formatada com as diferenças.
    """
    linhas_v1 = v1.splitlines(keepends=True)
    linhas_v2 = v2.splitlines(keepends=True)

    diff = difflib.unified_diff(
        linhas_v1,
        linhas_v2,
        fromfile="versao_1",
        tofile="versao_2",
        lineterm="",
    )

    return "\n".join(diff)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Pipeline completo de comparação
# ═══════════════════════════════════════════════════════════════════════════════

def comparar_versoes(
    path_v1: str | Path,
    path_v2: str | Path,
    modelo_whisper: str = "base",
    usar_cache: bool = True,
) -> ResultadoComparacao:
    """
    Pipeline completo de comparação entre duas versões de boletim.

    Executa:
    1. Transcrição de ambas as versões (se forem áudios)
    2. Comparação semântica via shared/avaliacao.py
    3. Geração de diff legível

    Args:
        path_v1: Caminho para versão 1 (áudio ou .txt).
        path_v2: Caminho para versão 2 (áudio ou .txt).
        modelo_whisper: Modelo Whisper para transcrição.
        usar_cache: Se True, usa cache de transcrição.

    Returns:
        ResultadoComparacao com todos os scores, diferenças e resumo.
    """
    path_v1 = Path(path_v1)
    path_v2 = Path(path_v2)

    # Carregar textos (transcrever se áudio, ler se .txt)
    texto_v1 = _carregar_texto(path_v1, modelo_whisper, usar_cache)
    texto_v2 = _carregar_texto(path_v2, modelo_whisper, usar_cache)

    # Comparação semântica
    avaliacao = comparar_textos(texto_v1, texto_v2)

    # Diff legível
    diferencas = gerar_diff(texto_v1, texto_v2)

    # Resumo
    resumo = _gerar_resumo(avaliacao, diferencas)

    return ResultadoComparacao(
        score_similaridade=avaliacao.score_sentido,
        score_sentido=avaliacao.score_sentido,
        score_entidades=avaliacao.score_entidades,
        score_literal=avaliacao.score_literal,
        score_final=avaliacao.score_final,
        aprovado=avaliacao.aprovado,
        diferencas=diferencas,
        versoes={
            "v1": {
                "texto": texto_v1,
                "path": str(path_v1),
                "entidades": extrair_entidades(texto_v1),
            },
            "v2": {
                "texto": texto_v2,
                "path": str(path_v2),
                "entidades": extrair_entidades(texto_v2),
            },
        },
        resumo=resumo,
        motivo=avaliacao.motivo,
    )


def comparar_textos_diretos(
    texto_v1: str,
    texto_v2: str,
) -> ResultadoComparacao:
    """
    Compara diretamente dois textos (sem transcrição).

    Útil quando os textos já estão disponíveis.

    Args:
        texto_v1: Texto da versão 1.
        texto_v2: Texto da versão 2.

    Returns:
        ResultadoComparacao completo.
    """
    avaliacao = comparar_textos(texto_v1, texto_v2)
    diferencas = gerar_diff(texto_v1, texto_v2)
    resumo = _gerar_resumo(avaliacao, diferencas)

    return ResultadoComparacao(
        score_similaridade=avaliacao.score_sentido,
        score_sentido=avaliacao.score_sentido,
        score_entidades=avaliacao.score_entidades,
        score_literal=avaliacao.score_literal,
        score_final=avaliacao.score_final,
        aprovado=avaliacao.aprovado,
        diferencas=diferencas,
        versoes={
            "v1": {
                "texto": texto_v1,
                "path": None,
                "entidades": extrair_entidades(texto_v1),
            },
            "v2": {
                "texto": texto_v2,
                "path": None,
                "entidades": extrair_entidades(texto_v2),
            },
        },
        resumo=resumo,
        motivo=avaliacao.motivo,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers privados
# ═══════════════════════════════════════════════════════════════════════════════

def _carregar_texto(
    path: Path,
    modelo: str = "base",
    usar_cache: bool = True,
) -> str:
    """
    Carrega texto de um arquivo.

    Se for .txt, lê diretamente. Se for áudio, transcreve com Whisper.

    Args:
        path: Caminho do arquivo.
        modelo: Modelo Whisper (para áudios).
        usar_cache: Usar cache de transcrição.

    Returns:
        Texto carregado/transcrito.
    """
    if path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8").strip()
    else:
        return transcrever_versao(path, modelo=modelo, usar_cache=usar_cache)


def _gerar_resumo(avaliacao: ResultadoAvaliacao, diferencas: list[Diferenca]) -> str:
    """
    Gera resumo textual da comparação.

    Args:
        avaliacao: Resultado da avaliação semântica.
        diferencas: Lista de diferenças encontradas.

    Returns:
        String com resumo formatado.
    """
    linhas = []
    linhas.append(f"Score de similaridade: {avaliacao.score_sentido:.0%}")
    linhas.append(f"Score de entidades: {avaliacao.score_entidades:.0%}")
    linhas.append(f"Score literal: {avaliacao.score_literal:.0%}")
    linhas.append(f"Score final: {avaliacao.score_final:.0%}")
    linhas.append(f"Status: {'APROVADO' if avaliacao.aprovado else 'REPROVADO'}")
    linhas.append(f"Motivo: {avaliacao.motivo}")
    linhas.append(f"Diferenças encontradas: {len(diferencas)}")

    if diferencas:
        linhas.append("\nDetalhes das diferenças:")
        for i, diff in enumerate(diferencas, 1):
            linhas.append(f"  {i}. [{diff.tipo.upper()}]")
            if diff.trecho_v1:
                linhas.append(f"     V1: '{diff.trecho_v1}'")
            if diff.trecho_v2:
                linhas.append(f"     V2: '{diff.trecho_v2}'")

    return "\n".join(linhas)
