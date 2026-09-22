#!/usr/bin/env python3
"""
Modulo de correcoes de alucinacoes do Whisper.

Estrategias:
1. Remocao de repeticoes (frases repetidas consecutivas)
2. Correcao via roteiro (quando disponivel): alinha texto transcrito com roteiro
   e substitui trechos alucinados pelo texto correto
3. Validacao de numeros (anos, valores) contra o roteiro
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional


def remover_repeticoes(segmentos: list[dict]) -> list[dict]:
    """
    Remove segmentos que sao repeticoes exatas ou quase-exatas de anteriores.
    Tambem remove frases curtas de "repeticao" tipicas de alucinacao do Whisper.
    """
    if not segmentos:
        return segmentos

    limiar_similaridade = 0.80
    segmentos_limpos = [segmentos[0]]

    for i in range(1, len(segmentos)):
        texto_atual = segmentos[i]["text"].strip().lower()
        texto_curto = len(texto_atual.split()) < 3

        if texto_curto:
            if not re.match(r'^[BM]\d', texto_atual, re.I):
                continue

        eh_repeticao = False
        for seg_anterior in segmentos_limpos[-5:]:
            texto_seg = seg_anterior["text"].strip().lower()
            if len(texto_seg.split()) < 3:
                continue
            sim_seg = SequenceMatcher(None, texto_atual, texto_seg).ratio()
            if sim_seg >= limiar_similaridade:
                eh_repeticao = True
                break

        PALAVRAS_CONTEXTO_LEGITIMO = ("direito", "arrependimento", "exercer")
        se_ja_visto_recente = "repete" in [s["text"].strip().lower() for s in segmentos_limpos[-3:]]
        if "repete" in texto_atual and not se_ja_visto_recente:
            if not any(p in texto_atual for p in PALAVRAS_CONTEXTO_LEGITIMO):
                eh_repeticao = True

        if not eh_repeticao:
            segmentos_limpos.append(segmentos[i])

    return segmentos_limpos


def normalizar_texto(texto: str) -> str:
    """Normaliza texto para comparacao — delega para shared.text_utils."""
    try:
        from shared.text_utils import normalizar_texto as _norm
        return _norm(texto)
    except ImportError:
        # Fallback se shared nao estiver no path
        import unicodedata
        if not texto:
            return ""
        texto = texto.lower()
        texto = unicodedata.normalize("NFD", texto)
        texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
        texto = re.sub(r"[^\w\s]", " ", texto)
        texto = re.sub(r"\s+", " ", texto).strip()
        return texto


def alinhar_com_roteiro(segmentos: list[dict], texto_roteiro: str) -> list[dict]:
    """
    Alinha os segmentos transcritos com o texto do roteiro.
    Substitui trechos alucinados pelo texto correto do roteiro.

    IMPORTANTE: nao sobrescreve seg["text"] com trechos do roteiro — isso
    contaminaria qualquer calculo de cobertura feito depois. Guardamos a
    hipotese de correcao em campos separados e deixamos o texto original
    intacto para fins de metricas.
    """
    if not texto_roteiro or not segmentos:
        return segmentos

    roteiro_norm = normalizar_texto(texto_roteiro)
    palavras_roteiro = set(roteiro_norm.split())

    segmentos_corrigidos = []
    for seg in segmentos:
        texto_norm = normalizar_texto(seg["text"])
        palavras_seg = set(texto_norm.split())

        if palavras_seg and palavras_roteiro:
            overlap = len(palavras_seg & palavras_roteiro) / len(palavras_seg)

            if overlap < 0.3 and len(texto_norm.split()) > 4:
                melhor_match = _encontrar_melhor_trecho(texto_norm, roteiro_norm)
                if melhor_match and melhor_match[1] > 0.5:
                    seg["texto_original"] = seg["text"]
                    seg["trecho_roteiro_sugerido"] = melhor_match[0]
                    seg["similaridade_sugestao"] = melhor_match[1]
                    seg["suspeita_alucinacao"] = True

        segmentos_corrigidos.append(seg)

    return segmentos_corrigidos


def _encontrar_melhor_trecho(texto: str, roteiro: str) -> Optional[tuple]:
    """Encontra o trecho mais similar no roteiro."""
    palavras = texto.split()
    if len(palavras) < 3:
        return None

    melhor_sim = 0.0
    melhor_trecho = ""

    janela = len(palavras)
    palavras_roteiro = roteiro.split()

    for i in range(len(palavras_roteiro) - janela + 1):
        trecho = " ".join(palavras_roteiro[i : i + janela])
        sim = SequenceMatcher(None, texto, trecho).ratio()
        if sim > melhor_sim:
            melhor_sim = sim
            melhor_trecho = trecho

    return (melhor_trecho, melhor_sim) if melhor_sim > 0.4 else None


def corrigir_numeros(segmentos: list[dict], texto_roteiro: str) -> list[dict]:
    """
    Corrige numeros especificos (anos) que o Whisper frequentemente alucina.

    Extrai APENAS anos do roteiro (4 digitos isolados), evitando misturar
    com valores monetarios.
    """
    if not texto_roteiro or not segmentos:
        return segmentos

    anos_roteiro = re.findall(r"(?<!\d)(?:19\d{2}|20\d{2})(?!\d)", texto_roteiro)
    anos_roteiro_set = set(anos_roteiro)

    segmentos_corrigidos = []
    for seg in segmentos:
        texto = seg["text"]
        anos = re.findall(r"\b(19\d{2}|20\d{2})\b", texto)
        for ano in anos:
            if ano not in anos_roteiro_set:
                candidatos = [
                    a for a in anos_roteiro_set if abs(int(ano) - int(a)) <= 50
                ]
                if len(candidatos) == 1:
                    texto = texto.replace(ano, candidatos[0])
                    seg["text_corrigido"] = texto

        seg["text"] = texto
        segmentos_corrigidos.append(seg)

    return segmentos_corrigidos


def corrigir_transcricao(segmentos: list[dict], texto_roteiro: Optional[str] = None) -> list[dict]:
    """
    Pipeline completo de correcao de alucinacoes.
    1. Remove repeticoes
    2. Se roteiro disponivel, alinha e corrige
    3. Corrige numeros
    """
    segmentos = remover_repeticoes(segmentos)
    if texto_roteiro:
        segmentos = alinhar_com_roteiro(segmentos, texto_roteiro)
        segmentos = corrigir_numeros(segmentos, texto_roteiro)
    return segmentos


if __name__ == "__main__":
    segmentos_teste = [
        {"start": 0.0, "end": 5.0, "text": "A Camara Criminal do TJRN manteve a decisao"},
        {"start": 5.0, "end": 10.0, "text": "que deixou de reconhecer falta grave de um apenado"},
        {"start": 10.0, "end": 15.0, "text": "Se reconhecer a pratica da falta grave, repete."},
        {"start": 15.0, "end": 20.0, "text": "Se reconhecer a pratica da falta grave."},
        {"start": 20.0, "end": 25.0, "text": "Para o Ministerio Publico, o rompimento do equipamento"},
        {"start": 25.0, "end": 30.0, "text": "ocorrido em marco de 2003 seria conduta equiparavel a fuga."},
    ]

    print("ANTES DA CORRECAO:")
    for seg in segmentos_teste:
        print(f"  [{seg['start']:5.1f}s] {seg['text']}")

    print("\nDEPOIS DA CORRECAO:")
    corrigidos = corrigir_transcricao(segmentos_teste)
    for seg in corrigidos:
        print(f"  [{seg['start']:5.1f}s] {seg['text']}")
