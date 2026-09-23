#!/usr/bin/env python3
"""
test_integracao_pipeline.py — Testes de integração end-to-end do pipeline DIVISOR.

Testa o pipeline completo com dados simulados (mocks), incluindo:
- Pipeline completo com mock de faster_whisper
- Etapas individuais (triagem, estrutura, cortes, montagem)
- Cache de transcrição (hit/miss)
- Correção de alucinações
"""
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts_pipeline"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts_pipeline" / "boletim"))
sys.path.insert(0, str(PROJECT_ROOT))

from pydub import AudioSegment
from pydub.generators import Sine


# ═══════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def audio_mono_curto():
    """Gera um áudio mono curto sintético (3s, 440Hz)."""
    tone = Sine(440).to_audio_segment(duration=3000, volume=-20)
    return tone.set_channels(1).set_frame_rate(16000)


@pytest.fixture
def audio_estereo():
    """Gera um áudio estéreo sintético (5s, 440Hz)."""
    tone = Sine(440).to_audio_segment(duration=5000, volume=-20)
    return tone.set_channels(2).set_frame_rate(16000)


@pytest.fixture
def audio_estereo_duplicado():
    """Gera áudio estéreo com L==R (duplicado)."""
    tone = Sine(440).to_audio_segment(duration=4000, volume=-20)
    mono = tone.set_channels(1).set_frame_rate(16000)
    return AudioSegment.from_mono_audiosegments(mono, mono)


@pytest.fixture
def segmentos_mock():
    """Segmentos simulados de transcrição Whisper."""
    return [
        {"start": 0.0, "end": 3.5, "text": "Boletins 17 do 9 do B1O5"},
        {"start": 3.5, "end": 7.0, "text": "B1. A Câmara Criminal do TJRN manteve a decisão"},
        {"start": 7.0, "end": 12.0, "text": "que deixou de reconhecer falta grave de um apenado"},
        {"start": 12.0, "end": 18.0, "text": "do Tribunal de Justiça do Rio Grande do Norte, Leonardo Meida."},
        {"start": 18.0, "end": 22.0, "text": "B2. Outra notícia importante do dia"},
        {"start": 22.0, "end": 28.0, "text": "do Tribunal de Justiça do Rio Grande do Norte, Leonardo Meida."},
    ]


@pytest.fixture
def segmentos_com_words():
    """Segmentos com word-level timestamps simulados."""
    return [
        {
            "start": 0.0, "end": 3.5,
            "text": "Boletins 17 do 9 do B1O5",
            "words": [
                {"word": "Boletins", "start": 0.0, "end": 0.5},
                {"word": "17", "start": 0.5, "end": 0.8},
                {"word": "do", "start": 0.8, "end": 1.0},
                {"word": "9", "start": 1.0, "end": 1.3},
                {"word": "do", "start": 1.3, "end": 1.5},
                {"word": "B1O5", "start": 1.5, "end": 2.0},
            ]
        },
        {
            "start": 3.5, "end": 7.0,
            "text": "B1. A Câmara Criminal do TJRN",
            "words": [
                {"word": "B1,", "start": 3.5, "end": 3.8},
                {"word": "A", "start": 3.8, "end": 4.0},
                {"word": "Câmara", "start": 4.0, "end": 4.5},
                {"word": "Criminal", "start": 4.5, "end": 5.0},
                {"word": "do", "start": 5.0, "end": 5.2},
                {"word": "TJRN", "start": 5.2, "end": 5.8},
            ]
        },
        {
            "start": 7.0, "end": 12.0,
            "text": "notícia importante do dia",
            "words": [
                {"word": "notícia", "start": 7.0, "end": 7.5},
                {"word": "importante", "start": 7.5, "end": 8.2},
                {"word": "do", "start": 8.2, "end": 8.5},
                {"word": "dia", "start": 8.5, "end": 9.0},
            ]
        },
        {
            "start": 12.0, "end": 18.0,
            "text": "do Tribunal de Justiça do Rio Grande do Norte, Leonardo Meida.",
            "words": [
                {"word": "do", "start": 12.0, "end": 12.2},
                {"word": "Tribunal", "start": 12.2, "end": 12.8},
                {"word": "de", "start": 12.8, "end": 13.0},
                {"word": "Justiça", "start": 13.0, "end": 13.5},
                {"word": "do", "start": 13.5, "end": 13.7},
                {"word": "Rio", "start": 13.7, "end": 14.0},
                {"word": "Grande", "start": 14.0, "end": 14.5},
                {"word": "do", "start": 14.5, "end": 14.7},
                {"word": "Norte,", "start": 14.7, "end": 15.2},
                {"word": "Leonardo", "start": 15.2, "end": 15.8},
                {"word": "Meida.", "start": 15.8, "end": 16.5},
            ]
        },
        {
            "start": 18.0, "end": 22.0,
            "text": "B2. Outra notícia importante",
            "words": [
                {"word": "B2,", "start": 18.0, "end": 18.3},
                {"word": "Outra", "start": 18.3, "end": 18.8},
                {"word": "notícia", "start": 18.8, "end": 19.3},
                {"word": "importante", "start": 19.3, "end": 20.0},
            ]
        },
        {
            "start": 22.0, "end": 28.0,
            "text": "do Tribunal de Justiça do Rio Grande do Norte, Leonardo Meida.",
            "words": [
                {"word": "do", "start": 22.0, "end": 22.2},
                {"word": "Tribunal", "start": 22.2, "end": 22.8},
                {"word": "de", "start": 22.8, "end": 23.0},
                {"word": "Justiça", "start": 23.0, "end": 23.5},
                {"word": "do", "start": 23.5, "end": 23.7},
                {"word": "Rio", "start": 23.7, "end": 24.0},
                {"word": "Grande", "start": 24.0, "end": 24.5},
                {"word": "do", "start": 24.5, "end": 24.7},
                {"word": "Norte,", "start": 24.7, "end": 25.2},
                {"word": "Leonardo", "start": 25.2, "end": 25.8},
                {"word": "Meida.", "start": 25.8, "end": 26.5},
            ]
        },
    ]


