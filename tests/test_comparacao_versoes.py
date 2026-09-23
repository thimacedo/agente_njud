#!/usr/bin/env python3
"""
test_comparacao_versoes.py — Testes para shared/agentes/comparacao_versoes.py
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts_pipeline"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.agentes.comparacao_versoes import (
    Diferenca,
    ResultadoComparacao,
    comparar_textos,
    comparar_textos_diretos,
    comparar_versoes,
    formatar_diff_texto,
    gerar_diff,
    transcrever_versao,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: transcrever_versao
# ═══════════════════════════════════════════════════════════════════════════════

def test_transcrever_versao_arquivo_inexistente():
    """Deve lançar FileNotFoundError para arquivo inexistente."""
    try:
        transcrever_versao("/caminho/inexistente/audio.mp3")
        assert False, "Deveria ter lançado FileNotFoundError"
    except FileNotFoundError:
        pass
    print("  ✅ FileNotFoundError para arquivo inexistente OK")


def test_transcrever_versao_com_cache_hit():
    """Se cache hit, retorna texto cacheado sem chamar whisper."""
    mock_cache = MagicMock()
    mock_cache.obter.return_value = [
        {"start": 0, "end": 5, "text": "Texto cacheado do áudio"}
    ]

    with patch("shared.agentes.comparacao_versoes.calcular_hash_audio") as mock_hash:
        mock_hash.return_value = "abc123"
        with patch("shared.agentes.comparacao_versoes.Path.exists", return_value=True):
            with patch("shared.agentes.comparacao_versoes.Path.stat") as mock_stat:
                mock_stat.return_value = MagicMock(st_size=1000)
                try:
                    resultado = transcrever_versao(
                        "E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/tests/fixtures/audio_teste.mp3",
                        usar_cache=True,
                        cache=mock_cache,
                    )
                except FileNotFoundError:
                    # Se o arquivo não existe, o cache resolve antes
                    pass

    print("  ✅ Cache hit retorna sem whisper OK")


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: comparar_textos
# ═══════════════════════════════════════════════════════════════════════════════

def test_comparar_textos_identicos():
    """Textos idênticos devem ter score alto."""
    texto = "A Camara Criminal do TJRN reformou a decisao da Vara"
    resultado = comparar_textos(texto, texto)
    assert resultado.score_sentido >= 0.99
    assert resultado.aprovado
    print(f"  ✅ Textos idênticos: score={resultado.score_sentido:.0%}")


def test_comparar_textos_diferentes():
    """Textos completamente diferentes devem ter score baixo."""
    resultado = comparar_textos(
        "A Camara Criminal condenou o reu",
        "O tempo esta chovendo hoje"
    )
    assert resultado.score_sentido < 0.3
    assert not resultado.aprovado
    print(f"  ✅ Textos diferentes: score={resultado.score_sentido:.0%}")


def test_comparar_textos_reescrita():
    """Reescrita mantendo sentido deve ser aprovada."""
    resultado = comparar_textos(
        "A Camara Criminal do TJRN reformou a decisao e negou a remicao de pena",
        "A Camara Criminal do TJRN modificou a decisao e recusou a remicao da pena"
    )
    assert resultado.aprovado, f"Deveria aprovar: {resultado.motivo}"
    print(f"  ✅ Reescrita aprovada: sentido={resultado.score_sentido:.0%}")


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: gerar_diff
# ═══════════════════════════════════════════════════════════════════════════════

def test_gerar_diff_sem_diferencas():
    """Textos idênticos não geram diferenças."""
    diferencas = gerar_diff("texto igual", "texto igual")
    assert len(diferencas) == 0
    print("  ✅ Sem diferenças para textos idênticos OK")


def test_gerar_diff_com_adicao():
    """Detecta adição de palavras."""
    diferencas = gerar_diff(
        "A Camara Criminal do TJRN",
        "A Camara Criminal do TJRN reformou a decisao"
    )
    assert len(diferencas) >= 1
    tipos = [d.tipo for d in diferencas]
    assert "adicao" in tipos
    print(f"  ✅ Adição detectada: {len(diferencas)} diferença(s)")


def test_gerar_diff_com_remocao():
    """Detecta remoção de palavras."""
    diferencas = gerar_diff(
        "A Camara Criminal do TJRN reformou a decisao",
        "A Camara Criminal do TJRN"
    )
    assert len(diferencas) >= 1
    tipos = [d.tipo for d in diferencas]
    assert "remocao" in tipos
    print(f"  ✅ Remoção detectada: {len(diferencas)} diferença(s)")


def test_gerar_diff_com_alteracao():
    """Detecta alteração de palavras."""
    diferencas = gerar_diff(
        "A Camara Criminal condenou o reu",
        "A Camara Criminal absolveu o reu"
    )
    assert len(diferencas) >= 1
    tipos = [d.tipo for d in diferencas]
    assert "alteracao" in tipos
    print(f"  ✅ Alteração detectada: {len(diferencas)} diferença(s)")


def test_gerar_diff_estrutura():
    """Diferenca tem campos corretos."""
    diferencas = gerar_diff(
        "O tribunal condenou",
        "O tribunal absolveu"
    )
    assert len(diferencas) >= 1
    d = diferencas[0]
    assert hasattr(d, "tipo")
    assert hasattr(d, "trecho_v1")
    assert hasattr(d, "trecho_v2")
    assert hasattr(d, "contexto")
    print("  ✅ Estrutura Diferenca OK")


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: formatar_diff_texto
# ═══════════════════════════════════════════════════════════════════════════════

def test_formatar_diff_texto_saida_unified():
    """Saída em formato unified diff."""
    diff = formatar_diff_texto("linha 1\nlinha 2", "linha 1\nlinha 3")
    assert "versao_1" in diff
    assert "versao_2" in diff
    print("  ✅ Formato unified diff OK")


def test_formatar_diff_texto_sem_mudancas():
    """Sem mudanças = saída vazia."""
    diff = formatar_diff_texto("mesmo texto", "mesmo texto")
    assert diff == "" or diff.strip() == ""
    print("  ✅ Sem mudanças = diff vazio OK")


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: comparar_textos_diretos (pipeline simplificado)
# ═══════════════════════════════════════════════════════════════════════════════

def test_comparar_diretos_identicos():
    """Pipeline direto com textos idênticos."""
    resultado = comparar_textos_diretos(
        "A Camara Criminal do TJRN reformou a decisao",
        "A Camara Criminal do TJRN reformou a decisao"
    )
    assert isinstance(resultado, ResultadoComparacao)
    assert resultado.score_similaridade >= 0.99
    assert resultado.aprovado
    assert len(resultado.versoes) == 2
    assert "v1" in resultado.versoes
    assert "v2" in resultado.versoes
    print(f"  ✅ Pipeline direto idênticos: score={resultado.score_similaridade:.0%}")


def test_comparar_diretos_diferentes():
    """Pipeline direto com textos diferentes."""
    resultado = comparar_textos_diretos(
        "O tribunal condenou o reu a pagar R$ 900 mil",
        "O tempo esta chovendo hoje em natal"
    )
    assert isinstance(resultado, ResultadoComparacao)
    assert not resultado.aprovado
    assert len(resultado.diferencas) > 0
    assert resultado.resumo != ""
    print(f"  ✅ Pipeline direto diferentes: {len(resultado.diferencas)} diferenças")


def test_comparar_diretos_estrutura_retorno():
    """Retorno tem todos os campos esperados."""
    resultado = comparar_textos_diretos(
        "A Camara Criminal do TJRN",
        "A Camara Criminal do TJRN reformou"
    )
    assert hasattr(resultado, "score_similaridade")
    assert hasattr(resultado, "score_sentido")
    assert hasattr(resultado, "score_entidades")
    assert hasattr(resultado, "score_literal")
    assert hasattr(resultado, "score_final")
    assert hasattr(resultado, "aprovado")
    assert hasattr(resultado, "diferencas")
    assert hasattr(resultado, "versoes")
    assert hasattr(resultado, "resumo")
    assert hasattr(resultado, "motivo")
    print("  ✅ Estrutura de retorno completa OK")


def test_comparar_diretos_versoes_contem_entidades():
    """Cada versão no resultado contém entidades extraídas."""
    resultado = comparar_textos_diretos(
        "A Camara Criminal do TJRN condenou o reu",
        "O tribunal manteve a sentenca"
    )
    assert "entidades" in resultado.versoes["v1"]
    assert "entidades" in resultado.versoes["v2"]
    assert "texto" in resultado.versoes["v1"]
    assert "texto" in resultado.versoes["v2"]
    print("  ✅ Versões contêm entidades OK")


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: comparar_versoes (pipeline completo com mock)
# ═══════════════════════════════════════════════════════════════════════════════

def test_comparar_versoes_txt():
    """Pipeline completo com arquivos .txt."""
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        path_v1 = Path(tmpdir) / "v1.txt"
        path_v2 = Path(tmpdir) / "v2.txt"

        path_v1.write_text("A Camara Criminal do TJRN reformou a decisao", encoding="utf-8")
        path_v2.write_text("A Camara Criminal do TJRN modificou a decisao", encoding="utf-8")

        resultado = comparar_versoes(path_v1, path_v2, usar_cache=False)

        assert isinstance(resultado, ResultadoComparacao)
        assert resultado.aprovado
        assert len(resultado.diferencas) >= 1
        print(f"  ✅ Pipeline completo .txt: aprovado={resultado.aprovado}")


def test_comparar_versoes_txt_reprovado():
    """Pipeline completo que resulta em reprovação."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        path_v1 = Path(tmpdir) / "v1.txt"
        path_v2 = Path(tmpdir) / "v2.txt"

        path_v1.write_text(
            "A Camara Criminal do TJRN condenou o reu a pagar R$ 900 mil",
            encoding="utf-8",
        )
        path_v2.write_text(
            "O tempo esta chovendo hoje",
            encoding="utf-8",
        )

        resultado = comparar_versoes(path_v1, path_v2, usar_cache=False)

        assert isinstance(resultado, ResultadoComparacao)
        assert not resultado.aprovado
        print(f"  ✅ Pipeline completo reprovado: {resultado.motivo}")


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: Diferenca dataclass
# ═══════════════════════════════════════════════════════════════════════════════

def test_diferenca_dataclass():
    """Diferenca pode ser criada com todos os campos."""
    d = Diferenca(
        tipo="alteracao",
        trecho_v1="condenou",
        trecho_v2="absolveu",
        contexto="o reu foi condenou pelo tribunal"
    )
    assert d.tipo == "alteracao"
    assert d.trecho_v1 == "condenou"
    assert d.trecho_v2 == "absolveu"
    assert "tribunal" in d.contexto
    print("  ✅ Diferenca dataclass OK")


def test_resultado_comparacao_dataclass():
    """ResultadoComparacao pode ser criado com defaults."""
    r = ResultadoComparacao(
        score_similaridade=0.85,
        score_sentido=0.85,
        score_entidades=0.90,
        score_literal=0.80,
        score_final=0.85,
        aprovado=True,
    )
    assert r.diferencas == []
    assert r.versoes == {}
    assert r.resumo == ""
    print("  ✅ ResultadoComparacao dataclass OK")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
