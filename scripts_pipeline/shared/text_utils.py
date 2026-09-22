#!/usr/bin/env python3
"""
text_utils.py — Funcoes de normalizacao de texto compartilhadas.

Centraliza a normalizacao de texto para garantir consistencia entre
todos os modulos do pipeline (corrigir_alucinacoes, auditoria_proativa,
processar_boletim_canonico, etc).

Unifica 3 implementacoes anteriores que divergiam na remocao de acentos.
"""
import re
import unicodedata


def normalizar_texto(texto: str) -> str:
    """
    Normaliza texto para comparacao.
    - Lowercase
    - Remove acentos (NFD decomposition)
    - Remove pontuacao (mantem apenas word chars e espacos)
    - Colapsa espacos multiplos

    Args:
        texto: Texto original (qualquer idioma)

    Returns:
        Texto normalizado para comparacao

    Exemplos:
        >>> normalizar_texto("Tribunal de Justica")
        'tribunal de justica'
        >>> normalizar_texto("R$ 1.199,90")
        'r 1 199 90'
        >>> normalizar_texto("Sao Paulo — Rio")
        'sao paulo rio'
    """
    if not texto:
        return ""
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def remover_acentos(texto: str) -> str:
    """
    Remove acentos de um texto (preserva case e pontuacao).

    Args:
        texto: Texto original

    Returns:
        Texto sem acentos

    Exemplo:
        >>> remover_acentos("Camara")
        'Camara'
    """
    if not texto:
        return ""
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def extrair_palavras_significativas(texto: str, min_len: int = 3) -> set:
    """
    Extrai conjunto de palavras significativas (remove stopwords comuns).

    Args:
        texto: Texto original
        min_len: Tamanho minimo da palavra

    Returns:
        Set de palavras unicas significativas
    """
    STOPWORDS = {
        "a", "o", "e", "de", "do", "da", "em", "um", "uma", "que", "para",
        "com", "por", "na", "no", "os", "as", "dos", "das", "se", "ao", "aos",
        "ou", "como", "mais", "mas", "ser", "foi", "sao", "tambem", "ate",
        "nao", "pelo", "pela", "seus", "sua", "suas", "dele", "dela", "entre",
        "sobre", "apos", "durante", "sem", "ja", "ainda", "quando", "cada",
        "mesmo", "bem", "onde", "isso", "este", "esta", "estas", "estes",
    }
    norm = normalizar_texto(texto)
    palavras = set(norm.split())
    return {p for p in palavras if len(p) >= min_len and p not in STOPWORDS}


if __name__ == "__main__":
    # Sanity check
    assert normalizar_texto("Camara Criminal") == "camara criminal"
    assert normalizar_texto("Sao Paulo") == "sao paulo"
    assert remover_acentos("Tribunal de Justica") == "Tribunal de Justica"
    assert "camara" in extrair_palavras_significativas("A Camara Criminal")
    print("OK — text_utils sanity check passou")
