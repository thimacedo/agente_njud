#!/usr/bin/env python3
"""
SPIKE #4: Testes unitários pytest.

Valida: criar testes para as funções puras do pipeline.
- normalizar_texto (text_utils)
- calcular_hash_audio + TranscricaoCache (transcricao_cache)
- DivisorConfig (config)
- remover_repeticoes (corrigir_alucinacoes)
"""
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

# Adicionar o path do projeto
sys.path.insert(0, str(Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/scripts_pipeline")))

# ═══════════════════════════════════════════════════════════
# TESTES: shared.text_utils
# ═══════════════════════════════════════════════════════════

from shared.text_utils import normalizar_texto, remover_acentos, extrair_palavras_significativas


def test_normalizar_basico():
    assert normalizar_texto("Tribunal de Justiça") == "tribunal de justica"


def test_normalizar_pontuacao():
    assert normalizar_texto("R$ 1.199,90") == "r 1 199 90"


def test_normalizar_espacos():
    assert normalizar_texto("  múltiplos   espaços  ") == "multiplos espacos"


def test_normalizar_vazio():
    assert normalizar_texto("") == ""
    assert normalizar_texto(None) == ""


def test_normalizar_acentos_complexos():
    assert normalizar_texto("São João") == "sao joao"
    assert normalizar_texto("coração") == "coracao"
    assert normalizar_texto("órgão") == "orgao"


def test_normalizar_preserva_numeros():
    assert normalizar_texto("2026") == "2026"
    assert normalizar_texto("B6") == "b6"


def test_remover_acentos():
    assert remover_acentos("Camara") == "Camara"
    assert remover_acentos("São Paulo") == "Sao Paulo"


def test_extrair_palavras_significativas():
    palavras = extrair_palavras_significativas("A Camara Criminal do TJRN")
    assert "camara" in palavras
    assert "criminal" in palavras
    assert "tjrn" in palavras
    assert "a" not in palavras  # stopword
    assert "do" not in palavras  # stopword


# ═══════════════════════════════════════════════════════════
# TESTES: shared.transcricao_cache
# ═══════════════════════════════════════════════════════════

from shared.transcricao_cache import calcular_hash_audio, TranscricaoCache


def test_hash_deterministo():
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        f.write(b"\x00" * 10000)
        caminho = Path(f.name)
    h1 = calcular_hash_audio(caminho)
    h2 = calcular_hash_audio(caminho)
    assert h1 == h2
    caminho.unlink()


def test_hash_detecta_mudanca():
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        f.write(b"\x00" * 10000)
        c1 = Path(f.name)
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        f.write(b"\x01" * 10000)
        c2 = Path(f.name)
    assert calcular_hash_audio(c1) != calcular_hash_audio(c2)
    c1.unlink()
    c2.unlink()


def test_cache_hit_miss():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = TranscricaoCache(Path(tmpdir))
        assert cache.obter("inexistente") is None
        cache.salvar("teste", [{"text": "ola"}])
        assert cache.obter("teste") == [{"text": "ola"}]


def test_cache_stats():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = TranscricaoCache(Path(tmpdir))
        cache.obter("miss1")
        cache.salvar("hit1", [])
        cache.obter("hit1")
        cache.obter("miss2")
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 2


def test_cache_limite_entradas():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = TranscricaoCache(Path(tmpdir), max_entries=3)
        for i in range(5):
            cache.salvar(f"hash_{i}", [])
        entradas = list(Path(tmpdir).glob("*.json"))
        assert len(entradas) == 3


def test_cache_limpar_tudo():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = TranscricaoCache(Path(tmpdir))
        cache.salvar("a", [])
        cache.salvar("b", [])
        cache.limpar_tudo()
        assert len(list(Path(tmpdir).glob("*.json"))) == 0


# ═══════════════════════════════════════════════════════════
# TESTES: shared.config
# ═══════════════════════════════════════════════════════════

from shared.config import DivisorConfig


def test_config_defaults():
    config = DivisorConfig()
    assert config.cobertura_min == 0.60
    assert config.whisper_model == "base"


def test_config_validacao_range():
    try:
        DivisorConfig(cobertura_min=1.5)
        assert False, "Deveria rejeitar"
    except ValueError:
        pass


def test_config_aplicar():
    config = DivisorConfig(cobertura_min=0.72, whisper_model="small")
    config.aplicar()
    assert os.environ["DIVISOR_COBERTURA_MIN"] == "0.72"
    assert os.environ["DIVISOR_WHISPER_MODEL"] == "small"
    # Cleanup
    del os.environ["DIVISOR_COBERTURA_MIN"]
    del os.environ["DIVISOR_THRESHOLD_SIMILARIDADE"]
    del os.environ["DIVISOR_WHISPER_MODEL"]


def test_config_carregar():
    os.environ["DIVISOR_COBERTURA_MIN"] = "0.65"
    config = DivisorConfig.carregar()
    assert config.cobertura_min == 0.65
    del os.environ["DIVISOR_COBERTURA_MIN"]


# ═══════════════════════════════════════════════════════════
# TESTES: corrigir_alucinacoes.remover_repeticoes
# ═══════════════════════════════════════════════════════════

# Importar direto do modulo
sys.path.insert(0, str(Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/scripts_pipeline/boletim")))
from corrigir_alucinacoes import remover_repeticoes, corrigir_numeros





def test_remover_repeticoes_exatas():
    """Repeticoes exatas devem ser removidas."""
    segmentos = [
        {"start": 0, "end": 1, "text": "O Tribunal de Justica do RN"},
        {"start": 1, "end": 2, "text": "O Tribunal de Justica do RN"},  # repetido exato
        {"start": 2, "end": 3, "text": "Outro texto diferente"},
    ]
    resultado = remover_repeticoes(segmentos)
    assert len(resultado) == 2  # remove o repetido, mantem os outros 2


def test_remover_repeticoes_vazios():
    assert remover_repeticoes([]) == []
    assert remover_repeticoes(None) == None


def test_remover_repete_alucinacao():
    segmentos = [
        {"start": 0, "end": 5, "text": "A Camara Criminal do TJRN"},
        {"start": 5, "end": 10, "text": "Se reconhecer a pratica da falta grave, repete."},
    ]
    resultado = remover_repeticoes(segmentos)
    assert len(resultado) == 1  # remove "repete" isolado


def test_preserva_repete_legitimo():
    segmentos = [
        {"start": 0, "end": 5, "text": "O direito de arrependimento"},
    ]
    resultado = remover_repeticoes(segmentos)
    assert len(resultado) == 1  # "arrependimento" esta na lista de excecao


def test_corrigir_numeros_ano():
    segmentos = [{"start": 0, "end": 5, "text": "ocorrido em marco de 2003"}]
    resultado = corrigir_numeros(segmentos, "ocorrido em marco de 2026 seria conduta")
    assert resultado[0]["text"] == "ocorrido em marco de 2026"


def test_corrigir_numeros_sem_roteiro():
    segmentos = [{"start": 0, "end": 5, "text": "ocorrido em 2026"}]
    resultado = corrigir_numeros(segmentos, "")
    assert resultado[0]["text"] == "ocorrido em 2026"  # sem alteração


# ═══════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
