"""
Testes para o módulo de tratamento de áudio.

Usa mocks de subprocess.run para evitar chamadas reais ao FFmpeg/ffprobe.
"""

import json
import subprocess
from unittest.mock import patch

import pytest

from src.gravador_inteligente.tratamento_audio import (
    TratamentoConfig,
    get_audio_info,
    measure_lufs,
    normalize_volume,
    process,
)

# =============================================================================
# get_audio_info
# =============================================================================


def _ffprobe_json_response():
    return {
        "format": {
            "duration": "8.88",
            "size": "426284",
            "bit_rate": "384039",
        },
        "streams": [
            {
                "codec_type": "audio",
                "codec_name": "pcm_s16le",
                "sample_rate": "24000",
                "channels": 1,
            }
        ],
    }


def test_get_audio_info_mock():
    """get_audio_info com subprocess.mock."""
    fake_stdout = json.dumps(_ffprobe_json_response())
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=fake_stdout, stderr=""
        )
        info = get_audio_info("fake.wav")
        assert info["duration"] == 8.88
        assert info["size_bytes"] == 426284
        assert info["codec"] == "pcm_s16le"
        assert info["sample_rate"] == 24000
        assert info["channels"] == 1


def test_get_audio_info_no_streams():
    """get_audio_info falha se não houver stream de áudio."""
    fake = {"format": {}, "streams": [{"codec_type": "video"}]}
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(fake), stderr=""
        )
        with pytest.raises(ValueError, match="Nenhum stream de áudio"):
            get_audio_info("fake.mp4")


def test_get_audio_info_ffprobe_fail():
    """get_audio_info falha se ffprobe retornar erro."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Erro genérico"
        )
        with pytest.raises(RuntimeError, match="ffprobe falhou"):
            get_audio_info("fake.wav")


# =============================================================================
# measure_lufs
# =============================================================================


def _loudnorm_json(input_i, input_tp, input_lra):
    return {
        "input_i": str(input_i),
        "input_tp": str(input_tp),
        "input_lra": str(input_lra),
        "input_thresh": "-24.5",
    }


def test_measure_lufs_mock():
    """measure_lufs com subprocess.mock."""
    loudnorm_output = _loudnorm_json(-18.5, -2.3, 9.1)
    # Use json.dumps para garantir JSON válido com aspas duplas (o parser de
    # measure_lufs usa output.index('{') + json.loads)
    stderr = f"media: ... {json.dumps(loudnorm_output)} ..."
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=stderr
        )
        result = measure_lufs("fake.mp3")
        assert result["input_i"] == -18.5
        assert result["input_tp"] == -2.3
        assert result["input_lra"] == 9.1


def test_measure_lufs_parse_fallback():
    """measure_lufs retorna zeros se não conseguir parsear JSON."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="não tem json aqui"
        )
        result = measure_lufs("fake.mp3")
        assert result["input_i"] == 0
        assert result["input_tp"] == 0


# =============================================================================
# normalize_volume
# =============================================================================


def test_normalize_volume_mock():
    """normalize_volume com subprocess.mock (loudnorm two-pass simulado)."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr='{"input_i": "-18.0", "input_tp": "-3.0", "input_lra": "11.0", "input_thresh": "-24.0"}',
            ),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ]
        with patch("src.gravador_inteligente.tratamento_audio.measure_lufs") as mock_measure:
            mock_measure.return_value = {
                "input_i": -16.1,
                "input_tp": -1.2,
                "input_lra": 10.5,
                "input_thresh": -24.0,
            }
            result = normalize_volume("in.mp3", "out.mp3", target_lufs=-16.0, target_peak_db=-1.0)
            assert result["status"] == "ok"
            assert result["target_lufs"] == -16.0


def test_normalize_volume_ffmpeg_fail():
    """normalize_volume falha se ffmpeg retornar erro."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr='{"input_i": "-18.0", "input_tp": "-3.0", "input_lra": "11.0", "input_thresh": "-24.0"}',
            ),
            subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="Erro fatal"),
        ]
        with pytest.raises(RuntimeError, match="Normalização falhou"):
            normalize_volume("in.mp3", "out.mp3")


# =============================================================================
# TratamentoConfig
# =============================================================================


def test_config_defaults():
    cfg = TratamentoConfig()
    assert cfg.target_lufs == -16.0
    assert cfg.target_peak_db == -1.0
    assert cfg.normalize is True
    assert cfg.reduce_noise is True
    assert cfg.reduce_breath is True
    assert cfg.remove_silence is False
    assert cfg.noise_reduction_strength == 0.5
    assert cfg.noise_method == "auto"
    assert cfg.temp_dir == "temp_processing"
    assert cfg.output_format == "mp3"


def test_config_customizada():
    cfg = TratamentoConfig(
        target_lufs=-14.0,
        normalize=False,
        reduce_noise=False,
        reduce_breath=False,
        remove_silence=True,
        min_silence_len_ms=3000,
    )
    assert cfg.target_lufs == -14.0
    assert cfg.normalize is False
    assert cfg.reduce_noise is False
    assert cfg.reduce_breath is False
    assert cfg.remove_silence is True
    assert cfg.min_silence_len_ms == 3000


# =============================================================================
# process (pipeline completo)
# =============================================================================


def test_process_pula_todas_as_etapas():
    """
    process() com todas as etapas desligadas valida arquivo inexistente.
    Teste completo do pipeline requer áudio real + ffmpeg — coberto por
    test_process_arquivo_inexistente() e testes de integração separados.
    """
    with pytest.raises(FileNotFoundError, match="Áudio não encontrado"):
        process("inexistente.wav", "saida.mp3", config=TratamentoConfig(
            normalize=False,
            reduce_noise=False,
            reduce_breath=False,
            remove_silence=False,
        ))


def test_process_arquivo_inexistente():
    """process() falha se o arquivo de entrada não existir."""
    with pytest.raises(FileNotFoundError, match="Áudio não encontrado"):
        process("inexistente.mp3", "saida.mp3")


# =============================================================================
# smoke test: import de todos os módulos
# =============================================================================


def test_imports():
    """Confirma que todos os módulos do tratamento importam sem erro."""
    assert True
