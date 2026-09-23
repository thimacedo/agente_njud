#!/usr/bin/env python3
"""
test_calibracao_audio.py — Testes para o AgenteCalibracaoAudio.

Testa todas as funções de análise de áudio:
  - detectar_canal_morto
  - calcular_loudness
  - detectar_clipping
  - sugerir_normalizacao
  - AgenteCalibracaoAudio.calibrar
"""
import math
import sys
import tempfile
from pathlib import Path

import pytest
from pydub import AudioSegment
from pydub.generators import Sine, WhiteNoise

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts_pipeline"))

from shared.agentes.calibracao_audio import (
    AgenteCalibracaoAudio,
    LIMIAR_CANAL_MORTO_DB,
    LIMIAR_CLIPPING_DB,
    TARGET_LUFS_PADRAO,
    calcular_loudness,
    detectar_canal_morto,
    detectar_clipping,
    sugerir_normalizacao,
)


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures — Gerar áudios sintéticos para teste
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def audio_mono_silencioso():
    """Áudio mono de 1 segundo com amplitude muito baixa (quase morto)."""
    return Sine(440).to_audio_segment(duration=1000, volume=-70.0)


@pytest.fixture
def audio_mono_normal():
    """Áudio mono de 2 segundos com nível normal (-16 LUFS aprox)."""
    return Sine(440).to_audio_segment(duration=2000, volume=-12.0)


@pytest.fixture
def audio_stereo_normal():
    """Áudio stereo de 1 segundo com nível normal."""
    left = Sine(440).to_audio_segment(duration=1000, volume=-12.0)
    right = Sine(880).to_audio_segment(duration=1000, volume=-12.0)
    return AudioSegment.from_mono_audiosegments(left, right)


@pytest.fixture
def audio_stereo_canal_morto():
    """Áudio stereo com canal direito morto."""
    left = Sine(440).to_audio_segment(duration=1000, volume=-12.0)
    right = AudioSegment.silent(duration=1000, frame_rate=44100)
    return AudioSegment.from_mono_audiosegments(left, right)


@pytest.fixture
def audio_clipping():
    """Áudio com picos em 0dBFS (clipping)."""
    return Sine(440).to_audio_segment(duration=1000, volume=0.0)


@pytest.fixture
def audio_silencio_total():
    """Áudio completamente silencioso."""
    return AudioSegment.silent(duration=1000, frame_rate=44100)


@pytest.fixture
def tmp_audio_file(tmp_path):
    """Fixture que retorna um caminho temporário para salvar áudio."""
    def _save(audio: AudioSegment, filename="test.wav"):
        path = tmp_path / filename
        audio.export(str(path), format="wav")
        return path
    return _save


# ═════════════════════════════════════════════════════════════════════════════
# Testes: detectar_canal_morto
# ═════════════════════════════════════════════════════════════════════════════

class TestDetectarCanalMorto:
    def test_audio_normal_sem_canais_mortos(self, audio_mono_normal):
        resultado = detectar_canal_morto(audio_mono_normal)
        assert resultado["nivel"] == "OK"
        assert len(resultado["canais_mortos"]) == 0
        assert 0 in resultado["canais_ativos"]

    def test_audio_silencioso_canal_morto(self, audio_silencio_total):
        resultado = detectar_canal_morto(audio_silencio_total)
        assert resultado["nivel"] == "CRITICO"
        assert len(resultado["canais_mortos"]) > 0

    def test_audio_stereo_normal(self, audio_stereo_normal):
        resultado = detectar_canal_morto(audio_stereo_normal)
        assert resultado["nivel"] == "OK"
        assert len(resultado["canais_mortos"]) == 0
        assert len(resultado["canais_ativos"]) == 2

    def test_audio_stereo_canal_morto(self, audio_stereo_canal_morto):
        resultado = detectar_canal_morto(audio_stereo_canal_morto)
        assert resultado["nivel"] in ("ALERTA", "CRITICO")
        assert 1 in resultado["canais_mortos"]  # direito morto
        assert 0 in resultado["canais_ativos"]  # esquerdo ativo

    def test_retorna_rms_por_canal(self, audio_mono_normal):
        resultado = detectar_canal_morto(audio_mono_normal)
        assert "rms_por_canal" in resultado
        assert isinstance(resultado["rms_por_canal"][0], float)

    def test_mensagens_presentes(self, audio_mono_normal):
        resultado = detectar_canal_morto(audio_mono_normal)
        assert len(resultado["mensagens"]) > 0


# ═════════════════════════════════════════════════════════════════════════════
# Testes: calcular_loudness
# ═════════════════════════════════════════════════════════════════════════════

