#!/usr/bin/env python3
"""
Módulo de correção de alucinações do Whisper.

Estratégias:
1. Remoção de repetições (frases repetidas consecutivas)
2. Correção via roteiro (quando disponível): alinha texto transcrito com roteiro
   e substitui trechos alucinados pelo texto correto
3. Validação de números (anos, valores) contra o roteiro
"""

import re
from difflib import SequenceMatcher
from typing import Optional


def remover_repeticoes(segmentos: list[dict]) -> list[dict]:
    """
    Remove segmentos que são repetições exatas ou quase-exatas de anteriores.
    Também remove frases curtas de "repetição" típicas de alucinação do Whisper.
    """
    if not segmentos:
        return segmentos

    limiar_similaridade = 0.80  # similaridade para considerar repetição
    segmentos_limpos = [segmentos[0]]

    for i in range(1, len(segmentos)):
        texto_atual = segmentos[i]["text"].strip().lower()
        texto_curto = len(texto_atual.split()) < 3

        # Ignorar segmentos muito curtos (<3 palavras) que não sejam significativos
        if texto_curto:
            # Mas manter se é uma claquete (B1, M2, etc)
            if not re.match(r'^[BM]\d', texto_atual, re.I):
                continue

        # Verificar se é repetição de qualquer dos últimos 5 segmentos
        eh_repeticao = False
        for seg_anterior in segmentos_limpos[-5:]:
            texto_seg = seg_anterior["text"].strip().lower()
            if len(texto_seg.split()) < 3:
                continue
            sim_seg = SequenceMatcher(None, texto_atual, texto_seg).ratio()
            if sim_seg >= limiar_similaridade:
                eh_repeticao = True
                break

        # Verificar se contém "repete" no meio (alucinação típica)
        if "repete" in texto_atual and "repete" not in [s["text"].strip().lower() for s in segmentos_limpos[-3:]]:
            # Se tem "repete" mas não é uma repetição real, provável alucinação
            # Manter apenas se for contexto legítimo
            if texto_atual.count("repete") > 0 and not any(
                palavra in texto_atual for palavra in ["direito", "arrependimento", "exercer"]
            ):
                eh_repeticao = True

        if not eh_repeticao:
            segmentos_limpos.append(segmentos[i])

    return segmentos_limpos


def normalizar_texto(texto: str) -> str:
    """Normaliza texto para comparação (sem acentos, lowercase, sem pontuação)."""
    import unicodedata

    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def alinhar_com_roteiro(
    segmentos: list[dict], texto_roteiro: str
) -> list[dict]:
    """
    Alinha os segmentos transcritos com o texto do roteiro.
    Substitui trechos alucinados pelo texto correto do roteiro.

    Estratégia:
    1. Normaliza ambos os textos
    2. Usa janela deslizante para encontrar correspondências
    3. Quando a similaridade é baixa, marca para correção
    4. Quando há repetições claras, remove
    """
    if not texto_roteiro or not segmentos:
        return segmentos

    roteiro_norm = normalizar_texto(texto_roteiro)
    palavras_roteiro = set(roteiro_norm.split())

    segmentos_corrigidos = []
    for seg in segmentos:
        texto_norm = normalizar_texto(seg["text"])
        palavras_seg = set(texto_norm.split())

        # Verificar overlap de palavras com o roteiro
        if palavras_seg and palavras_roteiro:
            overlap = len(palavras_seg & palavras_roteiro) / len(palavras_seg)

            # Se overlap muito baixo (< 30%), provável alucinação
            if overlap < 0.3 and len(texto_norm.split()) > 4:
                # Tentar encontrar trecho correspondente no roteiro
                melhor_match = _encontrar_melhor_trecho(texto_norm, roteiro_norm)
                if melhor_match and melhor_match[1] > 0.5:
                    # Manter segmento mas marcar como corrigido
                    seg["text"] = f"[{melhor_match[0]}]"
                    seg["corrigido"] = True

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
    Corrige números específicos (anos, valores) que o Whisper frequentemente alucina.

    Estratégia:
    1. Extrai números do roteiro (ex: 2026, 1.199,90)
    2. Nos segmentos, se houver número similar mas diferente, corrigir
    """
    if not texto_roteiro or not segmentos:
        return segmentos

    # Extrair números do roteiro
    numeros_roteiro = re.findall(r"\b\d{4}\b|\b\d{1,3}(?:\.\d{3})*(?:,\d{2})?\b", texto_roteiro)
    numeros_roteiro_norm = set()
    for num in numeros_roteiro:
        numeros_roteiro_norm.add(num.replace(".", "").replace(",", ""))

    segmentos_corrigidos = []
    for seg in segmentos:
        texto = seg["text"]

        # Procurar anos (4 dígitos)
        anos = re.findall(r"\b(19\d{2}|20\d{2})\b", texto)
        for ano in anos:
            ano_norm = ano
            # Se o ano não está no roteiro mas um ano similar está
            if ano_norm not in numeros_roteiro_norm:
                for num_rot in numeros_roteiro:
                    num_rot_norm = num_rot.replace(".", "").replace(",", "")
                    # Se é um ano 2-3 dígitos diferente (ex: 2003 vs 2026)
                    if len(num_rot_norm) == 4 and abs(int(ano) - int(num_rot_norm)) <= 50:
                        texto = texto.replace(ano, num_rot_norm)
                        seg["text_corrigido"] = texto

        seg["text"] = texto
        segmentos_corrigidos.append(seg)

    return segmentos_corrigidos


def corrigir_transcricao(
    segmentos: list[dict], texto_roteiro: Optional[str] = None
) -> list[dict]:
    """
    Pipeline completo de correção de alucinações.

    1. Remove repetições
    2. Se roteiro disponível, alinha e corrige
    3. Corrige números
    """
    # Etapa 1: Remover repetições
    segmentos = remover_repeticoes(segmentos)

    # Etapa 2: Alinhar com roteiro (se disponível)
    if texto_roteiro:
        segmentos = alinhar_com_roteiro(segmentos, texto_roteiro)
        segmentos = corrigir_numeros(segmentos, texto_roteiro)

    return segmentos


if __name__ == "__main__":
    # Teste simples
    segmentos_teste = [
        {"start": 0.0, "end": 5.0, "text": "A Câmara Criminal do TJRN manteve a decisão"},
        {"start": 5.0, "end": 10.0, "text": "que deixou de reconhecer falta grave de um apenado"},
        {"start": 10.0, "end": 15.0, "text": "Se reconhecer a prática da falta grave, repete."},
        {"start": 15.0, "end": 20.0, "text": "Se reconhecer a prática da falta grave."},  # REPETIÇÃO
        {"start": 20.0, "end": 25.0, "text": "Para o Ministério Público, o rompimento do equipamento"},
        {"start": 25.0, "end": 30.0, "text": "ocorrido em março de 2003 seria conduta equiparável a fuga."},  # 2003 vs 2026
    ]

    print("ANTES DA CORREÇÃO:")
    for seg in segmentos_teste:
        print(f"  [{seg['start']:5.1f}s] {seg['text']}")

    print("\nDEPOIS DA CORREÇÃO:")
    corrigidos = corrigir_transcricao(segmentos_teste)
    for seg in corrigidos:
        print(f"  [{seg['start']:5.1f}s] {seg['text']}")
