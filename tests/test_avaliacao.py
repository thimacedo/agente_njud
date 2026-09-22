#!/usr/bin/env python3
"""
test_avaliacao.py — Testes para shared/avaliacao.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts_pipeline"))

from shared.avaliacao import (
    avaliar_transcricao,
    extrair_entidades,
    calcular_similaridade_semantica,
    calcular_preservacao_entidades,
)


# ═══════════════════════════════════════════════════════════
# Testes: extrair_entidades
# ═══════════════════════════════════════════════════════════

def test_entidades_valores():
    texto = "O condenado deve pagar R$ 900 mil e R$ 1.199,90"
    entidades = extrair_entidades(texto)
    assert len(entidades["valores"]) >= 1
    print("  ✅ Entidades valores OK")


def test_entidades_datas():
    texto = "ocorrido em 10 de julho de 2026"
    entidades = extrair_entidades(texto)
    assert len(entidades["datas"]) >= 1
    print("  ✅ Entidades datas OK")


def test_entidades_termos():
    texto = "A Camara Criminal do TJRN condenou o reu"
    entidades = extrair_entidades(texto)
    assert "camara" in entidades["termos_essenciais"]
    assert "criminal" in entidades["termos_essenciais"]
    assert "tjrn" in entidades["termos_essenciais"]
    assert "condenou" in entidades["termos_essenciais"]
    print("  ✅ Entidades termos OK")


# ═══════════════════════════════════════════════════════════
# Testes: calcular_similaridade_semantica
# ═══════════════════════════════════════════════════════════

def test_semantica_identica():
    score = calcular_similaridade_semantica("texto teste", "texto teste")
    assert score >= 0.99  # Precisão de ponto flutuante
    print("  ✅ Semântica idêntica OK")


def test_semantica_reescrita():
    score = calcular_similaridade_semantica(
        "A Camara Criminal reformou a decisao",
        "A Camara Criminal modificou a decisao"
    )
    assert score > 0.7  # Mesmo sentido com sinônimos
    print(f"  ✅ Semântica reescrita OK: {score:.0%}")


def test_semantica_diferente():
    score = calcular_similaridade_semantica(
        "A Camara Criminal condenou o reu",
        "O tempo esta chovendo hoje"
    )
    assert score < 0.3  # Sentido completamente diferente
    print(f"  ✅ Semântica diferente OK: {score:.0%}")


# ═══════════════════════════════════════════════════════════
# Testes: avaliar_transcricao (integrado)
# ═══════════════════════════════════════════════════════════

def test_avaliacao_exata():
    """Texto exato = aprovado com 100%."""
    resultado = avaliar_transcricao(
        "A Camara Criminal do TJRN reformou a decisao",
        "A Camara Criminal do TJRN reformou a decisao"
    )
    assert resultado.aprovado
    assert resultado.score_literal == 1.0
    print("  ✅ Avaliação exata OK")


def test_avaliacao_reescrita_aprovada():
    """Reescrita mantendo sentido = APROVADO."""
    resultado = avaliar_transcricao(
        "A Camara Criminal do TJRN reformou decisao da Vara de Mossoro e negou a remicao de pena",
        "A Camara Criminal do TJRN modificou a decisao da Vara de Mossoro e recusou a remicao da pena"
    )
    assert resultado.aprovado, f"Deveria aprovar: {resultado.motivo}"
    print(f"  ✅ Reescrita aprovada: sentido={resultado.score_sentido:.0%}")


def test_avaliacao_correcao_cacofonia():
    """Correção de cacofonia = APROVADO."""
    resultado = avaliar_transcricao(
        "A sentenca concluiu que a mulher mantinha bens de origem ilicita",
        "A sentenca concluiu que a mulher mantinha bens ilicitos"
    )
    assert resultado.aprovado, f"Deveria aprovar: {resultado.motivo}"
    print(f"  ✅ Correção cacofonia aprovada: sentido={resultado.score_sentido:.0%}")


def test_avaliacao_perda_entidade_reprovada():
    """Perda de entidade essencial = REPROVADO."""
    resultado = avaliar_transcricao(
        "A Camara Criminal do TJRN condenou a reu a pagar R$ 900 mil",
        "O tribunal tomou uma decisao"
    )
    assert not resultado.aprovado
    print(f"  ✅ Perda entidade reprovada: {resultado.motivo}")


def test_avaliacao_corte_inaceitavel():
    """Corte que perde informação = REPROVADO."""
    resultado = avaliar_transcricao(
        "O condenado deve pagar R$ 900 mil em penas pecuniarias para 27 projetos sociais",
        "O condenado deve pagar"
    )
    assert not resultado.aprovado
    print(f"  ✅ Corte inaceitável reprovado: {resultado.motivo}")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