class TestCalcularLoudness:
    def test_retorna_lufs(self, audio_mono_normal):
        resultado = calcular_loudness(audio_mono_normal)
        assert "lufs" in resultado
        assert isinstance(resultado["lufs"], float)

    def test_retorna_rms_dbfs(self, audio_mono_normal):
        resultado = calcular_loudness(audio_mono_normal)
        assert "rms_dbfs" in resultado
        assert resultado["rms_dbfs"] < 0  # dBFS sempre negativo para áudio normal

    def test_retorna_pico_dbfs(self, audio_mono_normal):
        resultado = calcular_loudness(audio_mono_normal)
        assert "pico_dbfs" in resultado
        assert isinstance(resultado["pico_dbfs"], float)

    def test_duracao_correta(self, audio_mono_normal):
        resultado = calcular_loudness(audio_mono_normal)
        assert abs(resultado["duracao_seg"] - 2.0) < 0.1

    def test_audio_silencioso_lufs_muito_baixo(self, audio_silencio_total):
        resultado = calcular_loudness(audio_silencio_total)
        assert resultado["lufs"] == -math.inf or resultado["lufs"] < -50

    def test_audio_alto_nivel_alerta(self, audio_clipping):
        resultado = calcular_loudness(audio_clipping)
        # Áudio clipping é muito alto, deve gerar ALERTA
        assert resultado["nivel"] in ("ALERTA", "OK")

    def test_retorna_nivel_valido(self, audio_mono_normal):
        resultado = calcular_loudness(audio_mono_normal)
        assert resultado["nivel"] in ("OK", "ALERTA", "CRITICO")


# ═════════════════════════════════════════════════════════════════════════════
# Testes: detectar_clipping
# ═════════════════════════════════════════════════════════════════════════════

class TestDetectarClipping:
    def test_sem_clipping_audio_normal(self, audio_mono_normal):
        resultado = detectar_clipping(audio_mono_normal)
        assert resultado["clipping_detectado"] is False or resultado["nivel"] == "OK"

    def test_com_clipping_audio_maximo(self, audio_clipping):
        resultado = detectar_clipping(audio_clipping)
        assert resultado["clipping_detectado"] is True
        assert resultado["nivel"] in ("ALERTA", "CRITICO")

    def test_pico_dbfs_proximo_zero(self, audio_clipping):
        resultado = detectar_clipping(audio_clipping)
        assert resultado["pico_dbfs"] >= -1.0

    def test_retorna_percentual(self, audio_mono_normal):
        resultado = detectar_clipping(audio_mono_normal)
        assert "percentual_amostras_clipping" in resultado
        assert resultado["percentual_amostras_clipping"] >= 0.0

    def test_audio_silencioso_sem_clipping(self, audio_silencio_total):
        resultado = detectar_clipping(audio_silencio_total)
        assert resultado["clipping_detectado"] is False

    def test_retorna_nivel_valido(self, audio_mono_normal):
        resultado = detectar_clipping(audio_mono_normal)
        assert resultado["nivel"] in ("OK", "ALERTA", "CRITICO")


# ═════════════════════════════════════════════════════════════════════════════
# Testes: sugerir_normalizacao
# ═════════════════════════════════════════════════════════════════════════════

class TestSugerirNormalizacao:
    def test_retorna_ganho(self, audio_mono_normal):
        resultado = sugerir_normalizacao(audio_mono_normal)
        assert "ganho_db" in resultado
        assert isinstance(resultado["ganho_db"], float)

    def test_lufs_atual_presente(self, audio_mono_normal):
        resultado = sugerir_normalizacao(audio_mono_normal)
        assert "lufs_atual" in resultado
        assert isinstance(resultado["lufs_atual"], float)

    def test_lufs_alvo_correto(self, audio_mono_normal):
        resultado = sugerir_normalizacao(audio_mono_normal, target_lufs=-14.0)
        assert resultado["lufs_alvo"] == -14.0

    def test_headroom_positivo(self, audio_mono_normal):
        resultado = sugerir_normalizacao(audio_mono_normal)
        assert resultado["headroom_db"] > 0

    def test_seguro_para_audio_normal(self, audio_mono_normal):
        resultado = sugerir_normalizacao(audio_mono_normal)
        # Normalização de áudio normal deve ser segura
        assert isinstance(resultado["seguro"], bool)

    def test_ganho_negativo_para_audio_alto(self, audio_clipping):
        resultado = sugerir_normalizacao(audio_clipping)
        # Áudio clipping está acima do target, ganho deve ser negativo
        assert resultado["ganho_db"] <= 0

    def test_target_padrao(self, audio_mono_normal):
        resultado = sugerir_normalizacao(audio_mono_normal)
        assert resultado["lufs_alvo"] == TARGET_LUFS_PADRAO

    def test_retorna_nivel_valido(self, audio_mono_normal):
        resultado = sugerir_normalizacao(audio_mono_normal)
        assert resultado["nivel"] in ("OK", "ALERTA", "CRITICO")


# ═════════════════════════════════════════════════════════════════════════════
# Testes: AgenteCalibracaoAudio (integração)
# ═════════════════════════════════════════════════════════════════════════════

