#!/usr/bin/env python3
"""
test_core.py — Testes para funcoes puras de shared/core.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts_pipeline"))

from shared.core import (
    calcular_cobertura_roteiro,
    detectar_assinaturas,
    calcular_marcadores,
    detectar_claquete_geral,
    sincronizar_transcricao_com_cortes,
    Corte,
)
from shared.text_utils import normalizar_texto


# ═══════════════════════════════════════════════════════════
# Testes: calcular_cobertura_roteiro
# ═══════════════════════════════════════════════════════════

def test_cobertura_perfeita():
    cov, cob, tot = calcular_cobertura_roteiro(
        "A Camara Criminal do TJRN",
        "A Câmara Criminal do TJRN"
    )
    assert cov == 1.0
    assert cob == tot


def test_cobertura_parcial():
    cov, cob, tot = calcular_cobertura_roteiro(
        "A Camara Criminal",
        "A Câmara Criminal do TJRN manteve"
    )
    assert 0 < cov < 1.0


def test_cobertura_roteiro_vazio():
    cov, cob, tot = calcular_cobertura_roteiro("qualquer coisa", "")
    assert cov == 0.0


def test_cobertura_transcricao_vazia():
    cov, cob, tot = calcular_cobertura_roteiro("", "roteiro aqui")
    assert cov == 0.0


# ═══════════════════════════════════════════════════════════
# Testes: detectar_assinaturas
# ═══════════════════════════════════════════════════════════

def test_assinatura_completa():
    segmentos = [
        {"start": 0, "end": 5, "text": "noticia"},
        {"start": 5, "end": 10, "text": "do Tribunal de Justiça do Rio Grande do Norte"},
    ]
    resultado = detectar_assinaturas(segmentos)
    assert len(resultado) == 1


def test_assinatura_parcial():
    segmentos = [
        {"start": 0, "end": 5, "text": "Tribunal de Justiça do Rio Grande"},
        {"start": 5, "end": 10, "text": "do Norte"},
    ]
    resultado = detectar_assinaturas(segmentos)
    assert len(resultado) == 1


def test_sem_assinatura():
    segmentos = [
        {"start": 0, "end": 5, "text": "noticia sem assinatura"},
    ]
    resultado = detectar_assinaturas(segmentos)
    assert len(resultado) == 0


# ═══════════════════════════════════════════════════════════
# Testes: calcular_marcadores
# ═══════════════════════════════════════════════════════════

def test_marcadores_com_assinatura():
    segmentos = [
        {"start": 0, "end": 5, "text": "inicio"},
        {"start": 5, "end": 10, "text": "Tribunal de Justica do Rio Grande do Norte"},
        {"start": 10, "end": 15, "text": "proximo"},
    ]
    marcadores = calcular_marcadores(6, 10, [8.5], segmentos)
    assert 6 in marcadores
    assert marcadores[6] == 0.0
    assert 7 in marcadores


def test_marcadores_fallback():
    segmentos = [{"start": 0, "end": 60, "text": "sem assinatura"}]
    marcadores = calcular_marcadores(1, 5, [], segmentos)
    assert len(marcadores) == 5


# ═══════════════════════════════════════════════════════════
# Testes: detectar_claquete_geral
# ═══════════════════════════════════════════════════════════

def test_claquete_geral_detectada():
    segmentos = [
        {"start": 0, "end": 5, "text": "Boletins 18 do 9 do B6O10"},
        {"start": 5, "end": 10, "text": "B6. Noticia"},
    ]
    resultado = detectar_claquete_geral(segmentos, 6, 10)
    assert resultado is not None
    assert resultado[0] == 0


def test_sem_claquete_geral():
    segmentos = [
        {"start": 0, "end": 5, "text": "Noticia sem claquete"},
    ]
    resultado = detectar_claquete_geral(segmentos, 6, 10)
    assert resultado is None


# ═══════════════════════════════════════════════════════════
# Testes: sincronizar_transcricao_com_cortes
# ═══════════════════════════════════════════════════════════

def test_sync_sem_cortes():
    """Sem cortes = retornar igual."""
    segmentos = [
        {"start": 0, "end": 5, "text": "Olá mundo"},
        {"start": 5, "end": 10, "text": "Outro texto"},
    ]
    resultado = sincronizar_transcricao_com_cortes(segmentos, [])
    assert len(resultado) == 2
    assert resultado[0]["start"] == 0


def test_sync_corte_total():
    """Segmento totalmente coberto por corte = removido."""
    segmentos = [
        {"start": 0, "end": 5, "text": "manter"},
        {"start": 5, "end": 10, "text": "remover"},
        {"start": 10, "end": 15, "text": "manter 2"},
    ]
    cortes = [Corte(5, 10, "claquete")]
    resultado = sincronizar_transcricao_com_cortes(segmentos, cortes)
    assert len(resultado) == 2
    assert resultado[0]["text"] == "manter"
    assert resultado[1]["text"] == "manter 2"
    assert resultado[1]["start"] == 5  # 10 - 5


def test_sync_cortes_multiplos():
    """Múltiplos cortes em sequência."""
    segmentos = [
        {"start": 0, "end": 5, "text": "inicio"},
        {"start": 5, "end": 10, "text": "remover 1"},
        {"start": 10, "end": 15, "text": "meio"},
        {"start": 15, "end": 20, "text": "remover 2"},
        {"start": 20, "end": 25, "text": "fim"},
    ]
    cortes = [Corte(5, 10, "claquete"), Corte(15, 20, "repeticao")]
    resultado = sincronizar_transcricao_com_cortes(segmentos, cortes)
    assert len(resultado) == 3
    assert resultado[2]["start"] == 10  # 20 - 10


def test_sync_corte_no_meio():
    """Corte no meio de um segmento divide o texto."""
    segmentos = [
        {"start": 0, "end": 20, "text": "parte um parte dois parte tres"},
    ]
    cortes = [Corte(8, 12, "silencio")]
    resultado = sincronizar_transcricao_com_cortes(segmentos, cortes)
    assert len(resultado) == 2
    assert resultado[0]["end"] == 8
    assert resultado[1]["start"] == 8  # 12 - 4


def test_sync_cortes_sobrepostos():
    """Cortes sobrepostos são mesclados."""
    segmentos = [
        {"start": 0, "end": 30, "text": "texto longo com muitas palavras"},
    ]
    cortes = [Corte(5, 10, "corte 1"), Corte(8, 15, "corte 2")]
    resultado = sincronizar_transcricao_com_cortes(segmentos, cortes)
    assert len(resultado) == 2
    assert resultado[0]["end"] == 5
    assert resultado[1]["start"] == 5  # 15 - 10


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
