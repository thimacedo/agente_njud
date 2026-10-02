"""Verifica o carregador VAD real quando as dependências opcionais existem."""
import pytest


def test_silero_loader_detects_silence():
    silero = pytest.importorskip('silero_vad')
    torch = pytest.importorskip('torch')
    from divisor_boletins.deteccao import _carregar_silero_vad

    model = _carregar_silero_vad()
    assert model is not None
    assert silero.get_speech_timestamps(torch.zeros(16000), model, sampling_rate=16000) == []