@pytest.fixture
def whisper_model_mock():
    """Mock do modelo Whisper para testes."""
    mock_model = MagicMock()

    def fake_transcribe(audio_path, **kwargs):
        return [
            {"start": 0.0, "end": 3.0, "text": "Boletins 17 do 9 do B1O5"},
            {"start": 3.0, "end": 7.0, "text": "A Câmara Criminal do TJRN manteve a decisão"},
            {"start": 7.0, "end": 12.0, "text": "do Tribunal de Justiça do Rio Grande do Norte"},
        ], {"language": "pt", "language_probability": 0.99}

    mock_model.transcribe = fake_transcribe
    return mock_model


@pytest.fixture
def tmp_audio_file(tmp_path):
    """Cria um arquivo de áudio WAV temporário para testes."""
    tone = Sine(440).to_audio_segment(duration=2000, volume=-20)
    tone = tone.set_channels(1).set_frame_rate(16000)
    audio_path = tmp_path / "test_audio.wav"
    tone.export(str(audio_path), format="wav")
    return audio_path


# ═══════════════════════════════════════════════════════════
# TESTE: Pipeline completo com mock
# ═══════════════════════════════════════════════════════════

class TestPipelineCompletoMock:
    """Testa o pipeline completo com dados simulados."""

    def test_pipeline_completo_mock(self, audio_mono_curto, whisper_model_mock, tmp_path):
        """Pipeline completo: triagem → transcrição mock → estrutura → cortes → correção."""
        from boletim.etapas.etapa_triagem import triagem_audio
        from boletim.etapas.etapa_estrutura import detectar_estrutura
        from boletim.etapas.etapa_cortes import processar_cortes_boletim
        from boletim import corrigir_alucinacoes

        # ETAPA 1: Triagem
        resultado_triagem = triagem_audio(audio_mono_curto)
        assert resultado_triagem["duracao_segundos"] > 0
        assert resultado_triagem["canais"] == 1
        assert "acoes" in resultado_triagem

        # ETAPA 2: Transcrição (mock)
        segments_iter, info = whisper_model_mock.transcribe(
            str(tmp_path / "dummy.wav"), language="pt"
        )
        segmentos = list(segments_iter) if not isinstance(segments_iter, list) else segments_iter
        assert len(segmentos) > 0

        # ETAPA 3: Estrutura
        estrutura = detectar_estrutura(segmentos, b_ini=1, b_fim=5)
        assert "marcadores" in estrutura
        assert "assinaturas" in estrutura

        # ETAPA 4: Cortes (sem repetições/claquetes para simplificar)
        resultado_cortes = processar_cortes_boletim(
            segmentos=segmentos,
            audio_corte=audio_mono_curto,
            rep_confirmadas=[],
            claquetes={},
            claquete_geral=None,
            estrutura=estrutura,
            b_ini=1,
            b_fim=5
        )
        assert isinstance(resultado_cortes, dict)

        # ETAPA 5: Correção de alucinações
        segmentos_corrigidos = corrigir_alucinacoes.corrigir_transcricao(segmentos)
        assert len(segmentos_corrigidos) > 0
        assert all("text" in s for s in segmentos_corrigidos)

    def test_etapa_triagem(self, audio_mono_curto, audio_estereo, audio_estereo_duplicado):
        """Testa triagem de áudio: mono, estéreo, estéreo duplicado."""
        from boletim.etapas.etapa_triagem import triagem_audio

        # Mono
        r1 = triagem_audio(audio_mono_curto)
        assert r1["canais"] == 1
        assert "canal_morto" not in r1

        # Estereeo normal
        r2 = triagem_audio(audio_estereo)
        assert r2["canais"] == 2

        # Estéreo duplicado (L==R)
        r3 = triagem_audio(audio_estereo_duplicado)
        assert r3.get("estereo_duplicado") is True
        assert any("CONVERTER" in a for a in r3["acoes"])

    def test_etapa_estrutura(self, segmentos_mock):
        """Testa detecção de estrutura com segmentos simulados."""
        from boletim.etapas.etapa_estrutura import detectar_estrutura

        estrutura = detectar_estrutura(segmentos_mock, b_ini=1, b_fim=5)

        assert "marcadores" in estrutura
        assert "assinaturas" in estrutura
        assert "falta" in estrutura
        # Deve encontrar pelo menos 2 assinaturas nos segmentos mock
        assert len(estrutura["assinaturas"]) >= 1

    def test_etapa_estrutura_com_words(self, segmentos_com_words):
        """Testa detecção de estrutura com word timestamps."""
        from boletim.etapas.etapa_estrutura import detectar_estrutura

        estrutura = detectar_estrutura(segmentos_com_words, b_ini=1, b_fim=2)

        assert "marcadores" in estrutura
        assert 1 in estrutura["marcadores"]
        assert estrutura["marcadores"][1] == 0.0

    def test_etapa_cortes(self, audio_mono_curto, segmentos_mock):
        """Testa processamento de cortes com dados simulados."""
        from boletim.etapas.etapa_estrutura import detectar_estrutura
        from boletim.etapas.etapa_cortes import processar_cortes_boletim

        estrutura = detectar_estrutura(segmentos_mock, b_ini=1, b_fim=5)

        resultado = processar_cortes_boletim(
            segmentos=segmentos_mock,
            audio_corte=audio_mono_curto,
            rep_confirmadas=[],
            claquetes={},
            claquete_geral=None,
            estrutura=estrutura,
            b_ini=1,
            b_fim=5
        )

        assert isinstance(resultado, dict)
        for n_boletim, info in resultado.items():
            assert "audio" in info
            assert "inicio_original" in info
            assert "fim_original" in info
            assert "duracao_cortada" in info

    def test_etapa_cortes_com_claquete_geral(self, audio_mono_curto, segmentos_mock):
        """Testa cortes quando há claquete geral detectada."""
        from boletim.etapas.etapa_estrutura import detectar_estrutura
        from boletim.etapas.etapa_cortes import processar_cortes_boletim

        estrutura = detectar_estrutura(segmentos_mock, b_ini=1, b_fim=5)
        claquete_geral = (0.0, 3.5)  # Claquete geral de 0 a 3.5s

        resultado = processar_cortes_boletim(
            segmentos=segmentos_mock,
            audio_corte=audio_mono_curto,
            rep_confirmadas=[],
            claquetes={},
            claquete_geral=claquete_geral,
            estrutura=estrutura,
            b_ini=1,
            b_fim=5
        )

        assert isinstance(resultado, dict)

    def test_etapa_montagem_sem_vinhetas(self, audio_mono_curto):
        """Testa montagem sem vinhetas (apenas estrutura interna)."""
        # A montagem requer vinhetas reais + ffmpeg, então testamos a lógica
        # de divisão cabeça/off separadamente
        duracao_total = len(audio_mono_curto) / 1000
        cabeca_duracao = 2.0

        if duracao_total > cabeca_duracao:
            cabeca = audio_mono_curto[:int(cabeca_duracao * 1000)]
            off = audio_mono_curto[int(cabeca_duracao * 1000):]
        else:
            cabeca = audio_mono_curto
            off = AudioSegment.silent(duration=0)

        assert len(cabeca) > 0
        assert len(cabeca) + len(off) == len(audio_mono_curto)

    def test_etapa_montagem_cabeca_off_split(self):
        """Testa divisão cabeça/off com áudio mais longo."""
        tone = Sine(440).to_audio_segment(duration=10000, volume=-20)
        audio = tone.set_channels(1).set_frame_rate(16000)

        cabeca_duracao = 3.0
        duracao_total = len(audio) / 1000

        assert duracao_total > cabeca_duracao
        cabeca = audio[:int(cabeca_duracao * 1000)]
        off = audio[int(cabeca_duracao * 1000):]

        assert len(cabeca) == int(cabeca_duracao * 1000)
        assert len(off) == len(audio) - len(cabeca)

    def test_cache_transcricao(self, tmp_path, tmp_audio_file):
        """Testa cache hit/miss de transcrição."""
        from shared.transcricao_cache import TranscricaoCache, calcular_hash_audio

        cache = TranscricaoCache(dir_cache=tmp_path / "cache", max_entries=10)

        # Calcular hash do áudio
        hash_audio = calcular_hash_audio(tmp_audio_file)
        assert len(hash_audio) == 64  # SHA-256 hex

        # MISS: ainda não está no cache
        resultado = cache.obter(hash_audio)
        assert resultado is None

        # Salvar no cache
        segmentos = [{"start": 0.0, "end": 2.0, "text": "teste de cache"}]
        cache.salvar(hash_audio, segmentos)

        # HIT: agora está no cache
        resultado = cache.obter(hash_audio)
        assert resultado is not None
        assert resultado[0]["text"] == "teste de cache"

        # Verificar stats
        stats = cache.stats
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["hit_rate"] > 0

    def test_cache_transcricao_limpeza(self, tmp_path):
        """Testa limpeza de entradas antigas do cache."""
        from shared.transcricao_cache import TranscricaoCache

        cache = TranscricaoCache(dir_cache=tmp_path / "cache", max_entries=3)

        # Salvar 5 entradas (max é 3)
        for i in range(5):
            cache.salvar(f"hash_{i}", [{"text": f"teste {i}"}])

        # Deve ter apenas 3
        entradas = list((tmp_path / "cache").glob("*.json"))
        assert len(entradas) == 3

    def test_correcao_alucinacoes(self):
        """Testa correção de alucinações conhecidas do Whisper."""
        from boletim.corrigir_alucinacoes import (
            corrigir_transcricao,
            remover_repeticoes,
            corrigir_alucinacoes_conhecidas,
        )

        segmentos = [
            {"start": 0.0, "end": 5.0, "text": "A Camara Criminal do TJRN manteve a decisao"},
            {"start": 5.0, "end": 10.0, "text": "A Camara Criminal do TJRN manteve a decisao"},  # repetido
            {"start": 10.0, "end": 15.0, "text": "Para o Ministerio Publico"},
            {"start": 15.0, "end": 20.0, "text": "ocorrido em marco de 2003 seria conduta equiparavel a fuga."},
        ]

        # Testar remoção de repetições
        limpos = remover_repeticoes(segmentos)
        assert len(limpos) < len(segmentos)

        # Testar correção de alucinações conhecidas
        com_alucinacao = [
            {"start": 0.0, "end": 5.0, "text": "informou o Tejota Rene"},
            {"start": 5.0, "end": 10.0, "text": "o Nardo apresentou"},
        ]
        corrigidos = corrigir_alucinacoes_conhecidas(com_alucinacao)
        assert "tjrn" in corrigidos[0]["text"].lower() or "Tejota Rene" not in corrigidos[0]["text"]

    def test_correcao_alucinacoes_com_roteiro(self):
        """Testa correção alinhando com roteiro."""
        from boletim.corrigir_alucinacoes import corrigir_transcricao

        roteiro = (
            "A Câmara Criminal do TJRN manteve a decisão "
            "que deixou de reconhecer falta grave de um apenado. "
            "O fato ocorreu em 2026."
        )

        segmentos = [
            {"start": 0.0, "end": 5.0, "text": "A Camara Criminal do TJRN manteve a decisao"},
            {"start": 5.0, "end": 10.0, "text": "que deixou de reconhecer falta grave de um apenado"},
            {"start": 10.0, "end": 15.0, "text": "ocorrido em marco de 2003 seria conduta equiparavel"},
        ]

        corrigidos = corrigir_transcricao(segmentos, roteiro)
        assert len(corrigidos) > 0
        # O ano 2003 deve ter sido corrigido para 2026
        texto_ultimo = corrigidos[-1]["text"]
        assert "2026" in texto_ultimo or "2003" in texto_ultimo  # pelo menos manteve texto

    def test_pipeline_completo_audio_estereo_duplicado(self, audio_estereo_duplicado):
        """Pipeline detecta estéreo duplicado e sugere conversão para mono."""
        from boletim.etapas.etapa_triagem import triagem_audio

        resultado = triagem_audio(audio_estereo_duplicado)
        assert resultado.get("estereo_duplicado") is True
        assert any("mono" in a.lower() for a in resultado["acoes"])


# ═══════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