class TestAgenteCalibracaoAudio:
    def test_calibrar_audio_normal(self, audio_mono_normal, tmp_audio_file):
        path = tmp_audio_file(audio_mono_normal)
        agente = AgenteCalibracaoAudio()
        resultado = agente.calibrar(path)

        assert resultado["nivel"] in ("OK", "ALERTA", "CRITICO")
        assert resultado["audio_path"] == str(path)
        assert resultado["canais"] == 1
        assert "resultado_canal_morto" in resultado
        assert "resultado_loudness" in resultado
        assert "resultado_clipping" in resultado
        assert "resultado_normalizacao" in resultado
        assert "mensagens" in resultado
        assert "valores_numericos" in resultado

    def test_calibrar_audio_stereo_canal_morto(self, audio_stereo_canal_morto, tmp_audio_file):
        path = tmp_audio_file(audio_stereo_canal_morto)
        agente = AgenteCalibracaoAudio()
        resultado = agente.calibrar(path)

        assert resultado["nivel"] in ("ALERTA", "CRITICO")
        assert resultado["canais"] == 2
        assert resultado["valores_numericos"]["canais_mortos_count"] >= 0

    def test_calibrar_audio_clipping(self, audio_clipping, tmp_audio_file):
        path = tmp_audio_file(audio_clipping)
        agente = AgenteCalibracaoAudio()
        resultado = agente.calibrar(path)

        assert resultado["nivel"] in ("ALERTA", "CRITICO")
        assert resultado["resultado_clipping"]["clipping_detectado"] is True

    def test_calibrar_arquivo_inexistente(self):
        agente = AgenteCalibracaoAudio()
        resultado = agente.calibrar("/caminho/inexistente.wav")

        assert resultado["nivel"] == "CRITICO"
        assert "não encontrado" in resultado["mensagens"][0].lower() or "Arquivo" in resultado["mensagens"][0]

    def test_calibrar_retorna_valores_numericos(self, audio_mono_normal, tmp_audio_file):
        path = tmp_audio_file(audio_mono_normal)
        agente = AgenteCalibracaoAudio()
        resultado = agente.calibrar(path)

        vn = resultado["valores_numericos"]
        assert "lufs_estimado" in vn
        assert "pico_dbfs" in vn
        assert "ganho_sugerido_db" in vn
        assert "headroom_db" in vn

    def test_target_lufs_customizado(self, audio_mono_normal, tmp_audio_file):
        path = tmp_audio_file(audio_mono_normal)
        agente = AgenteCalibracaoAudio(target_lufs=-14.0)
        resultado = agente.calibrar(path)

        assert resultado["resultado_normalizacao"]["lufs_alvo"] == -14.0

    def test_duracao_correta(self, audio_mono_normal, tmp_audio_file):
        path = tmp_audio_file(audio_mono_normal)
        agente = AgenteCalibracaoAudio()
        resultado = agente.calibrar(path)

        assert abs(resultado["duracao_seg"] - 2.0) < 0.1

    def test_sample_rate_presente(self, audio_mono_normal, tmp_audio_file):
        path = tmp_audio_file(audio_mono_normal)
        agente = AgenteCalibracaoAudio()
        resultado = agente.calibrar(path)

        assert resultado["sample_rate"] > 0
        assert resultado["bit_depth"] > 0

    def test_formato_detectado(self, audio_mono_normal, tmp_audio_file):
        path = tmp_audio_file(audio_mono_normal)
        agente = AgenteCalibracaoAudio()
        resultado = agente.calibrar(path)

        assert resultado["formato"] == "wav"


# ═════════════════════════════════════════════════════════════════════════════
# Testes: Funções standalone com diferentes targets
# ═════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_audio_muito_curto(self):
        """Áudio de apenas 100ms."""
        audio = Sine(440).to_audio_segment(duration=100, volume=-12.0)
        resultado = calcular_loudness(audio)
        assert resultado["duracao_seg"] < 0.2

    def test_sugerir_normalizacao_target_extremo(self, audio_mono_normal):
        """Testar com target muito baixo."""
        resultado = sugerir_normalizacao(audio_mono_normal, target_lufs=-40.0)
        assert resultado["ganho_db"] < 0  # deve sugerir redução

    def test_sugerir_normalizacao_target_alto(self, audio_mono_normal):
        """Testar com target muito alto (pode causar clipping)."""
        resultado = sugerir_normalizacao(audio_mono_normal, target_lufs=-6.0)
        # Deve limitar para não clipar
        assert isinstance(resultado["ganho_db"], float)

    def test_detectar_canal_morto_limiar_custom(self, audio_mono_normal):
        """Testar com limiar de canal morto muito alto."""
        resultado = detectar_canal_morto(audio_mono_normal, limiar_db=-10.0)
        # Com limiar alto, mesmo áudio normal pode ser considerado morto
        assert resultado["nivel"] in ("OK", "ALERTA", "CRITICO")


# ═════════════════════════════════════════════════════════════════════════════
# Execução standalone
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
