"""
Funções de normalização e similaridade de texto.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


def normalizar_texto(texto: str) -> str:
    """Remove acentos, pontuação e normaliza espaços."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def normalizar_ancoras(ancoras: list[str]) -> list[str]:
    return [normalizar_texto(a) for a in ancoras]


def similaridade(a: str, b: str) -> float:
    """Ratio de similaridade entre duas strings (SequenceMatcher)."""
    return SequenceMatcher(None, a, b).ratio()
